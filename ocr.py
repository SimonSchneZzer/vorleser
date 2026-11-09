"""Texterkennung für eingescannte PDFs (Version 3.0) – lokal, ohne Netz.

macOS:   Seite mit Quartz rendern → Apple Vision (`VNRecognizeTextRequest`).
Windows: Seite mit PDFium rendern → `Windows.Media.Ocr` (braucht das Sprachpaket mit „Optischer Zeichenerkennung“).
Läuft als Auftrag im Hintergrund: Fortschritt „Seite X von Y“, abbrechbar (`jobs`, server.py).
"""
from __future__ import annotations

import threading
import time
import uuid

import meldungen
import paths

SKALIERUNG = 2.0          # ≈ 144 dpi – genug für Vision/Windows, noch schnell
MAX_SEITE_PX = 4000

OCR_FEHLT = "Texterkennung ist auf diesem System nicht verfügbar."
OCR_SPRACHPAKET = ("Für die Texterkennung fehlt unter Windows ein Sprachpaket. Öffne Einstellungen › Zeit und Sprache › "
                   "Sprache, wähle Deutsch (oder Englisch) › Sprachoptionen und installiere „Optische Zeichenerkennung“.")
OCR_FEHLER = "Die Texterkennung hat nicht geklappt. Versuch es noch einmal – oder exportiere das PDF neu."


def verfuegbar() -> bool:
    try:
        if paths.IS_MAC:
            import Quartz  # noqa: F401
            import Vision  # noqa: F401
            return True
        if paths.IS_WIN:
            import pypdfium2  # noqa: F401
            from winrt.windows.media.ocr import OcrEngine  # noqa: F401
            return True
    except Exception:
        pass
    return False


# --------------------------------------------------------------------------- #
# macOS
# --------------------------------------------------------------------------- #
class _Mac:
    def __init__(self, data: bytes):
        import Quartz
        from Foundation import NSData
        self.Q = Quartz
        provider = Quartz.CGDataProviderCreateWithCFData(NSData.dataWithBytes_length_(data, len(data)))
        self.doc = Quartz.CGPDFDocumentCreateWithProvider(provider)
        if self.doc is None:
            raise meldungen.Meldung(OCR_FEHLER)
        self.n = Quartz.CGPDFDocumentGetNumberOfPages(self.doc)

    def seite(self, i: int) -> str:
        import objc
        import Vision
        Q = self.Q
        with objc.autorelease_pool():
            page = Q.CGPDFDocumentGetPage(self.doc, i + 1)
            box = Q.CGPDFPageGetBoxRect(page, Q.kCGPDFCropBox)
            s = min(SKALIERUNG, MAX_SEITE_PX / max(box.size.width, box.size.height, 1))
            w, h = max(1, int(box.size.width * s)), max(1, int(box.size.height * s))
            ctx = Q.CGBitmapContextCreate(None, w, h, 8, 0, Q.CGColorSpaceCreateDeviceGray(), Q.kCGImageAlphaNone)
            Q.CGContextSetGrayFillColor(ctx, 1.0, 1.0)
            Q.CGContextFillRect(ctx, Q.CGRectMake(0, 0, w, h))
            Q.CGContextScaleCTM(ctx, s, s)
            Q.CGContextTranslateCTM(ctx, -box.origin.x, -box.origin.y)
            Q.CGContextDrawPDFPage(ctx, page)
            img = Q.CGBitmapContextCreateImage(ctx)
            req = Vision.VNRecognizeTextRequest.alloc().init()
            req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
            req.setUsesLanguageCorrection_(True)
            req.setRecognitionLanguages_(["de-DE", "en-US"])
            handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
            ok, err = handler.performRequests_error_([req], None)
            if not ok:
                raise RuntimeError(f"Vision: {err}")
            # Ergebnisse kommen grob von oben nach unten; nach Zeilenhöhe sortieren (Vision: Ursprung unten links)
            obs = sorted(req.results() or [], key=lambda o: (-round(o.boundingBox().origin.y, 2), o.boundingBox().origin.x))
            return "\n".join(str(o.topCandidates_(1)[0].string()) for o in obs if o.topCandidates_(1))


# --------------------------------------------------------------------------- #
# Windows (am Mac nicht testbar – siehe docs/PLAN-3.0.md „Windows-Teil C“)
# --------------------------------------------------------------------------- #
class _Win:
    def __init__(self, data: bytes):
        import pypdfium2 as pdfium
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine
        self.pdf = pdfium.PdfDocument(data)
        self.n = len(self.pdf)
        self.engine = None
        for tag in ("de-DE", "de", "en-US", "en"):
            try:
                lang = Language(tag)
                if OcrEngine.is_language_supported(lang):
                    self.engine = OcrEngine.try_create_from_language(lang)
                    break
            except Exception:
                continue
        if self.engine is None:
            self.engine = OcrEngine.try_create_from_user_profile_languages()
        if self.engine is None:
            raise meldungen.Meldung(OCR_SPRACHPAKET)

    def seite(self, i: int) -> str:
        import asyncio

        import pypdfium2.raw as pdfium_c
        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.storage.streams import DataWriter
        page = self.pdf[i]
        w0, h0 = page.get_size()
        s = min(SKALIERUNG, MAX_SEITE_PX / max(w0, h0, 1))
        bmp = page.render(scale=s, force_bitmap_format=pdfium_c.FPDFBitmap_BGRA)
        w, h, stride = bmp.width, bmp.height, bmp.stride
        buf = bytes(bmp.buffer)
        if stride != w * 4:                                  # Zeilen ohne Füllbytes
            buf = b"".join(buf[y * stride:y * stride + w * 4] for y in range(h))
        dw = DataWriter()
        dw.write_bytes(buf)
        sb = SoftwareBitmap.create_copy_from_buffer(dw.detach_buffer(), BitmapPixelFormat.BGRA8, w, h, BitmapAlphaMode.PREMULTIPLIED)

        async def run():
            return await self.engine.recognize_async(sb)
        res = asyncio.run(run())
        return "\n".join(line.text for line in res.lines)


# --------------------------------------------------------------------------- #
# Aufträge
# --------------------------------------------------------------------------- #
jobs: dict[str, dict] = {}
_lock = threading.Lock()


def start(data: bytes, name: str, fertig) -> dict:
    """Erkennung im Hintergrund starten. `fertig(seiten: list[str]) -> dict` baut daraus das Import-Ergebnis."""
    jid = uuid.uuid4().hex
    job = {"id": jid, "status": "running", "done": 0, "total": 0, "name": name, "started": time.time()}
    with _lock:
        for k in [k for k, j in jobs.items() if j["status"] != "running" and time.time() - j["started"] > 3600]:
            jobs.pop(k)                                      # alte Ergebnisse nicht ewig im Speicher halten
        jobs[jid] = job
    threading.Thread(target=_run, args=(job, data, fertig), daemon=True).start()
    return status(jid)


def _run(job: dict, data: bytes, fertig) -> None:
    try:
        eng = _Mac(data) if paths.IS_MAC else _Win(data) if paths.IS_WIN else None
        if eng is None:
            raise meldungen.Meldung(OCR_FEHLT)
        job["total"] = eng.n
        seiten = []
        for i in range(eng.n):
            if job.get("cancel"):
                job["status"] = "cancelled"
                return
            seiten.append(eng.seite(i))
            job["done"] = i + 1
        job["result"] = fertig(seiten)
        job["status"] = "ready"
    except Exception as e:
        meldungen.loggen("texterkennung", e)
        from importers import ImportFailed
        job["error"] = str(e) if isinstance(e, (meldungen.Meldung, ValueError, ImportFailed)) else OCR_FEHLER
        job["status"] = "error"


def status(jid: str) -> dict:
    job = jobs.get(jid)
    if job is None:
        raise KeyError("Texterkennung")
    return {k: v for k, v in job.items() if k != "cancel"}


def abbrechen(jid: str) -> None:
    if jid in jobs:
        jobs[jid]["cancel"] = True

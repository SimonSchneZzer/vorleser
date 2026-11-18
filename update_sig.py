"""Signierte Update-Infos (Ed25519, RFC 8032) – ohne zusätzliche Abhängigkeit.

Der Release-Workflow signiert die Update-Infos (Version, Adressen, Größen, Prüfsummen) mit einem privaten Schlüssel,
der nur als GitHub-Secret `UPDATE_SIGNING_KEY` existiert. Die App kennt nur den öffentlichen Schlüssel unten und spielt
nichts ein, dessen Signatur nicht passt. So kann auch jemand, der latest.json oder das Download-Repo verändert, keine
fremde Datei unterschieben (Sicherheitsprüfung 18.11.2026, siehe docs/DECISIONS.md).

Reine Python-Umsetzung nach RFC 8032 (Abschnitt 5.1, Referenz-Code in Abschnitt 6) – langsam (~0,1 s), aber eine
Prüfung pro neuer Version reicht. Geprüft mit den Testvektoren aus RFC 8032 (tests/test_update_sig.py).

Kommandozeile (nur Workflow/Einrichtung):
  python update_sig.py keygen              → neuer privater Schlüssel (hex) + öffentlicher Schlüssel
  python update_sig.py sign <datei>        → Signatur (base64) über die Datei; Schlüssel aus $UPDATE_SIGNING_KEY
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys

# Öffentlicher Schlüssel für Updates (hex). Gegenstück liegt nur als GitHub-Secret + Sicherung auf dem Homeserver.
PUBLIC_KEY = "1d4dbbc73c7a129543a7c7e41c402b48d840ec95b8a21dd2601b2b0b5bae5319"

_p = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p)
    x = pow(xx, (_p + 3) // 8, _p)
    if (x * x - xx) % _p != 0:
        x = (x * _I) % _p
    if x % 2 != 0:
        x = _p - x
    return x


_By = 4 * pow(5, _p - 2, _p) % _p
_Bx = _xrecover(_By)
_B = (_Bx, _By, 1, _Bx * _By % _p)        # erweiterte Koordinaten (X, Y, Z, T)
_ZERO = (0, 1, 1, 0)


def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C = 2 * P[3] * Q[3] * _d % _p
    D = 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s: int, P):
    Q = _ZERO
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _compress(P) -> bytes:
    zinv = pow(P[2], _p - 2, _p)
    x, y = P[0] * zinv % _p, P[1] * zinv % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= _p:
        return None
    x = _xrecover(y)
    if (x * x * (_d * y * y + 1) - (y * y - 1)) % _p != 0:     # kein Punkt der Kurve
        return None
    if x == 0 and sign:
        return None
    if (x & 1) != sign:
        x = _p - x
    return (x, y, 1, x * y % _p)


def _secret_expand(seed: bytes) -> tuple[int, bytes]:
    h = _H(seed)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(seed: bytes) -> bytes:
    a, _ = _secret_expand(seed)
    return _compress(_mul(a, _B))


def sign(seed: bytes, msg: bytes) -> bytes:
    a, prefix = _secret_expand(seed)
    A = _compress(_mul(a, _B))
    r = int.from_bytes(_H(prefix + msg), "little") % _L
    R = _compress(_mul(r, _B))
    h = int.from_bytes(_H(R + A + msg), "little") % _L
    s = (r + h * a) % _L
    return R + int.to_bytes(s, 32, "little")


def verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    """True nur bei gültiger Signatur. Wirft nie (kaputte Eingaben → False)."""
    try:
        if len(pub) != 32 or len(sig) != 64:
            return False
        A = _decompress(pub)
        R = _decompress(sig[:32])
        if A is None or R is None:
            return False
        s = int.from_bytes(sig[32:], "little")
        if s >= _L:
            return False
        h = int.from_bytes(_H(sig[:32] + pub + msg), "little") % _L
        return _equal(_mul(s, _B), _add(R, _mul(h, A)))
    except Exception:
        return False


def app_public_key() -> bytes:
    """Schlüssel der App. Für Tests (auch der gebauten App in CI) per Umgebung überschreibbar – kein Risiko: wer die
    Umgebung der App setzen kann, hat den Rechner ohnehin schon und könnte die App selbst austauschen."""
    override = os.environ.get("VORLESER_UPDATE_PUBKEY")
    return bytes.fromhex(override if override else PUBLIC_KEY)


def verify_b64(signed_b64: str, sig_b64: str) -> bytes | None:
    """Signierte Nutzlast (base64) prüfen; gibt die Bytes zurück oder None."""
    try:
        payload = base64.b64decode(signed_b64, validate=True)
        sig = base64.b64decode(sig_b64, validate=True)
    except Exception:
        return None
    return payload if verify(app_public_key(), payload, sig) else None


if __name__ == "__main__":
    if sys.argv[1:2] == ["keygen"]:
        seed = os.urandom(32)
        print("privat (Secret UPDATE_SIGNING_KEY):", seed.hex())
        print("öffentlich (PUBLIC_KEY):", public_key(seed).hex())
    elif sys.argv[1:2] == ["sign"] and len(sys.argv) == 3:
        seed = bytes.fromhex(os.environ["UPDATE_SIGNING_KEY"].strip())
        data = open(sys.argv[2], "rb").read()
        print(base64.b64encode(sign(seed, data)).decode())
    else:
        print(__doc__)
        sys.exit(2)

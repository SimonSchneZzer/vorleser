"""Test-Schlüssel für signierte Update-Infos (update_sig). conftest stellt die App per Umgebung auf diesen Schlüssel
und auf die Test-Adresse http://dl/ um – der echte Schlüssel bleibt unberührt."""
import base64
import json

import update_sig

TEST_SEED = bytes(range(32))
TEST_PUB = update_sig.public_key(TEST_SEED).hex()
TEST_DL = "http://dl/"


def signed_info(info: dict, seed: bytes = TEST_SEED) -> dict:
    """So wie der Release-Workflow: Nutzlast als base64 + Signatur darüber."""
    payload = json.dumps(info, sort_keys=True, separators=(",", ":")).encode()
    return {"version": info.get("version"), "signed": base64.b64encode(payload).decode(),
            "sig": base64.b64encode(update_sig.sign(seed, payload)).decode()}

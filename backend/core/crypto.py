"""Symmetric encryption for secrets the backend must hold at rest.

Same construction as the per-desktop channel key (sandbox/channel.py): AES-GCM
under one 32-byte master key, a versioned ``v1:`` prefix so the key can be
rotated later, and a caller-supplied AAD so a ciphertext sealed for one purpose
cannot be replayed as another. The master key defaults to WUYING_CHANNEL_KEY
so a deployment that already routes desktops needs no new secret; set
SECRETS_MASTER_KEY to keep platform tokens under their own key.
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import get_config

_PREFIX = "v1:"


class SecretsConfigError(RuntimeError):
    pass


def _master_key(value: str | None = None) -> bytes:
    if value is None:
        config = get_config()
        value = getattr(config, "secrets_master_key", "") or config.wuying_channel_key
    raw = (value or "").strip()
    if not raw:
        raise SecretsConfigError("SECRETS_MASTER_KEY (or WUYING_CHANNEL_KEY) is required to store platform tokens")
    try:
        key = bytes.fromhex(raw) if len(raw) == 64 else base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:  # pragma: no cover - defensive
        raise SecretsConfigError("master key must be 32 bytes encoded as hex or base64") from exc
    if len(key) != 32:
        raise SecretsConfigError("master key must decode to exactly 32 bytes")
    return key


def encrypt_secret(plaintext: str, aad: str, master_key: str | None = None) -> str:
    nonce = os.urandom(12)
    sealed = AESGCM(_master_key(master_key)).encrypt(nonce, plaintext.encode(), aad.encode())
    return _PREFIX + base64.urlsafe_b64encode(nonce + sealed).decode().rstrip("=")


def decrypt_secret(ciphertext: str, aad: str, master_key: str | None = None) -> str:
    if not ciphertext.startswith(_PREFIX):
        raise SecretsConfigError("unsupported secret ciphertext version")
    try:
        raw = base64.urlsafe_b64decode(ciphertext[len(_PREFIX):] + "===")
        return AESGCM(_master_key(master_key)).decrypt(raw[:12], raw[12:], aad.encode()).decode()
    except SecretsConfigError:
        raise
    except Exception as exc:
        raise SecretsConfigError("cannot decrypt stored secret") from exc


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

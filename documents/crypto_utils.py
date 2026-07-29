import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from django.conf import settings

KEYS_DIR = settings.BASE_DIR / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "municipal_signing.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "municipal_signing_pub.pem"


def _ensure_keys_dir():
    KEYS_DIR.mkdir(parents=True, exist_ok=True)


def generate_keypair():
    _ensure_keys_dir()
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend(),
    )
    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    public_key = private_key.public_key()
    with open(PUBLIC_KEY_PATH, "wb") as f:
        f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    return private_key, public_key


def _load_private_key():
    if not PRIVATE_KEY_PATH.exists():
        generate_keypair()
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())


def _load_public_key():
    if not PUBLIC_KEY_PATH.exists():
        generate_keypair()
    with open(PUBLIC_KEY_PATH, "rb") as f:
        return serialization.load_pem_public_key(f.read(), backend=default_backend())


def get_public_key_pem():
    _load_public_key()
    return PUBLIC_KEY_PATH.read_text()


def compute_file_hash(file_path):
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def sign_hash(hex_digest):
    private_key = _load_private_key()
    signature = private_key.sign(
        hex_digest.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return signature.hex()


def verify_signature(hex_digest, signature_hex):
    public_key = _load_public_key()
    try:
        public_key.verify(
            bytes.fromhex(signature_hex),
            hex_digest.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def compute_buffer_hash(buffer: bytes) -> str:
    return hashlib.sha256(buffer).hexdigest()

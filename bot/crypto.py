"""Encrypt and decrypt mailbox passwords."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class PasswordCrypto:
    def __init__(self, fernet_key: str) -> None:
        try:
            self._fernet = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
        except Exception as exc:  # noqa: BLE001 — surface a clear config error
            raise RuntimeError("Invalid FERNET_KEY; generate one with Fernet.generate_key()") from exc

    def encrypt(self, password: str) -> str:
        return self._fernet.encrypt(password.encode("utf-8")).decode("ascii")

    def decrypt(self, password_enc: str) -> str:
        try:
            return self._fernet.decrypt(password_enc.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Failed to decrypt mailbox password (wrong FERNET_KEY?)") from exc

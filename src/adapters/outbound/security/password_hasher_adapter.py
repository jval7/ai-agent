import base64
import binascii
import hashlib
import hmac
import secrets

import src.ports.password_hasher_port as password_hasher_port


class Pbkdf2PasswordHasherAdapter(password_hasher_port.PasswordHasherPort):
    def __init__(self, iterations: int = 210_000) -> None:
        self._iterations = iterations

    def hash_password(self, raw_password: str) -> str:
        salt = secrets.token_bytes(16)
        derived_key = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt,
            self._iterations,
        )
        salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
        key_b64 = base64.urlsafe_b64encode(derived_key).decode("ascii")
        return f"pbkdf2_sha256${self._iterations}${salt_b64}${key_b64}"

    def verify_password(self, raw_password: str, password_hash: str) -> bool:
        segments = password_hash.split("$")
        if len(segments) != 4:
            return False

        algorithm = segments[0]
        iterations_raw = segments[1]
        salt_b64 = segments[2]
        key_b64 = segments[3]

        if algorithm != "pbkdf2_sha256":
            return False

        try:
            iterations = int(iterations_raw)
            salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
            expected_key = base64.urlsafe_b64decode(key_b64.encode("ascii"))
        except ValueError:
            return False
        except binascii.Error:
            return False

        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(computed_key, expected_key)

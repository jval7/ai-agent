import base64
import binascii
import hashlib
import hmac
import json
import threading

import pydantic

import src.ports.clock_port as clock_port
import src.ports.jwt_provider_port as jwt_provider_port
import src.services.dto.auth_dto as auth_dto
import src.services.exceptions as service_exceptions


class Hs256JwtProviderAdapter(jwt_provider_port.JwtProviderPort):
    def __init__(self, secret: str, clock: clock_port.ClockPort) -> None:
        self._secret_bytes = secret.encode("utf-8")
        self._clock = clock
        self._revoked_refresh_jtis: set[str] = set()
        self._lock = threading.RLock()

    def encode(self, claims: auth_dto.TokenClaimsDTO) -> str:
        header_data = {"alg": "HS256", "typ": "JWT"}
        payload_data = claims.model_dump()
        header_json = json.dumps(header_data, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_json = json.dumps(payload_data, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        header_part = self._base64url_encode(header_json)
        payload_part = self._base64url_encode(payload_json)
        signed_part = f"{header_part}.{payload_part}"
        signature = hmac.new(
            self._secret_bytes,
            signed_part.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_part = self._base64url_encode(signature)
        return f"{signed_part}.{signature_part}"

    def decode(self, token: str) -> auth_dto.TokenClaimsDTO:
        parts = token.split(".")
        if len(parts) != 3:
            raise service_exceptions.AuthenticationError("invalid token format")

        header_part = parts[0]
        payload_part = parts[1]
        signature_part = parts[2]
        signed_part = f"{header_part}.{payload_part}"

        expected_signature = hmac.new(
            self._secret_bytes,
            signed_part.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_signature_part = self._base64url_encode(expected_signature)

        if not hmac.compare_digest(expected_signature_part, signature_part):
            raise service_exceptions.AuthenticationError("invalid token signature")

        try:
            payload_bytes = self._base64url_decode(payload_part)
            payload_dict = json.loads(payload_bytes.decode("utf-8"))
            claims = auth_dto.TokenClaimsDTO.model_validate(payload_dict)
        except binascii.Error as error:
            raise service_exceptions.AuthenticationError("invalid token payload") from error
        except UnicodeDecodeError as error:
            raise service_exceptions.AuthenticationError("invalid token payload") from error
        except json.JSONDecodeError as error:
            raise service_exceptions.AuthenticationError("invalid token payload") from error
        except pydantic.ValidationError as error:
            raise service_exceptions.AuthenticationError("invalid token claims") from error

        current_epoch = self._clock.now_epoch_seconds()
        if claims.exp <= current_epoch:
            raise service_exceptions.AuthenticationError("token expired")

        if claims.token_kind == "refresh" and self.is_refresh_jti_revoked(claims.jti):
            raise service_exceptions.AuthenticationError("refresh token revoked")

        return claims

    def revoke_refresh_jti(self, jti: str) -> None:
        with self._lock:
            self._revoked_refresh_jtis.add(jti)

    def is_refresh_jti_revoked(self, jti: str) -> bool:
        with self._lock:
            return jti in self._revoked_refresh_jtis

    def _base64url_encode(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _base64url_decode(self, value: str) -> bytes:
        padding = "=" * ((4 - (len(value) % 4)) % 4)
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))

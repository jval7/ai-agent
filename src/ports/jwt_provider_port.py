import abc

import src.services.dto.auth_dto as auth_dto


class JwtProviderPort(abc.ABC):
    @abc.abstractmethod
    def encode(self, claims: auth_dto.TokenClaimsDTO) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def decode(self, token: str) -> auth_dto.TokenClaimsDTO:
        raise NotImplementedError

    @abc.abstractmethod
    def revoke_refresh_jti(self, jti: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def is_refresh_jti_revoked(self, jti: str) -> bool:
        raise NotImplementedError

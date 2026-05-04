import abc


class EmailNotifierPort(abc.ABC):
    @abc.abstractmethod
    def send_account_invitation(
        self,
        to_email: str,
        to_name: str | None,
        invitation_url: str,
        tenant_name: str,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def send_password_reset(
        self,
        to_email: str,
        reset_url: str,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def send_welcome(
        self,
        to_email: str,
        to_name: str | None,
        tenant_name: str,
        login_url: str,
    ) -> None:
        raise NotImplementedError

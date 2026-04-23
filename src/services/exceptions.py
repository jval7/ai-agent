class ServiceError(Exception):
    """Base application service error."""


class AuthenticationError(ServiceError):
    """Raised when credentials or token validation fails."""


class AuthorizationError(ServiceError):
    """Raised when actor does not have access to a resource."""


class EntityNotFoundError(ServiceError):
    """Raised when entity does not exist."""


class DuplicateWebhookEventError(ServiceError):
    """Raised when webhook event has already been processed."""


class InvalidStateError(ServiceError):
    """Raised when requested state transition is invalid."""


class ExternalProviderError(ServiceError):
    """Raised when external adapter cannot complete operation."""


class WhatsappBillingNotConfiguredError(ServiceError):
    """Raised when Meta rejects a template send because the WABA has no payment method configured.

    Maps to Meta error code 131042.
    """


class WhatsappPreflightError(ServiceError):
    """Raised when the WhatsApp billing preflight fails for a non-billing reason.

    Carries the Meta error code so the HTTP layer can surface it to the caller.
    """

    def __init__(self, message: str, meta_error_code: int | None = None) -> None:
        super().__init__(message)
        self.meta_error_code = meta_error_code

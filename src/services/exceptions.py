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

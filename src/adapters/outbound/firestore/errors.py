import src.services.exceptions as service_exceptions


class FirestoreRepositoryError(service_exceptions.ExternalProviderError):
    """Raised when a Firestore read or write operation fails."""

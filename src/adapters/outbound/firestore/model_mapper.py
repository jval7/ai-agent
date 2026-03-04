import typing

import pydantic

import src.adapters.outbound.firestore.errors as firestore_errors

ModelType = typing.TypeVar("ModelType", bound=pydantic.BaseModel)


def model_to_document(model: pydantic.BaseModel) -> dict[str, object]:
    data = model.model_dump(mode="python")
    if not isinstance(data, dict):
        raise firestore_errors.FirestoreRepositoryError("invalid pydantic model dump format")
    return typing.cast(dict[str, object], data)


def parse_document(
    data: dict[str, object],
    model_type: type[ModelType],
    entity_name: str,
) -> ModelType:
    try:
        return model_type.model_validate(data)
    except pydantic.ValidationError as error:
        raise firestore_errors.FirestoreRepositoryError(
            f"invalid {entity_name} document format in firestore"
        ) from error

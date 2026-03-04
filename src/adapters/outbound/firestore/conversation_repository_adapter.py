import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.conversation as conversation_entity
import src.domain.entities.message as message_entity
import src.domain.entities.whatsapp_user as whatsapp_user_entity
import src.ports.conversation_repository_port as conversation_repository_port


class FirestoreConversationRepositoryAdapter(
    conversation_repository_port.ConversationRepositoryPort
):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save_whatsapp_user(self, whatsapp_user: whatsapp_user_entity.WhatsappUser) -> None:
        whatsapp_user_document = firestore_paths.tenant_whatsapp_user_document(
            self._client,
            whatsapp_user.tenant_id,
            whatsapp_user.id,
        )
        whatsapp_user_data = firestore_model_mapper.model_to_document(whatsapp_user)
        try:
            whatsapp_user_document.set(whatsapp_user_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save whatsapp user in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save whatsapp user in firestore"
            ) from error

    def get_whatsapp_user(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
    ) -> whatsapp_user_entity.WhatsappUser | None:
        whatsapp_user_document = firestore_paths.tenant_whatsapp_user_document(
            self._client,
            tenant_id,
            whatsapp_user_id,
        )
        try:
            snapshot = whatsapp_user_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read whatsapp user from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read whatsapp user from firestore"
            ) from error
        if not snapshot.exists:
            return None
        whatsapp_user_raw_data = snapshot.to_dict()
        if whatsapp_user_raw_data is None:
            return None
        return firestore_model_mapper.parse_document(
            whatsapp_user_raw_data,
            whatsapp_user_entity.WhatsappUser,
            "whatsapp user",
        )

    def save_conversation(self, conversation: conversation_entity.Conversation) -> None:
        conversation_document = firestore_paths.tenant_conversation_document(
            self._client,
            conversation.tenant_id,
            conversation.id,
        )
        conversation_lookup_document = firestore_paths.tenant_conversation_lookup_document(
            self._client,
            conversation.tenant_id,
            conversation.whatsapp_user_id,
        )
        conversation_copy = conversation.model_copy(deep=True)
        existing_conversation = self.get_conversation_by_id(conversation.tenant_id, conversation.id)
        if existing_conversation is not None:
            conversation_copy.messages = [
                message.model_copy(deep=True) for message in existing_conversation.messages
            ]
        conversation_data = firestore_model_mapper.model_to_document(conversation_copy)
        lookup_data: dict[str, str] = {"conversation_id": conversation.id}

        batch = self._client.batch()
        batch.set(conversation_document, conversation_data)
        batch.set(conversation_lookup_document, lookup_data)
        try:
            batch.commit()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save conversation in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save conversation in firestore"
            ) from error

    def get_conversation_by_whatsapp_user(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
    ) -> conversation_entity.Conversation | None:
        conversation_lookup_document = firestore_paths.tenant_conversation_lookup_document(
            self._client,
            tenant_id,
            whatsapp_user_id,
        )
        try:
            lookup_snapshot = conversation_lookup_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read conversation from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read conversation from firestore"
            ) from error
        if not lookup_snapshot.exists:
            return None
        lookup_raw_data = lookup_snapshot.to_dict()
        if lookup_raw_data is None:
            return None

        conversation_id_value = lookup_raw_data.get("conversation_id")
        if not isinstance(conversation_id_value, str):
            raise firestore_errors.FirestoreRepositoryError(
                "invalid conversation lookup format in firestore"
            )
        return self.get_conversation_by_id(tenant_id, conversation_id_value)

    def get_conversation_by_id(
        self,
        tenant_id: str,
        conversation_id: str,
    ) -> conversation_entity.Conversation | None:
        conversation_document = firestore_paths.tenant_conversation_document(
            self._client,
            tenant_id,
            conversation_id,
        )
        try:
            snapshot = conversation_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read conversation from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read conversation from firestore"
            ) from error
        if not snapshot.exists:
            return None
        conversation_raw_data = snapshot.to_dict()
        if conversation_raw_data is None:
            return None
        conversation = firestore_model_mapper.parse_document(
            conversation_raw_data,
            conversation_entity.Conversation,
            "conversation",
        )
        if conversation.tenant_id != tenant_id:
            return None
        return conversation

    def list_conversations(self, tenant_id: str) -> list[conversation_entity.Conversation]:
        conversations_collection = firestore_paths.tenant_conversations_collection(
            self._client,
            tenant_id,
        )
        try:
            snapshots = list(conversations_collection.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list conversations from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list conversations from firestore"
            ) from error

        conversations: list[conversation_entity.Conversation] = []
        for snapshot in snapshots:
            conversation_raw_data = snapshot.to_dict()
            if conversation_raw_data is None:
                continue
            conversation = firestore_model_mapper.parse_document(
                conversation_raw_data,
                conversation_entity.Conversation,
                "conversation",
            )
            if conversation.tenant_id == tenant_id:
                conversations.append(conversation)
        return conversations

    def save_message(self, message: message_entity.Message) -> None:
        conversation_document = firestore_paths.tenant_conversation_document(
            self._client,
            message.tenant_id,
            message.conversation_id,
        )
        transaction = self._client.transaction()

        @google_cloud_firestore.transactional  # type: ignore[misc]
        def _append_message(current_transaction: google_cloud_firestore.Transaction) -> None:
            snapshot = conversation_document.get(transaction=current_transaction)
            if not snapshot.exists:
                raise firestore_errors.FirestoreRepositoryError(
                    "conversation not found in firestore for message"
                )
            conversation_raw_data = snapshot.to_dict()
            if conversation_raw_data is None:
                raise firestore_errors.FirestoreRepositoryError(
                    "conversation not found in firestore for message"
                )
            conversation = firestore_model_mapper.parse_document(
                conversation_raw_data,
                conversation_entity.Conversation,
                "conversation",
            )
            if conversation.tenant_id != message.tenant_id:
                raise firestore_errors.FirestoreRepositoryError(
                    "conversation tenant mismatch in firestore for message"
                )
            updated_conversation = conversation.model_copy(deep=True)
            updated_conversation.messages.append(message.model_copy(deep=True))
            conversation_data = firestore_model_mapper.model_to_document(updated_conversation)
            current_transaction.set(conversation_document, conversation_data, merge=False)

        try:
            _append_message(transaction)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save message in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save message in firestore"
            ) from error

    def list_messages(self, tenant_id: str, conversation_id: str) -> list[message_entity.Message]:
        conversation = self.get_conversation_by_id(tenant_id, conversation_id)
        if conversation is None:
            return []
        return [message.model_copy(deep=True) for message in conversation.messages]

    def delete_messages(self, tenant_id: str, conversation_id: str) -> None:
        conversation = self.get_conversation_by_id(tenant_id, conversation_id)
        if conversation is None:
            return
        updated_conversation = conversation.model_copy(deep=True)
        updated_conversation.messages = []
        conversation_document = firestore_paths.tenant_conversation_document(
            self._client,
            tenant_id,
            conversation_id,
        )
        conversation_data = firestore_model_mapper.model_to_document(updated_conversation)
        try:
            conversation_document.set(conversation_data, merge=False)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete messages from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete messages from firestore"
            ) from error

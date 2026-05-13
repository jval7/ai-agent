import json
import logging
import typing
import urllib.parse

import httpx

import src.infra.settings as app_settings
import src.ports.whatsapp_provider_port as whatsapp_provider_port
import src.services.dto.webhook_dto as webhook_dto
import src.services.dto.whatsapp_dto as whatsapp_dto
import src.services.dto.whatsapp_template_dto as whatsapp_template_dto
import src.services.exceptions as service_exceptions

logger = logging.getLogger(__name__)


class MetaWhatsappProviderAdapter(whatsapp_provider_port.WhatsappProviderPort):
    def __init__(self, settings: app_settings.Settings, timeout_seconds: float = 15.0) -> None:
        self._settings = settings
        self._client = httpx.Client(timeout=timeout_seconds)

    def build_embedded_signup_url(self, state: str) -> str:
        query_params = {
            "client_id": self._settings.meta_app_id,
            "redirect_uri": self._settings.meta_redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": "whatsapp_business_management,whatsapp_business_messaging",
        }
        encoded_query = urllib.parse.urlencode(query_params)
        return f"https://www.facebook.com/{self._settings.meta_api_version}/dialog/oauth?{encoded_query}"

    def exchange_code_for_credentials(
        self,
        code: str,
        *,
        from_js_sdk: bool = False,
        js_sdk_origin_url: str | None = None,
    ) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        self._validate_embedded_signup_settings()
        access_token = self._exchange_code_for_access_token(
            code, from_js_sdk=from_js_sdk, js_sdk_origin_url=js_sdk_origin_url
        )

        business_id = self._resolve_business_id(access_token)
        debug_target_ids = self._fetch_debug_target_ids(access_token)
        waba_id, phone_number_id = self._resolve_waba_and_phone_number_id(
            access_token=access_token,
            business_id=business_id,
            debug_target_ids=debug_target_ids,
        )

        return whatsapp_dto.EmbeddedSignupCredentialsDTO(
            phone_number_id=phone_number_id,
            business_account_id=waba_id,
            access_token=access_token,
        )

    def resolve_credentials_from_token(
        self, access_token: str
    ) -> whatsapp_dto.EmbeddedSignupCredentialsDTO:
        business_id = self._resolve_business_id(access_token)
        debug_target_ids = self._fetch_debug_target_ids(access_token)
        waba_id, phone_number_id = self._resolve_waba_and_phone_number_id(
            access_token=access_token,
            business_id=business_id,
            debug_target_ids=debug_target_ids,
        )
        return whatsapp_dto.EmbeddedSignupCredentialsDTO(
            phone_number_id=phone_number_id,
            business_account_id=waba_id,
            access_token=access_token,
        )

    def subscribe_app_to_waba(self, access_token: str, business_account_id: str) -> None:
        subscribed_apps_url = f"https://graph.facebook.com/{self._settings.meta_api_version}/{business_account_id}/subscribed_apps"
        headers = {"Authorization": f"Bearer {access_token}"}
        response_payload = self._post_json(
            url=subscribed_apps_url,
            operation_label="subscribing app to waba",
            headers=headers,
            body={"subscribed_fields": ["messages", "smb_message_echoes"]},
        )
        self._assert_success_flag(response_payload, "subscribing app to waba")

    def register_phone_number(
        self, access_token: str, phone_number_id: str, registration_pin: str | None = None
    ) -> None:
        pin = (registration_pin or "").strip()

        register_url = f"https://graph.facebook.com/{self._settings.meta_api_version}/{phone_number_id}/register"
        headers = {"Authorization": f"Bearer {access_token}"}
        body: dict[str, str] = {"messaging_product": "whatsapp"}
        if pin:
            body["pin"] = pin

        response_payload = self._post_json(
            url=register_url,
            operation_label="registering phone number",
            headers=headers,
            body=body,
        )
        self._assert_success_flag(response_payload, "registering phone number")

    def send_text_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        text: str,
    ) -> str:
        messages_url = f"https://graph.facebook.com/{self._settings.meta_api_version}/{phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        body = {
            "messaging_product": "whatsapp",
            "to": whatsapp_user_id,
            "type": "text",
            "text": {"body": text},
        }

        response_payload = self._post_json(
            url=messages_url,
            operation_label="sending whatsapp message",
            headers=headers,
            body=body,
        )

        messages = response_payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise service_exceptions.ExternalProviderError(
                "meta did not return outbound message id"
            )

        first_message = messages[0]
        if not isinstance(first_message, dict):
            raise service_exceptions.ExternalProviderError("invalid outbound message payload")

        outbound_message_id = first_message.get("id")
        if not isinstance(outbound_message_id, str) or not outbound_message_id:
            raise service_exceptions.ExternalProviderError("missing outbound message id")

        return outbound_message_id

    def send_template_message(
        self,
        access_token: str,
        phone_number_id: str,
        whatsapp_user_id: str,
        template_name: str,
        language_code: str,
        body_parameters: list[str],
    ) -> str:
        messages_url = (
            f"https://graph.facebook.com/{self._settings.meta_api_version}"
            f"/{phone_number_id}/messages"
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        components: list[dict[str, object]] = (
            [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": param} for param in body_parameters],
                }
            ]
            if body_parameters
            else []
        )
        body = {
            "messaging_product": "whatsapp",
            "to": whatsapp_user_id,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components,
            },
        }

        response_payload = self._post_json(
            url=messages_url,
            operation_label="sending whatsapp template message",
            headers=headers,
            body=body,
        )

        messages = response_payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise service_exceptions.ExternalProviderError(
                "meta did not return outbound message id"
            )

        first_message = messages[0]
        if not isinstance(first_message, dict):
            raise service_exceptions.ExternalProviderError("invalid outbound message payload")

        outbound_message_id = first_message.get("id")
        if not isinstance(outbound_message_id, str) or not outbound_message_id:
            raise service_exceptions.ExternalProviderError("missing outbound message id")

        return outbound_message_id

    def parse_incoming_message_events(
        self, payload: dict[str, typing.Any]
    ) -> list[webhook_dto.IncomingMessageEventDTO]:
        events: list[webhook_dto.IncomingMessageEventDTO] = []

        entries = payload.get("entry")
        if not isinstance(entries, list):
            return events

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            changes = entry.get("changes")
            if not isinstance(changes, list):
                continue

            for change in changes:
                if not isinstance(change, dict):
                    continue

                change_field = change.get("field")
                value = change.get("value")
                if not isinstance(value, dict):
                    continue

                metadata = value.get("metadata")
                if not isinstance(metadata, dict):
                    continue

                phone_number_id = metadata.get("phone_number_id")
                if not isinstance(phone_number_id, str) or not phone_number_id:
                    continue

                contacts = value.get("contacts")
                contact_name_by_wa_id: dict[str, str] = {}
                if isinstance(contacts, list):
                    for contact in contacts:
                        if not isinstance(contact, dict):
                            continue
                        wa_id = contact.get("wa_id")
                        profile = contact.get("profile")
                        if not isinstance(wa_id, str):
                            continue
                        if not isinstance(profile, dict):
                            continue
                        profile_name = profile.get("name")
                        if isinstance(profile_name, str):
                            contact_name_by_wa_id[wa_id] = profile_name

                messages = value.get("messages")
                if isinstance(messages, list):
                    for message in messages:
                        if not isinstance(message, dict):
                            continue

                        message_type = message.get("type")
                        if message_type != "text":
                            continue

                        whatsapp_user_id = message.get("from")
                        message_id = message.get("id")
                        text_payload = message.get("text")
                        if not isinstance(text_payload, dict):
                            continue
                        text_body = text_payload.get("body")

                        if not isinstance(whatsapp_user_id, str) or not whatsapp_user_id:
                            continue
                        if not isinstance(message_id, str) or not message_id:
                            continue
                        if not isinstance(text_body, str) or not text_body.strip():
                            continue

                        whatsapp_user_name = contact_name_by_wa_id.get(whatsapp_user_id)
                        event = webhook_dto.IncomingMessageEventDTO(
                            provider_event_id=message_id,
                            phone_number_id=phone_number_id,
                            whatsapp_user_id=whatsapp_user_id,
                            whatsapp_user_name=whatsapp_user_name,
                            message_id=message_id,
                            message_type=message_type,
                            source="CUSTOMER",
                            message_text=text_body,
                        )
                        events.append(event)

                if change_field != "smb_message_echoes":
                    continue

                message_echoes = value.get("message_echoes")
                if not isinstance(message_echoes, list):
                    continue

                for message_echo in message_echoes:
                    if not isinstance(message_echo, dict):
                        continue

                    message_id = message_echo.get("id")
                    if not isinstance(message_id, str) or not message_id:
                        continue

                    whatsapp_user_id = message_echo.get("to")
                    if not isinstance(whatsapp_user_id, str) or not whatsapp_user_id:
                        continue

                    message_type = message_echo.get("type")
                    if not isinstance(message_type, str) or not message_type:
                        continue

                    message_text = f"[professional_app_non_text:{message_type}]"
                    if message_type == "text":
                        text_payload = message_echo.get("text")
                        if not isinstance(text_payload, dict):
                            continue
                        text_body = text_payload.get("body")
                        if not isinstance(text_body, str) or not text_body.strip():
                            continue
                        message_text = text_body

                    event = webhook_dto.IncomingMessageEventDTO(
                        provider_event_id=message_id,
                        phone_number_id=phone_number_id,
                        whatsapp_user_id=whatsapp_user_id,
                        whatsapp_user_name=None,
                        message_id=message_id,
                        message_type=message_type,
                        source="PROFESSIONAL_APP",
                        message_text=message_text,
                    )
                    events.append(event)

        return events

    def parse_message_status_events(
        self, payload: dict[str, typing.Any]
    ) -> list[webhook_dto.MessageStatusEventDTO]:
        events: list[webhook_dto.MessageStatusEventDTO] = []

        entries = payload.get("entry")
        if not isinstance(entries, list):
            return events

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            changes = entry.get("changes")
            if not isinstance(changes, list):
                continue

            for change in changes:
                if not isinstance(change, dict):
                    continue

                value = change.get("value")
                if not isinstance(value, dict):
                    continue

                metadata = value.get("metadata")
                if not isinstance(metadata, dict):
                    continue

                phone_number_id = metadata.get("phone_number_id")
                if not isinstance(phone_number_id, str) or not phone_number_id:
                    continue

                statuses = value.get("statuses")
                if not isinstance(statuses, list):
                    continue

                for status_payload in statuses:
                    if not isinstance(status_payload, dict):
                        continue

                    provider_message_id = status_payload.get("id")
                    if not isinstance(provider_message_id, str) or not provider_message_id:
                        continue

                    raw_status = status_payload.get("status")
                    if raw_status not in ("sent", "delivered", "read", "failed"):
                        continue

                    recipient_id = status_payload.get("recipient_id")
                    if not isinstance(recipient_id, str) or not recipient_id:
                        continue

                    timestamp_epoch_seconds: int | None = None
                    raw_timestamp = status_payload.get("timestamp")
                    if isinstance(raw_timestamp, str) and raw_timestamp.isdigit():
                        timestamp_epoch_seconds = int(raw_timestamp)
                    elif isinstance(raw_timestamp, int):
                        timestamp_epoch_seconds = raw_timestamp

                    error_code: int | None = None
                    error_title: str | None = None
                    error_message: str | None = None
                    errors_payload = status_payload.get("errors")
                    if isinstance(errors_payload, list) and errors_payload:
                        first_error = errors_payload[0]
                        if isinstance(first_error, dict):
                            raw_code = first_error.get("code")
                            if isinstance(raw_code, int):
                                error_code = raw_code
                            raw_title = first_error.get("title")
                            if isinstance(raw_title, str) and raw_title.strip():
                                error_title = raw_title.strip()
                            error_data = first_error.get("error_data")
                            if isinstance(error_data, dict):
                                raw_details = error_data.get("details")
                                if isinstance(raw_details, str) and raw_details.strip():
                                    error_message = raw_details.strip()
                            if error_message is None:
                                raw_message = first_error.get("message")
                                if isinstance(raw_message, str) and raw_message.strip():
                                    error_message = raw_message.strip()

                    # Use a composite key so the dedup check stays unique even
                    # when the same wamid emits multiple lifecycle callbacks
                    # (sent → delivered → read).
                    provider_event_id = f"{provider_message_id}:{raw_status}"

                    events.append(
                        webhook_dto.MessageStatusEventDTO(
                            provider_event_id=provider_event_id,
                            phone_number_id=phone_number_id,
                            provider_message_id=provider_message_id,
                            recipient_id=recipient_id,
                            status=raw_status,
                            timestamp_epoch_seconds=timestamp_epoch_seconds,
                            error_code=error_code,
                            error_title=error_title,
                            error_message=error_message,
                        )
                    )

        return events

    def list_message_templates(
        self, access_token: str, waba_id: str
    ) -> list[whatsapp_template_dto.TemplateDTO]:
        url = f"https://graph.facebook.com/{self._settings.meta_api_version}/{waba_id}/message_templates"
        headers = {"Authorization": f"Bearer {access_token}"}
        response_payload = self._get_json(
            url=url,
            operation_label="listing message templates",
            headers=headers,
        )
        raw_data = response_payload.get("data")
        if not isinstance(raw_data, list):
            raise service_exceptions.ExternalProviderError(
                "meta did not return templates data array"
            )
        templates: list[whatsapp_template_dto.TemplateDTO] = []
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            template_id = item.get("id")
            name = item.get("name")
            category = item.get("category")
            language = item.get("language")
            status = item.get("status")
            if not isinstance(template_id, str) or not template_id:
                continue
            if not isinstance(name, str) or not name:
                continue
            if not isinstance(category, str) or not category:
                continue
            if not isinstance(language, str) or not language:
                continue
            if not isinstance(status, str) or not status:
                continue
            raw_components = item.get("components")
            components: list[whatsapp_template_dto.TemplateComponentDTO] = []
            if isinstance(raw_components, list):
                for raw_comp in raw_components:
                    if not isinstance(raw_comp, dict):
                        continue
                    comp_type = raw_comp.get("type")
                    comp_text = raw_comp.get("text", "")
                    if isinstance(comp_type, str) and comp_type:
                        components.append(
                            whatsapp_template_dto.TemplateComponentDTO(
                                type=comp_type,
                                text=comp_text if isinstance(comp_text, str) else "",
                            )
                        )
            templates.append(
                whatsapp_template_dto.TemplateDTO(
                    id=template_id,
                    name=name,
                    category=category,
                    language=language,
                    status=status,
                    components=components,
                )
            )
        return templates

    def create_message_template(
        self,
        access_token: str,
        waba_id: str,
        template: whatsapp_template_dto.CreateTemplateRequestDTO,
    ) -> whatsapp_template_dto.TemplateDTO:
        url = f"https://graph.facebook.com/{self._settings.meta_api_version}/{waba_id}/message_templates"
        headers = {"Authorization": f"Bearer {access_token}"}
        body: dict[str, typing.Any] = {
            "name": template.name,
            "category": template.category,
            "language": template.language,
            "components": [
                {
                    "type": comp.type,
                    "text": comp.text,
                    **(
                        {"example": {"body_text": [comp.example_values]}}
                        if comp.type == "BODY" and comp.example_values
                        else {}
                    ),
                }
                for comp in template.components
            ],
        }
        response_payload = self._post_json(
            url=url,
            operation_label="creating message template",
            headers=headers,
            body=body,
        )
        template_id = response_payload.get("id")
        if not isinstance(template_id, str) or not template_id:
            raise service_exceptions.ExternalProviderError(
                "meta did not return template id after creation"
            )
        status = response_payload.get("status", "PENDING")
        return whatsapp_template_dto.TemplateDTO(
            id=template_id,
            name=template.name,
            category=template.category,
            language=template.language,
            status=status if isinstance(status, str) else "PENDING",
            components=list(template.components),
        )

    def delete_message_template(self, access_token: str, waba_id: str, template_name: str) -> None:
        url = f"https://graph.facebook.com/{self._settings.meta_api_version}/{waba_id}/message_templates"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"name": template_name}
        self._delete_json(
            url=url,
            operation_label="deleting message template",
            headers=headers,
            params=params,
        )

    def _validate_embedded_signup_settings(self) -> None:
        if not self._settings.meta_app_id:
            raise service_exceptions.ExternalProviderError("META_APP_ID is required")
        if not self._settings.meta_app_secret:
            raise service_exceptions.ExternalProviderError("META_APP_SECRET is required")
        if not self._settings.meta_redirect_uri:
            raise service_exceptions.ExternalProviderError("META_REDIRECT_URI is required")

    def _exchange_code_for_access_token(
        self,
        code: str,
        *,
        from_js_sdk: bool = False,
        js_sdk_origin_url: str | None = None,
    ) -> str:
        api_version = "v21.0" if from_js_sdk else self._settings.meta_api_version
        token_url = f"https://graph.facebook.com/{api_version}/oauth/access_token"
        params: dict[str, str] = {
            "client_id": self._settings.meta_app_id,
            "client_secret": self._settings.meta_app_secret,
            "code": code,
        }
        if not from_js_sdk:
            params["redirect_uri"] = self._settings.meta_redirect_uri
        logger.info(
            "whatsapp.exchange.debug",
            extra={
                "event_data": {
                    "event": "whatsapp.exchange.debug",
                    "from_js_sdk": from_js_sdk,
                    "has_redirect_uri": "redirect_uri" in params,
                    "redirect_uri_value": params.get("redirect_uri", "")[:100],
                    "token_url": token_url,
                    "client_id": params.get("client_id", "")[:10] + "...",
                    "code_prefix": code[:20] + "...",
                    "params_keys": list(params.keys()),
                }
            },
        )
        if from_js_sdk:
            try:
                response = self._client.post(token_url, data=params)
                response.raise_for_status()
                token_payload = response.json()
            except httpx.HTTPStatusError as error:
                response_body = error.response.text[:500] if error.response else "no response"
                raise service_exceptions.ExternalProviderError(
                    f"meta rejected request while exchanging embedded signup code: {response_body}"
                ) from error
            except (httpx.TimeoutException, httpx.RequestError, json.JSONDecodeError) as error:
                raise service_exceptions.ExternalProviderError(
                    f"error while exchanging embedded signup code: {error}"
                ) from error
        else:
            token_payload = self._get_json(
                url=token_url,
                operation_label="exchanging embedded signup code",
                params=params,
            )

        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise service_exceptions.ExternalProviderError(
                "meta token exchange did not return access_token"
            )

        return access_token

    def _resolve_business_id(self, access_token: str) -> str | None:
        businesses_url = (
            f"https://graph.facebook.com/{self._settings.meta_api_version}/me/businesses"
        )
        businesses_payload = self._try_get_json(
            url=businesses_url,
            operation_label="listing businesses",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if businesses_payload is None:
            return None

        data_items = businesses_payload.get("data")
        if not isinstance(data_items, list) or not data_items:
            return None

        first_item = data_items[0]
        if not isinstance(first_item, dict):
            return None

        business_id = first_item.get("id")
        if not isinstance(business_id, str) or not business_id:
            return None

        return business_id

    def _fetch_debug_target_ids(self, access_token: str) -> list[str]:
        debug_token_url = (
            f"https://graph.facebook.com/{self._settings.meta_api_version}/debug_token"
        )
        app_access_token = f"{self._settings.meta_app_id}|{self._settings.meta_app_secret}"
        debug_payload = self._try_get_json(
            url=debug_token_url,
            operation_label="debugging embedded token",
            params={
                "input_token": access_token,
                "access_token": app_access_token,
            },
        )
        if debug_payload is None:
            return []

        data_payload = debug_payload.get("data")
        if not isinstance(data_payload, dict):
            return []

        granular_scopes = data_payload.get("granular_scopes")
        if not isinstance(granular_scopes, list):
            return []

        target_ids: list[str] = []
        for scope_item in granular_scopes:
            if not isinstance(scope_item, dict):
                continue
            scope_target_ids = scope_item.get("target_ids")
            if not isinstance(scope_target_ids, list):
                continue
            for target_id in scope_target_ids:
                if isinstance(target_id, str) and target_id:
                    target_ids.append(target_id)

        return target_ids

    def _resolve_waba_and_phone_number_id(
        self,
        access_token: str,
        business_id: str | None,
        debug_target_ids: list[str],
    ) -> tuple[str, str]:
        candidate_waba_ids: list[str] = []
        if business_id is not None:
            candidate_waba_ids.extend(
                self._fetch_waba_ids_for_business(
                    access_token=access_token,
                    business_id=business_id,
                    edge_name="client_whatsapp_business_accounts",
                )
            )
            candidate_waba_ids.extend(
                self._fetch_waba_ids_for_business(
                    access_token=access_token,
                    business_id=business_id,
                    edge_name="owned_whatsapp_business_accounts",
                )
            )

        candidate_waba_ids.extend(debug_target_ids)

        unique_candidate_ids: list[str] = []
        seen_candidate_ids: set[str] = set()
        for candidate_id in candidate_waba_ids:
            if candidate_id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate_id)
            unique_candidate_ids.append(candidate_id)

        for candidate_waba_id in unique_candidate_ids:
            phone_number_id = self._fetch_phone_number_id_for_waba(
                access_token=access_token,
                waba_id=candidate_waba_id,
            )
            if phone_number_id is not None:
                return candidate_waba_id, phone_number_id

        raise service_exceptions.ExternalProviderError("meta rejected phone number lookup")

    def _fetch_waba_ids_for_business(
        self,
        access_token: str,
        business_id: str,
        edge_name: str,
    ) -> list[str]:
        edge_url = f"https://graph.facebook.com/{self._settings.meta_api_version}/{business_id}/{edge_name}"
        edge_payload = self._try_get_json(
            url=edge_url,
            operation_label=f"loading business edge {edge_name}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if edge_payload is None:
            return []

        data_items = edge_payload.get("data")
        if not isinstance(data_items, list):
            return []

        waba_ids: list[str] = []
        for data_item in data_items:
            if not isinstance(data_item, dict):
                continue
            waba_id = data_item.get("id")
            if isinstance(waba_id, str) and waba_id:
                waba_ids.append(waba_id)

        return waba_ids

    def _fetch_phone_number_id_for_waba(self, access_token: str, waba_id: str) -> str | None:
        phone_numbers_url = (
            f"https://graph.facebook.com/{self._settings.meta_api_version}/{waba_id}/phone_numbers"
        )
        phone_numbers_payload = self._try_get_json(
            url=phone_numbers_url,
            operation_label="loading phone numbers",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if phone_numbers_payload is None:
            return None

        data_items = phone_numbers_payload.get("data")
        if not isinstance(data_items, list) or not data_items:
            return None

        first_item = data_items[0]
        if not isinstance(first_item, dict):
            return None

        phone_number_id = first_item.get("id")
        if not isinstance(phone_number_id, str) or not phone_number_id:
            return None

        return phone_number_id

    def _get_json(
        self,
        url: str,
        operation_label: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, typing.Any]:
        try:
            response = self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError(
                f"timeout while {operation_label}"
            ) from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                f"network error while {operation_label}"
            ) from error
        except httpx.HTTPStatusError as error:
            response_body = error.response.text[:500] if error.response else "no response"
            raise service_exceptions.ExternalProviderError(
                f"meta rejected request while {operation_label}: {response_body}"
            ) from error
        except json.JSONDecodeError as error:
            raise service_exceptions.ExternalProviderError(
                f"invalid response while {operation_label}"
            ) from error

        if not isinstance(payload, dict):
            raise service_exceptions.ExternalProviderError(
                f"invalid payload format while {operation_label}"
            )

        return payload

    def _try_get_json(
        self,
        url: str,
        operation_label: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, typing.Any] | None:
        try:
            return self._get_json(
                url=url,
                operation_label=operation_label,
                params=params,
                headers=headers,
            )
        except service_exceptions.ExternalProviderError:
            return None

    def _post_json(
        self,
        url: str,
        operation_label: str,
        headers: dict[str, str],
        body: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        try:
            response = self._client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError(
                f"timeout while {operation_label}"
            ) from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                f"network error while {operation_label}"
            ) from error
        except httpx.HTTPStatusError as error:
            response_text = error.response.text.strip()
            if response_text:
                raise service_exceptions.ExternalProviderError(
                    f"meta rejected request while {operation_label}: {response_text}"
                ) from error
            raise service_exceptions.ExternalProviderError(
                f"meta rejected request while {operation_label}"
            ) from error
        except json.JSONDecodeError as error:
            raise service_exceptions.ExternalProviderError(
                f"invalid response while {operation_label}"
            ) from error

        if not isinstance(payload, dict):
            raise service_exceptions.ExternalProviderError(
                f"invalid payload format while {operation_label}"
            )

        return payload

    def _delete_json(
        self,
        url: str,
        operation_label: str,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> dict[str, typing.Any]:
        try:
            response = self._client.delete(url, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError(
                f"timeout while {operation_label}"
            ) from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                f"network error while {operation_label}"
            ) from error
        except httpx.HTTPStatusError as error:
            response_text = error.response.text.strip()
            if response_text:
                raise service_exceptions.ExternalProviderError(
                    f"meta rejected request while {operation_label}: {response_text}"
                ) from error
            raise service_exceptions.ExternalProviderError(
                f"meta rejected request while {operation_label}"
            ) from error
        except json.JSONDecodeError as error:
            raise service_exceptions.ExternalProviderError(
                f"invalid response while {operation_label}"
            ) from error

        if not isinstance(payload, dict):
            raise service_exceptions.ExternalProviderError(
                f"invalid payload format while {operation_label}"
            )

        return payload

    def _assert_success_flag(self, payload: dict[str, typing.Any], operation_label: str) -> None:
        success = payload.get("success")
        if success is not True:
            raise service_exceptions.ExternalProviderError(
                f"meta did not confirm success while {operation_label}"
            )

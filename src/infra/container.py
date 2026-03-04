import src.adapters.outbound.firestore.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.firestore.blacklist_repository_adapter as blacklist_repository_adapter
import src.adapters.outbound.firestore.client_factory as firestore_client_factory
import src.adapters.outbound.firestore.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.firestore.google_calendar_connection_repository_adapter as google_calendar_connection_repository_adapter
import src.adapters.outbound.firestore.memory_admin_adapter as memory_admin_adapter
import src.adapters.outbound.firestore.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.firestore.processed_webhook_event_repository_adapter as processed_webhook_event_repository_adapter
import src.adapters.outbound.firestore.refresh_token_repository_adapter as refresh_token_repository_adapter
import src.adapters.outbound.firestore.scheduling_repository_adapter as scheduling_repository_adapter
import src.adapters.outbound.firestore.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.firestore.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.firestore.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.adapters.outbound.google_calendar.google_calendar_provider_adapter as google_calendar_provider_adapter
import src.adapters.outbound.llm_gemini.gemini_llm_provider_adapter as gemini_llm_provider_adapter
import src.adapters.outbound.secret_manager.app_config_secret_loader_adapter as app_config_secret_loader_adapter
import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.adapters.outbound.whatsapp_meta.meta_whatsapp_provider_adapter as meta_whatsapp_provider_adapter
import src.infra.langsmith_tracer as langsmith_tracer
import src.infra.settings as app_settings
import src.infra.system_adapters as system_adapters
import src.services.use_cases.agent_service as agent_service
import src.services.use_cases.auth_service as auth_service
import src.services.use_cases.blacklist_service as blacklist_service
import src.services.use_cases.conversation_control_service as conversation_control_service
import src.services.use_cases.conversation_query_service as conversation_query_service
import src.services.use_cases.google_calendar_onboarding_service as google_calendar_onboarding_service
import src.services.use_cases.memory_admin_service as memory_admin_service
import src.services.use_cases.onboarding_status_service as onboarding_status_service
import src.services.use_cases.patient_query_service as patient_query_service
import src.services.use_cases.scheduling_inbox_service as scheduling_inbox_service
import src.services.use_cases.scheduling_service as scheduling_service
import src.services.use_cases.webhook_service as webhook_service
import src.services.use_cases.whatsapp_onboarding_service as whatsapp_onboarding_service


class AppContainer:
    def __init__(self) -> None:
        self.app_config_secret_loader = (
            app_config_secret_loader_adapter.SecretManagerAppConfigLoaderAdapter()
        )
        loaded_app_config_secret = self.app_config_secret_loader.load()
        self.settings = app_settings.Settings.from_secret_json(
            raw_app_config_json=loaded_app_config_secret.secret_json,
            adc_project_id=loaded_app_config_secret.project_id,
        )
        if not self.settings.google_cloud_project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be configured")

        self.clock_adapter = system_adapters.SystemClockAdapter()
        self.id_generator_adapter = system_adapters.UuidIdGeneratorAdapter()
        self.firestore_client = firestore_client_factory.build_client(
            project_id=self.settings.google_cloud_project_id,
            database_id=self.settings.firestore_database_id,
        )

        self.tenant_repository = tenant_repository_adapter.FirestoreTenantRepositoryAdapter(
            self.firestore_client
        )
        self.user_repository = user_repository_adapter.FirestoreUserRepositoryAdapter(
            self.firestore_client
        )
        self.agent_profile_repository = (
            agent_profile_repository_adapter.FirestoreAgentProfileRepositoryAdapter(
                self.firestore_client
            )
        )
        self.whatsapp_connection_repository = (
            whatsapp_connection_repository_adapter.FirestoreWhatsappConnectionRepositoryAdapter(
                self.firestore_client
            )
        )
        self.google_calendar_connection_repository = google_calendar_connection_repository_adapter.FirestoreGoogleCalendarConnectionRepositoryAdapter(
            self.firestore_client
        )
        self.conversation_repository = (
            conversation_repository_adapter.FirestoreConversationRepositoryAdapter(
                self.firestore_client
            )
        )
        self.scheduling_repository = (
            scheduling_repository_adapter.FirestoreSchedulingRepositoryAdapter(
                self.firestore_client
            )
        )
        self.processed_webhook_event_repository = processed_webhook_event_repository_adapter.FirestoreProcessedWebhookEventRepositoryAdapter(
            self.firestore_client
        )
        self.blacklist_repository = (
            blacklist_repository_adapter.FirestoreBlacklistRepositoryAdapter(self.firestore_client)
        )
        self.memory_admin_adapter = memory_admin_adapter.FirestoreMemoryAdminAdapter(
            self.firestore_client
        )
        self.patient_repository = patient_repository_adapter.FirestorePatientRepositoryAdapter(
            self.firestore_client
        )
        self.refresh_token_repository = (
            refresh_token_repository_adapter.FirestoreRefreshTokenRepositoryAdapter(
                self.firestore_client
            )
        )

        self.password_hasher_adapter = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
        self.jwt_provider_adapter = jwt_provider_adapter.Hs256JwtProviderAdapter(
            secret=self.settings.jwt_secret,
            clock=self.clock_adapter,
        )

        self.whatsapp_provider_adapter = meta_whatsapp_provider_adapter.MetaWhatsappProviderAdapter(
            settings=self.settings,
        )
        self.google_calendar_provider_adapter = (
            google_calendar_provider_adapter.GoogleCalendarProviderAdapter(
                settings=self.settings,
            )
        )
        self.langsmith_tracer = langsmith_tracer.LangsmithTracer(
            enabled=self.settings.langsmith_tracing_enabled,
            project_name=self.settings.langsmith_project,
            api_key=self.settings.langsmith_api_key,
            api_url=self.settings.langsmith_endpoint,
            workspace_id=self.settings.langsmith_workspace_id,
            environment=self.settings.langsmith_environment,
            tags=self.settings.langsmith_tags,
        )
        self.llm_provider_adapter = gemini_llm_provider_adapter.GeminiLlmProviderAdapter(
            project_id=self.settings.google_cloud_project_id,
            location=self.settings.gemini_location,
            model=self.settings.gemini_model,
            max_output_tokens=self.settings.gemini_max_output_tokens,
            tracer=self.langsmith_tracer,
        )

        self.auth_service = auth_service.AuthService(
            tenant_repository=self.tenant_repository,
            user_repository=self.user_repository,
            agent_profile_repository=self.agent_profile_repository,
            password_hasher=self.password_hasher_adapter,
            jwt_provider=self.jwt_provider_adapter,
            refresh_token_repository=self.refresh_token_repository,
            id_generator=self.id_generator_adapter,
            clock=self.clock_adapter,
            default_system_prompt=self.settings.default_system_prompt,
            access_ttl_seconds=self.settings.jwt_access_ttl_seconds,
            refresh_ttl_seconds=self.settings.jwt_refresh_ttl_seconds,
        )

        self.agent_service = agent_service.AgentService(
            agent_profile_repository=self.agent_profile_repository,
            clock=self.clock_adapter,
            default_system_prompt=self.settings.default_system_prompt,
        )

        self.whatsapp_onboarding_service = whatsapp_onboarding_service.WhatsappOnboardingService(
            whatsapp_connection_repository=self.whatsapp_connection_repository,
            whatsapp_provider=self.whatsapp_provider_adapter,
            id_generator=self.id_generator_adapter,
            clock=self.clock_adapter,
            webhook_verify_token=self.settings.meta_webhook_verify_token,
        )
        self.google_calendar_onboarding_service = (
            google_calendar_onboarding_service.GoogleCalendarOnboardingService(
                google_calendar_connection_repository=self.google_calendar_connection_repository,
                google_calendar_provider=self.google_calendar_provider_adapter,
                id_generator=self.id_generator_adapter,
                clock=self.clock_adapter,
            )
        )
        self.scheduling_service = scheduling_service.SchedulingService(
            scheduling_repository=self.scheduling_repository,
            conversation_repository=self.conversation_repository,
            google_calendar_onboarding_service=self.google_calendar_onboarding_service,
            id_generator=self.id_generator_adapter,
            clock=self.clock_adapter,
        )
        self.scheduling_inbox_service = scheduling_inbox_service.SchedulingInboxService(
            scheduling_repository=self.scheduling_repository,
            scheduling_service=self.scheduling_service,
            google_calendar_onboarding_service=self.google_calendar_onboarding_service,
            conversation_repository=self.conversation_repository,
            whatsapp_connection_repository=self.whatsapp_connection_repository,
            whatsapp_provider=self.whatsapp_provider_adapter,
            id_generator=self.id_generator_adapter,
            clock=self.clock_adapter,
            llm_provider=self.llm_provider_adapter,
            agent_profile_repository=self.agent_profile_repository,
            default_system_prompt=self.settings.default_system_prompt,
        )

        self.webhook_service = webhook_service.WebhookService(
            whatsapp_connection_repository=self.whatsapp_connection_repository,
            conversation_repository=self.conversation_repository,
            patient_repository=self.patient_repository,
            processed_webhook_event_repository=self.processed_webhook_event_repository,
            blacklist_repository=self.blacklist_repository,
            agent_profile_repository=self.agent_profile_repository,
            scheduling_service=self.scheduling_service,
            llm_provider=self.llm_provider_adapter,
            whatsapp_provider=self.whatsapp_provider_adapter,
            id_generator=self.id_generator_adapter,
            clock=self.clock_adapter,
            default_system_prompt=self.settings.default_system_prompt,
            context_message_limit=self.settings.conversation_context_messages,
            tracer=self.langsmith_tracer,
        )

        self.conversation_query_service = conversation_query_service.ConversationQueryService(
            conversation_repository=self.conversation_repository,
        )
        self.conversation_control_service = conversation_control_service.ConversationControlService(
            conversation_repository=self.conversation_repository,
            clock=self.clock_adapter,
        )
        self.blacklist_service = blacklist_service.BlacklistService(
            blacklist_repository=self.blacklist_repository,
            clock=self.clock_adapter,
        )
        self.memory_admin_service = memory_admin_service.MemoryAdminService(
            memory_admin=self.memory_admin_adapter
        )
        self.onboarding_status_service = onboarding_status_service.OnboardingStatusService(
            whatsapp_onboarding_service=self.whatsapp_onboarding_service,
            google_calendar_onboarding_service=self.google_calendar_onboarding_service,
        )
        self.patient_query_service = patient_query_service.PatientQueryService(
            patient_repository=self.patient_repository,
        )

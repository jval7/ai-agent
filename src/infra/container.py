import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.blacklist_repository_adapter as blacklist_repository_adapter
import src.adapters.outbound.inmemory.conversation_repository_adapter as conversation_repository_adapter
import src.adapters.outbound.inmemory.memory_admin_adapter as memory_admin_adapter
import src.adapters.outbound.inmemory.processed_webhook_event_repository_adapter as processed_webhook_event_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.adapters.outbound.llm_anthropic.anthropic_llm_provider_adapter as anthropic_llm_provider_adapter
import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.adapters.outbound.whatsapp_meta.meta_whatsapp_provider_adapter as meta_whatsapp_provider_adapter
import src.infra.settings as app_settings
import src.infra.system_adapters as system_adapters
import src.services.use_cases.agent_service as agent_service
import src.services.use_cases.auth_service as auth_service
import src.services.use_cases.blacklist_service as blacklist_service
import src.services.use_cases.conversation_control_service as conversation_control_service
import src.services.use_cases.conversation_query_service as conversation_query_service
import src.services.use_cases.memory_admin_service as memory_admin_service
import src.services.use_cases.webhook_service as webhook_service
import src.services.use_cases.whatsapp_onboarding_service as whatsapp_onboarding_service


class AppContainer:
    def __init__(self) -> None:
        self.settings = app_settings.Settings.from_env()

        self.clock_adapter = system_adapters.SystemClockAdapter()
        self.id_generator_adapter = system_adapters.UuidIdGeneratorAdapter()

        self.store = in_memory_store.InMemoryStore(
            persistence_file_path=self.settings.memory_json_file_path
        )
        self.tenant_repository = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(
            self.store
        )
        self.user_repository = user_repository_adapter.InMemoryUserRepositoryAdapter(self.store)
        self.agent_profile_repository = (
            agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(self.store)
        )
        self.whatsapp_connection_repository = (
            whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(
                self.store
            )
        )
        self.conversation_repository = (
            conversation_repository_adapter.InMemoryConversationRepositoryAdapter(self.store)
        )
        self.processed_webhook_event_repository = processed_webhook_event_repository_adapter.InMemoryProcessedWebhookEventRepositoryAdapter(
            self.store
        )
        self.blacklist_repository = blacklist_repository_adapter.InMemoryBlacklistRepositoryAdapter(
            self.store
        )
        self.memory_admin_adapter = memory_admin_adapter.InMemoryMemoryAdminAdapter(self.store)

        self.password_hasher_adapter = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
        self.jwt_provider_adapter = jwt_provider_adapter.Hs256JwtProviderAdapter(
            secret=self.settings.jwt_secret,
            clock=self.clock_adapter,
        )

        self.whatsapp_provider_adapter = meta_whatsapp_provider_adapter.MetaWhatsappProviderAdapter(
            settings=self.settings,
        )
        self.llm_provider_adapter = anthropic_llm_provider_adapter.AnthropicLlmProviderAdapter(
            api_key=self.settings.anthropic_api_key,
            model=self.settings.anthropic_model,
            api_version=self.settings.anthropic_api_version,
            max_tokens=self.settings.anthropic_max_tokens,
        )

        self.auth_service = auth_service.AuthService(
            tenant_repository=self.tenant_repository,
            user_repository=self.user_repository,
            agent_profile_repository=self.agent_profile_repository,
            password_hasher=self.password_hasher_adapter,
            jwt_provider=self.jwt_provider_adapter,
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

        self.webhook_service = webhook_service.WebhookService(
            whatsapp_connection_repository=self.whatsapp_connection_repository,
            conversation_repository=self.conversation_repository,
            processed_webhook_event_repository=self.processed_webhook_event_repository,
            blacklist_repository=self.blacklist_repository,
            agent_profile_repository=self.agent_profile_repository,
            llm_provider=self.llm_provider_adapter,
            whatsapp_provider=self.whatsapp_provider_adapter,
            id_generator=self.id_generator_adapter,
            clock=self.clock_adapter,
            default_system_prompt=self.settings.default_system_prompt,
            context_message_limit=self.settings.conversation_context_messages,
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

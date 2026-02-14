import fastapi

import src.entrypoints.web.exceptions.http_exception_handlers as http_exception_handlers
import src.entrypoints.web.routers.agent_router as agent_router
import src.entrypoints.web.routers.auth_router as auth_router
import src.entrypoints.web.routers.conversation_router as conversation_router
import src.entrypoints.web.routers.dev_router as dev_router
import src.entrypoints.web.routers.health_router as health_router
import src.entrypoints.web.routers.oauth_router as oauth_router
import src.entrypoints.web.routers.webhook_router as webhook_router
import src.entrypoints.web.routers.whatsapp_router as whatsapp_router
import src.infra.container as app_container


def create_app() -> fastapi.FastAPI:
    app = fastapi.FastAPI(title="AI Agent WhatsApp MVP", version="0.1.0")
    app.state.container = app_container.AppContainer()

    app.include_router(health_router.router)
    app.include_router(auth_router.router)
    app.include_router(agent_router.router)
    app.include_router(whatsapp_router.router)
    app.include_router(webhook_router.router)
    app.include_router(conversation_router.router)
    app.include_router(oauth_router.router)
    if app.state.container.settings.enable_dev_endpoints:
        app.include_router(dev_router.router)

    http_exception_handlers.register_exception_handlers(app)
    return app


app = create_app()

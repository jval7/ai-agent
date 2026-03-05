import json

import pytest

import src.infra.settings as settings_module


def test_from_secret_json_applies_overrides() -> None:
    settings = settings_module.Settings.from_secret_json(
        raw_app_config_json=json.dumps(
            {
                "META_REDIRECT_URI": "https://new.example.com/callback",
                "CONTEXT_MESSAGE_LIMIT": 50,
                "ENABLE_DEV_ENDPOINTS": False,
                "CORS_ALLOWED_ORIGINS": [
                    "https://app.example.com",
                    "https://admin.example.com",
                ],
                "LANGSMITH_TAGS": ["prod", "gcp"],
            }
        ),
        adc_project_id="project-from-adc",
    )

    assert settings.meta_redirect_uri == "https://new.example.com/callback"
    assert settings.conversation_context_messages == 50
    assert settings.enable_dev_endpoints is False
    assert settings.google_cloud_project_id == "project-from-adc"
    assert settings.cors_allowed_origins == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert settings.langsmith_tags == ["prod", "gcp"]


def test_from_secret_json_raises_when_json_is_invalid() -> None:
    with pytest.raises(ValueError, match="App config secret must be valid JSON"):
        settings_module.Settings.from_secret_json(
            raw_app_config_json="{invalid-json",
            adc_project_id="project-from-adc",
        )


def test_from_secret_json_uses_secret_project_override() -> None:
    settings = settings_module.Settings.from_secret_json(
        raw_app_config_json=json.dumps({"GOOGLE_CLOUD_PROJECT": "project-from-secret"}),
        adc_project_id="project-from-adc",
    )

    assert settings.google_cloud_project_id == "project-from-secret"


def test_from_secret_json_applies_cors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS_OVERRIDE",
        "http://localhost:5173,http://127.0.0.1:5173",
    )

    settings = settings_module.Settings.from_secret_json(
        raw_app_config_json=json.dumps(
            {
                "CORS_ALLOWED_ORIGINS": [
                    "https://app.example.com",
                    "https://admin.example.com",
                ]
            }
        ),
        adc_project_id="project-from-adc",
    )

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

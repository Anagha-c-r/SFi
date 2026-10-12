"""Settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "GDI Reporting Portal")
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./gdi_portal.db")

    # Security
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_minutes: int = int(os.getenv("JWT_MINUTES", "480"))
    # Fernet key used to encrypt each institution's CBK client secret at rest.
    # Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")
    cors_origins: list[str] = field(default_factory=lambda: _list("CORS_ORIGINS", "http://localhost:5173"))

    # CBK GDI endpoints (from the guide's "How to set up environment" table)
    cbk_token_url: str = os.getenv("CBK_TOKEN_URL", "https://gdi.centralbank.go.ke/oauth2/v1/token")
    cbk_uat_base: str = os.getenv("CBK_UAT_BASE", "https://gdi.centralbank.go.ke/preprod")
    cbk_prod_base: str = os.getenv("CBK_PROD_BASE", "https://gdi.centralbank.go.ke:443")
    cbk_timeout_seconds: float = float(os.getenv("CBK_TIMEOUT_SECONDS", "120"))
    # The guide does not say which size triggers MaximumSizeExceeded; above this
    # many rows the portal sends the data as an attached CSV instead of JSON.
    json_row_limit: int = int(os.getenv("JSON_ROW_LIMIT", "5000"))

    # First platform admin, created on startup if no users exist
    bootstrap_admin_email: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@finoworks.com")
    bootstrap_admin_password: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    seed_demo_data: bool = _bool("SEED_DEMO_DATA", False)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()

# backend/core/settings.py
from __future__ import annotations
from typing import List, Optional
import json
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

def _parse_cors(val: str | List[str] | None) -> List[str]:
    """
    Akzeptiert:
      - JSON-Liste: '["http://localhost:5173","http://localhost:3000"]'
      - Kommaliste: 'http://localhost:5173,http://localhost:3000'
      - Liste[str]
    """
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    s = str(val).strip()
    if not s:
        return []
    try:
        data = json.loads(s)
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return [x.strip() for x in s.split(",") if x.strip()]

class Settings(BaseSettings):
    # --- API / App ---
    API_PREFIX: str = "/api"
    DEBUG: bool = False
    # diese beiden kommen bei dir in der .env vor:
    API_HOST: Optional[str] = None
    API_PORT: Optional[int] = None

    # --- CORS ---
    CORS_ORIGINS: List[str] = Field(default_factory=list)

    # --- DB: entweder DATABASE_URL ODER POSTGRES_* ---
    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None  # "5433" wird sauber zu int geparst

    # --- Sonstiges, das bei dir in .env auftaucht ---
    GRAFANA_ADMIN_USER: Optional[str] = None
    GRAFANA_ADMIN_PASSWORD: Optional[str] = None
    VITE_API_URL: Optional[str] = None  # stört dann nicht mehr, auch wenn's eher ins FE gehört

    # pydantic v2 settings-config:
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",  # <<<<< unbekannte .env-Variablen NICHT mehr verbieten
    )

    @property
    def sqlalchemy_dsn(self) -> str:
        """DSN für SQLAlchemy: bevorzugt DATABASE_URL; sonst aus POSTGRES_* gebaut."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # sinnvolle Defaults, falls Einzelwerte fehlen
        user = self.POSTGRES_USER or "postgres"
        pwd  = self.POSTGRES_PASSWORD or ""
        host = self.POSTGRES_HOST or "localhost"
        port = self.POSTGRES_PORT or 5432
        db   = self.POSTGRES_DB or "postgres"
        auth = f"{user}:{pwd}" if pwd else user
        return f"postgresql://{auth}@{host}:{port}/{db}"

    def cors_origins_list(self) -> List[str]:
        return _parse_cors(self.CORS_ORIGINS)

settings = Settings()

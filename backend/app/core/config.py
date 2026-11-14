"""
Application configuration – reads from environment / .env file.
Never hard-code secrets here.
"""

from typing import Any, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change_me"
    port: int = 8000

    # CORS – accepts JSON list or comma-separated URLs
    allowed_origins: Union[list[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("allowed_origins")
    @classmethod
    def assemble_cors_origins(cls, v: Any):
        if isinstance(v, str):
            v_strip = v.strip()
            if v_strip.startswith("[") and v_strip.endswith("]"):
                import json
                try:
                    return json.loads(v_strip)
                except Exception:
                    pass
            return [i.strip() for i in v_strip.split(",") if i.strip()]
        return v

    # Gemini AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Database (populated later)
    database_url: str = ""

    # File storage
    upload_dir: str = "uploads"
    extracted_text_dir: str = "extracted_text"
    max_file_size_mb: int = 10

    # OCR configuration
    tesseract_cmd: str = ""

    # Supabase Cloud Storage & Database
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket: str = "metro-documents"


settings = Settings()

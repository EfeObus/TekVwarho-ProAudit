"""
TekVwarho ProAudit - Configuration Settings

This module handles all application configuration using Pydantic Settings.
Environment variables are loaded from .env file.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ===========================================
    # APPLICATION CONFIGURATION
    # ===========================================
    app_name: str = "TekVwarho ProAudit"
    app_env: str = "development"
    debug: bool = True
    secret_key: str  # Required - must be set in .env
    api_version: str = "v1"
    
    # ===========================================
    # DATABASE CONFIGURATION
    # ===========================================
    database_url: str  # Required - must be set in .env
    database_url_async: str  # Required - must be set in .env
    postgres_user: str  # Required - must be set in .env
    postgres_password: str  # Required - must be set in .env
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "tekvwarho_proaudit"
    
    # ===========================================
    # JWT AUTHENTICATION
    # ===========================================
    jwt_secret_key: str  # Required - must be set in .env
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # ===========================================
    # REDIS CONFIGURATION
    # ===========================================
    redis_url: str = "redis://localhost:6379/0"
    
    # ===========================================
    # NRS/FIRS E-INVOICING API (Federal Inland Revenue Service)
    # Development: https://api-dev.i-fis.com
    # Production: https://atrs-api.firs.gov.ng
    # ===========================================
    nrs_api_url: str = "https://api-dev.i-fis.com"
    nrs_api_url_prod: str = "https://atrs-api.firs.gov.ng"
    nrs_api_key: str = ""
    nrs_sandbox_mode: bool = True
    
    @property
    def nrs_active_url(self) -> str:
        """Get the active NRS API URL based on sandbox mode."""
        return self.nrs_api_url if self.nrs_sandbox_mode else self.nrs_api_url_prod
    
    # ===========================================
    # OCR SERVICE (Azure Form Recognizer)
    # ===========================================
    azure_form_recognizer_endpoint: str = ""
    azure_form_recognizer_key: str = ""
    
    # ===========================================
    # FILE STORAGE
    # ===========================================
    storage_backend: str = "local"
    storage_local_path: str = "./uploads"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_s3_bucket: Optional[str] = None
    
    # ===========================================
    # EMAIL CONFIGURATION
    # ===========================================
    mail_server: str = "smtp.gmail.com"
    mail_port: int = 587
    mail_use_tls: bool = True
    mail_username: str = ""
    mail_password: str = ""
    
    # ===========================================
    # SUPER ADMIN CONFIGURATION (Hardcoded Credentials)
    # These are the default credentials for the Super Admin account.
    # In production, override these via environment variables!
    # ===========================================
    super_admin_email: str = "superadmin@tekvwarho.com"
    super_admin_password: str = "SuperAdmin@TekVwarho2026!"
    super_admin_first_name: str = "Super"
    super_admin_last_name: str = "Admin"
    
    # ===========================================
    # CORS SETTINGS
    # ===========================================
    cors_origins: str = "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,http://localhost:5120,http://127.0.0.1:5120"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env.lower() == "development"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to avoid reading .env file on every call.
    """
    return Settings()


# Export settings instance
settings = get_settings()

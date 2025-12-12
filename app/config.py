"""
Configuration Management

This module loads environment variables from .env file and provides
a centralized Settings object for the entire application.

Usage:
    from app.config import settings
    
    print(settings.github_token)
    print(settings.devin_api_key)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All values are read from .env file or environment variables.
    Required fields will raise an error if not provided.
    """
    
    # GitHub API Configuration
    github_token: str
    
    # Devin API Configuration
    devin_api_key: str
    devin_api_url: str = "https://api.devin.ai/v1"
    
    # Backend API Settings
    orchestrator_host: str = "0.0.0.0"
    orchestrator_port: int = 8000
    
    # Database Configuration
    database_url: str = "sqlite:///./devin_cli.db"
    
    # Polling Configuration
    devin_poll_interval: int = 15  # seconds between polls
    devin_poll_timeout: int = 1800  # max time to wait (30 minutes)
    devin_poll_max_interval: int = 30  # max interval for exponential backoff
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields in .env
    )


# Create a single instance to use throughout the application
# This will automatically load the .env file when imported
settings = Settings()


# Validate that critical settings are present
def validate_settings():
    """Validate that all required settings are configured properly."""
    errors = []
    
    if not settings.github_token or settings.github_token == "your_github_token_here":
        errors.append("GITHUB_TOKEN is not configured in .env file")
    
    if not settings.devin_api_key or settings.devin_api_key == "your_devin_api_key_here":
        errors.append("DEVIN_API_KEY is not configured in .env file")
    
    if errors:
        error_msg = "\n".join(errors)
        raise ValueError(
            f"Configuration errors:\n{error_msg}\n\n"
            f"Please update your .env file with valid credentials.\n"
            f"See .env.example for reference."
        )


if __name__ == "__main__":
    # Test configuration when run directly
    print("Configuration loaded successfully!")
    print(f"GitHub Token: {'*' * 20} (hidden)")
    print(f"Devin API Key: {'*' * 20} (hidden)")
    print(f"Devin API URL: {settings.devin_api_url}")
    print(f"Orchestrator: {settings.orchestrator_host}:{settings.orchestrator_port}")
    print(f"Database: {settings.database_url}")


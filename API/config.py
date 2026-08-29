import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = int(os.environ.get("PORT", 8081))
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
    
    # Performance
    MAX_RETRIES: int = int(os.environ.get("MAX_RETRIES", 3))
    TIMEOUT: int = int(os.environ.get("TIMEOUT", 20))
    PARALLEL_WORKERS: int = int(os.environ.get("PARALLEL_WORKERS", 1))
    
    # Data files
    DATA_DIR: str = os.environ.get("DATA_DIR", "/app/data")
    SITES_FILE: str = os.path.join(DATA_DIR, "sites.txt")
    PROXIES_FILE: str = os.path.join(DATA_DIR, "proxies.txt")
    
    # Defaults
    DEFAULT_PRICE: str = "2.95 USD"
    DEFAULT_GATEWAY: str = "Shopify Payments"
    
    # Email generation
    EMAIL_DOMAINS: List[str] = [
        "gmail.com", "outlook.com", "yahoo.com",
        "protonmail.com", "hotmail.com"
    ]
    
    class Config:
        env_file = ".env"

settings = Settings()

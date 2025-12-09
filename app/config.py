from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Impact Unplugged"
    GOOGLE_API_KEY: str
    OPENROUTER_API_KEY: str
    MISTRAL_API_KEY: str
    CHROMA_DB_DIR: str = "./chroma_db"
    GITHUB_TOKEN: str = ""
    
    # Multi-repo settings
    MAX_REPOS: int = 10
    REPOS_BASE_DIR: str = "./repos"
    
    # Performance settings
    MAX_FILE_SIZE_KB: int = 500
    BATCH_SIZE: int = 10
    
    # Gemini optimization
    ENABLE_LLM_CACHE: bool = True
    MIN_IMPACT_FOR_LLM: int = 3  # Only use LLM if impact score >= 3
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
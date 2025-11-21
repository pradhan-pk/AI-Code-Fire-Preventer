from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Code Fire Preventer"
    GOOGLE_API_KEY: str
    CHROMA_DB_DIR: str = "./chroma_db"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

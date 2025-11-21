import sys
import os

try:
    from app.config import get_settings
    from app.services.repo_manager import RepoManager
    from app.services.vector_store import VectorStore
    from app.services.analyzer import DependencyAnalyzer
    from main import app
    print("Imports successful. Syntax looks good.")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")

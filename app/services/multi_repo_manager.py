import os
import shutil
from typing import List, Dict, Optional
from git import Repo
from dataclasses import dataclass
from app.config import get_settings

settings = get_settings()

@dataclass
class RepoMetadata:
    """Metadata for a cloned repository"""
    repo_id: str
    repo_url: str
    repo_path: str
    language: str  # 'python', 'java', 'mixed'
    commit_sha: Optional[str] = None

class MultiRepoManager:
    """Manages multiple repositories for cross-repo dependency analysis"""
    
    def __init__(self):
        self.repos_base_dir = settings.REPOS_BASE_DIR
        os.makedirs(self.repos_base_dir, exist_ok=True)
        self.repos: Dict[str, RepoMetadata] = {}
        
    def add_repository(self, repo_url: str, commit_sha: str = None) -> RepoMetadata:
        """
        Clone and register a repository
        
        Args:
            repo_url: GitHub repository URL
            commit_sha: Optional commit SHA to checkout
            
        Returns:
            RepoMetadata object with repository information
        """
        # Generate unique repo ID
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        repo_id = f"{repo_name}_{commit_sha[:7] if commit_sha else 'main'}"
        
        # Return existing if already cloned
        if repo_id in self.repos:
            return self.repos[repo_id]
            
        repo_path = os.path.join(self.repos_base_dir, repo_id)
        
        try:
            # Clone or fetch repository
            if os.path.exists(repo_path):
                repo = Repo(repo_path)
                repo.remotes.origin.fetch()
            else:
                repo = Repo.clone_from(repo_url, repo_path)
            
            # Checkout specific commit or default branch
            if commit_sha:
                repo.git.checkout(commit_sha)
            else:
                try:
                    repo.git.checkout('main')
                except:
                    try:
                        repo.git.checkout('master')
                    except:
                        pass  # Stay on current HEAD
                        
            # Detect primary language
            language = self._detect_language(repo_path)
            
            # Create metadata
            metadata = RepoMetadata(
                repo_id=repo_id,
                repo_url=repo_url,
                repo_path=repo_path,
                language=language,
                commit_sha=commit_sha
            )
            
            self.repos[repo_id] = metadata
            return metadata
            
        except Exception as e:
            raise Exception(f"Failed to add repository {repo_url}: {str(e)}")
    
    def _detect_language(self, repo_path: str) -> str:
        """
        Detect primary language(s) in repository by counting file extensions
        
        Args:
            repo_path: Path to repository
            
        Returns:
            'python', 'java', or 'mixed'
        """
        py_files = 0
        java_files = 0
        
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.endswith('.py'):
                    py_files += 1
                elif file.endswith('.java'):
                    java_files += 1
        
        if py_files > 0 and java_files > 0:
            return 'mixed'
        elif java_files > py_files:
            return 'java'
        else:
            return 'python'
    
    def get_all_files(self) -> Dict[str, List[str]]:
        """
        Get all relevant code files from all repositories
        
        Returns:
            Dictionary mapping repo_id to list of file paths
        """
        all_files = {}
        valid_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs'}
        
        for repo_id, metadata in self.repos.items():
            files = []
            
            for root, dirs, filenames in os.walk(metadata.repo_path):
                # Skip hidden directories like .git
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in filenames:
                    if any(file.endswith(ext) for ext in valid_extensions):
                        full_path = os.path.join(root, file)
                        
                        # Check file size to avoid huge files
                        try:
                            file_size = os.path.getsize(full_path) / 1024  # KB
                            
                            if file_size <= settings.MAX_FILE_SIZE_KB:
                                files.append(full_path)
                        except:
                            continue
            
            all_files[repo_id] = files
            
        return all_files
    
    def get_repo_by_path(self, file_path: str) -> Optional[RepoMetadata]:
        """
        Find which repository a file belongs to
        
        Args:
            file_path: Full path to a file
            
        Returns:
            RepoMetadata if found, None otherwise
        """
        for metadata in self.repos.values():
            if file_path.startswith(metadata.repo_path):
                return metadata
        return None
    
    def get_base_path(self):
        # Extract common root path for all repos
        if not self.repos:
            return ""

        sample_path = next(iter(self.repos.values())).repo_path
        return os.path.dirname(sample_path)

    
    def get_repo_by_url(self, repo_url: str) -> Optional[RepoMetadata]:
        """
        Find repository metadata by URL
        
        Args:
            repo_url: Repository URL
            
        Returns:
            RepoMetadata if found, None otherwise
        """
        for metadata in self.repos.values():
            if metadata.repo_url == repo_url:
                return metadata
        return None
    
    def cleanup(self):
        """Clean up all cloned repositories"""
        for metadata in self.repos.values():
            if os.path.exists(metadata.repo_path):
                try:
                    shutil.rmtree(metadata.repo_path)
                except Exception as e:
                    print(f"Failed to cleanup {metadata.repo_path}: {e}")
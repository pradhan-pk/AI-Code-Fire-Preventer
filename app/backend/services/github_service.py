import os
import shutil
from pathlib import Path
import subprocess
import logging

logger = logging.getLogger(__name__)

class GitHubService:
    def __init__(self):
        self.repos_dir = Path("/tmp/code_analyzer_repos")
        self.repos_dir.mkdir(exist_ok=True)
    
    async def clone_repository(self, url: str, token: str, branch: str = "main") -> Path:
        """Clone a GitHub repository using PAT"""
        try:
            # Extract repo name from URL
            repo_name = url.rstrip('/').split('/')[-1].replace('.git', '')
            repo_path = self.repos_dir / repo_name
            
            # Remove existing directory if it exists
            if repo_path.exists():
                shutil.rmtree(repo_path)
            
            # Construct authenticated URL
            if url.startswith('https://'):
                auth_url = url.replace('https://', f'https://{token}@')
            else:
                auth_url = url
            
            # Clone repository
            cmd = ['git', 'clone', '-b', branch, '--depth', '1', auth_url, str(repo_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Failed to clone repository: {result.stderr}")
            
            logger.info(f"Successfully cloned repository to {repo_path}")
            return repo_path
            
        except Exception as e:
            logger.error(f"Error cloning repository: {str(e)}")
            raise
    
    async def get_changed_files(self, repo_path: Path, commit_hash: str = None) -> list:
        """Get list of changed files in a commit"""
        try:
            if commit_hash:
                cmd = ['git', '-C', str(repo_path), 'diff-tree', '--no-commit-id', '--name-only', '-r', commit_hash]
            else:
                cmd = ['git', '-C', str(repo_path), 'diff', '--name-only', 'HEAD~1', 'HEAD']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')
            return []
            
        except Exception as e:
            logger.error(f"Error getting changed files: {str(e)}")
            return []
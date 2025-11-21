import os
import shutil
import tempfile
from typing import List
from git import Repo

class RepoManager:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    def clone_repo(self, repo_url: str, commit_sha: str = None) -> str:
        """
        Clones the repo to a persistent 'repos/' directory.
        If commit_sha is provided, checks out that commit.
        """
        try:
            # Extract repo name from URL
            repo_name = repo_url.split('/')[-1]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            
            # Use a persistent 'repos' directory in the project root
            # This ensures paths are stable and accessible
            project_root = os.getcwd()
            repos_dir = os.path.join(project_root, "repos")
            os.makedirs(repos_dir, exist_ok=True)
            
            self.temp_dir = os.path.join(repos_dir, repo_name)
            
            if os.path.exists(self.temp_dir):
                # Repo exists, fetch latest to ensure we have the commit
                repo = Repo(self.temp_dir)
                repo.remotes.origin.fetch()
            else:
                # Clone fresh
                repo = Repo.clone_from(repo_url, self.temp_dir)
            
            # Checkout specific commit if requested
            if commit_sha:
                repo.git.checkout(commit_sha)
                print(f"Checked out commit {commit_sha} in {self.temp_dir}")
            else:
                # Default to main/master if no commit specified (e.g. for initial analysis)
                # Try to find default branch
                try:
                    repo.git.checkout('main')
                except:
                    try:
                        repo.git.checkout('master')
                    except:
                        pass # Stay on current HEAD
                
            return self.temp_dir
        except Exception as e:
            raise Exception(f"Failed to clone/checkout repository: {str(e)}")

    def get_files(self, repo_path: str) -> List[str]:
        """Traverses the repo and returns a list of relevant file paths."""
        relevant_files = []
        # Add more extensions as needed
        valid_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.rb', '.php'}
        
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories like .git
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if any(file.endswith(ext) for ext in valid_extensions):
                    full_path = os.path.join(root, file)
                    relevant_files.append(full_path)
                    
        return relevant_files

    def cleanup(self):
        """Cleans up the temporary directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

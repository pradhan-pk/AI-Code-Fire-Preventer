# app/services/github_service.py

import requests
from typing import List, Dict
import re

class GitHubService:
    def __init__(self, token: str = None):
        self.token = token
        self.headers = {}
        if token:
            self.headers['Authorization'] = f'token {token}'
        self.headers['Accept'] = 'application/vnd.github.v3+json'
    
    def get_commit_diff(self, repo_url: str, commit_sha: str) -> List[Dict[str, str]]:
        """
        Fetch commit diff from GitHub API.
        
        Args:
            repo_url: Full GitHub repo URL (e.g., https://github.com/owner/repo)
            commit_sha: Commit SHA or short SHA
            
        Returns:
            List of changed files with their diffs
        """
        print(f"\n=== GITHUB DIFF FETCHER ===")
        print(f"Repo URL: {repo_url}")
        print(f"Commit SHA: {commit_sha}")
        
        # Extract owner and repo from URL
        # URL format: https://github.com/owner/repo or https://github.com/owner/repo.git
        repo_url = repo_url.rstrip('/').rstrip('.git')
        parts = repo_url.split('/')
        
        if len(parts) < 2:
            print(f"ERROR: Invalid repo URL format: {repo_url}")
            return []
        
        owner = parts[-2]
        repo = parts[-1]
        
        print(f"Owner: {owner}")
        print(f"Repo: {repo}")
        
        # GitHub API endpoint
        api_url = f'https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}'
        
        print(f"API URL: {api_url}")
        print(f"Headers: {list(self.headers.keys())}")
        
        try:
            response = requests.get(api_url, headers=self.headers, timeout=10)
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 404:
                print(f"ERROR: Commit not found. This could mean:")
                print(f"  1. The commit SHA is incorrect")
                print(f"  2. The repository is private and needs authentication")
                print(f"  3. The commit hasn't been pushed yet")
                return []
            
            if response.status_code == 403:
                print(f"ERROR: API rate limit exceeded or authentication required")
                print(f"Response: {response.text[:200]}")
                return []
            
            response.raise_for_status()
            
            commit_data = response.json()
            
            # Extract files from commit
            files = commit_data.get('files', [])
            
            print(f"Files changed in commit: {len(files)}")
            
            diff_data = []
            
            for file_info in files:
                filename = file_info.get('filename', '')
                status = file_info.get('status', '')  # added, modified, removed
                patch = file_info.get('patch', '')
                
                print(f"  - {filename} ({status})")
                
                diff_entry = {
                    'file_path': filename,
                    'filename': filename,  # Add both for compatibility
                    'status': status,
                    'patch': patch,
                    'additions': file_info.get('additions', 0),
                    'deletions': file_info.get('deletions', 0),
                    'changes': file_info.get('changes', 0)
                }
                
                diff_data.append(diff_entry)
            
            print(f"Total diff entries created: {len(diff_data)}")
            print(f"===========================\n")
            
            return diff_data
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Failed to fetch commit diff: {e}")
            print(f"===========================\n")
            return []
        except Exception as e:
            print(f"ERROR: Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            print(f"===========================\n")
            return []
    
    def compare_commits(self, repo_url: str, base_sha: str, head_sha: str) -> List[Dict[str, str]]:
        """
        Compare two commits to get the diff.
        Useful for comparing branches or commit ranges.
        """
        repo_url = repo_url.rstrip('/').rstrip('.git')
        parts = repo_url.split('/')
        owner = parts[-2]
        repo = parts[-1]
        
        api_url = f'https://api.github.com/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}'
        
        try:
            response = requests.get(api_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            compare_data = response.json()
            files = compare_data.get('files', [])
            
            diff_data = []
            for file_info in files:
                diff_entry = {
                    'file_path': file_info.get('filename', ''),
                    'filename': file_info.get('filename', ''),
                    'status': file_info.get('status', ''),
                    'patch': file_info.get('patch', ''),
                    'additions': file_info.get('additions', 0),
                    'deletions': file_info.get('deletions', 0),
                    'changes': file_info.get('changes', 0)
                }
                diff_data.append(diff_entry)
            
            return diff_data
            
        except Exception as e:
            print(f"Error comparing commits: {e}")
            return []
    
    def get_file_content(self, repo_url: str, file_path: str, ref: str = 'main') -> str:
        """
        Fetch the content of a specific file from a repository.
        """
        repo_url = repo_url.rstrip('/').rstrip('.git')
        parts = repo_url.split('/')
        owner = parts[-2]
        repo = parts[-1]
        
        api_url = f'https://api.github.com/repos/{owner}/{repo}/contents/{file_path}'
        
        params = {'ref': ref}
        
        try:
            response = requests.get(api_url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            content_data = response.json()
            
            # GitHub returns base64 encoded content
            import base64
            content = base64.b64decode(content_data['content']).decode('utf-8')
            
            return content
            
        except Exception as e:
            print(f"Error fetching file content: {e}")
            return ""
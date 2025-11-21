import requests
import re
from typing import List, Dict, Any, Tuple

class GitHubService:
    def __init__(self, token: str = None):
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if token:
            self.headers["Authorization"] = f"token {token}"

    def get_commit_diff(self, repo_url: str, commit_sha: str) -> List[Dict[str, Any]]:
        """
        Fetches the commit details and parses the diff to find changed lines.
        """
        # Extract owner and repo from URL
        # Expected format: https://github.com/owner/repo
        match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if not match:
            raise ValueError("Invalid GitHub URL")
        
        owner, repo = match.groups()
        if repo.endswith('.git'):
            repo = repo[:-4]
            
        api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"
        
        response = requests.get(api_url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch commit: {response.status_code} {response.text}")
            
        commit_data = response.json()
        changes = []
        
        for file in commit_data.get('files', []):
            filename = file.get('filename')
            patch = file.get('patch')
            status = file.get('status') # modified, added, removed, renamed
            
            if not patch:
                continue
                
            changed_lines = self._parse_patch(patch)
            
            changes.append({
                "file_path": filename,
                "status": status,
                "changed_lines": changed_lines, # List of line numbers in the NEW file
                "patch": patch
            })
            
        return changes

    def _parse_patch(self, patch: str) -> List[int]:
        """
        Parses a unified diff patch string to extract the line numbers of added/modified lines.
        Returns a list of line numbers in the new file version.
        """
        changed_lines = []
        # Regex to match chunk headers: @@ -old_start,old_len +new_start,new_len @@
        chunk_header_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
        
        current_line_number = 0
        
        lines = patch.split('\n')
        
        for line in lines:
            if line.startswith('@@'):
                match = chunk_header_re.match(line)
                if match:
                    start_line = int(match.group(1))
                    current_line_number = start_line
            elif line.startswith('+'):
                # Added or modified line
                changed_lines.append(current_line_number)
                current_line_number += 1
            elif line.startswith(' '):
                # Context line, just advance counter
                current_line_number += 1
            elif line.startswith('-'):
                # Removed line, doesn't exist in new file, so don't count for new line numbers
                pass
                
        return changed_lines

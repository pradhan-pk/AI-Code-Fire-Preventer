import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import json
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path("/app/data/codeanalyzer.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database with all tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Repositories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                github_token TEXT NOT NULL,
                branch TEXT NOT NULL DEFAULT 'main',
                status TEXT NOT NULL DEFAULT 'pending',
                last_commit_hash TEXT,
                last_analyzed_at TEXT,
                created_at TEXT NOT NULL,
                webhook_id TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        
        # Modules table (code modules/services within repos)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                id TEXT PRIMARY KEY,
                repo_id TEXT NOT NULL,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                file_count INTEGER DEFAULT 0,
                function_count INTEGER DEFAULT 0,
                class_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
            )
        ''')
        
        # Code chunks table (functions, classes, blocks)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS code_chunks (
                id TEXT PRIMARY KEY,
                module_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                chunk_type TEXT NOT NULL,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                start_line INTEGER,
                end_line INTEGER,
                embedding_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
            )
        ''')
        
        # Dependencies table (direct dependencies)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dependencies (
                id TEXT PRIMARY KEY,
                source_module_id TEXT NOT NULL,
                target_module_id TEXT NOT NULL,
                dependency_type TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_module_id) REFERENCES modules(id) ON DELETE CASCADE,
                FOREIGN KEY (target_module_id) REFERENCES modules(id) ON DELETE CASCADE
            )
        ''')
        
        # Graph communities table (GraphRAG)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS graph_communities (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                community_id INTEGER NOT NULL,
                level INTEGER NOT NULL,
                nodes TEXT NOT NULL,
                summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        
        # Analyses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                repo_id TEXT NOT NULL,
                branch TEXT NOT NULL,
                commit_hash TEXT NOT NULL,
                changed_files TEXT NOT NULL,
                impacted_modules TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                recommendations TEXT NOT NULL,
                analysis_result TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
            )
        ''')
        
        # File changes tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_changes (
                id TEXT PRIMARY KEY,
                repo_id TEXT NOT NULL,
                commit_hash TEXT NOT NULL,
                file_path TEXT NOT NULL,
                change_type TEXT NOT NULL,
                processed BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    # Project operations
    def create_project(self, project_id: str, name: str, description: str = "") -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT INTO projects (id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (project_id, name, description, now, now))
        
        conn.commit()
        conn.close()
        return {"id": project_id, "name": name, "description": description}
    
    def get_projects(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM projects ORDER BY created_at DESC')
        projects = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return projects
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    # Repository operations
    def create_repository(self, repo_data: Dict) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT INTO repositories 
            (id, project_id, name, url, github_token, branch, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            repo_data['id'], repo_data['project_id'], repo_data['name'],
            repo_data['url'], repo_data['github_token'], 
            repo_data.get('branch', 'main'), 'pending', now
        ))
        
        conn.commit()
        conn.close()
        return repo_data
    
    def get_repositories(self, project_id: str) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM repositories WHERE project_id = ? ORDER BY created_at DESC',
            (project_id,)
        )
        repos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return repos
    
    def update_repository_status(self, repo_id: str, status: str, **kwargs):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = ["status = ?"]
        params = [status]
        
        if 'last_commit_hash' in kwargs:
            updates.append("last_commit_hash = ?")
            params.append(kwargs['last_commit_hash'])
        
        if 'webhook_id' in kwargs:
            updates.append("webhook_id = ?")
            params.append(kwargs['webhook_id'])
        
        params.append(repo_id)
        
        cursor.execute(
            f"UPDATE repositories SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        conn.close()
    
    # Module operations
    def create_module(self, module_data: Dict) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT INTO modules 
            (id, repo_id, name, path, file_count, function_count, class_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            module_data['id'], module_data['repo_id'], module_data['name'],
            module_data['path'], module_data.get('file_count', 0),
            module_data.get('function_count', 0), module_data.get('class_count', 0),
            now, now
        ))
        
        conn.commit()
        conn.close()
        return module_data
    
    def get_modules(self, repo_id: str) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM modules WHERE repo_id = ? ORDER BY name',
            (repo_id,)
        )
        modules = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return modules
    
    def get_project_modules(self, project_id: str) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.* FROM modules m
            JOIN repositories r ON m.repo_id = r.id
            WHERE r.project_id = ?
            ORDER BY m.name
        ''', (project_id,))
        modules = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return modules
    
    # Analysis operations
    def create_analysis(self, analysis_data: Dict) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT INTO analyses 
            (id, project_id, repo_id, branch, commit_hash, changed_files, 
             impacted_modules, risk_level, recommendations, analysis_result, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analysis_data['id'], analysis_data['project_id'], analysis_data['repo_id'],
            analysis_data['branch'], analysis_data['commit_hash'],
            json.dumps(analysis_data['changed_files']),
            json.dumps(analysis_data['impacted_modules']),
            analysis_data['risk_level'],
            json.dumps(analysis_data['recommendations']),
            json.dumps(analysis_data.get('analysis_result', {})),
            now
        ))
        
        conn.commit()
        conn.close()
        return analysis_data
    
    def get_recent_analyses(self, project_id: str, limit: int = 10) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM analyses 
            WHERE project_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (project_id, limit))
        
        analyses = []
        for row in cursor.fetchall():
            analysis = dict(row)
            analysis['changed_files'] = json.loads(analysis['changed_files'])
            analysis['impacted_modules'] = json.loads(analysis['impacted_modules'])
            analysis['recommendations'] = json.loads(analysis['recommendations'])
            if analysis['analysis_result']:
                analysis['analysis_result'] = json.loads(analysis['analysis_result'])
            analyses.append(analysis)
        
        conn.close()
        return analyses

db = Database()
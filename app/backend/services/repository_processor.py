import logging
import shutil
import subprocess
from pathlib import Path
import uuid
from typing import List, Dict, Any

from database import db
from services.code_chunker import CodeChunker
from services.vector_db import VectorDBService
from services.graph_rag import GraphRAG
from services.ollama_service import OllamaService
from services.github_service import GitHubService

logger = logging.getLogger(__name__)

class RepositoryProcessor:
    """Process repositories: clone, chunk, embed, build graph"""
    
    def __init__(self):
        self.chunker = CodeChunker()
        self.vector_db = VectorDBService()
        self.graph_rag = GraphRAG()
        self.ollama = OllamaService()
        self.github = GitHubService()
        self.repos_dir = Path("/tmp/code_analyzer_repos")
        self.repos_dir.mkdir(exist_ok=True)
    
    async def process_repository(self, repo_id: str):
        """Main repository processing pipeline"""
        try:
            logger.info(f"Processing repository {repo_id}")
            db.update_repository_status(repo_id, 'analyzing')
            
            # Get repository details
            repos = db.get_repositories(None)  # Get all repos
            repo = next((r for r in repos if r['id'] == repo_id), None)
            
            if not repo:
                raise Exception("Repository not found")
            
            # Step 1: Clone repository
            repo_path = await self.github.clone_repository(
                repo['url'],
                repo['github_token'],
                repo['branch']
            )
            
            # Step 2: Analyze structure and create modules
            modules = await self.analyze_structure(repo_id, repo_path)
            
            # Step 3: Extract and chunk code
            all_chunks = await self.extract_chunks(modules, repo_path)
            
            # Step 4: Generate embeddings and store in vector DB
            await self.generate_embeddings(repo_id, all_chunks)
            
            # Step 5: Build dependency graph
            dependencies = await self.analyze_dependencies(modules, all_chunks)
            
            # Step 6: Build GraphRAG
            self.graph_rag.build_graph(modules, dependencies, all_chunks)
            self.graph_rag.detect_communities()
            
            # Step 7: Setup GitHub webhook
            # webhook_url = await self.github.setup_webhook(repo['url'], repo['github_token'], repo_id)
            # db.update_repository_status(repo_id, 'completed', webhook_id=webhook_url)
            
            db.update_repository_status(repo_id, 'completed')
            logger.info(f"Repository {repo_id} processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing repository {repo_id}: {str(e)}")
            db.update_repository_status(repo_id, 'error')
            raise
    
    async def analyze_structure(self, repo_id: str, repo_path: Path) -> List[Dict]:
        """Analyze repository structure and identify modules"""
        modules = []
        
        # Find all directories with code files
        for item in repo_path.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item.name not in ['node_modules', 'venv', '__pycache__', 'dist', 'build', '.git']:
                module_data = self._analyze_directory(item, repo_path)
                if module_data and module_data['file_count'] > 0:
                    module_data['id'] = str(uuid.uuid4())
                    module_data['repo_id'] = repo_id
                    db.create_module(module_data)
                    modules.append(module_data)
        
        logger.info(f"Found {len(modules)} modules in repository")
        return modules
    
    def _analyze_directory(self, dir_path: Path, repo_root: Path) -> Dict:
        """Analyze a directory to determine if it's a module"""
        code_files = []
        function_count = 0
        class_count = 0
        
        for file_path in dir_path.rglob('*'):
            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs']:
                code_files.append(file_path)
        
        if not code_files:
            return None
        
        return {
            'name': dir_path.name,
            'path': str(dir_path.relative_to(repo_root)),
            'file_count': len(code_files),
            'function_count': function_count,
            'class_count': class_count,
            'files': [str(f.relative_to(repo_root)) for f in code_files]
        }
    
    async def extract_chunks(self, modules: List[Dict], repo_path: Path) -> List[Dict]:
        """Extract code chunks from all modules"""
        all_chunks = []
        
        for module in modules:
            for file_rel_path in module.get('files', []):
                file_path = repo_path / file_rel_path
                
                if not file_path.exists():
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Chunk the file
                    chunks = self.chunker.chunk_file(file_path, content)
                    
                    # Add module_id to each chunk
                    for chunk in chunks:
                        chunk['module_id'] = module['id']
                        all_chunks.append(chunk)
                    
                    # Update module stats
                    func_count = sum(1 for c in chunks if c['type'] == 'function')
                    class_count = sum(1 for c in chunks if c['type'] == 'class')
                    
                except Exception as e:
                    logger.warning(f"Error processing file {file_path}: {e}")
        
        logger.info(f"Extracted {len(all_chunks)} code chunks")
        return all_chunks
    
    async def generate_embeddings(self, repo_id: str, chunks: List[Dict]):
        """Generate and store embeddings for code chunks"""
        documents = []
        metadatas = []
        ids = []
        
        for chunk in chunks:
            # Create rich context for embedding
            context = self._create_chunk_context(chunk)
            
            documents.append(context)
            metadatas.append({
                'chunk_id': chunk['id'],
                'module_id': chunk['module_id'],
                'type': chunk['type'],
                'name': chunk['name'],
                'file_path': chunk['file_path']
            })
            ids.append(chunk['id'])
        
        # Store in vector DB
        self.vector_db.add_documents(repo_id, documents, metadatas, ids)
        logger.info(f"Stored {len(documents)} embeddings")
    
    def _create_chunk_context(self, chunk: Dict) -> str:
        """Create rich context for chunk embedding"""
        context_parts = [
            f"File: {chunk['file_path']}",
            f"Type: {chunk['type']}",
            f"Name: {chunk['name']}",
        ]
        
        if chunk.get('docstring'):
            context_parts.append(f"Documentation: {chunk['docstring']}")
        
        context_parts.append(f"Code:\n{chunk['code']}")
        
        return "\n".join(context_parts)
    
    async def analyze_dependencies(self, modules: List[Dict], chunks: List[Dict]) -> List[Dict]:
        """Analyze dependencies between modules"""
        dependencies = []
        
        # Build import map
        import_map = {}
        for chunk in chunks:
            if chunk['type'] == 'imports' and 'imports' in chunk:
                import_map[chunk['module_id']] = chunk['imports']
        
        # Detect dependencies
        for source_module in modules:
            source_imports = import_map.get(source_module['id'], [])
            
            for target_module in modules:
                if source_module['id'] == target_module['id']:
                    continue
                
                # Check if source imports from target
                target_name = target_module['name']
                for imp in source_imports:
                    if target_name in imp:
                        dep_id = str(uuid.uuid4())
                        dependencies.append({
                            'id': dep_id,
                            'source_module_id': source_module['id'],
                            'target_module_id': target_module['id'],
                            'dependency_type': 'import'
                        })
                        break
        
        logger.info(f"Found {len(dependencies)} dependencies")
        return dependencies
    
    async def update_changed_files(self, repo_id: str, changed_files: List[str]):
        """Re-process only changed files"""
        logger.info(f"Updating {len(changed_files)} changed files")
        
        # Get repository and modules
        repos = db.get_repositories(None)
        repo = next((r for r in repos if r['id'] == repo_id), None)
        
        if not repo:
            return
        
        modules = db.get_modules(repo_id)
        repo_path = self.repos_dir / repo['name']
        
        # Re-chunk and re-embed changed files
        for file_path in changed_files:
            # Find which module this file belongs to
            module = None
            for m in modules:
                if file_path.startswith(m['path']):
                    module = m
                    break
            
            if not module:
                continue
            
            full_path = repo_path / file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    chunks = self.chunker.chunk_file(full_path, content)
                    
                    # Remove old embeddings for this file
                    # Add new embeddings
                    for chunk in chunks:
                        chunk['module_id'] = module['id']
                    
                    await self.generate_embeddings(repo_id, chunks)
                    
                except Exception as e:
                    logger.error(f"Error updating file {file_path}: {e}")
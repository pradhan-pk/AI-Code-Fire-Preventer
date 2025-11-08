import os
from pathlib import Path
from typing import List, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

class CodeAnalyzer:
    def __init__(self):
        self.code_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', 
            '.cpp', '.c', '.rs', '.rb', '.php', '.cs', '.swift'
        }
    
    async def analyze_repository(self, repo_path: Path) -> List[Dict[str, Any]]:
        """Analyze repository structure and identify modules"""
        modules = []
        
        try:
            # Find all potential modules (directories with code files)
            for item in repo_path.iterdir():
                if item.is_dir() and not item.name.startswith('.') and item.name not in ['node_modules', 'venv', '__pycache__', 'dist', 'build']:
                    module_info = await self.analyze_module(item, repo_path)
                    if module_info and module_info['file_count'] > 0:
                        modules.append(module_info)
            
            # Analyze dependencies between modules
            modules = await self.analyze_dependencies(modules, repo_path)
            
            logger.info(f"Found {len(modules)} modules in repository")
            return modules
            
        except Exception as e:
            logger.error(f"Error analyzing repository: {str(e)}")
            return []
    
    async def analyze_module(self, module_path: Path, repo_root: Path) -> Dict[str, Any]:
        """Analyze a single module"""
        try:
            files = []
            for root, _, filenames in os.walk(module_path):
                for filename in filenames:
                    if any(filename.endswith(ext) for ext in self.code_extensions):
                        file_path = Path(root) / filename
                        rel_path = file_path.relative_to(repo_root)
                        files.append(str(rel_path))
            
            if not files:
                return None
            
            return {
                "name": module_path.name,
                "path": str(module_path.relative_to(repo_root)),
                "file_count": len(files),
                "files": files,
                "dependencies": [],
                "dependents": []
            }
            
        except Exception as e:
            logger.error(f"Error analyzing module {module_path}: {str(e)}")
            return None
    
    async def analyze_dependencies(self, modules: List[Dict[str, Any]], repo_root: Path) -> List[Dict[str, Any]]:
        """Analyze dependencies between modules"""
        try:
            # Simple dependency detection based on imports
            for module in modules:
                for file_path in module['files']:
                    full_path = repo_root / file_path
                    if full_path.exists():
                        imports = await self.extract_imports(full_path)
                        
                        # Check if imports reference other modules
                        for imp in imports:
                            for other_module in modules:
                                if other_module['name'] != module['name']:
                                    if other_module['name'] in imp or other_module['path'] in imp:
                                        if other_module['name'] not in module['dependencies']:
                                            module['dependencies'].append(other_module['name'])
            
            # Calculate dependents (reverse dependencies)
            for module in modules:
                for other_module in modules:
                    if module['name'] in other_module['dependencies']:
                        if other_module['name'] not in module['dependents']:
                            module['dependents'].append(other_module['name'])
            
            return modules
            
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {str(e)}")
            return modules
    
    async def extract_imports(self, file_path: Path) -> List[str]:
        """Extract import statements from a code file"""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Python imports
                if file_path.suffix == '.py':
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.startswith('import ') or line.startswith('from '):
                            imports.append(line)
                
                # JavaScript/TypeScript imports
                elif file_path.suffix in ['.js', '.ts', '.tsx', '.jsx']:
                    for line in content.split('\n'):
                        line = line.strip()
                        if 'import ' in line or 'require(' in line:
                            imports.append(line)
                
                # Java imports
                elif file_path.suffix == '.java':
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.startswith('import '):
                            imports.append(line)
        
        except Exception as e:
            logger.debug(f"Error extracting imports from {file_path}: {str(e)}")
        
        return imports
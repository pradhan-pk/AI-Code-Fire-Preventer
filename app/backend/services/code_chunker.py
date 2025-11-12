import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging
import hashlib

logger = logging.getLogger(__name__)

class CodeChunker:
    """Advanced code chunking using AST parsing"""
    
    def __init__(self):
        self.supported_extensions = {
            '.py': self.chunk_python,
            '.js': self.chunk_javascript,
            '.ts': self.chunk_javascript,
            '.java': self.chunk_java,
        }
    
    def chunk_file(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Chunk a file based on its extension"""
        ext = file_path.suffix.lower()
        
        if ext in self.supported_extensions:
            try:
                return self.supported_extensions[ext](file_path, content)
            except Exception as e:
                logger.warning(f"AST parsing failed for {file_path}: {e}. Using fallback.")
                return self.chunk_fallback(file_path, content)
        else:
            return self.chunk_fallback(file_path, content)
    
    def chunk_python(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Extract functions and classes from Python code using AST"""
        chunks = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                chunk = None
                
                if isinstance(node, ast.FunctionDef):
                    chunk = {
                        'type': 'function',
                        'name': node.name,
                        'start_line': node.lineno,
                        'end_line': node.end_lineno or node.lineno,
                        'code': ast.get_source_segment(content, node) or "",
                        'file_path': str(file_path),
                        'docstring': ast.get_docstring(node) or "",
                        'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
                        'args': [arg.arg for arg in node.args.args],
                    }
                
                elif isinstance(node, ast.ClassDef):
                    chunk = {
                        'type': 'class',
                        'name': node.name,
                        'start_line': node.lineno,
                        'end_line': node.end_lineno or node.lineno,
                        'code': ast.get_source_segment(content, node) or "",
                        'file_path': str(file_path),
                        'docstring': ast.get_docstring(node) or "",
                        'bases': [self._get_name(base) for base in node.bases],
                        'methods': [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                    }
                
                if chunk:
                    chunk['id'] = self._generate_chunk_id(chunk)
                    chunks.append(chunk)
            
            # Add file-level imports and constants
            imports_chunk = self._extract_imports_python(tree, content, file_path)
            if imports_chunk:
                chunks.insert(0, imports_chunk)
        
        except Exception as e:
            logger.error(f"Error parsing Python file {file_path}: {e}")
        
        return chunks
    
    def chunk_javascript(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Extract functions and classes from JavaScript/TypeScript"""
        chunks = []
        lines = content.split('\n')
        
        # Simple regex-based extraction for JS/TS
        # In production, use proper JS parser like esprima or tree-sitter
        import re
        
        # Extract functions
        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)'
        for match in re.finditer(func_pattern, content):
            func_name = match.group(1)
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            
            # Find function end (simple brace counting)
            end_line = self._find_block_end(lines, start_line - 1)
            
            chunk = {
                'type': 'function',
                'name': func_name,
                'start_line': start_line,
                'end_line': end_line,
                'code': '\n'.join(lines[start_line-1:end_line]),
                'file_path': str(file_path),
                'id': hashlib.md5(f"{file_path}:{func_name}:{start_line}".encode()).hexdigest()
            }
            chunks.append(chunk)
        
        # Extract classes
        class_pattern = r'(?:export\s+)?class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            end_line = self._find_block_end(lines, start_line - 1)
            
            chunk = {
                'type': 'class',
                'name': class_name,
                'start_line': start_line,
                'end_line': end_line,
                'code': '\n'.join(lines[start_line-1:end_line]),
                'file_path': str(file_path),
                'id': hashlib.md5(f"{file_path}:{class_name}:{start_line}".encode()).hexdigest()
            }
            chunks.append(chunk)
        
        return chunks
    
    def chunk_java(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Extract classes and methods from Java code"""
        # Similar to JavaScript, use regex or proper parser
        return self.chunk_javascript(file_path, content)
    
    def chunk_fallback(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Fallback chunking for unsupported languages"""
        # Split into logical blocks based on blank lines
        chunks = []
        lines = content.split('\n')
        
        current_block = []
        start_line = 1
        
        for i, line in enumerate(lines, 1):
            if line.strip():
                current_block.append(line)
            else:
                if current_block and len(current_block) > 3:  # Minimum block size
                    chunk = {
                        'type': 'block',
                        'name': f"block_{start_line}",
                        'start_line': start_line,
                        'end_line': i - 1,
                        'code': '\n'.join(current_block),
                        'file_path': str(file_path),
                        'id': hashlib.md5(f"{file_path}:block:{start_line}".encode()).hexdigest()
                    }
                    chunks.append(chunk)
                
                current_block = []
                start_line = i + 1
        
        # Add last block
        if current_block and len(current_block) > 3:
            chunk = {
                'type': 'block',
                'name': f"block_{start_line}",
                'start_line': start_line,
                'end_line': len(lines),
                'code': '\n'.join(current_block),
                'file_path': str(file_path),
                'id': hashlib.md5(f"{file_path}:block:{start_line}".encode()).hexdigest()
            }
            chunks.append(chunk)
        
        return chunks
    
    def _extract_imports_python(self, tree: ast.AST, content: str, file_path: Path) -> Dict[str, Any]:
        """Extract import statements from Python code"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_line = ast.get_source_segment(content, node)
                if import_line:
                    imports.append(import_line)
        
        if imports:
            return {
                'type': 'imports',
                'name': 'imports',
                'start_line': 1,
                'end_line': max([n.lineno for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))], default=1),
                'code': '\n'.join(imports),
                'file_path': str(file_path),
                'imports': imports,
                'id': hashlib.md5(f"{file_path}:imports".encode()).hexdigest()
            }
        return None
    
    def _get_name(self, node: ast.AST) -> str:
        """Get name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return str(node)
    
    def _generate_chunk_id(self, chunk: Dict[str, Any]) -> str:
        """Generate unique ID for chunk"""
        key = f"{chunk['file_path']}:{chunk['type']}:{chunk['name']}:{chunk['start_line']}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _find_block_end(self, lines: List[str], start_line: int) -> int:
        """Find end of code block using brace counting"""
        brace_count = 0
        in_block = False
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_block = True
                elif char == '}':
                    brace_count -= 1
                    
                if in_block and brace_count == 0:
                    return i + 1
        
        return len(lines)
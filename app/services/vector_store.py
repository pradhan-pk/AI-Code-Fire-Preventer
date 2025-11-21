import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict
import os
import ast
from app.config import get_settings

settings = get_settings()

class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)
        # Use a default embedding function for now (all-MiniLM-L6-v2 is standard)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="code_chunks",
            embedding_function=self.embedding_fn
        )

    def chunk_file(self, file_path: str, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
        """
        Splits file content into chunks.
        Uses AST for Python files, sliding window for others.
        """
        if file_path.endswith('.py'):
            return self._chunk_python_ast(file_path, content)
        else:
            return self._chunk_sliding_window(file_path, content, chunk_size, overlap)

    def _chunk_python_ast(self, file_path: str, content: str) -> List[Dict]:
        """
        Chunks Python code by functions and classes using AST.
        """
        chunks = []
        try:
            tree = ast.parse(content)
            lines = content.splitlines()
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # Get the source code segment
                    start_line = node.lineno - 1
                    end_line = node.end_lineno
                    chunk_text = "\n".join(lines[start_line:end_line])
                    
                    # Add context (parents) if needed, but for now just the node
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {
                            "file_path": file_path,
                            "start_line": start_line + 1,
                            "end_line": end_line,
                            "type": "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class",
                            "name": node.name
                        }
                    })
            
            # If no functions/classes found, fallback to sliding window or just take whole file if small
            if not chunks:
                return self._chunk_sliding_window(file_path, content)
                
        except Exception as e:
            print(f"AST parse failed for {file_path}: {e}, falling back to sliding window.")
            return self._chunk_sliding_window(file_path, content)
            
        return chunks

    def _chunk_sliding_window(self, file_path: str, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
        """
        Simple sliding window approach.
        """
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_length = 0
        
        for i, line in enumerate(lines):
            current_chunk.append(line)
            current_length += len(line)
            
            if current_length >= chunk_size:
                chunk_text = "\n".join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "file_path": file_path,
                        "start_line": i - len(current_chunk) + 1,
                        "end_line": i,
                        "type": "text_chunk"
                    }
                })
                # Overlap
                overlap_lines = int(overlap / (current_length / len(current_chunk))) if len(current_chunk) > 0 else 0
                current_chunk = current_chunk[-overlap_lines:] if overlap_lines > 0 else []
                current_length = sum(len(l) for l in current_chunk)
        
        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "file_path": file_path,
                    "start_line": len(lines) - len(current_chunk),
                    "end_line": len(lines),
                    "type": "text_chunk"
                }
            })
            
        return chunks

    def get_function_chunk(self, file_path: str, function_name: str) -> str:
        """
        Retrieves the code chunk for a specific function.
        """
        results = self.collection.get(
            where={
                "$and": [
                    {"file_path": file_path},
                    {"name": function_name},
                    {"type": "function"}
                ]
            }
        )
        
        if results and results['documents']:
            return results['documents'][0]
        return ""

    def ingest_files(self, file_paths: List[str]):
        """Reads files, chunks them, and stores in ChromaDB."""
        ids = []
        documents = []
        metadatas = []
        
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                chunks = self.chunk_file(file_path, content)
                
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{file_path}_{i}"
                    ids.append(chunk_id)
                    documents.append(chunk['text'])
                    metadatas.append(chunk['metadata'])
                    
            except Exception as e:
                print(f"Error processing file {file_path}: {e}")
                continue
        
        if ids:
            # Upsert in batches if needed, but Chroma handles reasonable sizes
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

    def query(self, query_text: str, n_results: int = 5):
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )

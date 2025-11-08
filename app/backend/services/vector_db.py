import chromadb
from chromadb.config import Settings
import logging
from typing import List, Dict, Any
import hashlib

logger = logging.getLogger(__name__)

class VectorDBService:
    def __init__(self):
        # Initialize ChromaDB in-memory
        self.client = chromadb.Client(Settings(
            anonymized_telemetry=False,
            allow_reset=True
        ))
        self.collections = {}
        logger.info("ChromaDB initialized in-memory mode")
    
    def get_or_create_collection(self, repo_id: str):
        """Get or create a collection for a repository"""
        if repo_id not in self.collections:
            try:
                # Collection names must be alphanumeric
                collection_name = f"repo_{hashlib.md5(repo_id.encode()).hexdigest()[:16]}"
                self.collections[repo_id] = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"repo_id": repo_id}
                )
                logger.info(f"Created collection for repository {repo_id}")
            except Exception as e:
                logger.error(f"Error creating collection: {str(e)}")
                raise
        
        return self.collections[repo_id]
    
    def add_documents(self, repo_id: str, documents: List[str], metadatas: List[Dict], ids: List[str]):
        """Add documents to the vector database"""
        try:
            collection = self.get_or_create_collection(repo_id)
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Added {len(documents)} documents to collection {repo_id}")
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}")
            raise
    
    def query_similar(self, repo_id: str, query_text: str, n_results: int = 10) -> Dict[str, Any]:
        """Query for similar code snippets"""
        try:
            collection = self.get_or_create_collection(repo_id)
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Error querying collection: {str(e)}")
            return {"ids": [], "documents": [], "metadatas": []}
    
    def delete_collection(self, repo_id: str):
        """Delete a collection"""
        try:
            if repo_id in self.collections:
                collection_name = f"repo_{hashlib.md5(repo_id.encode()).hexdigest()[:16]}"
                self.client.delete_collection(collection_name)
                del self.collections[repo_id]
                logger.info(f"Deleted collection for repository {repo_id}")
        except Exception as e:
            logger.error(f"Error deleting collection: {str(e)}")
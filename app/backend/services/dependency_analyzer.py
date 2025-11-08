import logging
from pathlib import Path
from typing import List, Dict, Any
import hashlib

logger = logging.getLogger(__name__)

class DependencyAnalyzer:
    def __init__(self, vector_db, ollama_service):
        self.vector_db = vector_db
        self.ollama_service = ollama_service
    
    async def process_repository(self, repo_id: str, repo_path: Path, modules: List[Dict[str, Any]]):
        """Process repository and store code embeddings"""
        try:
            documents = []
            metadatas = []
            ids = []
            
            for module in modules:
                for file_path in module.get('files', []):
                    full_path = repo_path / file_path
                    
                    if full_path.exists() and full_path.stat().st_size < 500000:  # Skip very large files
                        try:
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                                if content.strip():
                                    # Create document ID
                                    doc_id = hashlib.md5(file_path.encode()).hexdigest()
                                    
                                    documents.append(content)
                                    metadatas.append({
                                        "file_path": file_path,
                                        "module": module['name'],
                                        "module_path": module['path']
                                    })
                                    ids.append(doc_id)
                        except Exception as e:
                            logger.debug(f"Error reading file {file_path}: {str(e)}")
            
            # Store in vector database
            if documents:
                self.vector_db.add_documents(repo_id, documents, metadatas, ids)
                logger.info(f"Stored {len(documents)} documents in vector DB for repo {repo_id}")
            
        except Exception as e:
            logger.error(f"Error processing repository: {str(e)}")
            raise
    
    async def analyze_impact(self, repo_id: str, changed_files: List[str]) -> List[Dict[str, Any]]:
        """Analyze impact of changed files on other modules"""
        impacted_modules = []
        
        try:
            for changed_file in changed_files:
                # Query vector DB for similar/related code
                results = self.vector_db.query_similar(repo_id, changed_file, n_results=10)
                
                if results.get('metadatas'):
                    for metadata_list in results['metadatas']:
                        for metadata in metadata_list:
                            if metadata['file_path'] != changed_file:
                                # Check if already in impacted list
                                existing = next(
                                    (m for m in impacted_modules if m['module'] == metadata['module']),
                                    None
                                )
                                
                                if not existing:
                                    impacted_modules.append({
                                        "module": metadata['module'],
                                        "module_path": metadata['module_path'],
                                        "affected_files": [metadata['file_path']],
                                        "impact_type": "potential",
                                        "confidence": "medium"
                                    })
                                else:
                                    if metadata['file_path'] not in existing['affected_files']:
                                        existing['affected_files'].append(metadata['file_path'])
            
            logger.info(f"Found {len(impacted_modules)} potentially impacted modules")
            return impacted_modules
            
        except Exception as e:
            logger.error(f"Error analyzing impact: {str(e)}")
            return []
    
    async def generate_recommendations(self, changed_files: List[str], impacted_modules: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on impact analysis"""
        recommendations = []
        
        try:
            if not impacted_modules:
                recommendations.append("No direct module dependencies detected. Changes appear isolated.")
                recommendations.append("Still recommend running full test suite to ensure no indirect impacts.")
            else:
                recommendations.append(f"This change impacts {len(impacted_modules)} module(s). Review carefully before merging.")
                
                for module in impacted_modules:
                    recommendations.append(
                        f"Test module '{module['module']}' thoroughly - {len(module['affected_files'])} file(s) may be affected"
                    )
                
                if len(impacted_modules) > 3:
                    recommendations.append("High number of impacted modules. Consider breaking this change into smaller PRs.")
                
                recommendations.append("Run integration tests across all impacted modules before deployment.")
        
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            recommendations.append("Unable to generate detailed recommendations. Please review changes manually.")
        
        return recommendations
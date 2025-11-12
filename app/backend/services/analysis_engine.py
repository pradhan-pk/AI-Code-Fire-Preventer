import logging
from typing import List, Dict, Any
import uuid
from datetime import datetime, timezone

from database import db
from services.vector_db import VectorDBService
from services.graph_rag import GraphRAG
from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

class AnalysisEngine:
    """Analyze code changes and detect impacts"""
    
    def __init__(self):
        self.vector_db = VectorDBService()
        self.graph_rag = GraphRAG()
        self.ollama = OllamaService()
    
    async def analyze_commit(self, repo_id: str, commit_hash: str, changed_files: List[str], branch: str):
        """Analyze impact of a commit"""
        try:
            logger.info(f"Analyzing commit {commit_hash} in repo {repo_id}")
            
            # Get project_id from repo
            repos = db.get_repositories(None)
            repo = next((r for r in repos if r['id'] == repo_id), None)
            
            if not repo:
                logger.error(f"Repository {repo_id} not found")
                return
            
            project_id = repo['project_id']
            
            # Step 1: Find similar code using vector search
            similar_chunks = await self.find_similar_code(repo_id, changed_files)
            
            # Step 2: Get graph context
            graph_context = self.graph_rag.get_relevant_context(changed_files)
            
            # Step 3: Analyze impact using LLM
            impact_analysis = await self.analyze_with_llm(
                changed_files,
                similar_chunks,
                graph_context
            )
            
            # Step 4: Determine risk level
            risk_level = self.calculate_risk_level(impact_analysis)
            
            # Step 5: Generate recommendations
            recommendations = await self.generate_recommendations(impact_analysis)
            
            # Step 6: Save analysis
            analysis_id = str(uuid.uuid4())
            analysis_data = {
                'id': analysis_id,
                'project_id': project_id,
                'repo_id': repo_id,
                'branch': branch,
                'commit_hash': commit_hash,
                'changed_files': changed_files,
                'impacted_modules': impact_analysis.get('impacted_modules', []),
                'risk_level': risk_level,
                'recommendations': recommendations,
                'analysis_result': impact_analysis
            }
            
            db.create_analysis(analysis_data)
            logger.info(f"Analysis {analysis_id} completed with risk level: {risk_level}")
            
            return analysis_data
            
        except Exception as e:
            logger.error(f"Error analyzing commit: {str(e)}")
            raise
    
    async def find_similar_code(self, repo_id: str, changed_files: List[str]) -> List[Dict]:
        """Find similar code chunks using vector search"""
        all_similar = []
        
        for file_path in changed_files:
            query = f"File: {file_path}"
            results = self.vector_db.query_similar(repo_id, query, n_results=10)
            
            if results.get('metadatas'):
                for metadata_list in results['metadatas']:
                    all_similar.extend(metadata_list)
        
        return all_similar
    
    async def analyze_with_llm(self, changed_files: List[str], similar_chunks: List[Dict], graph_context: Dict) -> Dict:
        """Analyze impact using LLM with vector + graph context"""
        
        # Build comprehensive prompt
        prompt = self._build_analysis_prompt(changed_files, similar_chunks, graph_context)
        
        # Get LLM analysis
        try:
            response = await self.ollama.analyze_code(prompt, "")
            
            # Parse response
            impacted_modules = []
            if isinstance(response, dict) and 'impacted_modules' in response:
                impacted_modules = response['impacted_modules']
            
            return {
                'impacted_modules': impacted_modules,
                'raw_analysis': response
            }
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {'impacted_modules': [], 'raw_analysis': str(e)}
    
    def _build_analysis_prompt(self, changed_files: List[str], similar_chunks: List[Dict], graph_context: Dict) -> str:
        """Build comprehensive analysis prompt"""
        prompt_parts = [
            "You are analyzing code changes to detect potential breaking changes and impacts.",
            "\n## Changed Files:",
            *[f"- {f}" for f in changed_files],
            "\n## Similar Code (from vector search):",
        ]
        
        for chunk in similar_chunks[:5]:  # Limit to top 5
            prompt_parts.append(f"- {chunk.get('type')}: {chunk.get('name')} in {chunk.get('file_path')}")
        
        prompt_parts.extend([
            "\n## Dependency Context (from graph):",
            f"- Direct dependencies: {len(graph_context.get('direct_dependencies', []))}",
            f"- Indirect dependencies: {len(graph_context.get('indirect_dependencies', []))}",
            f"- Dependents: {len(graph_context.get('dependents', []))}",
            f"- Affected communities: {len(graph_context.get('communities', []))}",
            "\n## Task:",
            "Analyze the impact of these changes:",
            "1. Which modules will be affected?",
            "2. What is the severity of impact (low/medium/high/critical)?",
            "3. Are there any breaking changes?",
            "4. What should developers be aware of?",
            "\nProvide your analysis in JSON format with keys: impacted_modules, severity, breaking_changes, notes"
        ])
        
        return "\n".join(prompt_parts)
    
    def calculate_risk_level(self, analysis: Dict) -> str:
        """Calculate overall risk level"""
        impacted_count = len(analysis.get('impacted_modules', []))
        
        if impacted_count == 0:
            return 'low'
        elif impacted_count <= 2:
            return 'medium'
        elif impacted_count <= 5:
            return 'high'
        else:
            return 'critical'
    
    async def generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        impacted_count = len(analysis.get('impacted_modules', []))
        
        if impacted_count == 0:
            recommendations.append("Changes appear isolated with no detected impacts.")
            recommendations.append("Still recommend running full test suite before merging.")
        else:
            recommendations.append(f"This change impacts {impacted_count} module(s).")
            recommendations.append("Review and test all impacted modules before merging.")
            
            if impacted_count > 3:
                recommendations.append("Consider breaking this into smaller, focused changes.")
            
            recommendations.append("Run integration tests across affected modules.")
            recommendations.append("Update documentation if public APIs changed.")
        
        return recommendations
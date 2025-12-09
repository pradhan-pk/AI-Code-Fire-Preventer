from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.config import get_settings
from app.services.multi_repo_manager import MultiRepoManager
from app.services.github_service import GitHubService

from app.services.enhanced_analysis import (
    parse_source_file,
    analyze_changes_for_session,
    LLM_CACHE  # Import cache to clear it
)

import os
import json

app = FastAPI(title="Impact Unplugged")
settings = get_settings()

# Global state
analysis_sessions: Dict[str, Any] = {}

class RepoInfo(BaseModel):
    url: str
    commit_sha: Optional[str] = None

class MultiRepoRequest(BaseModel):
    repos: List[RepoInfo]
    session_id: str

class ImpactRequest(BaseModel):
    session_id: str
    changed_repo_url: str
    commit_sha: str
    github_token: Optional[str] = None

@app.get("/")
def read_root():
    return {"message": "Impact Unplugged API - Multi-Repo Analysis"}

@app.post("/analyze-multi-repo")
async def analyze_multi_repo(request: MultiRepoRequest, background_tasks: BackgroundTasks):
    """Analyze multiple repositories and build unified dependency graph"""
    
    if len(request.repos) > settings.MAX_REPOS:
        raise HTTPException(status_code=400, 
                          detail=f"Maximum {settings.MAX_REPOS} repositories allowed")
    
    session_id = request.session_id
    
    # FIX 1: Clean up existing session data before starting new analysis
    if session_id in analysis_sessions:
        old_session = analysis_sessions[session_id]
        if 'repo_manager' in old_session:
            try:
                old_session['repo_manager'].cleanup()
            except Exception as e:
                print(f"Cleanup warning: {e}")
        
        # Clear cached graph data
        if 'cached_graph' in old_session:
            del old_session['cached_graph']
    
    repo_manager = MultiRepoManager()
    
    try:
        # Clone all repositories
        repo_metadata = []
        for repo_info in request.repos:
            metadata = repo_manager.add_repository(
                repo_info.url,
                repo_info.commit_sha
            )
            repo_metadata.append(metadata)
        
        # Get all files
        all_files = repo_manager.get_all_files()
        total_files = sum(len(files) for files in all_files.values())
        
        # FIX 2: Reset session state completely
        analysis_sessions[session_id] = {
            'repo_manager': repo_manager,
            'metadata': repo_metadata,
            'status': 'analyzing',
            'all_file_analyses': {},  # Initialize empty
            'cached_graph': None,      # Clear cached graph
            'error': None
        }
        
        # Start background analysis
        background_tasks.add_task(
            run_multi_repo_analysis, 
            session_id, 
            repo_manager, 
            all_files
        )
        
        return {
            "session_id": session_id,
            "message": "Multi-repo analysis started",
            "repositories": len(request.repos),
            "total_files": total_files,
            "status": "analyzing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_multi_repo_analysis(session_id: str, repo_manager: MultiRepoManager, 
                                   all_files: Dict[str, List[str]]):
    """Background task to analyze all repositories"""
    try:
        all_file_analyses = {}
        
        # Analyze each repository
        for repo_id, files in all_files.items():
            file_analyses = []
            
            print(f"Analyzing {len(files)} files for {repo_id}")
            
            # Process in batches
            for i in range(0, len(files), settings.BATCH_SIZE):
                batch = files[i:i + settings.BATCH_SIZE]
                
                for file_path in batch:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Parse file
                        analysis = parse_source_file(content, file_path)
                        file_analyses.append(analysis)
                        
                    except Exception as e:
                        print(f"Error analyzing {file_path}: {e}")
                        continue
            
            all_file_analyses[repo_id] = file_analyses
            print(f"Completed analysis for {repo_id}: {len(file_analyses)} files")
        
        # FIX 3: Update session atomically
        if session_id in analysis_sessions:
            analysis_sessions[session_id].update({
                'status': 'completed',
                'all_file_analyses': all_file_analyses,
                'error': None
            })
        
        print(f"✓ Multi-repo analysis completed for session {session_id}")
        
    except Exception as e:
        if session_id in analysis_sessions:
            analysis_sessions[session_id]['status'] = 'failed'
            analysis_sessions[session_id]['error'] = str(e)
        print(f"✗ Analysis failed: {e}")

@app.get("/analysis-status/{session_id}")
def get_analysis_status(session_id: str):
    """Check analysis status"""
    if session_id not in analysis_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = analysis_sessions[session_id]
    return {
        "session_id": session_id,
        "status": session.get('status', 'unknown'),
        "repositories": len(session.get('metadata', [])),
        "error": session.get('error')
    }

@app.get("/dependency-graph/{session_id}")
def get_dependency_graph(session_id: str):
    """Retrieve unified dependency graph"""
    if session_id not in analysis_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = analysis_sessions[session_id]
    
    if session['status'] != 'completed':
        return {"status": session['status'], "message": "Analysis not completed"}
    
    try:
        # FIX 4: Check if cached graph exists and is valid
        if session.get('cached_graph') is not None:
            print("Returning cached graph")
            return session['cached_graph']
        
        # Build graph on-demand
        print("Building dependency graph...")
        from app.services.enhanced_analysis import build_function_graph
        import networkx as nx
        
        all_file_analyses = session.get('all_file_analyses', {})
        
        if not all_file_analyses:
            raise HTTPException(status_code=400, detail="No file analyses available")
        
        combined_graph = nx.DiGraph()
        
        for repo_id, file_analyses in all_file_analyses.items():
            print(f"Building graph for {repo_id}: {len(file_analyses)} files")
            G = build_function_graph(file_analyses, repo_id)
            combined_graph = nx.compose(combined_graph, G)
        
        graph_data = nx.node_link_data(combined_graph)
        
        # Ensure all nodes have 'id' field
        for node in graph_data['nodes']:
            if 'id' not in node:
                node['id'] = node.get('name', 'unknown')
        
        # Cache it
        session['cached_graph'] = graph_data
        print(f"Graph built: {len(graph_data['nodes'])} nodes, {len(graph_data['links'])} edges")
        
        return graph_data
        
    except Exception as e:
        import traceback
        print(f"Graph error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-impact")
async def analyze_impact(request: ImpactRequest):
    """Analyze impact of changes across multiple repositories"""
    
    if request.session_id not in analysis_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = analysis_sessions[request.session_id]
    
    if session['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Analysis not completed")
    
    try:
        print(f"\n{'='*60}")
        print(f"IMPACT ANALYSIS REQUEST")
        print(f"Session: {request.session_id[:8]}")
        print(f"Repo: {request.changed_repo_url}")
        print(f"Commit: {request.commit_sha}")
        print(f"{'='*60}\n")
        
        # FIX 5: Clear LLM cache for this specific analysis to get fresh results
        # (Only clear if this is a new commit)
        cache_key = f"{request.changed_repo_url}:{request.commit_sha}"
        if cache_key not in getattr(session, '_analyzed_commits', set()):
            # Mark as new analysis
            if '_analyzed_commits' not in session:
                session['_analyzed_commits'] = set()
            session['_analyzed_commits'].add(cache_key)
            
            # Optional: Clear LLM cache for truly fresh analysis
            # LLM_CACHE.clear()  # Uncomment if you want no caching between runs
        
        # Get commit diff
        github_service = GitHubService(token=request.github_token)
        diff_data = github_service.get_commit_diff(
            request.changed_repo_url, 
            request.commit_sha
        )
        
        if not diff_data:
            print("WARNING: No diff data returned from GitHub")
            return {
                "session_id": request.session_id,
                "commit_sha": request.commit_sha,
                "changed_files": 0,
                "direct_impacts": 0,
                "indirect_impacts": 0,
                "cascading_impacts": 0,
                "breaking_changes": 0,
                "detailed_impacts": {},
                "risk_analysis": "No changes detected in commit",
                "llm_summary": "",
                "graph": {}
            }
        
        print(f"Diff data: {len(diff_data)} files changed")
        for d in diff_data[:3]:
            print(f"  - {d.get('file_path', 'NO PATH')}")
        
        # Run enhanced analysis
        repo_manager = session['repo_manager']
        all_file_analyses = session.get('all_file_analyses', {})
        
        print(f"Running analysis with {len(all_file_analyses)} repos analyzed")
        
        analysis_result = analyze_changes_for_session(
            diff_data,
            repo_manager,
            all_file_analyses,
            changed_repo_url=request.changed_repo_url
        )
        
        # Extract impacts
        impacts = analysis_result['impacts']
        
        print(f"\n{'='*60}")
        print(f"IMPACT RESULTS")
        print(f"Direct: {len(impacts.get('direct', []))}")
        print(f"Indirect: {len(impacts.get('indirect', []))}")
        print(f"Cascading: {len(impacts.get('cascading', []))}")
        print(f"Breaking: {len(impacts.get('breaking_changes', []))}")
        print(f"{'='*60}\n")
        
        # Format response
        return {
            "session_id": request.session_id,
            "commit_sha": request.commit_sha,
            "changed_files": len(diff_data),
            "direct_impacts": len(impacts.get('direct', [])),
            "indirect_impacts": len(impacts.get('indirect', [])),
            "cascading_impacts": len(impacts.get('cascading', [])),
            "breaking_changes": len(impacts.get('breaking_changes', [])),
            "detailed_impacts": {
                "direct": impacts.get('direct', [])[:20],
                "indirect": impacts.get('indirect', [])[:20],
                "cascading": impacts.get('cascading', [])[:20],
                "breaking_changes": impacts.get('breaking_changes', [])
            },
            "risk_analysis": analysis_result.get('llm_report_pretty', 'No analysis available'),
            "llm_summary": analysis_result.get('llm_report_summary', ''),
            "graph": analysis_result.get('graph', {})
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in analyze_impact:\n{error_details}")
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\n{error_details}")

@app.delete("/session/{session_id}")
def cleanup_session(session_id: str):
    """Clean up analysis session"""
    if session_id in analysis_sessions:
        session = analysis_sessions[session_id]
        if 'repo_manager' in session:
            try:
                session['repo_manager'].cleanup()
            except Exception as e:
                print(f"Cleanup error: {e}")
        del analysis_sessions[session_id]
        
        # FIX 6: Optionally clear LLM cache when session is deleted
        # LLM_CACHE.clear()
        
        return {"message": "Session cleaned up"}
    
    raise HTTPException(status_code=404, detail="Session not found")

# FIX 7: Add endpoint to force cache clear if needed
@app.post("/clear-cache/{session_id}")
def clear_session_cache(session_id: str):
    """Clear cached data for a session"""
    if session_id in analysis_sessions:
        session = analysis_sessions[session_id]
        
        # Clear cached graph
        if 'cached_graph' in session:
            session['cached_graph'] = None
        
        # Clear analyzed commits tracking
        if '_analyzed_commits' in session:
            session['_analyzed_commits'].clear()
        
        # Clear global LLM cache
        LLM_CACHE.clear()
        
        return {"message": "Cache cleared for session"}
    
    raise HTTPException(status_code=404, detail="Session not found")
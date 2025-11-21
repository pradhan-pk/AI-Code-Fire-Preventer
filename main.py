from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any
from app.config import get_settings
from app.services.repo_manager import RepoManager
from app.services.vector_store import VectorStore
from app.services.analyzer import DependencyAnalyzer
import os

app = FastAPI(title="Code Fire Preventer")
settings = get_settings()

# Global state for demo purposes (in production, use a proper DB)
analysis_results: Dict[str, Any] = {}

class AnalyzeRequest(BaseModel):
    repo_url: str

class AnalyzeResponse(BaseModel):
    message: str
    repo_path: str
    files_found: int

@app.get("/")
def read_root():
    return {"message": "Welcome to Code Fire Preventer API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repo(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    repo_manager = RepoManager()
    
    try:
        # 1. Clone Repo
        repo_path = repo_manager.clone_repo(request.repo_url)
        
        # 2. Get Files
        files = repo_manager.get_files(repo_path)
        
        if not files:
            raise HTTPException(status_code=400, detail="No relevant code files found in the repository.")
            
        # 3. Ingest into Vector DB (Background task or sync? Let's do sync for now to ensure it's ready)
        vector_store = VectorStore()
        vector_store.ingest_files(files)
        
        # 4. Analyze Dependencies (This takes time, so we'll do it in background and store result)
        background_tasks.add_task(run_analysis, repo_path, files)
        
        return AnalyzeResponse(
            message="Analysis started. Check /dependencies later.",
            repo_path=repo_path,
            files_found=len(files)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_analysis(repo_path: str, files: List[str]):
    analyzer = DependencyAnalyzer()
    file_analyses = []
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            analysis = analyzer.analyze_file_dependencies(file_path, content)
            file_analyses.append(analysis)
        except Exception as e:
            print(f"Failed to analyze {file_path}: {e}")
            
    graph_data = analyzer.build_dependency_graph(file_analyses)
    
    # Store result keyed by repo path (simplified)
    analysis_results["latest"] = graph_data
    
    # Persist graph
    try:
        graph_path = os.path.join(repo_path, "dependency_graph.json")
        analyzer.save_graph(graph_data, graph_path)
        print(f"Graph saved to {graph_path}")
    except Exception as e:
        print(f"Failed to save graph: {e}")
        
    print("Analysis complete.")

from app.services.github_service import GitHubService

class ImpactRequest(BaseModel):
    repo_url: str
    commit_sha: str
    github_token: str = None

@app.post("/analyze-impact")
async def analyze_impact(request: ImpactRequest):
    repo_manager = RepoManager()
    analyzer = DependencyAnalyzer()
    vector_store = VectorStore()
    github_service = GitHubService(token=request.github_token)
    
    try:
        # 1. Get Diff
        diff_data = github_service.get_commit_diff(request.repo_url, request.commit_sha)
        
        # 2. Get Repo Path (Persistent & Checkout)
        # This ensures we have the file content at the right commit
        repo_path = repo_manager.clone_repo(request.repo_url, request.commit_sha)
        
        # 3. Load Graph
        # Note: The graph might have been built from 'main'. 
        # If the commit is very different, the graph might be stale. 
        # Ideally, we should rebuild the graph for the commit or assume the graph is "close enough".
        # For this MVP, we load the existing graph.
        graph_path = os.path.join(repo_path, "dependency_graph.json")
        graph_data = analyzer.load_graph(graph_path)
        
        if not graph_data:
            # Fallback: Run analysis if graph doesn't exist (might take time)
            # For now, return error or trigger background analysis
            raise HTTPException(status_code=404, detail="Dependency graph not found. Please run /analyze first to build the graph.")
            
        # 4. Analyze Impact
        report = analyzer.analyze_impact(diff_data, graph_data, vector_store, repo_path)
        
        return report
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dependencies")
def get_dependencies(repo_url: str):
    """
    Retrieves the dependency graph for a given repository.
    """
    try:
        # Reconstruct repo path (logic matches RepoManager)
        repo_name = repo_url.split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
            
        project_root = os.getcwd()
        repos_dir = os.path.join(project_root, "repos")
        repo_path = os.path.join(repos_dir, repo_name)
        graph_path = os.path.join(repo_path, "dependency_graph.json")
        
        if not os.path.exists(graph_path):
            return {"status": "error", "message": "Dependency graph not found. Please run /analyze first."}
            
        analyzer = DependencyAnalyzer()
        graph_data = analyzer.load_graph(graph_path)
        return graph_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

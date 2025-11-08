from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import asyncio

# Import custom services
from services.github_service import GitHubService
from services.code_analyzer import CodeAnalyzer
from services.vector_db import VectorDBService
from services.ollama_service import OllamaService
from services.dependency_analyzer import DependencyAnalyzer

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="AI Code Analyzer")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Initialize services
vector_db = VectorDBService()
ollama_service = OllamaService()
github_service = GitHubService()
code_analyzer = CodeAnalyzer()
dependency_analyzer = DependencyAnalyzer(vector_db, ollama_service)

# Define Models
class Repository(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    url: str
    github_token: str
    branch: str = "main"
    status: str = "pending"  # pending, analyzing, completed, error
    modules_count: int = 0
    dependencies_count: int = 0
    last_analyzed: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class RepositoryCreate(BaseModel):
    name: str
    url: str
    github_token: str
    branch: str = "main"

class ModuleInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    name: str
    path: str
    file_count: int
    dependencies: List[str] = []
    dependents: List[str] = []

class AnalysisRequest(BaseModel):
    repo_id: str
    commit_hash: Optional[str] = None
    pr_number: Optional[int] = None
    changed_files: List[str] = []

class ImpactAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    analysis_type: str  # commit or pr
    reference: str  # commit hash or PR number
    changed_files: List[str]
    impacted_modules: List[Dict[str, Any]]
    risk_level: str  # low, medium, high, critical
    recommendations: List[str]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# API Routes
@api_router.get("/")
async def root():
    return {"message": "AI Code Analyzer API", "status": "running"}

@api_router.get("/health")
async def health_check():
    ollama_status = await ollama_service.check_connection()
    return {
        "api": "healthy",
        "ollama": "connected" if ollama_status else "disconnected",
        "vector_db": "active"
    }

# Repository Management
@api_router.post("/repositories", response_model=Repository)
async def create_repository(repo: RepositoryCreate, background_tasks: BackgroundTasks):
    repo_dict = repo.model_dump()
    repo_obj = Repository(**repo_dict)
    
    doc = repo_obj.model_dump()
    await db.repositories.insert_one(doc)
    
    # Start background analysis
    background_tasks.add_task(analyze_repository, repo_obj.id)
    
    return repo_obj

@api_router.get("/repositories", response_model=List[Repository])
async def get_repositories():
    repos = await db.repositories.find({}, {"_id": 0}).to_list(1000)
    return repos

@api_router.get("/repositories/{repo_id}", response_model=Repository)
async def get_repository(repo_id: str):
    repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo

@api_router.delete("/repositories/{repo_id}")
async def delete_repository(repo_id: str):
    result = await db.repositories.delete_one({"id": repo_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Clean up related data
    await db.modules.delete_many({"repo_id": repo_id})
    await db.analyses.delete_many({"repo_id": repo_id})
    vector_db.delete_collection(repo_id)
    
    return {"message": "Repository deleted successfully"}

# Module Information
@api_router.get("/repositories/{repo_id}/modules", response_model=List[ModuleInfo])
async def get_repository_modules(repo_id: str):
    modules = await db.modules.find({"repo_id": repo_id}, {"_id": 0}).to_list(1000)
    return modules

@api_router.get("/repositories/{repo_id}/dependencies")
async def get_dependency_graph(repo_id: str):
    modules = await db.modules.find({"repo_id": repo_id}, {"_id": 0}).to_list(1000)
    
    # Build graph structure for visualization
    nodes = []
    edges = []
    
    for module in modules:
        nodes.append({
            "id": module["id"],
            "label": module["name"],
            "path": module["path"],
            "file_count": module["file_count"]
        })
        
        for dep in module.get("dependencies", []):
            edges.append({
                "source": module["id"],
                "target": dep,
                "type": "dependency"
            })
    
    return {"nodes": nodes, "edges": edges}

# Impact Analysis
@api_router.post("/analyze/impact", response_model=ImpactAnalysis)
async def analyze_impact(request: AnalysisRequest, background_tasks: BackgroundTasks):
    repo = await db.repositories.find_one({"id": request.repo_id}, {"_id": 0})
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    if repo["status"] != "completed":
        raise HTTPException(status_code=400, detail="Repository analysis not completed yet")
    
    # Perform impact analysis
    impacted_modules = await dependency_analyzer.analyze_impact(
        request.repo_id,
        request.changed_files
    )
    
    # Calculate risk level
    risk_level = calculate_risk_level(impacted_modules)
    
    # Generate recommendations
    recommendations = await dependency_analyzer.generate_recommendations(
        request.changed_files,
        impacted_modules
    )
    
    analysis = ImpactAnalysis(
        repo_id=request.repo_id,
        analysis_type="commit" if request.commit_hash else "pr",
        reference=request.commit_hash or str(request.pr_number),
        changed_files=request.changed_files,
        impacted_modules=impacted_modules,
        risk_level=risk_level,
        recommendations=recommendations
    )
    
    # Save analysis
    doc = analysis.model_dump()
    await db.analyses.insert_one(doc)
    
    return analysis

@api_router.get("/repositories/{repo_id}/analyses", response_model=List[ImpactAnalysis])
async def get_analyses(repo_id: str):
    analyses = await db.analyses.find({"repo_id": repo_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return analyses

@api_router.get("/analyses/{analysis_id}", response_model=ImpactAnalysis)
async def get_analysis(analysis_id: str):
    analysis = await db.analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis

# Background Tasks
async def analyze_repository(repo_id: str):
    try:
        # Update status
        await db.repositories.update_one(
            {"id": repo_id},
            {"$set": {"status": "analyzing"}}
        )
        
        # Get repository details
        repo = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
        
        # Clone repository
        repo_path = await github_service.clone_repository(
            repo["url"],
            repo["github_token"],
            repo["branch"]
        )
        
        # Analyze code structure
        modules = await code_analyzer.analyze_repository(repo_path)
        
        # Store modules in database
        for module in modules:
            module["repo_id"] = repo_id
            await db.modules.insert_one(module)
        
        # Generate embeddings and store in vector DB
        await dependency_analyzer.process_repository(
            repo_id,
            repo_path,
            modules
        )
        
        # Update repository status
        await db.repositories.update_one(
            {"id": repo_id},
            {
                "$set": {
                    "status": "completed",
                    "modules_count": len(modules),
                    "last_analyzed": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
    except Exception as e:
        logging.error(f"Error analyzing repository {repo_id}: {str(e)}")
        await db.repositories.update_one(
            {"id": repo_id},
            {"$set": {"status": "error"}}
        )

def calculate_risk_level(impacted_modules: List[Dict[str, Any]]) -> str:
    if not impacted_modules:
        return "low"
    
    total_impact = len(impacted_modules)
    critical_impact = sum(1 for m in impacted_modules if m.get("impact_type") == "breaking")
    
    if critical_impact > 0:
        return "critical"
    elif total_impact > 5:
        return "high"
    elif total_impact > 2:
        return "medium"
    else:
        return "low"

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
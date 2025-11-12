import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time

# Configuration
st.set_page_config(
    page_title="AI Code Impact Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_URL = "http://localhost:8001/api"

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }
    .risk-critical {
        background-color: #fee;
        color: #c00;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-weight: 600;
    }
    .risk-high {
        background-color: #ffeaa7;
        color: #d63031;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-weight: 600;
    }
    .risk-medium {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-weight: 600;
    }
    .risk-low {
        background-color: #d4edda;
        color: #155724;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-weight: 600;
    }
    .status-completed {
        color: #00b894;
        font-weight: 600;
    }
    .status-analyzing {
        color: #0984e3;
        font-weight: 600;
    }
    .status-error {
        color: #d63031;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_project' not in st.session_state:
    st.session_state.current_project = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Dashboard"

# Helper functions
def get_projects():
    try:
        response = requests.get(f"{API_URL}/projects")
        return response.json() if response.status_code == 200 else []
    except:
        return []

def create_project(name, description):
    try:
        response = requests.post(f"{API_URL}/projects", json={"name": name, "description": description})
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Error creating project: {e}")
        return None

def get_repositories(project_id):
    try:
        response = requests.get(f"{API_URL}/projects/{project_id}/repositories")
        return response.json() if response.status_code == 200 else []
    except:
        return []

def add_repository(project_id, name, url, token, branch):
    try:
        response = requests.post(f"{API_URL}/repositories", json={
            "project_id": project_id,
            "name": name,
            "url": url,
            "github_token": token,
            "branch": branch
        })
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Error adding repository: {e}")
        return None

def get_modules(project_id):
    try:
        response = requests.get(f"{API_URL}/projects/{project_id}/modules")
        return response.json() if response.status_code == 200 else []
    except:
        return []

def get_analyses(project_id):
    try:
        response = requests.get(f"{API_URL}/projects/{project_id}/analyses")
        return response.json() if response.status_code == 200 else []
    except:
        return []

# Sidebar - Project Selection
with st.sidebar:
    st.markdown("## 🎯 Projects")
    
    projects = get_projects()
    
    if projects:
        project_names = {p['name']: p['id'] for p in projects}
        selected_project_name = st.selectbox(
            "Select Project",
            options=list(project_names.keys()),
            key="project_selector"
        )
        st.session_state.current_project = next((p for p in projects if p['name'] == selected_project_name), None)
    else:
        st.info("No projects yet. Create one below!")
        st.session_state.current_project = None
    
    st.markdown("---")
    
    # Create new project
    with st.expander("➕ Create New Project"):
        with st.form("new_project_form"):
            project_name = st.text_input("Project Name")
            project_desc = st.text_area("Description")
            
            if st.form_submit_button("Create Project"):
                if project_name:
                    result = create_project(project_name, project_desc)
                    if result:
                        st.success(f"Project '{project_name}' created!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("Project name is required")
    
    st.markdown("---")
    
    # Navigation
    st.markdown("## 📍 Navigation")
    pages = ["Dashboard", "Repositories", "Dependencies", "Analyses"]
    for page in pages:
        if st.button(page, key=f"nav_{page}", use_container_width=True):
            st.session_state.current_page = page

# Main Content
if not st.session_state.current_project:
    st.markdown('<div class="main-header">🔍 AI Code Impact Analyzer</div>', unsafe_allow_html=True)
    st.markdown("""
    ### Welcome to AI Code Impact Analyzer
    
    This tool helps you:
    - 🎯 Detect breaking changes across module dependencies
    - 🔍 Analyze code impacts using AI and Graph RAG
    - 📊 Visualize dependency graphs
    - ⚠️ Get risk assessments for code changes
    
    **Get started by creating a project in the sidebar!**
    """)
else:
    project = st.session_state.current_project
    
    # Dashboard Page
    if st.session_state.current_page == "Dashboard":
        st.markdown(f'<div class="main-header">📊 {project["name"]} - Dashboard</div>', unsafe_allow_html=True)
        
        # Fetch data
        repos = get_repositories(project['id'])
        modules = get_modules(project['id'])
        analyses = get_analyses(project['id'])
        
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Repositories", len(repos))
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Modules", len(modules))
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            completed_repos = sum(1 for r in repos if r['status'] == 'completed')
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Ready", completed_repos)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Analyses", len(analyses))
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Recent Analyses
        st.markdown("### 📋 Recent Analyses")
        
        if analyses:
            for analysis in analyses[:5]:
                with st.expander(f"🔍 {analysis['commit_hash'][:8]} - {analysis['branch']} ({datetime.fromisoformat(analysis['created_at']).strftime('%Y-%m-%d %H:%M')})"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**Changed Files:** {len(analysis['changed_files'])}")
                        for file in analysis['changed_files'][:5]:
                            st.markdown(f"- `{file}`")
                        
                        if analysis['impacted_modules']:
                            st.markdown(f"**Impacted Modules:** {len(analysis['impacted_modules'])}")
                    
                    with col2:
                        risk = analysis['risk_level']
                        st.markdown(f'<span class="risk-{risk}">{risk.upper()}</span>', unsafe_allow_html=True)
                    
                    if analysis['recommendations']:
                        st.markdown("**Recommendations:**")
                        for rec in analysis['recommendations']:
                            st.markdown(f"- {rec}")
        else:
            st.info("No analyses yet. Analyses will appear here automatically when commits are detected.")
        
        st.markdown("---")
        
        # Module Overview
        st.markdown("### 📦 Module Overview")
        
        if modules:
            df = pd.DataFrame(modules)
            st.dataframe(
                df[['name', 'path', 'file_count', 'function_count', 'class_count']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No modules found. Add repositories to get started.")
    
    # Repositories Page
    elif st.session_state.current_page == "Repositories":
        st.markdown(f'<div class="main-header">📚 {project["name"]} - Repositories</div>', unsafe_allow_html=True)
        
        repos = get_repositories(project['id'])
        
        # Add Repository Form
        with st.expander("➕ Add New Repository", expanded=len(repos)==0):
            with st.form("add_repo_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    repo_name = st.text_input("Repository Name", placeholder="my-service")
                    repo_url = st.text_input("GitHub URL", placeholder="https://github.com/user/repo")
                
                with col2:
                    repo_token = st.text_input("GitHub Token", type="password", placeholder="ghp_xxxx")
                    repo_branch = st.text_input("Branch", value="main")
                
                if st.form_submit_button("Add Repository", use_container_width=True):
                    if all([repo_name, repo_url, repo_token, repo_branch]):
                        result = add_repository(project['id'], repo_name, repo_url, repo_token, repo_branch)
                        if result:
                            st.success(f"Repository '{repo_name}' added! Processing started...")
                            time.sleep(2)
                            st.rerun()
                    else:
                        st.error("All fields are required")
        
        st.markdown("---")
        
        # Repository List
        if repos:
            for repo in repos:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.markdown(f"### {repo['name']}")
                        st.markdown(f"`{repo['url']}`")
                        st.markdown(f"Branch: **{repo['branch']}**")
                    
                    with col2:
                        status = repo['status']
                        status_class = f"status-{status}"
                        st.markdown(f'<div class="{status_class}">{status.upper()}</div>', unsafe_allow_html=True)
                    
                    with col3:
                        if repo['last_analyzed_at']:
                            st.markdown(f"Last analyzed:")
                            st.markdown(f"_{datetime.fromisoformat(repo['last_analyzed_at']).strftime('%Y-%m-%d %H:%M')}_")
                    
                    st.markdown("---")
        else:
            st.info("No repositories added yet")
    
    # Dependencies Page
    elif st.session_state.current_page == "Dependencies":
        st.markdown(f'<div class="main-header">🔗 {project["name"]} - Dependencies</div>', unsafe_allow_html=True)
        
        st.markdown("""
        ### Dependency Graph
        
        Visual representation of module dependencies will be shown here once repositories are analyzed.
        """)
        
        modules = get_modules(project['id'])
        
        if modules:
            # Create a simple visualization
            st.markdown("### Module List")
            df = pd.DataFrame(modules)
            st.dataframe(df[['name', 'path', 'file_count']], use_container_width=True, hide_index=True)
        else:
            st.info("No modules to visualize yet")
    
    # Analyses Page
    elif st.session_state.current_page == "Analyses":
        st.markdown(f'<div class="main-header">📊 {project["name"]} - Analysis History</div>', unsafe_allow_html=True)
        
        analyses = get_analyses(project['id'])
        
        if analyses:
            # Risk distribution
            risk_counts = {}
            for analysis in analyses:
                risk = analysis['risk_level']
                risk_counts[risk] = risk_counts.get(risk, 0) + 1
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown("### Risk Distribution")
                fig = px.pie(
                    values=list(risk_counts.values()),
                    names=list(risk_counts.keys()),
                    color=list(risk_counts.keys()),
                    color_discrete_map={
                        'low': '#00b894',
                        'medium': '#fdcb6e',
                        'high': '#e17055',
                        'critical': '#d63031'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("### Analysis Timeline")
                df = pd.DataFrame(analyses)
                df['created_at'] = pd.to_datetime(df['created_at'])
                df = df.sort_values('created_at')
                
                fig = px.scatter(
                    df,
                    x='created_at',
                    y='risk_level',
                    color='risk_level',
                    color_discrete_map={
                        'low': '#00b894',
                        'medium': '#fdcb6e',
                        'high': '#e17055',
                        'critical': '#d63031'
                    },
                    hover_data=['commit_hash', 'branch']
                )
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            # Detailed list
            st.markdown("### All Analyses")
            
            for analysis in analyses:
                with st.expander(f"{datetime.fromisoformat(analysis['created_at']).strftime('%Y-%m-%d %H:%M')} - {analysis['commit_hash'][:8]}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Branch:** {analysis['branch']}")
                        st.markdown(f"**Commit:** `{analysis['commit_hash']}`")
                        st.markdown(f"**Changed Files:** {len(analysis['changed_files'])}")
                        
                        for file in analysis['changed_files']:
                            st.markdown(f"- `{file}`")
                    
                    with col2:
                        risk = analysis['risk_level']
                        st.markdown(f'### <span class="risk-{risk}">{risk.upper()}</span>', unsafe_allow_html=True)
                        
                        if analysis['impacted_modules']:
                            st.markdown(f"**{len(analysis['impacted_modules'])}** modules impacted")
                    
                    if analysis['recommendations']:
                        st.markdown("**Recommendations:**")
                        for i, rec in enumerate(analysis['recommendations'], 1):
                            st.markdown(f"{i}. {rec}")
        else:
            st.info("No analyses yet")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    AI Code Impact Analyzer | Powered by Ollama & GraphRAG
</div>
""", unsafe_allow_html=True)

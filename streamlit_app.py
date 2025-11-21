import streamlit as st
import requests
import json
import networkx as nx
from streamlit_agraph import agraph, Node, Edge, Config

# Constants
API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Impact Unplugged", layout="wide")

st.title("Impact Unplugged ⚡️")
st.markdown("### AI-Driven Code Impact Analysis")

# Tabs
tab1, tab2 = st.tabs(["🔍 Repository Analysis", "💥 Impact Analysis"])

# --- Tab 1: Repository Analysis ---
with tab1:
    st.header("Analyze Repository")
    repo_url = st.text_input("GitHub Repository URL", placeholder="https://github.com/owner/repo")
    
    if st.button("Analyze Repo"):
        if not repo_url:
            st.error("Please enter a repository URL.")
        else:
            with st.spinner("Cloning and Analyzing... This may take a while."):
                try:
                    response = requests.post(f"{API_BASE_URL}/analyze", json={"repo_url": repo_url})
                    if response.status_code == 200:
                        st.success("Analysis Complete!")
                        st.session_state['repo_url'] = repo_url
                    else:
                        st.error(f"Analysis failed: {response.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

    # Display Graph if available
    if 'repo_url' in st.session_state:
        st.subheader("Dependency Graph")
        if st.button("Load Graph"):
            try:
                response = requests.get(f"{API_BASE_URL}/dependencies", params={"repo_url": st.session_state['repo_url']})
                if response.status_code == 200:
                    graph_data = response.json()
                    
                    # Visualize with agraph
                    nodes = []
                    edges = []
                    
                    # Limit nodes for performance if graph is huge
                    # For demo, we show all or top N
                    
                    for node in graph_data['nodes']:
                        node_id = node['id']
                        # Shorten label
                        label = node_id.split('/')[-1]
                        nodes.append(Node(id=node_id, label=label, size=15, shape="dot"))
                        
                    for link in graph_data['links']:
                        edges.append(Edge(source=link['source'], target=link['target'], type="CURVE_SMOOTH"))
                    
                    config = Config(width=800, height=600, directed=True, physics=True, hierarchy=False)
                    
                    return_value = agraph(nodes=nodes, edges=edges, config=config)
                else:
                    st.warning("Could not load graph. Make sure analysis is complete.")
            except Exception as e:
                st.error(f"Error loading graph: {e}")

# --- Tab 2: Impact Analysis ---
with tab2:
    st.header("Analyze Commit Impact")
    
    col1, col2 = st.columns(2)
    with col1:
        impact_repo_url = st.text_input("Repository URL", value=st.session_state.get('repo_url', ''), key="impact_repo")
        commit_sha = st.text_input("Commit SHA", placeholder="e.g., 7b3f1...")
    with col2:
        github_token = st.text_input("GitHub Token (Optional)", type="password")
        
    if st.button("Analyze Impact"):
        if not impact_repo_url or not commit_sha:
            st.error("Please provide Repo URL and Commit SHA.")
        else:
            with st.spinner("Analyzing Impact..."):
                payload = {
                    "repo_url": impact_repo_url,
                    "commit_sha": commit_sha,
                    "github_token": github_token if github_token else None
                }
                try:
                    response = requests.post(f"{API_BASE_URL}/analyze-impact", json=payload)
                    if response.status_code == 200:
                        report = response.json()
                        
                        st.success("Impact Analysis Ready!")
                        
                        # Display Results
                        st.subheader("🎯 Direct Impact")
                        if report['direct_impact']:
                            for item in report['direct_impact']:
                                st.code(item, language="text")
                        else:
                            st.info("No functions directly modified (or none mapped).")
                            
                        st.subheader("🌊 Ripple Effect (Affected Callers)")
                        if report['ripple_effect']:
                            for item in report['ripple_effect']:
                                st.warning(f"⚠️ {item}")
                        else:
                            st.success("No ripple effects detected.")
                            
                        st.subheader("🤖 AI Risk Assessment")
                        st.markdown(report['risk_analysis'])
                        
                    else:
                        st.error(f"Analysis failed: {response.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

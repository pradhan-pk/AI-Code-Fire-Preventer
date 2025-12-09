import streamlit as st
import requests
import json
import networkx as nx
from streamlit_agraph import agraph, Node, Edge, Config
import time
import uuid

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="Impact Unplugged", layout="wide", page_icon="⚡")

# Custom CSS
st.markdown("""
<style>
.impact-card {
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 0.5rem 0;
}
.breaking { background-color: #ff4444; color: white; }
.high { background-color: #ff9800; }
.medium { background-color: #ffc107; }
.low { background-color: #4caf50; color: white; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ Impact Unplugged")
st.markdown("### Multi-Repository Code Impact Analysis")

# Session management
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Sidebar
with st.sidebar:
    st.header("Session Info")
    st.text("Short ID:")
    st.code(st.session_state.session_id[:8])
    
    st.text("Full Session ID:")
    st.code(st.session_state.session_id)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 New", key="new_session_btn", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.analysis_status = None
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear Cache", key="clear_cache_btn", use_container_width=True):
            try:
                response = requests.post(
                    f"{API_BASE}/clear-cache/{st.session_state.session_id}"
                )
                if response.status_code == 200:
                    st.success("Cache cleared!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to clear cache")
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.divider()
    st.markdown("**Status:**")
    if 'analysis_status' in st.session_state:
        status = st.session_state.analysis_status
        if status == 'completed':
            st.success("✅ Ready")
        elif status == 'analyzing':
            st.info("⏳ Analyzing...")
        else:
            st.error(f"❌ {status}")
    else:
        st.info("🆕 No analysis yet")

# Tabs
tab1, tab2, tab3 = st.tabs(["📦 Repository Setup", "💥 Impact Analysis", "📊 Dependency Graph"])

# Tab 1: Multi-Repo Setup
with tab1:
    st.header("Add Repositories")
    
    if 'repos' not in st.session_state:
        st.session_state.repos = []
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        repo_url = st.text_input(
            "Repository URL", 
            placeholder="https://github.com/owner/repo",
            key="repo_url_input"
        )
    
    with col2:
        commit_sha = st.text_input(
            "Commit SHA (optional)", 
            placeholder="7b3f1a...",
            key="commit_sha_input"
        )
    
    if st.button("➕ Add Repository", key="add_repo_btn"):
        if repo_url:
            st.session_state.repos.append({"url": repo_url, "commit_sha": commit_sha or None})
            st.success(f"Added: {repo_url}")
            st.rerun()
    
    # Display added repos
    if st.session_state.repos:
        st.subheader(f"Repositories ({len(st.session_state.repos)})")
        
        for idx, repo in enumerate(st.session_state.repos):
            col1, col2 = st.columns([4, 1])
            with col1:
                commit_display = f"@ {repo['commit_sha'][:7]}" if repo['commit_sha'] else ""
                st.text(f"{repo['url']} {commit_display}")
            with col2:
                if st.button("❌", key=f"remove_{idx}"):
                    st.session_state.repos.pop(idx)
                    st.rerun()
        
        st.divider()
        
        # Add warning if re-analyzing
        if st.session_state.get('analysis_status') == 'completed':
            st.warning("⚠️ Starting new analysis will replace existing data. Consider clearing cache first.")
        
        if st.button("🚀 Start Analysis", type="primary", key="start_analysis_btn"):
            with st.spinner("Analyzing repositories..."):
                payload = {
                    "repos": st.session_state.repos,
                    "session_id": st.session_state.session_id
                }
                
                try:
                    response = requests.post(f"{API_BASE}/analyze-multi-repo", json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✓ Analysis started! Processing {result['total_files']} files")
                        st.session_state.analysis_status = 'analyzing'
                        
                        # Poll for status
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        max_polls = 30  # 60 seconds max
                        for i in range(max_polls):
                            time.sleep(2)
                            
                            try:
                                status_response = requests.get(
                                    f"{API_BASE}/analysis-status/{st.session_state.session_id}"
                                )
                                
                                if status_response.status_code == 200:
                                    status_data = status_response.json()
                                    st.session_state.analysis_status = status_data['status']
                                    
                                    if status_data['status'] == 'completed':
                                        progress_bar.progress(100)
                                        status_text.success("✅ Analysis completed!")
                                        time.sleep(1)
                                        st.rerun()
                                        break
                                    elif status_data['status'] == 'failed':
                                        status_text.error(f"❌ Failed: {status_data.get('error')}")
                                        break
                                    
                                    progress = min(95, int((i + 1) / max_polls * 100))
                                    progress_bar.progress(progress)
                                    status_text.info(f"Processing... {progress}%")
                            except Exception as poll_error:
                                status_text.warning(f"Status check failed: {poll_error}")
                                break
                        
                        if st.session_state.analysis_status == 'analyzing':
                            status_text.warning("⚠️ Analysis taking longer than expected. Check status manually.")
                    else:
                        st.error(f"Error: {response.text}")
                        
                except Exception as e:
                    st.error(f"Connection error: {e}")

# Tab 2: Impact Analysis  
with tab2:
    st.header("Analyze Commit Impact")
    
    if st.session_state.get('analysis_status') != 'completed':
        st.warning("⚠️ Please complete repository analysis first")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            impact_repo = st.selectbox(
                "Select Repository",
                options=[r['url'] for r in st.session_state.repos] if st.session_state.repos else [],
                key="impact_repo_select"
            )
        
        with col2:
            impact_commit = st.text_input(
                "Commit SHA", 
                placeholder="abc123...",
                key="impact_commit_input"
            )
        
        github_token = st.text_input(
            "GitHub Token (optional)", 
            type="password",
            key="github_token_input",
            help="Required for private repositories"
        )
        
        # Add a unique key based on commit to force fresh analysis
        analysis_key = f"{impact_repo}:{impact_commit}"
        
        if st.button("🔍 Analyze Impact", type="primary", key="analyze_impact_btn"):
            if not impact_commit:
                st.error("Please provide a commit SHA")
            else:
                with st.spinner("Analyzing impact..."):
                    payload = {
                        "session_id": st.session_state.session_id,
                        "changed_repo_url": impact_repo,
                        "commit_sha": impact_commit,
                        "github_token": github_token or None
                    }
                    
                    try:
                        response = requests.post(f"{API_BASE}/analyze-impact", json=payload)
                        
                        if response.status_code == 200:
                            report = response.json()
                            
                            # Store in session state with unique key
                            st.session_state[f'report_{analysis_key}'] = report
                            
                            # Debug info
                            with st.expander("🔍 Debug: API Response"):
                                st.json({
                                    "changed_files": report.get('changed_files'),
                                    "direct_impacts": report.get('direct_impacts'),
                                    "indirect_impacts": report.get('indirect_impacts'),
                                    "cascading_impacts": report.get('cascading_impacts'),
                                    "breaking_changes": report.get('breaking_changes')
                                })
                            
                            # Summary metrics
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("Direct Impacts", report.get('direct_impacts', 0))
                            with col2:
                                st.metric("Indirect Impacts", report.get('indirect_impacts', 0))
                            with col3:
                                st.metric("Cascading Impacts", report.get('cascading_impacts', 0))
                            with col4:
                                st.metric("⚠️ Breaking Changes", report.get('breaking_changes', 0))
                            
                            st.divider()
                            
                            # Breaking Changes
                            breaking_list = report.get('detailed_impacts', {}).get('breaking_changes', [])
                            if breaking_list:
                                st.error("### 🚨 Breaking Changes Detected")
                                
                                for change in breaking_list:
                                    if isinstance(change, dict):
                                        location = change.get('location', change.get('node', 'Unknown'))
                                        severity = change.get('severity', 0)
                                        description = change.get('description', change.get('reason', 'No description'))
                                        change_type = change.get('change_type', 'breaking')
                                        
                                        with st.expander(f"🔴 {location}", expanded=True):
                                            st.markdown(f"**Type:** {change_type}")
                                            st.markdown(f"**Severity:** {severity}/5")
                                            st.markdown(f"**Description:**")
                                            st.text(description)
                            
                            # Direct Impacts
                            direct_list = report.get('detailed_impacts', {}).get('direct', [])
                            if direct_list:
                                st.subheader(f"🎯 Direct Impacts ({len(direct_list)})")
                                for impact in direct_list[:10]:
                                    if isinstance(impact, dict):
                                        node = impact.get('affected_node', impact.get('node', 'Unknown'))
                                        severity = impact.get('severity', 0)
                                        reason = impact.get('reason', 'No reason provided')
                                        
                                        severity_class = 'high' if severity >= 4 else 'medium'
                                        st.markdown(f"""
                                        <div class="impact-card {severity_class}">
                                            <strong>{node}</strong><br>
                                            Severity: {severity}/5 | {reason}
                                        </div>
                                        """, unsafe_allow_html=True)
                            
                            # Indirect Impacts
                            indirect_list = report.get('detailed_impacts', {}).get('indirect', [])
                            if indirect_list:
                                with st.expander(f"🔄 Indirect Impacts ({len(indirect_list)})"):
                                    for impact in indirect_list[:15]:
                                        if isinstance(impact, dict):
                                            node = impact.get('affected_node', impact.get('node', 'Unknown'))
                                            severity = impact.get('severity', 0)
                                            reason = impact.get('reason', 'No reason')
                                            st.text(f"• {node} (Severity: {severity}) - {reason}")
                            
                            # Cascading Impacts
                            cascading_list = report.get('detailed_impacts', {}).get('cascading', [])
                            if cascading_list:
                                with st.expander(f"⛓️ Cascading Impacts ({len(cascading_list)})"):
                                    for impact in cascading_list[:15]:
                                        if isinstance(impact, dict):
                                            source = impact.get('source_node', 'Unknown')
                                            target = impact.get('affected_node', impact.get('node', 'Unknown'))
                                            severity = impact.get('severity', 0)
                                            st.text(f"• {source} → {target} (Severity: {severity})")
                            
                            # AI Risk Analysis
                            st.divider()
                            st.subheader("🤖 AI Risk Analysis")
                            risk_text = report.get('risk_analysis', 'No analysis available')
                            
                            try:
                                if isinstance(risk_text, str) and risk_text.startswith('{'):
                                    risk_json = json.loads(risk_text)
                                    
                                    if 'breaking' in risk_json:
                                        st.markdown("**Breaking Changes:**")
                                        for item in risk_json['breaking']:
                                            st.write(f"- {item}")
                                    
                                    if 'actions' in risk_json:
                                        st.markdown("**Recommended Actions:**")
                                        for item in risk_json['actions']:
                                            st.write(f"- {item}")
                                    
                                    if 'tests' in risk_json:
                                        st.markdown("**Suggested Tests:**")
                                        for item in risk_json['tests']:
                                            st.write(f"- {item}")
                                else:
                                    st.markdown(risk_text)
                            except:
                                st.markdown(risk_text)
                            
                            # LLM Summary
                            if 'llm_summary' in report and report['llm_summary']:
                                with st.expander("📋 Detailed Summary"):
                                    st.text(report['llm_summary'])
                            
                        else:
                            st.error(f"Error {response.status_code}: {response.text}")
                            
                    except Exception as e:
                        st.error(f"Connection error: {e}")
                        import traceback
                        with st.expander("Stack Trace"):
                            st.code(traceback.format_exc())

# Tab 3: Dependency Graph
with tab3:
    st.header("Dependency Graph Visualization")
    
    if st.session_state.get('analysis_status') != 'completed':
        st.warning("⚠️ Please complete repository analysis first")
    else:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            graph_filter = st.selectbox(
                "Filter by Repository",
                ["All"] + [r['url'].split('/')[-1] for r in st.session_state.repos],
                key="graph_filter_select"
            )
        
        with col2:
            node_limit = st.number_input(
                "Max Nodes", 
                min_value=50, 
                max_value=500, 
                value=100,
                key="node_limit_input"
            )
        
        if st.button("📊 Load Graph", key="load_graph_btn"):
            with st.spinner("Loading graph..."):
                try:
                    response = requests.get(
                        f"{API_BASE}/dependency-graph/{st.session_state.session_id}"
                    )
                    
                    if response.status_code == 200:
                        graph_data = response.json()
                        
                        # Filter and limit nodes
                        nodes = []
                        edges = []
                        
                        node_count = 0
                        for node in graph_data['nodes']:
                            if node_count >= node_limit:
                                break
                            
                            node_id = node['id']
                            
                            # Apply filter
                            if graph_filter != "All" and graph_filter not in node_id:
                                continue
                            
                            # Color by type
                            color = "#4285f4"
                            if node.get('type') == 'function':
                                color = "#34a853"
                            elif node.get('type') == 'external':
                                color = "#ea4335"
                            
                            label = node_id.split('::')[-1] if '::' in node_id else node_id
                            
                            nodes.append(Node(
                                id=node_id,
                                label=label[:30],
                                size=20,
                                color=color,
                                shape="dot"
                            ))
                            node_count += 1
                        
                        node_ids = {n.id for n in nodes}
                        
                        for link in graph_data['links']:
                            if link['source'] in node_ids and link['target'] in node_ids:
                                edge_color = "#ff6b6b" if link.get('relation') == 'cross_repo_import' else "#999"
                                
                                edges.append(Edge(
                                    source=link['source'],
                                    target=link['target'],
                                    color=edge_color,
                                    type="CURVE_SMOOTH"
                                ))
                        
                        st.info(f"Displaying {len(nodes)} nodes and {len(edges)} edges")
                        
                        config = Config(
                            width=1200,
                            height=700,
                            directed=True,
                            physics=True,
                            hierarchical=False,
                            nodeHighlightBehavior=True,
                            highlightColor="#F7A7A6",
                            collapsible=True
                        )
                        
                        agraph(nodes=nodes, edges=edges, config=config)
                        
                        # Legend
                        st.markdown("""
                        **Legend:**
                        - 🔵 Files | 🟢 Functions | 🔴 External Dependencies
                        - Red edges = Cross-repo dependencies
                        """)
                        
                    else:
                        st.error(f"Error: {response.text}")
                        
                except Exception as e:
                    st.error(f"Connection error: {e}")

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666;">
    Impact Unplugged | Multi-Repository Code Analysis | Powered by Gemini 2.0 Flash
</div>
""", unsafe_allow_html=True)
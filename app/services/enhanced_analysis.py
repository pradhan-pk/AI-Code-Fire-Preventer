# app/services/enhanced_analysis.py
import ast
import json
import os
import re
import requests
import hashlib
from dataclasses import dataclass, asdict
from typing import Dict, List, Any
import networkx as nx
import google.generativeai as genai

from app.config import get_settings
settings = get_settings()

# --- Data models ---
@dataclass
class FileAnalysis:
    file_path: str
    defined_functions: List[str]
    defined_classes: List[str]
    imports: List[str]
    calls: List[Dict[str, str]]
    orm_fields: List[str]
    source: str

@dataclass
class BreakingChange:
    change_type: str
    location: str
    severity: int
    description: str

@dataclass
class CascadeImpact:
    source_node: str
    affected_node: str
    severity: int
    reason: str

def find_changed_nodes(diff_data, G, changed_repo_url=None):
    """
    Map changed files from diff_data to nodes in the graph.
    Now repo-aware to avoid matching files from wrong repositories.
    IMPROVED: Better path matching and more flexible matching strategies.
    """
    print(f"\n=== FIND_CHANGED_NODES DEBUG ===")
    print(f"Diff data entries: {len(diff_data)}")
    print(f"Graph nodes: {len(G.nodes())}")
    print(f"Changed repo URL: {changed_repo_url}")
    
    nodes = []
    
    # Extract repo name from URL if provided
    repo_name = None
    if changed_repo_url:
        # Extract repo name from URL like "https://github.com/owner/repo"
        repo_name = changed_repo_url.rstrip('/').split('/')[-1]
        print(f"Extracted repo name: {repo_name}")
    
    # Show some graph nodes for debugging
    sample_nodes = list(G.nodes())[:5]
    print(f"\nSample graph nodes:")
    for node in sample_nodes:
        data = G.nodes[node]
        print(f"  - {node}")
        print(f"    type: {data.get('type')}, repo_id: {data.get('repo_id', 'N/A')}")
    
    for change in diff_data:
        f = change.get('file_path') or change.get('filename')  # Try both keys
        if not f:
            print(f"\nWarning: Change with no file_path: {change}")
            continue
        
        # Normalize the changed file path
        f_norm = os.path.normpath(f).replace('\\', '/')
        f_basename = os.path.basename(f)
        
        # Remove leading slashes or ./ prefixes
        f_norm = f_norm.lstrip('./')
        
        print(f"\nLooking for changed file: {f_norm} (basename: {f_basename})")
        
        matches_found = 0
        for node, data in G.nodes(data=True):
            node_type = data.get('type')
            node_repo_id = data.get('repo_id', '')
            
            # IMPORTANT: Filter by repository first
            if repo_name and node_repo_id:
                # Check if this node is from the correct repository
                # repo_id format is like "finflow-auth-service_main"
                if repo_name not in node_repo_id:
                    continue  # Skip nodes from other repos
            
            # Get the node's file path
            node_path = data.get('file', data.get('path', ''))
            if not node_path:
                continue
                
            node_path_norm = os.path.normpath(node_path).replace('\\', '/')
            node_basename = os.path.basename(node_path_norm)
            
            # Check if this node is in the changed file - MULTIPLE STRATEGIES
            if node_type in ('function', 'class', 'file'):
                # Strategy 1: Exact basename match
                if f_basename == node_basename:
                    nodes.append(node)
                    matches_found += 1
                    print(f"  ✓ MATCH (basename): {node} (type: {node_type}, repo: {node_repo_id})")
                    continue
                
                # Strategy 2: Changed path ends with node path (or vice versa)
                if f_norm.endswith(node_path_norm) or node_path_norm.endswith(f_norm):
                    nodes.append(node)
                    matches_found += 1
                    print(f"  ✓ MATCH (suffix): {node} (type: {node_type}, repo: {node_repo_id})")
                    continue
                
                # Strategy 3: Path contains the other (for nested structures)
                if f_norm in node_path_norm or node_path_norm in f_norm:
                    nodes.append(node)
                    matches_found += 1
                    print(f"  ✓ MATCH (contains): {node} (type: {node_type}, repo: {node_repo_id})")
                    continue
        
        if matches_found == 0:
            print(f"  ✗ NO MATCHES FOUND for {f_norm}")
            # Show potential matches from the correct repo
            print(f"    Checking for files with similar names in {repo_name}...")
            potential_matches = []
            for node, data in G.nodes(data=True):
                node_repo_id = data.get('repo_id', '')
                node_path = data.get('file', data.get('path', ''))
                
                if repo_name and repo_name in node_repo_id and node_path:
                    node_basename = os.path.basename(node_path)
                    # Show files with similar names
                    if f_basename.lower() in node_basename.lower() or node_basename.lower() in f_basename.lower():
                        potential_matches.append((node_path, node_repo_id))
            
            if potential_matches:
                print(f"    Found {len(potential_matches)} potential matches:")
                for path, repo in potential_matches[:3]:
                    print(f"      - {path} (repo: {repo})")
    
    unique_nodes = list(set(nodes))
    print(f"\nTotal changed nodes found: {len(unique_nodes)}")
    
    # Show breakdown by repo
    repos = {}
    for node in unique_nodes:
        repo_id = G.nodes[node].get('repo_id', 'unknown')
        repos[repo_id] = repos.get(repo_id, 0) + 1
    
    print(f"Changed nodes by repository:")
    for repo_id, count in repos.items():
        print(f"  {repo_id}: {count} nodes")
    
    print(f"===================================\n")
    
    return unique_nodes

def format_llm_report_human(readable_llm_output):
    if not readable_llm_output:
        return "No LLM analysis available."
    
    if isinstance(readable_llm_output, dict):
        try:
            return json.dumps(readable_llm_output, indent=2)
        except Exception:
            return str(readable_llm_output)
    return str(readable_llm_output)

def format_llm_report_bullets(llm_json):
    lines = []
    if not isinstance(llm_json, dict):
        return str(llm_json)
    
    for section in ("breaking", "actions", "tests"):
        items = llm_json.get(section, [])
        if not items:
            continue
        lines.append(f"\n=== {section.upper()} ===")
        for i, item in enumerate(items, 1):
            if isinstance(item, dict):
                desc = item.get("description") or item.get("reason") or str(item)
                lines.append(f"{i}. {desc}")
            else:
                lines.append(f"{i}. {item}")
    return "\n".join(lines)

def summarize_cascade_and_breaking(impacts, breaking_list):
    lines = []

    # Breaking changes summary
    if breaking_list:
        lines.append("BREAKING CHANGES:")
        for b in breaking_list:
            lines.append(f"- {b.change_type} at {b.location}: {b.description}")

    # Cascading impacts summary
    for cat in ("direct", "indirect", "cascading"):
        items = impacts.get(cat, [])
        if items:
            lines.append(f"\n{cat.upper()} IMPACTS:")
            for it in items:
                lines.append(f"- {it['source_node']} → {it['affected_node']} (sev {it['severity']}): {it['reason']}")

    return "\n".join(lines)

# --- LLM Fallbacks ---
class RateLimitError(Exception): pass

# Simple in-memory cache for repeated prompts
LLM_CACHE = {}

def hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode('utf-8')).hexdigest()

def get_ai_response_safe(prompt: str) -> str:
    """
    Uses cache + fallback-first approach: Mistral → Llama → Google
    """
    h = hash_prompt(prompt)
    if h in LLM_CACHE:
        return LLM_CACHE[h]

    for fn in [call_mistral, call_openrouter_llama_scout, call_google_api]:
        try:
            resp = fn(prompt)
            LLM_CACHE[h] = resp
            return resp
        except RateLimitError:
            continue
        except Exception:
            continue
    return f"LLM unavailable for prompt (cached fallback)."

def call_google_api(prompt):
    import google.generativeai as genai
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
    try:
        resp = model.generate_content(
            prompt, 
            generation_config=genai.GenerationConfig(temperature=0.0, max_output_tokens=800)
        )
        return getattr(resp, 'text', str(resp))
    except Exception as e:
        # Gemini client exception object may contain response details
        msg = str(e)
        if hasattr(e, "response"):
            msg = str(getattr(e, "response", e))
        # Also check for quota error in JSON response detail
        if "429" in msg or "quota exceeded" in msg.lower():
            raise RateLimitError()
        raise

def call_openrouter_llama_scout(prompt: str):
    """
    Calls Llama-4 Scout (OpenRouter name: meta-llama/Llama-3.1-405B-Scout)
    using OpenRouter.ai unified API.
    """
    api_key = os.getenv("OPENROUTER_API_KEY") or settings.OPENROUTER_API_KEY
    if not api_key:
        raise Exception("Missing OPENROUTER_API_KEY")

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost",      # optional but recommended
        "X-Title": "AI-Code-Fire-Preventer"      # optional
    }

    body = {
        "model": "meta-llama/Llama-3.1-405B-Scout",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.0
    }

    try:
        response = requests.post(url, json=body, headers=headers)
        if response.status_code == 429:
            raise RateLimitError()

        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        if "429" in str(e):
            raise RateLimitError()
        raise

def call_mistral(prompt):
    from mistralai import Mistral
    import os
    api_key = os.getenv("MISTRAL_API_KEY") or settings.MISTRAL_API_KEY
    client = Mistral(api_key=api_key)
    try:
        resp = client.chat.complete(
            model="mistral-medium-latest",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    except Exception as e:
        if "rate limit" in str(e).lower():
            raise RateLimitError()
        raise
    return f"Mistral AI fallback response for prompt (truncated): {prompt[:500]}"

def get_ai_response(prompt):
    try:
        return call_google_api(prompt)
    except RateLimitError:
        try:
            print('Google API rate limit exceeded, falling back to OpenRouter Llama Scout...')
            return call_openrouter_llama_scout(prompt)
        except Exception:
            print('OpenRouter Llama Scout failed, falling back to Mistral AI...')
            return call_mistral(prompt)


# --- AST parser ---
class ASTFileParser(ast.NodeVisitor):
    def __init__(self, source: str):
        self.source = source
        self.defined_functions: List[str] = []
        self.defined_classes: List[str] = []
        self.imports: List[str] = []
        self.calls: List[Dict[str,str]] = []
        self.orm_fields: List[str] = []
        try:
            self.tree = ast.parse(source)
        except Exception:
            self.tree = None

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        name = node.name
        self.defined_functions.append(name)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                nm = self._get_call_name(child)
                if nm: self.calls.append({'caller': name, 'callee': nm})
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        clsname = node.name
        self.defined_classes.append(clsname)
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_name = f"{clsname}.{item.name}"
                self.defined_functions.append(method_name)
                for child in ast.walk(item):
                    if isinstance(child, ast.Call):
                        nm = self._get_call_name(child)
                        if nm: self.calls.append({'caller': method_name, 'callee': nm})
            elif isinstance(item, ast.Assign):
                if len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                    target = item.targets[0].id
                    if isinstance(item.value, ast.Call):
                        fn = getattr(item.value.func, 'id', None) or getattr(item.value.func, 'attr', None)
                        if fn and fn.lower() in ('column','field'):
                            self.orm_fields.append(target)
        self.generic_visit(node)

    def visit_Assign(self, node):
        if len(node.targets)==1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            if isinstance(node.value, ast.Call):
                fn = getattr(node.value.func, 'id', None) or getattr(node.value.func, 'attr', None)
                if fn and fn.lower() in ('column','field'):
                    self.orm_fields.append(target)
        self.generic_visit(node)

    def _get_call_name(self, call_node: ast.Call) -> str:
        try:
            func = call_node.func
            if isinstance(func, ast.Name): return func.id
            elif isinstance(func, ast.Attribute):
                parts=[]
                node=func
                while isinstance(node, ast.Attribute):
                    parts.append(node.attr)
                    node=node.value
                if isinstance(node, ast.Name):
                    parts.append(node.id)
                return '.'.join(reversed(parts))
        except Exception:
            return ""
        return ""

    def analyze(self) -> FileAnalysis:
        return FileAnalysis(
            file_path="<unknown>",
            defined_functions=self.defined_functions,
            defined_classes=self.defined_classes,
            imports=list(set(self.imports)),
            calls=self.calls,
            orm_fields=self.orm_fields,
            source=self.source
        )

def parse_source_file(content: str, file_path: str) -> FileAnalysis:
    p = ASTFileParser(content)
    if p.tree is not None:
        p.visit(p.tree)
    fa = p.analyze()
    fa.file_path = file_path
    return fa

# --- Graph builder ---
def build_function_graph(file_analyses: List[FileAnalysis], repo_id: str) -> nx.DiGraph:
    """Build dependency graph from file analyses with IMPROVED call resolution"""
    print(f"\n=== BUILD_FUNCTION_GRAPH DEBUG ===")
    print(f"Repo ID: {repo_id}")
    print(f"Files to analyze: {len(file_analyses)}")
    
    G = nx.DiGraph()
    
    # Track statistics
    nodes_added = 0
    edges_added = 0
    calls_processed = 0
    calls_resolved = 0
    
    # Phase 1: Add all nodes
    for fa in file_analyses:
        file_node = f"{repo_id}::file::{fa.file_path}"
        G.add_node(file_node, id=file_node, type='file', repo_id=repo_id, path=fa.file_path)
        nodes_added += 1
        
        for fn in fa.defined_functions:
            fn_node = f"{repo_id}::fn::{fa.file_path}::{fn}"
            G.add_node(fn_node, id=fn_node, type='function', name=fn, repo_id=repo_id, file=fa.file_path)
            G.add_edge(file_node, fn_node, relation='defines')
            nodes_added += 1
            edges_added += 1
            
        for cls in fa.defined_classes:
            cls_node = f"{repo_id}::class::{fa.file_path}::{cls}"
            G.add_node(cls_node, id=cls_node, type='class', name=cls, repo_id=repo_id, file=fa.file_path)
            G.add_edge(file_node, cls_node, relation='defines')
            nodes_added += 1
            edges_added += 1
            
        for imp in fa.imports:
            ext = f"external::{imp}"
            if not G.has_node(ext):
                G.add_node(ext, id=ext, type='external', name=imp)
                nodes_added += 1
            G.add_edge(file_node, ext, relation='imports')
            edges_added += 1

    # Phase 2: Build comprehensive symbol map
    symbol_by_name = {}
    symbol_by_simple_name = {}  # Just the function name without class
    
    for node, data in G.nodes(data=True):
        if data.get('type') == 'function':
            full_name = data['name']
            # Store by full name
            symbol_by_name[full_name] = node
            
            # Store by simple name (method name only)
            simple_name = full_name.split('.')[-1]
            if simple_name not in symbol_by_simple_name:
                symbol_by_simple_name[simple_name] = []
            symbol_by_simple_name[simple_name].append(node)
            
        elif data.get('type') == 'class':
            # Also index classes
            symbol_by_name[data['name']] = node

    print(f"Symbol table - full names: {len(symbol_by_name)}")
    print(f"Symbol table - simple names: {len(symbol_by_simple_name)}")
    print(f"Sample symbols: {list(symbol_by_name.keys())[:5]}")

    # Phase 3: Add call edges with better resolution
    for fa in file_analyses:
        for call in fa.calls:
            calls_processed += 1
            
            caller_name = call['caller']
            callee_name = call['callee']
            
            # Build full caller node ID
            caller_node = f"{repo_id}::fn::{fa.file_path}::{caller_name}"
            
            # Skip if caller doesn't exist (shouldn't happen)
            if not G.has_node(caller_node):
                continue
            
            # Skip empty callee
            if not callee_name:
                continue

            callee_node = None
            
            # Strategy 1: Exact match on full name
            if callee_name in symbol_by_name:
                callee_node = symbol_by_name[callee_name]
            
            # Strategy 2: Match on simple name (last component)
            elif '.' in callee_name:
                simple = callee_name.split('.')[-1]
                if simple in symbol_by_simple_name:
                    # Prefer matches from the same file
                    candidates = symbol_by_simple_name[simple]
                    same_file = [c for c in candidates if fa.file_path in c]
                    callee_node = same_file[0] if same_file else candidates[0]
            else:
                # No dot - try simple name lookup
                if callee_name in symbol_by_simple_name:
                    candidates = symbol_by_simple_name[callee_name]
                    same_file = [c for c in candidates if fa.file_path in c]
                    callee_node = same_file[0] if same_file else candidates[0]

            if callee_node:
                # Add call edge
                G.add_edge(caller_node, callee_node, relation='calls')
                edges_added += 1
                calls_resolved += 1
            else:
                # Fallback: external node (library call, etc.)
                ext_node = f"external::{callee_name}"
                if not G.has_node(ext_node):
                    G.add_node(ext_node, id=ext_node, type='external', name=callee_name)
                    nodes_added += 1
                G.add_edge(caller_node, ext_node, relation='calls')
                edges_added += 1

    print(f"\nGraph building complete:")
    print(f"  Nodes added: {nodes_added}")
    print(f"  Edges added: {edges_added}")
    print(f"  Calls processed: {calls_processed}")
    print(f"  Calls resolved: {calls_resolved} ({calls_resolved*100//max(1,calls_processed)}%)")
    
    # Show sample call edges
    call_edges = [(s, t, d) for s, t, d in G.edges(data=True) if d.get('relation') == 'calls']
    print(f"  Total call edges: {len(call_edges)}")
    if call_edges:
        print(f"  Sample call edges:")
        for s, t, d in call_edges[:3]:
            print(f"    {s.split('::')[-1]} -> {t.split('::')[-1]}")
    
    print(f"===================================\n")

    return G

def add_cross_repo_call_edges(combined_graph):
    """
    Add edges between functions across different repositories based on:
    1. HTTP API calls (e.g., requests.post to another service)
    2. Shared function names (common patterns like get_db, verify_password)
    3. Import statements that reference other services
    """
    print(f"\n=== ADDING CROSS-REPO EDGES ===")
    
    # Get all external nodes (potential API calls)
    external_nodes = [
        (node, data) 
        for node, data in combined_graph.nodes(data=True) 
        if data.get('type') == 'external'
    ]
    
    print(f"External nodes to analyze: {len(external_nodes)}")
    
    # Track repos and their functions
    repo_functions = {}  # repo_id -> list of function names
    for node, data in combined_graph.nodes(data=True):
        if data.get('type') == 'function':
            repo_id = data.get('repo_id', '')
            if repo_id:
                if repo_id not in repo_functions:
                    repo_functions[repo_id] = []
                repo_functions[repo_id].append((node, data.get('name', '')))
    
    print(f"Repositories with functions: {list(repo_functions.keys())}")
    
    cross_edges_added = 0
    
    # Strategy 1: Match external calls to functions in other repos
    for ext_node, ext_data in external_nodes:
        ext_name = ext_data.get('name', '')
        
        # Get all nodes that call this external
        callers = list(combined_graph.predecessors(ext_node))
        
        for caller in callers:
            caller_data = combined_graph.nodes[caller]
            caller_repo = caller_data.get('repo_id', '')
            
            # Look for matching function in OTHER repos
            for target_repo_id, functions in repo_functions.items():
                if target_repo_id == caller_repo:
                    continue  # Skip same repo
                
                for fn_node, fn_name in functions:
                    # Match if:
                    # 1. External name matches function name
                    # 2. External name contains function name
                    # 3. Function name is in external path (e.g., "auth.verify_password")
                    
                    fn_simple = fn_name.split('.')[-1]
                    ext_simple = ext_name.split('.')[-1]
                    
                    if (fn_simple == ext_simple or 
                        fn_simple in ext_name or 
                        ext_simple in fn_name):
                        
                        # Add cross-repo call edge
                        combined_graph.add_edge(
                            caller, 
                            fn_node, 
                            relation='cross_repo_call'
                        )
                        cross_edges_added += 1
                        
                        if cross_edges_added <= 5:
                            print(f"  ✓ Cross-repo: {caller.split('::')[-1]} -> {fn_node.split('::')[-1]}")
    
    print(f"Cross-repo edges added: {cross_edges_added}")
    print(f"================================\n")
    
    return cross_edges_added

# --- Cross-repo call edges ---
def add_cross_repo_edges(combined_graph, all_file_analyses):
    """
    Add edges between functions in different repos if they call each other.
    """
    symbol_by_name = {}
    for repo_id, fas in all_file_analyses.items():
        for fa in fas:
            for fn in fa.defined_functions:
                node = f"{repo_id}::fn::{fa.file_path}::{fn}"
                symbol_by_name[fn] = node

    # For each function call, add cross-repo edges if symbol exists in another repo
    for repo_id, fas in all_file_analyses.items():
        for fa in fas:
            for call in fa.calls:
                caller = f"{repo_id}::fn::{fa.file_path}::{call['caller']}"
                callee_name = call['callee']
                callee_node = symbol_by_name.get(callee_name)
                if callee_node and caller != callee_node:
                    combined_graph.add_edge(caller, callee_node, relation='cross_repo_call')


# --- Breaking changes ---
FIELD_REMOVE_RE = re.compile(r"^-.*?(\b\w+\b)\s*=\s*(?:Column|Field)\b", re.IGNORECASE)
FIELD_ADD_RE = re.compile(r"^\+.*?(\b\w+\b)\s*=\s*(?:Column|Field)\b", re.IGNORECASE)

# Replace the detect_field_level_changes function in enhanced_analysis.py

import re
from typing import List, Dict

# Replace detect_field_level_changes in enhanced_analysis.py
# This is the simpler version that uses LLM for everything

def detect_field_level_changes(diff_data: List[Dict[str, str]]) -> List[BreakingChange]:
    """
    Simple LLM-powered breaking change detection.
    Analyzes each diff using AI to find breaking changes.
    
    Note: This version calls LLM for every changed file.
    For cost optimization, use detect_breaking_changes_smart() instead.
    """
    print(f"\n=== LLM BREAKING CHANGE DETECTION ===")
    results = []
    
    if not diff_data:
        return results
    
    for change in diff_data:
        file_path = change.get('file_path', change.get('filename', ''))
        patch = change.get('patch', '')
        status = change.get('status', '')
        
        if not patch:
            continue
        
        print(f"\nAnalyzing: {file_path}")
        
        # Skip very large patches (over 2000 chars) to avoid token limits
        if len(patch) > 2000:
            patch = patch[:2000] + "\n... (truncated)"
        
        # Build the LLM prompt
        prompt = f"""You are a senior software engineer analyzing code changes for breaking changes.

FILE: {file_path}
STATUS: {status}

DIFF:
```diff
{patch}
```

Analyze this diff and identify ALL potential breaking changes. For EACH breaking change, provide:

1. **Type**: field_removed, field_renamed, type_changed, api_changed, contract_broken, etc.
2. **Severity**: 1-5 (1=minor, 5=critical/data loss)
3. **Description**: What broke, why it's breaking, and what will fail
4. **Evidence**: The specific lines that show the breaking change

Look for:
- Database field removals or renames (Column changes)
- Required fields added without defaults
- Type changes (String → Boolean, etc.)
- API endpoint changes
- Function signature changes
- Model/schema changes that affect serialization
- Removed functions/classes that other code might depend on

IMPORTANT: 
- Be thorough - catch subtle breaking changes like default value changes
- If a field is removed and a similar field is added, flag it as a rename
- Consider downstream impact (databases, APIs, other services)

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
  "breaking_changes": [
    {{
      "type": "field_renamed",
      "severity": 4,
      "field_old": "kyc_status",
      "field_new": "kyc_verified",
      "description": "Field 'kyc_status' was removed and 'kyc_verified' was added. This breaks database queries, serialization, and API contracts.",
      "impact": ["Database queries filtering by kyc_status", "API responses expecting kyc_status", "ORM operations"],
      "evidence": "- kyc_status = Column(String, default='pending')\\n+ kyc_verified = Column(Boolean, default=False)"
    }}
  ]
}}

If NO breaking changes found, return: {{"breaking_changes": []}}
"""
        
        try:
            # Use the quota-safe LLM call
            response = get_ai_response_safe(prompt)
            
            # Parse JSON response
            response = response.strip()
            
            # Extract JSON from response (handle cases where LLM adds markdown)
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0]
            elif '```' in response:
                response = response.split('```')[1].split('```')[0]
            
            # Remove any leading/trailing whitespace
            response = response.strip()
            
            # Parse JSON
            analysis = json.loads(response)
            
            breaking_list = analysis.get('breaking_changes', [])
            
            print(f"  ✓ LLM found {len(breaking_list)} breaking changes")
            
            # Convert to BreakingChange objects
            for bc in breaking_list:
                change_type = bc.get('type', 'unknown')
                severity = bc.get('severity', 3)
                description = bc.get('description', '')
                
                # Enhanced description with impact details
                impact = bc.get('impact', [])
                if impact:
                    description += f"\n\nIMPACT:\n" + "\n".join(f"  • {item}" for item in impact)
                
                evidence = bc.get('evidence', '')
                if evidence:
                    description += f"\n\nEVIDENCE:\n{evidence}"
                
                # Add field details if available
                old_field = bc.get('field_old', '')
                new_field = bc.get('field_new', '')
                if old_field:
                    description = f"[{old_field} → {new_field or 'removed'}]\n" + description
                
                results.append(BreakingChange(
                    change_type=change_type,
                    location=file_path,
                    severity=severity,
                    description=description
                ))
                
                print(f"    [{severity}/5] {change_type}: {description[:80]}...")
        
        except json.JSONDecodeError as e:
            print(f"  ✗ Failed to parse LLM response: {e}")
            print(f"    Response preview: {response[:200]}...")
        
        except Exception as e:
            print(f"  ✗ LLM analysis failed: {e}")
    
    print(f"\nTotal breaking changes detected: {len(results)}")
    print(f"===================================\n")
    
    return results


def _similar_strings(s1: str, s2: str, threshold: float = 0.6) -> bool:
    """
    Simple string similarity check (Levenshtein-like).
    Returns True if strings are similar enough to be considered a rename.
    """
    s1, s2 = s1.lower(), s2.lower()
    
    # Exact substring match
    if s1 in s2 or s2 in s1:
        return True
    
    # Common prefix/suffix
    if len(s1) > 3 and len(s2) > 3:
        if s1[:4] == s2[:4] or s1[-4:] == s2[-4:]:
            return True
    
    # Simple Levenshtein distance
    if len(s1) == 0 or len(s2) == 0:
        return False
    
    distance = _levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    similarity = 1 - (distance / max_len)
    
    return similarity >= threshold


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def _extract_column_type(definition: str) -> str:
    """Extract the type from a Column definition."""
    # Match patterns like: String, Integer, Boolean, String(50), etc.
    type_match = re.search(r'(String|Integer|Boolean|Float|DateTime|Date|Text|JSON|ARRAY)(?:\(.*?\))?', definition)
    if type_match:
        return type_match.group(0)
    return definition.split(',')[0].strip()  # Fallback to first part

# --- OpenAPI drift ---
def _deep_diff(a,b,path="") -> List[str]:
    diffs=[]
    if isinstance(a, dict) and isinstance(b, dict):
        for key in set(list(a.keys())+list(b.keys())):
            pa, pb = a.get(key), b.get(key)
            subpath=f"{path}/{key}"
            if key not in a: diffs.append(f"Added: {subpath}")
            elif key not in b: diffs.append(f"Removed: {subpath}")
            else: diffs += _deep_diff(pa,pb,subpath)
    elif isinstance(a,list) and isinstance(b,list):
        if a!=b: diffs.append(f"List changed at {path}")
    else:
        if a!=b: diffs.append(f"Value changed at {path}: {a} → {b}")
    return diffs

def detect_openapi_drift(repo_base: str) -> List[BreakingChange]:
    results=[]
    current = os.path.join(repo_base,'openapi.json')
    prev = os.path.join(repo_base,'openapi_prev.json')
    if os.path.exists(current) and os.path.exists(prev):
        try:
            with open(current) as fc, open(prev) as fp:
                a=json.load(fp); b=json.load(fc)
            diffs=_deep_diff(a,b)
            for d in diffs:
                results.append(BreakingChange('openapi_drift', current, 4, d))
        except Exception: pass
    return results

# --- Map changed files to graph nodes ---
import os

# --- Cascading impacts ---
def find_all_impacts_and_score(G, changed_nodes, breaking_list, openapi_drifts):
    """
    COMPLETELY REWRITTEN impact finder that actually works for microservices.
    
    Key insight: In microservices, most impacts are WITHIN the same file or service,
    not across services. We need to detect:
    1. What functions call the changed functions (intra-file)
    2. What external services might call these via APIs
    3. Shared resources (like DB models) that could affect other services
    """
    print(f"\n=== FIND_ALL_IMPACTS_AND_SCORE (FIXED VERSION) ===")
    print(f"Changed nodes: {len(changed_nodes)}")
    print(f"Breaking changes: {len(breaking_list)}")
    print(f"OpenAPI drifts: {len(openapi_drifts)}")
    print(f"Total graph nodes: {G.number_of_nodes()}")
    print(f"Total graph edges: {G.number_of_edges()}")
    
    impacts = {"direct": [], "indirect": [], "cascading": [], "breaking_changes": []}

    # Severity boost map
    boost = {}
    for b in breaking_list + openapi_drifts:
        boost[b.location] = boost.get(b.location, 0) + b.severity

    if G.number_of_edges() == 0:
        print("WARNING: Graph has no edges!")
        return {k: [asdict(x) for x in v] for k, v in impacts.items()}
    
    # === ANALYZE GRAPH STRUCTURE ===
    print(f"\n=== ANALYZING EDGE TYPES ===")
    edge_types = {}
    calls_edges = []
    
    for src, tgt, data in G.edges(data=True):
        rel = data.get('relation', 'unknown')
        edge_types[rel] = edge_types.get(rel, 0) + 1
        
        if rel == 'calls':
            calls_edges.append((src, tgt))
    
    print(f"Edge breakdown:")
    for rel, count in sorted(edge_types.items(), key=lambda x: -x[1]):
        print(f"  {rel}: {count}")
    
    print(f"\nTotal 'calls' edges: {len(calls_edges)}")
    if calls_edges:
        print("Sample call relationships:")
        for src, tgt in calls_edges[:5]:
            print(f"  {src.split('::')[-1]} calls {tgt.split('::')[-1]}")
    
    # === BUILD REVERSE CALL MAP ===
    print(f"\n=== BUILDING CALLER MAP ===")
    
    # Map: function -> list of functions that call it
    callers_of = {}
    
    for src, tgt, data in G.edges(data=True):
        if data.get('relation') == 'calls':
            if tgt not in callers_of:
                callers_of[tgt] = []
            callers_of[tgt].append(src)
    
    print(f"Functions that are called by others: {len(callers_of)}")
    
    # === FIND IMPACTS FOR EACH CHANGED NODE ===
    print(f"\n=== ANALYZING CHANGED NODES ===")
    
    changed_functions = [n for n in changed_nodes if '::fn::' in n]
    changed_classes = [n for n in changed_nodes if '::class::' in n]
    changed_files = [n for n in changed_nodes if '::file::' in n]
    
    print(f"Changed functions: {len(changed_functions)}")
    print(f"Changed classes: {len(changed_classes)}")
    print(f"Changed files: {len(changed_files)}")
    
    # Strategy 1: Direct function calls
    direct_impacts_found = 0
    for func_node in changed_functions:
        func_name = func_node.split('::')[-1]
        
        if func_node in callers_of:
            callers = callers_of[func_node]
            print(f"\n✓ {func_name} is called by {len(callers)} functions:")
            
            for caller in callers:
                caller_name = caller.split('::')[-1]
                print(f"    - {caller_name}")
                
                impacts['direct'].append(CascadeImpact(
                    source_node=func_node,
                    affected_node=caller,
                    severity=4,
                    reason=f"directly calls {func_name}"
                ))
                direct_impacts_found += 1
                
                # Find who calls the caller (indirect)
                if caller in callers_of:
                    for indirect_caller in callers_of[caller]:
                        impacts['indirect'].append(CascadeImpact(
                            source_node=func_node,
                            affected_node=indirect_caller,
                            severity=3,
                            reason=f"calls {caller_name}, which uses {func_name}"
                        ))
        else:
            print(f"\n✗ {func_name} is not called by any tracked function")
    
    # Strategy 2: Class usage (models, schemas)
    for class_node in changed_classes:
        class_name = class_node.split('::')[-1]
        
        # Find functions that reference this class
        class_refs = []
        for node, data in G.nodes(data=True):
            if data.get('type') == 'function':
                # Check if any calls reference this class
                for pred in G.predecessors(node):
                    if class_node == pred:
                        class_refs.append(node)
        
        if class_refs:
            print(f"\n✓ {class_name} is used by {len(class_refs)} functions")
            for ref in class_refs:
                impacts['direct'].append(CascadeImpact(
                    source_node=class_node,
                    affected_node=ref,
                    severity=3,
                    reason=f"uses model {class_name}"
                ))
                direct_impacts_found += 1
    
    # Strategy 3: If still no impacts, analyze file-level dependencies
    if direct_impacts_found == 0 and changed_files:
        print(f"\n⚠️  No direct function calls found.")
        print(f"   Analyzing file-level dependencies...")
        
        for file_node in changed_files:
            file_path = G.nodes[file_node].get('path', '')
            file_name = os.path.basename(file_path)
            
            # Find all nodes defined in this file
            file_contents = [
                n for n in G.successors(file_node)
                if G[file_node][n].get('relation') == 'defines'
            ]
            
            print(f"\n  File {file_name} defines {len(file_contents)} items")
            
            # These are all potentially impacted
            for item in file_contents[:10]:  # Limit to prevent spam
                item_name = item.split('::')[-1]
                item_type = G.nodes[item].get('type', 'unknown')
                
                impacts['direct'].append(CascadeImpact(
                    source_node=file_node,
                    affected_node=item,
                    severity=2,
                    reason=f"{item_type} modified in {file_name}"
                ))
    
    # Strategy 4: Cross-repo potential impacts based on common patterns
    print(f"\n=== CHECKING CROSS-SERVICE PATTERNS ===")
    
    # Functions like get_db, verify_password are often called from other services
    high_risk_patterns = [
        'get_db', 'verify', 'authenticate', 'authorize',
        'create_user', 'get_user', 'update_user',
        'create_transaction', 'get_balance'
    ]
    
    for func_node in changed_functions:
        func_name = func_node.split('::')[-1].lower()
        
        for pattern in high_risk_patterns:
            if pattern in func_name:
                # This is a high-risk function that might be called externally
                print(f"  ⚠️  High-risk pattern: {func_name}")
                
                # Look for similar functions in other repos (potential callers)
                repo_id = G.nodes[func_node].get('repo_id', '')
                
                for other_node, other_data in G.nodes(data=True):
                    other_repo = other_data.get('repo_id', '')
                    
                    # Different repo, same type
                    if other_repo and other_repo != repo_id and other_data.get('type') == 'function':
                        impacts['cascading'].append(CascadeImpact(
                            source_node=func_node,
                            affected_node=other_node,
                            severity=2,
                            reason=f"potential cross-service dependency (pattern: {pattern})"
                        ))
                
                break  # Only add once per function
    
    # Add breaking changes
    for b in breaking_list + openapi_drifts:
        impacts["breaking_changes"].append(b)
    
    # === FINAL REPORT ===
    print(f"\n=== FINAL IMPACT SUMMARY ===")
    print(f"  Direct impacts: {len(impacts['direct'])}")
    print(f"  Indirect impacts: {len(impacts['indirect'])}")
    print(f"  Cascading impacts: {len(impacts['cascading'])}")
    print(f"  Breaking changes: {len(impacts['breaking_changes'])}")
    
    if impacts['direct']:
        print(f"\n  Top 3 direct impacts:")
        for impact in impacts['direct'][:3]:
            print(f"    - {impact.affected_node.split('::')[-1]} ({impact.reason})")
    
    print(f"===================================\n")

    return {k: [asdict(x) for x in v] for k, v in impacts.items()}

# --- LLM analysis ---
LLM_PROMPT_TEMPLATE = """
You are given:
- A concise list of changed files and diff summaries:
{diff_summary}
- A short list of breaking items:
{breaking_summary}
- A short list of cascading impacts (source → target):
{cascade_summary}
Produce:
1) Prioritized breaking changes
2) Recommended remediation
3) Suggested high-priority end-to-end tests
Return only JSON: {{ "breaking": [...], "actions": [...], "tests": [...] }}
"""

def generate_llm_analysis(diff_data, breaking_changes, cascade_impacts):
    diff_summary = "\n".join(
        [f"{d['file_path']}: " + " | ".join(d.get('patch','').splitlines()[:3]) for d in diff_data]
    )[:2000]  # truncate

    breaking_summary = "\n".join(
        [f"{b.change_type}@{b.location}: {b.description}" for b in breaking_changes]
    )[:1000]

    casc = []
    for k in ('direct','indirect','cascading'):
        for it in cascade_impacts.get(k, []):
            casc.append(f"{it['source_node']}->{it['affected_node']} (sev {it['severity']})")
    cascade_summary = "\n".join(casc)[:1000]

    prompt = LLM_PROMPT_TEMPLATE.format(
        diff_summary=diff_summary or "none",
        breaking_summary=breaking_summary or "none",
        cascade_summary=cascade_summary or "none"
    )

    # **Use quota-safe LLM call instead of direct Google call**
    try:
        text = get_ai_response_safe(prompt)
        start = text.find('{'); end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        return {"raw": text}
    except Exception as e:
        return {"error": str(e)}


# --- Top-level orchestrator ---
def analyze_changes_for_session(diff_data, repo_manager, all_file_analyses, changed_repo_url=None):
    """
    Analyze changes and produce impacts with FORCED LLM analysis.
    """
    print(f"\n=== ANALYZE_CHANGES_FOR_SESSION ===")
    print(f"Diff entries: {len(diff_data)}")
    print(f"File analyses repos: {list(all_file_analyses.keys())}")
    print(f"Changed repo: {changed_repo_url}")
    
    # --- Build combined graph ---
    combined_graph = nx.DiGraph()
    for repo_id, fas in all_file_analyses.items():
        print(f"Building graph for {repo_id} with {len(fas)} files")
        G = build_function_graph(fas, repo_id)
        combined_graph = nx.compose(combined_graph, G)

    print(f"Combined graph: {combined_graph.number_of_nodes()} nodes, {combined_graph.number_of_edges()} edges")
    add_cross_repo_call_edges(combined_graph)
    print(f"After cross-repo: {combined_graph.number_of_nodes()} nodes, {combined_graph.number_of_edges()} edges")

    # --- Detect breaking changes ---
    breaking_list = detect_field_level_changes(diff_data)
    openapi_drifts = []
    for md in repo_manager.repos.values():
        openapi_drifts += detect_openapi_drift(md.repo_path)

    print(f"Breaking changes: {len(breaking_list)}")
    print(f"OpenAPI drifts: {len(openapi_drifts)}")

    # --- Map changed files to graph nodes (WITH REPO FILTERING) ---
    changed_nodes = find_changed_nodes(diff_data, combined_graph, changed_repo_url)
    print(f"Changed nodes mapped: {len(changed_nodes)}")

    # --- Map breaking changes to graph nodes ---
    for b in breaking_list + openapi_drifts:
        b_loc_norm = os.path.normpath(b.location)
        if b_loc_norm in combined_graph:
            b.location = b_loc_norm
        else:
            for node, data in combined_graph.nodes(data=True):
                node_path = os.path.normpath(data.get('file', data.get('path', '')))
                if b_loc_norm in node_path:
                    b.location = node
                    break

    # --- Compute cascading/indirect/direct impacts ---
    impacts = find_all_impacts_and_score(combined_graph, changed_nodes, breaking_list, openapi_drifts)

    # --- Calculate total items ---
    total_items = (
        len(changed_nodes) +  # ← ADD THIS: count changed nodes even if no impacts yet
        len(breaking_list) + 
        len(openapi_drifts) + 
        sum(len(impacts.get(k, [])) for k in ('direct','indirect','cascading'))
    )

    print(f"Total items for LLM: {total_items}")

    # --- LLM analysis (ALWAYS RUN if we have diff data) ---
    llm_report_raw = None
    llm_report_pretty = "No analysis available."
    llm_report_bullets = ""
    llm_report_summary = "No summary available."

    # Run LLM if we have ANY changes (even if no impacts detected yet)
    if len(diff_data) > 0:  # Changed condition
        print("Running LLM analysis...")
        try:
            llm_report_raw = generate_llm_analysis(diff_data, breaking_list + openapi_drifts, impacts)
            llm_report_pretty = format_llm_report_human(llm_report_raw)
            llm_report_bullets = format_llm_report_bullets(llm_report_raw)
            llm_report_summary = summarize_cascade_and_breaking(impacts, breaking_list + openapi_drifts)
            print("LLM analysis completed")
        except Exception as e:
            print(f"LLM analysis failed: {e}")
            llm_report_pretty = f"LLM analysis failed: {str(e)}"

    # --- Graph JSON for UI ---
    graph_json = nx.node_link_data(combined_graph)
    for n in graph_json['nodes']:
        if 'id' not in n:
            n['id'] = n.get('name') or 'unknown'

    print(f"===================================\n")

    return {
        "changed_nodes": changed_nodes,
        "impacts": impacts,
        "breaking_changes": [asdict(b) for b in breaking_list + openapi_drifts],
        "llm_report_raw": llm_report_raw,
        "llm_report_pretty": llm_report_pretty,
        "llm_report_bullets": llm_report_bullets,
        "llm_report_summary": llm_report_summary,
        "graph": graph_json
    }
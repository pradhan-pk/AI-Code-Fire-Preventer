import google.generativeai as genai
import json
import networkx as nx
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from app.config import get_settings
import os

settings = get_settings()

# --- Pydantic Models for Structured Output ---
class FunctionCall(BaseModel):
    caller: str = Field(..., description="Name of the function making the call")
    callee: str = Field(..., description="Name of the function or module being called")

class FileAnalysis(BaseModel):
    file_path: str
    defined_functions: List[str] = Field(default_factory=list, description="List of functions defined in this file")
    defined_classes: List[str] = Field(default_factory=list, description="List of classes defined in this file")
    imports: List[str] = Field(default_factory=list, description="List of modules or files imported")
    calls: List[FunctionCall] = Field(default_factory=list, description="List of function calls made within this file")

class DependencyAnalyzer:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def analyze_file_dependencies(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Uses GenAI to extract dependencies from a single file using structured output.
        """
        prompt = f"""
        Analyze the following code file and extract its dependencies.
        File Path: {file_path}
        
        Code Content:
        ```
        {content[:15000]} 
        ```
        
        Extract:
        1. Defined functions and classes.
        2. Imports (modules or other files).
        3. Function calls (who calls whom).
        """
        
        try:
            # Use generation_config for JSON schema enforcement (if supported by lib version)
            # Or just rely on the model's ability to follow the Pydantic schema in prompt
            # For robustness with 2.5-flash, we can use response_schema if available, 
            # but let's stick to a strong prompt + Pydantic validation for now to be safe across versions.
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=FileAnalysis
                )
            )
            
            # Parse JSON
            analysis_data = json.loads(response.text)
            # Ensure file_path is set correctly (model might hallucinate it)
            analysis_data['file_path'] = file_path
            
            # Validate with Pydantic
            analysis = FileAnalysis(**analysis_data)
            return analysis.model_dump()
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return FileAnalysis(file_path=file_path).model_dump()

    def resolve_imports(self, file_analyses: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Creates a mapping of 'module_name' -> 'file_path' to help link imports.
        This is a heuristic approach.
        """
        module_map = {}
        for analysis in file_analyses:
            path = analysis['file_path']
            # Heuristic: filename without extension is often the module name
            basename = os.path.basename(path)
            module_name = os.path.splitext(basename)[0]
            module_map[module_name] = path
            
            # Also map the full path relative to repo root if possible (complex logic omitted for brevity)
        return module_map

    def build_dependency_graph(self, file_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Constructs a graph from the analysis results with symbol resolution.
        """
        G = nx.DiGraph()
        module_map = self.resolve_imports(file_analyses)
        
        for analysis in file_analyses:
            file_node = analysis['file_path']
            G.add_node(file_node, type='file')
            
            # Add functions
            for func in analysis.get('defined_functions', []):
                func_node = f"{file_node}::{func}"
                G.add_node(func_node, type='function')
                G.add_edge(file_node, func_node, relation='defines')
            
            # Add imports (File -> File dependencies)
            for imp in analysis.get('imports', []):
                # Try to resolve import to a file
                # 1. Direct match (e.g., "utils" -> "utils.py")
                resolved_path = module_map.get(imp)
                if not resolved_path:
                    # 2. Try splitting (e.g., "app.services.utils" -> "utils")
                    parts = imp.split('.')
                    if parts[-1] in module_map:
                        resolved_path = module_map[parts[-1]]
                
                if resolved_path:
                    G.add_edge(file_node, resolved_path, relation='imports')
                else:
                    # External dependency or unresolved
                    G.add_node(imp, type='external_module')
                    G.add_edge(file_node, imp, relation='imports')

            # Add calls (Function -> Function/Module)
            for call in analysis.get('calls', []):
                caller_name = call.get('caller')
                callee_name = call.get('callee')
                
                caller_node = f"{file_node}::{caller_name}"
                
                # Try to resolve callee
                # If callee is "other_func", check if it's in this file
                if callee_name in analysis.get('defined_functions', []):
                    callee_node = f"{file_node}::{callee_name}"
                    G.add_edge(caller_node, callee_node, relation='calls')
                else:
                    # Check if it's "module.func"
                    if '.' in callee_name:
                        mod, func = callee_name.split('.', 1)
                        if mod in module_map:
                            target_file = module_map[mod]
                            # We assume the function exists there (optimistic linking)
                            callee_node = f"{target_file}::{func}"
                            G.add_edge(caller_node, callee_node, relation='calls')
                        else:
                            # External call
                            G.add_edge(caller_node, callee_name, relation='calls')
                    else:
                        # Unresolved local or global
                        G.add_edge(caller_node, callee_name, relation='calls')

        return nx.node_link_data(G)

    def save_graph(self, graph_data: Dict[str, Any], output_path: str):
        """Saves the graph to a JSON file."""
        with open(output_path, 'w') as f:
            json.dump(graph_data, f, indent=2)

    def load_graph(self, input_path: str) -> Dict[str, Any]:
        """Loads the graph from a JSON file."""
        if not os.path.exists(input_path):
            return None
        with open(input_path, 'r') as f:
            return json.load(f)

    def analyze_impact(self, diff_data: List[Dict[str, Any]], graph_data: Dict[str, Any], vector_store, repo_path: str) -> Dict[str, Any]:
        """
        Analyzes the impact of changes based on the diff and dependency graph.
        """
        G = nx.node_link_graph(graph_data)
        affected_nodes = set()
        impact_report = {
            "direct_impact": [],
            "ripple_effect": [],
            "risk_analysis": ""
        }
        
        # 1. Map Diff to Graph Nodes
        for change in diff_data:
            # Construct full path to match what's in VectorStore/Graph
            # diff_data has relative path (e.g. "app/main.py")
            # repo_path is absolute (e.g. "/Users/.../repos/repo_name")
            # We need to join them.
            relative_path = change['file_path']
            full_path = os.path.join(repo_path, relative_path)
            
            # Find nodes in G that match this file
            # G nodes are absolute paths
            file_nodes = [n for n in G.nodes if str(n).startswith(full_path)]
            
            for node in file_nodes:
                if G.nodes[node].get('type') == 'function':
                    affected_nodes.add(node)
                    impact_report["direct_impact"].append(node)

        # 2. Find Ripple Effect
        ripple_nodes = set()
        for node in affected_nodes:
            predecessors = G.predecessors(node)
            for pred in predecessors:
                edge_data = G.get_edge_data(pred, node)
                if edge_data.get('relation') == 'calls':
                    ripple_nodes.add(pred)
                    impact_report["ripple_effect"].append(pred)

        # 3. LLM Risk Analysis
        # Fetch code for affected and ripple nodes
        context = "Changed Files Content:\n"
        
        # Add full content of changed files to context
        for change in diff_data:
            try:
                full_path = os.path.join(repo_path, change['file_path'])
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    context += f"File: {change['file_path']}\n```\n{content}\n```\n---\n"
            except Exception as e:
                print(f"Could not read file {change['file_path']}: {e}")

        context += "\nAffected Functions (Directly Changed):\n"
        for node in list(affected_nodes):
            if "::" in node:
                fname = node.split("::")[1]
                fpath = node.split("::")[0]
                code = vector_store.get_function_chunk(fpath, fname)
                context += f"Function {fname} in {fpath}:\n{code}\n---\n"
                
        context += "\nAffected Callers (Ripple Effect):\n"
        for node in list(ripple_nodes)[:5]: # Limit to 5 to avoid context overflow
            if "::" in node:
                fname = node.split("::")[1]
                fpath = node.split("::")[0]
                code = vector_store.get_function_chunk(fpath, fname)
                context += f"Function {fname} in {fpath}:\n{code}\n---\n"

        print(f"\nContext Length: {len(context)}")
        
        prompt = f"""
        Analyze the impact of the following code changes.
        
        {context}
        
        Predict:
        1. Potential risks (bugs, logic errors).
        2. Functional impact (what features might break).
        3. Suggested test cases.
        
        Return a concise markdown report.
        """
        
        try:
            # Use lower temperature for more deterministic results
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2
                )
            )
            impact_report["risk_analysis"] = response.text
        except Exception as e:
            impact_report["risk_analysis"] = f"Failed to generate analysis: {e}"
            
        return impact_report


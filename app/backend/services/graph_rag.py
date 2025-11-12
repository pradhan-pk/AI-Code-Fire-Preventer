import networkx as nx
import logging
from typing import List, Dict, Any, Set
import json
from collections import defaultdict

logger = logging.getLogger(__name__)

class GraphRAG:
    """GraphRAG implementation for code dependency analysis"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.communities = {}
        self.community_summaries = {}
    
    def build_graph(self, modules: List[Dict], dependencies: List[Dict], code_chunks: List[Dict]):
        """Build dependency graph from modules and dependencies"""
        self.graph.clear()
        
        # Add module nodes
        for module in modules:
            self.graph.add_node(
                module['id'],
                type='module',
                name=module['name'],
                path=module['path'],
                data=module
            )
        
        # Add code chunk nodes
        for chunk in code_chunks:
            self.graph.add_node(
                chunk['id'],
                type='chunk',
                chunk_type=chunk['type'],
                name=chunk['name'],
                file_path=chunk['file_path'],
                code=chunk['code'][:500]  # Store limited code for context
            )
            
            # Link chunk to its module
            module_id = chunk.get('module_id')
            if module_id:
                self.graph.add_edge(module_id, chunk['id'], relationship='contains')
        
        # Add dependency edges
        for dep in dependencies:
            self.graph.add_edge(
                dep['source_module_id'],
                dep['target_module_id'],
                relationship='depends_on',
                dep_type=dep['dependency_type']
            )
        
        logger.info(f"Graph built: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
    
    def detect_communities(self, resolution: float = 1.0):
        """Detect communities using Louvain algorithm"""
        try:
            # Convert to undirected for community detection
            undirected = self.graph.to_undirected()
            
            # Use Louvain for community detection
            communities = nx.community.louvain_communities(undirected, resolution=resolution)
            
            # Store communities
            self.communities = {}
            for i, community in enumerate(communities):
                self.communities[i] = list(community)
                logger.info(f"Community {i}: {len(community)} nodes")
            
            return self.communities
        except Exception as e:
            logger.error(f"Community detection failed: {e}")
            return {}
    
    def generate_community_summaries(self, ollama_service) -> Dict[int, str]:
        """Generate summaries for each community using LLM"""
        summaries = {}
        
        for comm_id, nodes in self.communities.items():
            # Get node details
            node_info = []
            for node_id in nodes:
                node_data = self.graph.nodes[node_id]
                node_info.append({
                    'id': node_id,
                    'type': node_data.get('type'),
                    'name': node_data.get('name'),
                }
                )
            
            # Generate summary (async wrapper needed)
            summary = f"Community {comm_id} with {len(nodes)} components"
            summaries[comm_id] = summary
        
        self.community_summaries = summaries
        return summaries
    
    def get_relevant_context(self, changed_files: List[str], max_hops: int = 2) -> Dict[str, Any]:
        """Get relevant graph context for changed files"""
        context = {
            'direct_dependencies': set(),
            'indirect_dependencies': set(),
            'dependents': set(),
            'communities': set(),
            'nodes': [],
            'edges': []
        }
        
        # Find nodes related to changed files
        affected_nodes = set()
        for node_id, data in self.graph.nodes(data=True):
            if data.get('type') == 'chunk':
                file_path = data.get('file_path', '')
                if any(changed_file in file_path for changed_file in changed_files):
                    affected_nodes.add(node_id)
        
        if not affected_nodes:
            return context
        
        # Get dependencies (outgoing edges)
        for node in affected_nodes:
            # Direct dependencies
            for successor in self.graph.successors(node):
                context['direct_dependencies'].add(successor)
                context['nodes'].append(self._get_node_info(successor))
            
            # Indirect dependencies (up to max_hops)
            for successor in nx.descendants(self.graph, node):
                if successor not in context['direct_dependencies']:
                    path_length = nx.shortest_path_length(self.graph, node, successor)
                    if path_length <= max_hops:
                        context['indirect_dependencies'].add(successor)
        
        # Get dependents (incoming edges)
        for node in affected_nodes:
            for predecessor in self.graph.predecessors(node):
                context['dependents'].add(predecessor)
                context['nodes'].append(self._get_node_info(predecessor))
        
        # Find which communities are affected
        for comm_id, nodes in self.communities.items():
            if affected_nodes.intersection(nodes):
                context['communities'].add(comm_id)
        
        # Get edges between relevant nodes
        all_relevant = affected_nodes.union(
            context['direct_dependencies'],
            context['indirect_dependencies'],
            context['dependents']
        )
        
        for u, v in self.graph.edges():
            if u in all_relevant or v in all_relevant:
                context['edges'].append({
                    'source': u,
                    'target': v,
                    'relationship': self.graph[u][v].get('relationship', 'unknown')
                })
        
        # Convert sets to lists for JSON serialization
        context['direct_dependencies'] = list(context['direct_dependencies'])
        context['indirect_dependencies'] = list(context['indirect_dependencies'])
        context['dependents'] = list(context['dependents'])
        context['communities'] = list(context['communities'])
        
        return context
    
    def _get_node_info(self, node_id: str) -> Dict[str, Any]:
        """Get node information"""
        if node_id not in self.graph:
            return {}
        
        data = self.graph.nodes[node_id]
        return {
            'id': node_id,
            'type': data.get('type'),
            'name': data.get('name'),
            'path': data.get('path') or data.get('file_path'),
        }
    
    def export_graph(self) -> Dict[str, Any]:
        """Export graph for visualization"""
        nodes = []
        edges = []
        
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                'id': node_id,
                'label': data.get('name', node_id[:8]),
                'type': data.get('type'),
                'title': data.get('name')  # Hover text
            })
        
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                'from': u,
                'to': v,
                'label': data.get('relationship', ''),
                'arrows': 'to'
            })
        
        return {'nodes': nodes, 'edges': edges}
# app/services/dependency_resolver.py
import networkx as nx
from typing import Dict, Set, List

class CrossRepoDependencyResolver:
    def __init__(self):
        self.global_graph = nx.DiGraph()
        # Track which repo owns which node
        self.node_to_repo = {}

    def add_repo_graph(self, repo_id: str, local_graph: nx.DiGraph):
        for node in local_graph.nodes():
            global_node = f"{repo_id}::{node}"
            self.node_to_repo[global_node] = repo_id
            self.global_graph.add_node(global_node)
        for u, v in local_graph.edges():
            self.global_graph.add_edge(f"{repo_id}::{u}", f"{repo_id}::{v}")

    def get_transitive_impact(self, changed_nodes: List[str]) -> Set[str]:
        impacted = set()
        reversed_graph = self.global_graph.reverse()
        for node in changed_nodes:
            global_node = node  # assumed already namespaced
            if global_node in reversed_graph:
                for caller in nx.dfs_preorder_nodes(reversed_graph, source=global_node):
                    impacted.add(caller)
        return impacted

    def get_repo_of_node(self, node: str) -> str:
        return self.node_to_repo.get(node, "unknown")
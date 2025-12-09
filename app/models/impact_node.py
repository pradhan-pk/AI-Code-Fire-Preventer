# app/models/impact_node.py
from dataclasses import dataclass

@dataclass
class ImpactNode:
    node_id: str
    severity: int
    reason: str

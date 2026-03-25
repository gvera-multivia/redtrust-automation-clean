from dataclasses import dataclass
from enum import Enum

class NodeStatus(Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"

@dataclass
class NodeInfo:
    node_id: str
    ip_address: str
    hostname: str
    status: NodeStatus
    screen_unlocked: bool
    current_task: str = None
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    last_heartbeat: float = 0.0
    completed_tasks: int = 0
    failed_tasks: int = 0
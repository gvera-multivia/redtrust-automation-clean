import os
from dataclasses import dataclass
from typing import Dict, List
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    task_id: str
    task_type: str
    parameters: Dict
    status: TaskStatus
    assigned_node: str = None
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    result: any = None
    error_message: str = None
    estimated_duration: float = 0.0
    actual_duration: float = 0.0
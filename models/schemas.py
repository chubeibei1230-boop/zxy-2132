from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import uuid


@dataclass
class ScheduleRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: str = ""
    time_slot: str = ""
    staff_count: int = 0
    department: str = "default"


@dataclass
class SimulationParams:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "方案1"
    reception_capacity: int = 5
    service_duration: float = 15.0
    break_interval: float = 60.0
    peak_factor: float = 1.5
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SimulationResult:
    params_id: str = ""
    params_name: str = ""
    timestamps: List[float] = field(default_factory=list)
    wait_times: List[float] = field(default_factory=list)
    reception_volumes: List[float] = field(default_factory=list)
    avg_wait_time: float = 0.0
    max_wait_time: float = 0.0
    total_reception: float = 0.0
    cost_estimate: float = 0.0
    wait_time_ma: List[float] = field(default_factory=list)
    reception_ma: List[float] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class User:
    username: str
    role: str
    password: str = ""


ROLES = {
    "admin": "管理员",
    "user": "普通用户",
    "auditor": "审计员"
}

ROLE_PERMISSIONS = {
    "admin": ["upload_schedule", "simulate", "view_reports", "export", "manage_users"],
    "user": ["simulate", "view_reports", "export"],
    "auditor": ["view_reports", "export"]
}

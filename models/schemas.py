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
    created_by: str = ""
    department: str = "default"


@dataclass
class SimulationResult:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
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
    created_by: str = ""
    department: str = "default"


@dataclass
class BaselineScheme:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    result_id: str = ""
    result_snapshot: Dict = field(default_factory=dict)
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    department: str = "default"
    description: str = ""
    is_active: bool = True


@dataclass
class ReviewComparisonItem:
    result_id: str = ""
    result_name: str = ""
    avg_wait_time_diff: float = 0.0
    avg_wait_time_change_rate: float = 0.0
    max_wait_time_diff: float = 0.0
    max_wait_time_change_rate: float = 0.0
    total_reception_diff: float = 0.0
    total_reception_change_rate: float = 0.0
    cost_estimate_diff: float = 0.0
    cost_estimate_change_rate: float = 0.0
    unit_cost_diff: float = 0.0
    unit_cost_change_rate: float = 0.0
    conclusion: str = ""
    score: float = 0.0


@dataclass
class ReviewRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    baseline_id: str = ""
    baseline_name: str = ""
    comparison_items: List[ReviewComparisonItem] = field(default_factory=list)
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    department: str = "default"
    remarks: str = ""


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
    "admin": ["upload_schedule", "simulate", "view_reports", "export", "manage_users", "manage_baseline", "manage_review", "view_all_reviews", "create_review", "set_own_baseline"],
    "user": ["simulate", "view_reports", "export", "create_review", "view_own_reviews", "set_own_baseline"],
    "auditor": ["view_reports", "view_all_reviews", "view_baseline"]
}

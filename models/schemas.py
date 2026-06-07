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
class ThresholdConfig:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "默认阈值模板"
    avg_wait_time_max: float = 10.0
    avg_wait_time_warning: float = 7.0
    max_wait_time_max: float = 30.0
    max_wait_time_warning: float = 20.0
    total_reception_min: float = 200.0
    total_reception_warning: float = 250.0
    cost_estimate_max: float = 5000.0
    cost_estimate_warning: float = 4000.0
    unit_cost_max: float = 20.0
    unit_cost_warning: float = 15.0
    is_default: bool = False
    created_by: str = "admin"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    department: str = "default"


@dataclass
class ThresholdEvaluation:
    avg_wait_time_status: str = "达标"
    avg_wait_time_reason: str = ""
    max_wait_time_status: str = "达标"
    max_wait_time_reason: str = ""
    total_reception_status: str = "达标"
    total_reception_reason: str = ""
    cost_estimate_status: str = "达标"
    cost_estimate_reason: str = ""
    unit_cost_status: str = "达标"
    unit_cost_reason: str = ""
    overall_status: str = "达标"
    overall_score: float = 100.0
    key_reasons: List[str] = field(default_factory=list)
    recommendation_priority: int = 1
    conclusion_summary: str = ""


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
    threshold_template_id: str = ""
    threshold_template_name: str = ""
    threshold_evaluation: Optional[ThresholdEvaluation] = None


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
    threshold_evaluation: Optional[ThresholdEvaluation] = None
    threshold_conclusion: str = ""


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
    status: str = "已完成"


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
    "admin": ["upload_schedule", "simulate", "view_reports", "export", "manage_users", "manage_baseline", "manage_review", "view_all_reviews", "create_review", "set_own_baseline", "manage_threshold_templates", "view_threshold_templates", "apply_threshold_template"],
    "user": ["simulate", "view_reports", "export", "create_review", "view_own_reviews", "set_own_baseline", "view_threshold_templates", "apply_threshold_template"],
    "auditor": ["view_reports", "view_all_reviews", "view_baseline", "view_threshold_templates", "export"]
}

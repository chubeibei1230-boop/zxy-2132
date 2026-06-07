import os
import json
import csv
import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict
from models.schemas import (
    ScheduleRecord, SimulationParams, SimulationResult,
    BaselineScheme, ReviewComparisonItem, ReviewRecord,
    ThresholdConfig, ThresholdEvaluation
)


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_files")
EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)


def load_schedule_data(filepath: Optional[str] = None) -> List[ScheduleRecord]:
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "schedule.csv")
    
    if not os.path.exists(filepath):
        return []
    
    records = []
    try:
        df = pd.read_csv(filepath)
        for _, row in df.iterrows():
            record = ScheduleRecord(
                date=str(row.get("date", "")),
                time_slot=str(row.get("time_slot", "")),
                staff_count=int(row.get("staff_count", 0)),
                department=str(row.get("department", "default"))
            )
            records.append(record)
    except Exception as e:
        print(f"加载排班数据失败: {e}")
    
    return records


def save_schedule_data(records: List[ScheduleRecord], filepath: Optional[str] = None) -> bool:
    ensure_dirs()
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "schedule.csv")
    
    try:
        data = []
        for r in records:
            data.append({
                "id": r.id,
                "date": r.date,
                "time_slot": r.time_slot,
                "staff_count": r.staff_count,
                "department": r.department
            })
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return True
    except Exception as e:
        print(f"保存排班数据失败: {e}")
        return False


def load_simulation_params(filepath: Optional[str] = None) -> List[SimulationParams]:
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "simulation_params.json")
    
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data_list = json.load(f)
        
        params_list = []
        for data in data_list:
            params = SimulationParams(
                id=data.get("id", ""),
                name=data.get("name", ""),
                reception_capacity=int(data.get("reception_capacity", 5)),
                service_duration=float(data.get("service_duration", 15.0)),
                break_interval=float(data.get("break_interval", 60.0)),
                peak_factor=float(data.get("peak_factor", 1.5)),
                created_at=data.get("created_at", "")
            )
            params_list.append(params)
        return params_list
    except Exception as e:
        print(f"加载模拟参数失败: {e}")
        return []


def save_simulation_params(params_list: List[SimulationParams], filepath: Optional[str] = None) -> bool:
    ensure_dirs()
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "simulation_params.json")
    
    try:
        data = []
        for p in params_list:
            data.append({
                "id": p.id,
                "name": p.name,
                "reception_capacity": p.reception_capacity,
                "service_duration": p.service_duration,
                "break_interval": p.break_interval,
                "peak_factor": p.peak_factor,
                "created_at": p.created_at
            })
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存模拟参数失败: {e}")
        return False


def dict_to_threshold_evaluation(data: Optional[Dict]) -> Optional[ThresholdEvaluation]:
    if data is None:
        return None
    try:
        return ThresholdEvaluation(
            avg_wait_time_status=data.get("avg_wait_time_status", "达标"),
            avg_wait_time_reason=data.get("avg_wait_time_reason", ""),
            max_wait_time_status=data.get("max_wait_time_status", "达标"),
            max_wait_time_reason=data.get("max_wait_time_reason", ""),
            total_reception_status=data.get("total_reception_status", "达标"),
            total_reception_reason=data.get("total_reception_reason", ""),
            cost_estimate_status=data.get("cost_estimate_status", "达标"),
            cost_estimate_reason=data.get("cost_estimate_reason", ""),
            unit_cost_status=data.get("unit_cost_status", "达标"),
            unit_cost_reason=data.get("unit_cost_reason", ""),
            overall_status=data.get("overall_status", "达标"),
            overall_score=float(data.get("overall_score", 100.0)),
            key_reasons=data.get("key_reasons", []),
            recommendation_priority=int(data.get("recommendation_priority", 1)),
            conclusion_summary=data.get("conclusion_summary", "")
        )
    except Exception:
        return None


def threshold_evaluation_to_dict(evaluation: Optional[ThresholdEvaluation]) -> Optional[Dict]:
    if evaluation is None:
        return None
    return {
        "avg_wait_time_status": evaluation.avg_wait_time_status,
        "avg_wait_time_reason": evaluation.avg_wait_time_reason,
        "max_wait_time_status": evaluation.max_wait_time_status,
        "max_wait_time_reason": evaluation.max_wait_time_reason,
        "total_reception_status": evaluation.total_reception_status,
        "total_reception_reason": evaluation.total_reception_reason,
        "cost_estimate_status": evaluation.cost_estimate_status,
        "cost_estimate_reason": evaluation.cost_estimate_reason,
        "unit_cost_status": evaluation.unit_cost_status,
        "unit_cost_reason": evaluation.unit_cost_reason,
        "overall_status": evaluation.overall_status,
        "overall_score": evaluation.overall_score,
        "key_reasons": evaluation.key_reasons,
        "recommendation_priority": evaluation.recommendation_priority,
        "conclusion_summary": evaluation.conclusion_summary
    }


def load_simulation_results(filepath: Optional[str] = None) -> List[SimulationResult]:
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "simulation_results.json")
    
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data_list = json.load(f)
        
        results = []
        for data in data_list:
            threshold_eval_data = data.get("threshold_evaluation")
            result = SimulationResult(
                id=data.get("id", ""),
                params_id=data.get("params_id", ""),
                params_name=data.get("params_name", ""),
                timestamps=data.get("timestamps", []),
                wait_times=data.get("wait_times", []),
                reception_volumes=data.get("reception_volumes", []),
                avg_wait_time=float(data.get("avg_wait_time", 0.0)),
                max_wait_time=float(data.get("max_wait_time", 0.0)),
                total_reception=float(data.get("total_reception", 0.0)),
                cost_estimate=float(data.get("cost_estimate", 0.0)),
                wait_time_ma=data.get("wait_time_ma", []),
                reception_ma=data.get("reception_ma", []),
                created_at=data.get("created_at", ""),
                created_by=data.get("created_by", ""),
                department=data.get("department", "default"),
                threshold_template_id=data.get("threshold_template_id", ""),
                threshold_template_name=data.get("threshold_template_name", ""),
                threshold_evaluation=dict_to_threshold_evaluation(threshold_eval_data)
            )
            results.append(result)
        return results
    except Exception as e:
        print(f"加载模拟结果失败: {e}")
        return []


def save_simulation_results(results: List[SimulationResult], filepath: Optional[str] = None) -> bool:
    ensure_dirs()
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "simulation_results.json")
    
    try:
        data = []
        for r in results:
            data.append({
                "id": r.id,
                "params_id": r.params_id,
                "params_name": r.params_name,
                "timestamps": r.timestamps,
                "wait_times": r.wait_times,
                "reception_volumes": r.reception_volumes,
                "avg_wait_time": r.avg_wait_time,
                "max_wait_time": r.max_wait_time,
                "total_reception": r.total_reception,
                "cost_estimate": r.cost_estimate,
                "wait_time_ma": r.wait_time_ma,
                "reception_ma": r.reception_ma,
                "created_at": r.created_at,
                "created_by": r.created_by,
                "department": r.department,
                "threshold_template_id": r.threshold_template_id,
                "threshold_template_name": r.threshold_template_name,
                "threshold_evaluation": threshold_evaluation_to_dict(r.threshold_evaluation)
            })
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存模拟结果失败: {e}")
        return False


def export_results_to_csv(results: List[SimulationResult], filename: Optional[str] = None) -> str:
    ensure_dirs()
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"simulation_report_{timestamp}.csv"
    
    filepath = os.path.join(EXPORT_DIR, filename)
    
    try:
        rows = []
        for r in results:
            rows.append({
                "方案名称": r.params_name,
                "平均等待时长(分钟)": round(r.avg_wait_time, 2),
                "最大等待时长(分钟)": round(r.max_wait_time, 2),
                "总接待量": round(r.total_reception, 2),
                "预估成本(元)": round(r.cost_estimate, 2),
                "创建时间": r.created_at
            })
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return filepath
    except Exception as e:
        print(f"导出结果失败: {e}")
        return ""


def export_detailed_results(result: SimulationResult, filename: Optional[str] = None) -> str:
    ensure_dirs()
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"detailed_{result.params_name}_{timestamp}.csv"
    
    filepath = os.path.join(EXPORT_DIR, filename)
    
    try:
        rows = []
        for i in range(len(result.timestamps)):
            rows.append({
                "时间(分钟)": result.timestamps[i],
                "等待时长(分钟)": round(result.wait_times[i], 2),
                "接待量": round(result.reception_volumes[i], 2),
                "等待时长MA": round(result.wait_time_ma[i], 2) if i < len(result.wait_time_ma) else "",
                "接待量MA": round(result.reception_ma[i], 2) if i < len(result.reception_ma) else ""
            })
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return filepath
    except Exception as e:
        print(f"导出详细结果失败: {e}")
        return ""


def parse_uploaded_schedule(file_content) -> List[ScheduleRecord]:
    records = []
    try:
        import io
        df = pd.read_csv(io.StringIO(file_content.decode("utf-8-sig")))
        for _, row in df.iterrows():
            record = ScheduleRecord(
                date=str(row.get("date", row.get("日期", ""))),
                time_slot=str(row.get("time_slot", row.get("时段", ""))),
                staff_count=int(row.get("staff_count", row.get("排班人数", 0))),
                department=str(row.get("department", row.get("部门", "default")))
            )
            records.append(record)
    except Exception as e:
        print(f"解析上传文件失败: {e}")
    return records


def load_baseline_schemes(filepath: Optional[str] = None) -> List[BaselineScheme]:
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "baseline_schemes.json")
    
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data_list = json.load(f)
        
        baselines = []
        for data in data_list:
            baseline = BaselineScheme(
                id=data.get("id", ""),
                name=data.get("name", ""),
                result_id=data.get("result_id", ""),
                result_snapshot=data.get("result_snapshot", {}),
                created_by=data.get("created_by", ""),
                created_at=data.get("created_at", ""),
                department=data.get("department", "default"),
                description=data.get("description", ""),
                is_active=data.get("is_active", True)
            )
            baselines.append(baseline)
        return baselines
    except Exception as e:
        print(f"加载基线方案失败: {e}")
        return []


def save_baseline_schemes(baselines: List[BaselineScheme], filepath: Optional[str] = None) -> bool:
    ensure_dirs()
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "baseline_schemes.json")
    
    try:
        data = []
        for b in baselines:
            data.append({
                "id": b.id,
                "name": b.name,
                "result_id": b.result_id,
                "result_snapshot": b.result_snapshot,
                "created_by": b.created_by,
                "created_at": b.created_at,
                "department": b.department,
                "description": b.description,
                "is_active": b.is_active
            })
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存基线方案失败: {e}")
        return False


def add_baseline_scheme(baseline: BaselineScheme) -> bool:
    baselines = load_baseline_schemes()
    baselines.append(baseline)
    return save_baseline_schemes(baselines)


def update_baseline_scheme(baseline_id: str, **kwargs) -> bool:
    baselines = load_baseline_schemes()
    for i, b in enumerate(baselines):
        if b.id == baseline_id:
            for key, value in kwargs.items():
                if hasattr(b, key):
                    setattr(b, key, value)
            baselines[i] = b
            return save_baseline_schemes(baselines)
    return False


def delete_baseline_scheme(baseline_id: str) -> bool:
    baselines = load_baseline_schemes()
    baselines = [b for b in baselines if b.id != baseline_id]
    return save_baseline_schemes(baselines)


def get_baseline_by_id(baseline_id: str) -> Optional[BaselineScheme]:
    baselines = load_baseline_schemes()
    for b in baselines:
        if b.id == baseline_id:
            return b
    return None


def load_review_records(filepath: Optional[str] = None) -> List[ReviewRecord]:
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "review_records.json")
    
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data_list = json.load(f)
        
        records = []
        for data in data_list:
            items_data = data.get("comparison_items", [])
            items = []
            for item_data in items_data:
                item = ReviewComparisonItem(
                    result_id=item_data.get("result_id", ""),
                    result_name=item_data.get("result_name", ""),
                    avg_wait_time_diff=float(item_data.get("avg_wait_time_diff", 0.0)),
                    avg_wait_time_change_rate=float(item_data.get("avg_wait_time_change_rate", 0.0)),
                    max_wait_time_diff=float(item_data.get("max_wait_time_diff", 0.0)),
                    max_wait_time_change_rate=float(item_data.get("max_wait_time_change_rate", 0.0)),
                    total_reception_diff=float(item_data.get("total_reception_diff", 0.0)),
                    total_reception_change_rate=float(item_data.get("total_reception_change_rate", 0.0)),
                    cost_estimate_diff=float(item_data.get("cost_estimate_diff", 0.0)),
                    cost_estimate_change_rate=float(item_data.get("cost_estimate_change_rate", 0.0)),
                    unit_cost_diff=float(item_data.get("unit_cost_diff", 0.0)),
                    unit_cost_change_rate=float(item_data.get("unit_cost_change_rate", 0.0)),
                    conclusion=item_data.get("conclusion", ""),
                    score=float(item_data.get("score", 0.0)),
                    threshold_evaluation=dict_to_threshold_evaluation(item_data.get("threshold_evaluation")),
                    threshold_conclusion=item_data.get("threshold_conclusion", "")
                )
                items.append(item)
            
            record = ReviewRecord(
                id=data.get("id", ""),
                name=data.get("name", ""),
                baseline_id=data.get("baseline_id", ""),
                baseline_name=data.get("baseline_name", ""),
                comparison_items=items,
                created_by=data.get("created_by", ""),
                created_at=data.get("created_at", ""),
                department=data.get("department", "default"),
                remarks=data.get("remarks", "")
            )
            records.append(record)
        return records
    except Exception as e:
        print(f"加载复盘记录失败: {e}")
        return []


def save_review_records(records: List[ReviewRecord], filepath: Optional[str] = None) -> bool:
    ensure_dirs()
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "review_records.json")
    
    try:
        data = []
        for r in records:
            items_data = []
            for item in r.comparison_items:
                items_data.append({
                    "result_id": item.result_id,
                    "result_name": item.result_name,
                    "avg_wait_time_diff": item.avg_wait_time_diff,
                    "avg_wait_time_change_rate": item.avg_wait_time_change_rate,
                    "max_wait_time_diff": item.max_wait_time_diff,
                    "max_wait_time_change_rate": item.max_wait_time_change_rate,
                    "total_reception_diff": item.total_reception_diff,
                    "total_reception_change_rate": item.total_reception_change_rate,
                    "cost_estimate_diff": item.cost_estimate_diff,
                    "cost_estimate_change_rate": item.cost_estimate_change_rate,
                    "unit_cost_diff": item.unit_cost_diff,
                    "unit_cost_change_rate": item.unit_cost_change_rate,
                    "conclusion": item.conclusion,
                    "score": item.score,
                    "threshold_evaluation": threshold_evaluation_to_dict(item.threshold_evaluation),
                    "threshold_conclusion": item.threshold_conclusion
                })
            data.append({
                "id": r.id,
                "name": r.name,
                "baseline_id": r.baseline_id,
                "baseline_name": r.baseline_name,
                "comparison_items": items_data,
                "created_by": r.created_by,
                "created_at": r.created_at,
                "department": r.department,
                "remarks": r.remarks
            })
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存复盘记录失败: {e}")
        return False


def load_threshold_templates(filepath: Optional[str] = None) -> List[ThresholdConfig]:
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "threshold_templates.json")
    
    if not os.path.exists(filepath):
        default_template = ThresholdConfig(
            name="系统默认阈值",
            is_default=True,
            created_by="system"
        )
        save_threshold_templates([default_template])
        return [default_template]
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data_list = json.load(f)
        
        templates = []
        for data in data_list:
            template = ThresholdConfig(
                id=data.get("id", ""),
                name=data.get("name", ""),
                avg_wait_time_max=float(data.get("avg_wait_time_max", 10.0)),
                avg_wait_time_warning=float(data.get("avg_wait_time_warning", 7.0)),
                max_wait_time_max=float(data.get("max_wait_time_max", 30.0)),
                max_wait_time_warning=float(data.get("max_wait_time_warning", 20.0)),
                total_reception_min=float(data.get("total_reception_min", 200.0)),
                total_reception_warning=float(data.get("total_reception_warning", 250.0)),
                cost_estimate_max=float(data.get("cost_estimate_max", 5000.0)),
                cost_estimate_warning=float(data.get("cost_estimate_warning", 4000.0)),
                unit_cost_max=float(data.get("unit_cost_max", 20.0)),
                unit_cost_warning=float(data.get("unit_cost_warning", 15.0)),
                is_default=data.get("is_default", False),
                created_by=data.get("created_by", ""),
                created_at=data.get("created_at", ""),
                department=data.get("department", "default")
            )
            templates.append(template)
        return templates
    except Exception as e:
        print(f"加载阈值模板失败: {e}")
        return []


def save_threshold_templates(templates: List[ThresholdConfig], filepath: Optional[str] = None) -> bool:
    ensure_dirs()
    if filepath is None:
        filepath = os.path.join(DATA_DIR, "threshold_templates.json")
    
    try:
        data = []
        for t in templates:
            data.append({
                "id": t.id,
                "name": t.name,
                "avg_wait_time_max": t.avg_wait_time_max,
                "avg_wait_time_warning": t.avg_wait_time_warning,
                "max_wait_time_max": t.max_wait_time_max,
                "max_wait_time_warning": t.max_wait_time_warning,
                "total_reception_min": t.total_reception_min,
                "total_reception_warning": t.total_reception_warning,
                "cost_estimate_max": t.cost_estimate_max,
                "cost_estimate_warning": t.cost_estimate_warning,
                "unit_cost_max": t.unit_cost_max,
                "unit_cost_warning": t.unit_cost_warning,
                "is_default": t.is_default,
                "created_by": t.created_by,
                "created_at": t.created_at,
                "department": t.department
            })
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存阈值模板失败: {e}")
        return False


def add_threshold_template(template: ThresholdConfig) -> bool:
    templates = load_threshold_templates()
    if template.is_default:
        for t in templates:
            t.is_default = False
    templates.append(template)
    return save_threshold_templates(templates)


def update_threshold_template(template_id: str, **kwargs) -> bool:
    templates = load_threshold_templates()
    for i, t in enumerate(templates):
        if t.id == template_id:
            if kwargs.get("is_default", False):
                for other in templates:
                    other.is_default = False
            for key, value in kwargs.items():
                if hasattr(t, key):
                    setattr(t, key, value)
            templates[i] = t
            return save_threshold_templates(templates)
    return False


def delete_threshold_template(template_id: str) -> bool:
    templates = load_threshold_templates()
    templates = [t for t in templates if t.id != template_id]
    if templates and not any(t.is_default for t in templates):
        templates[0].is_default = True
    return save_threshold_templates(templates)


def get_default_threshold_template() -> Optional[ThresholdConfig]:
    templates = load_threshold_templates()
    for t in templates:
        if t.is_default:
            return t
    if templates:
        return templates[0]
    return None


def get_threshold_template_by_id(template_id: str) -> Optional[ThresholdConfig]:
    templates = load_threshold_templates()
    for t in templates:
        if t.id == template_id:
            return t
    return None


def add_review_record(record: ReviewRecord) -> bool:
    records = load_review_records()
    records.append(record)
    return save_review_records(records)


def delete_review_record(record_id: str) -> bool:
    records = load_review_records()
    records = [r for r in records if r.id != record_id]
    return save_review_records(records)


def get_review_by_id(record_id: str) -> Optional[ReviewRecord]:
    records = load_review_records()
    for r in records:
        if r.id == record_id:
            return r
    return None


def export_review_report(review: ReviewRecord, filename: Optional[str] = None) -> str:
    ensure_dirs()
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"review_report_{review.id}_{timestamp}.csv"
    
    filepath = os.path.join(EXPORT_DIR, filename)
    
    try:
        rows = []
        rows.append({
            "复盘名称": review.name,
            "基线方案": review.baseline_name,
            "创建人": review.created_by,
            "创建时间": review.created_at[:19] if review.created_at else "",
            "部门": review.department,
            "备注": review.remarks
        })
        rows.append({})
        
        rows.append({
            "对比方案": "",
            "平均等待时长差异": "",
            "平均等待变化率": "",
            "最大等待时长差异": "",
            "最大等待变化率": "",
            "总接待量差异": "",
            "总接待量变化率": "",
            "预估成本差异": "",
            "预估成本变化率": "",
            "单位成本差异": "",
            "单位成本变化率": "",
            "综合结论": "",
            "综合评分": ""
        })
        
        for item in review.comparison_items:
            rows.append({
                "对比方案": item.result_name,
                "平均等待时长差异": f"{item.avg_wait_time_diff:+.2f}分钟",
                "平均等待变化率": f"{item.avg_wait_time_change_rate:+.2%}",
                "最大等待时长差异": f"{item.max_wait_time_diff:+.2f}分钟",
                "最大等待变化率": f"{item.max_wait_time_change_rate:+.2%}",
                "总接待量差异": f"{item.total_reception_diff:+.2f}人",
                "总接待量变化率": f"{item.total_reception_change_rate:+.2%}",
                "预估成本差异": f"{item.cost_estimate_diff:+.2f}元",
                "预估成本变化率": f"{item.cost_estimate_change_rate:+.2%}",
                "单位成本差异": f"{item.unit_cost_diff:+.2f}元/人",
                "单位成本变化率": f"{item.unit_cost_change_rate:+.2%}",
                "综合结论": item.conclusion,
                "综合评分": f"{item.score:.2f}"
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return filepath
    except Exception as e:
        print(f"导出复盘报告失败: {e}")
        return ""

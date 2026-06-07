import os
import json
import csv
import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict
from models.schemas import ScheduleRecord, SimulationParams, SimulationResult


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
            result = SimulationResult(
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
                created_at=data.get("created_at", "")
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
                "created_at": r.created_at
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

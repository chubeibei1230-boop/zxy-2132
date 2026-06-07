import numpy as np
from typing import List, Tuple, Optional, Dict
from models.schemas import SimulationParams, SimulationResult, ReviewComparisonItem


def moving_average(data: List[float], window: int = 5) -> List[float]:
    if len(data) < window:
        return data.copy()
    result = []
    for i in range(len(data)):
        start = max(0, i - window + 1)
        end = i + 1
        window_data = data[start:end]
        result.append(np.mean(window_data))
    return result


def generate_arrival_pattern(total_minutes: int = 480, peak_factor: float = 1.5) -> List[float]:
    base_rate = 1.0
    arrivals = []
    peak_center = total_minutes * 0.5
    peak_width = total_minutes * 0.3
    
    for t in range(total_minutes):
        peak_effect = np.exp(-((t - peak_center) ** 2) / (2 * peak_width ** 2))
        rate = base_rate * (1 + (peak_factor - 1) * peak_effect)
        arrivals.append(rate)
    
    return arrivals


def run_simulation(
    params: SimulationParams,
    schedule_staff: Optional[List[int]] = None,
    total_minutes: int = 480,
    ma_window: int = 10
) -> SimulationResult:
    reception_capacity = params.reception_capacity
    service_duration = params.service_duration
    break_interval = params.break_interval
    peak_factor = params.peak_factor
    
    if schedule_staff is None or len(schedule_staff) == 0:
        effective_capacity = reception_capacity
    else:
        schedule_staff_array = np.array(schedule_staff)
        avg_staff = np.mean(schedule_staff_array)
        if avg_staff > 0:
            effective_capacity = int(reception_capacity * (avg_staff / 2))
        else:
            effective_capacity = reception_capacity
    
    arrivals = generate_arrival_pattern(total_minutes, peak_factor)
    
    timestamps = list(range(total_minutes))
    wait_times = []
    reception_volumes = []
    queue = 0.0
    total_served = 0.0
    
    service_rate_per_minute = effective_capacity / service_duration
    
    for t in range(total_minutes):
        arrival_rate = arrivals[t]
        
        if (t + 1) % int(break_interval) == 0:
            current_service_rate = service_rate_per_minute * 0.5
        else:
            current_service_rate = service_rate_per_minute
        
        queue += arrival_rate
        served = min(queue, current_service_rate)
        queue -= served
        total_served += served
        
        current_wait = queue * service_duration / max(effective_capacity, 1)
        
        wait_times.append(current_wait)
        reception_volumes.append(served)
    
    wait_time_ma = moving_average(wait_times, ma_window)
    reception_ma = moving_average(reception_volumes, ma_window)
    
    avg_wait = np.mean(wait_times)
    max_wait = np.max(wait_times)
    total_reception = total_served
    
    cost_per_staff_per_hour = 50
    estimated_hours = total_minutes / 60
    cost_estimate = effective_capacity * cost_per_staff_per_hour * estimated_hours
    
    result = SimulationResult(
        params_id=params.id,
        params_name=params.name,
        timestamps=timestamps,
        wait_times=wait_times,
        reception_volumes=reception_volumes,
        avg_wait_time=avg_wait,
        max_wait_time=max_wait,
        total_reception=total_reception,
        cost_estimate=cost_estimate,
        wait_time_ma=wait_time_ma,
        reception_ma=reception_ma,
    )
    
    return result


def compare_results(results: List[SimulationResult]) -> dict:
    comparison = {
        "names": [r.params_name for r in results],
        "avg_wait_times": [r.avg_wait_time for r in results],
        "max_wait_times": [r.max_wait_time for r in results],
        "total_receptions": [r.total_reception for r in results],
        "cost_estimates": [r.cost_estimate for r in results],
    }
    return comparison


def calculate_unit_cost(result: SimulationResult) -> float:
    if result.total_reception > 0:
        return result.cost_estimate / result.total_reception
    return 0.0


def calculate_change_rate(current: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return (current - baseline) / abs(baseline)


def evaluate_conclusion(
    avg_wait_diff: float,
    max_wait_diff: float,
    total_recep_diff: float,
    cost_diff: float,
    unit_cost_diff: float
) -> str:
    score = 0.0
    
    if avg_wait_diff < 0:
        score += 2.0
    elif avg_wait_diff == 0:
        score += 1.0
    
    if max_wait_diff < 0:
        score += 1.5
    elif max_wait_diff == 0:
        score += 0.75
    
    if total_recep_diff > 0:
        score += 2.0
    elif total_recep_diff == 0:
        score += 1.0
    
    if cost_diff < 0:
        score += 1.5
    elif cost_diff == 0:
        score += 0.75
    
    if unit_cost_diff < 0:
        score += 2.0
    elif unit_cost_diff == 0:
        score += 1.0
    
    max_score = 9.0
    normalized_score = score / max_score
    
    if normalized_score >= 0.7:
        return "更优"
    elif normalized_score >= 0.4:
        return "持平"
    else:
        return "退化"


def calculate_comparison_item(
    baseline_result: SimulationResult,
    compare_result: SimulationResult
) -> ReviewComparisonItem:
    baseline_unit_cost = calculate_unit_cost(baseline_result)
    compare_unit_cost = calculate_unit_cost(compare_result)
    
    avg_wait_diff = compare_result.avg_wait_time - baseline_result.avg_wait_time
    max_wait_diff = compare_result.max_wait_time - baseline_result.max_wait_time
    total_recep_diff = compare_result.total_reception - baseline_result.total_reception
    cost_diff = compare_result.cost_estimate - baseline_result.cost_estimate
    unit_cost_diff = compare_unit_cost - baseline_unit_cost
    
    avg_wait_change = calculate_change_rate(compare_result.avg_wait_time, baseline_result.avg_wait_time)
    max_wait_change = calculate_change_rate(compare_result.max_wait_time, baseline_result.max_wait_time)
    total_recep_change = calculate_change_rate(compare_result.total_reception, baseline_result.total_reception)
    cost_change = calculate_change_rate(compare_result.cost_estimate, baseline_result.cost_estimate)
    unit_cost_change = calculate_change_rate(compare_unit_cost, baseline_unit_cost)
    
    conclusion = evaluate_conclusion(
        avg_wait_diff, max_wait_diff, total_recep_diff, cost_diff, unit_cost_diff)
    
    score = calculate_comprehensive_score(
        avg_wait_diff, max_wait_diff, total_recep_diff, cost_diff, unit_cost_diff,
        baseline_result.avg_wait_time, baseline_result.max_wait_time,
        baseline_result.total_reception, baseline_result.cost_estimate,
        baseline_unit_cost
    )
    
    return ReviewComparisonItem(
        result_id=compare_result.id,
        result_name=compare_result.params_name,
        avg_wait_time_diff=avg_wait_diff,
        avg_wait_time_change_rate=avg_wait_change,
        max_wait_time_diff=max_wait_diff,
        max_wait_time_change_rate=max_wait_change,
        total_reception_diff=total_recep_diff,
        total_reception_change_rate=total_recep_change,
        cost_estimate_diff=cost_diff,
        cost_estimate_change_rate=cost_change,
        unit_cost_diff=unit_cost_diff,
        unit_cost_change_rate=unit_cost_change,
        conclusion=conclusion,
        score=score
    )


def calculate_comprehensive_score(
    avg_wait_diff: float,
    max_wait_diff: float,
    total_recep_diff: float,
    cost_diff: float,
    unit_cost_diff: float,
    baseline_avg_wait: float,
    baseline_max_wait: float,
    baseline_total_recep: float,
    baseline_cost: float,
    baseline_unit_cost: float
) -> float:
    score = 0.0
    
    if baseline_avg_wait > 0:
        avg_wait_improve = -avg_wait_diff / baseline_avg_wait
        score += avg_wait_improve * 25.0
    if baseline_max_wait > 0:
        max_wait_improve = -max_wait_diff / baseline_max_wait
        score += max_wait_improve * 20.0
    
    if baseline_total_recep > 0:
        total_recep_improve = total_recep_diff / baseline_total_recep
        score += total_recep_improve * 25.0
    
    if baseline_cost > 0:
        cost_improve = -cost_diff / baseline_cost
        score += cost_improve * 15.0
    
    if baseline_unit_cost > 0:
        unit_cost_improve = -unit_cost_diff / baseline_unit_cost
        score += unit_cost_improve * 15.0
    
    return round(score + 50.0, 2)


def perform_review_comparison(
    baseline_result: SimulationResult,
    compare_results: List[SimulationResult]
) -> List[ReviewComparisonItem]:
    items = []
    for result in compare_results:
        item = calculate_comparison_item(baseline_result, result)
        items.append(item)
    
    items.sort(key=lambda x: x.score, reverse=True)
    return items

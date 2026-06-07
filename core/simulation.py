import numpy as np
from typing import List, Tuple, Optional
from models.schemas import SimulationParams, SimulationResult


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

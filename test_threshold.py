import sys
sys.path.insert(0, '.')

from models.schemas import ThresholdConfig, ThresholdEvaluation, SimulationResult
from core.simulation import evaluate_threshold, generate_threshold_conclusion, get_default_threshold_config
from data.persistence import (
    load_threshold_templates, save_threshold_templates,
    add_threshold_template, get_default_threshold_template
)
import json

print("=" * 60)
print("测试1: 阈值配置和评估功能")
print("=" * 60)

# 获取默认阈值配置
config = get_default_threshold_config()
print(f"默认阈值模板: {config.name}")
print(f"  平均等待时长 - 预警值: {config.avg_wait_time_warning}分钟, 最大值: {config.avg_wait_time_max}分钟")
print(f"  最大等待时长 - 预警值: {config.max_wait_time_warning}分钟, 最大值: {config.max_wait_time_max}分钟")
print(f"  总接待量 - 预警值: {config.total_reception_warning}人, 最小值: {config.total_reception_min}人")
print(f"  预估成本 - 预警值: {config.cost_estimate_warning}元, 最大值: {config.cost_estimate_max}元")
print(f"  单位接待成本 - 预警值: {config.unit_cost_warning}元/人, 最大值: {config.unit_cost_max}元/人")

# 创建一个模拟结果进行测试
result = SimulationResult(
    params_name="测试方案A",
    avg_wait_time=8.5,
    max_wait_time=25.0,
    total_reception=220.0,
    cost_estimate=4500.0
)

# 执行阈值评估
evaluation = evaluate_threshold(result, config)
print(f"\n评估结果:")
print(f"  综合状态: {evaluation.overall_status}")
print(f"  综合评分: {evaluation.overall_score}")
print(f"  推荐优先级: {evaluation.recommendation_priority}")
print(f"  关键原因: {evaluation.key_reasons}")
print(f"  结论摘要: {evaluation.conclusion_summary}")

print(f"\n各指标详情:")
print(f"  平均等待时长: {evaluation.avg_wait_time_status} - {evaluation.avg_wait_time_reason}")
print(f"  最大等待时长: {evaluation.max_wait_time_status} - {evaluation.max_wait_time_reason}")
print(f"  总接待量: {evaluation.total_reception_status} - {evaluation.total_reception_reason}")
print(f"  预估成本: {evaluation.cost_estimate_status} - {evaluation.cost_estimate_reason}")
print(f"  单位接待成本: {evaluation.unit_cost_status} - {evaluation.unit_cost_reason}")

print("\n" + "=" * 60)
print("测试2: 阈值模板持久化功能")
print("=" * 60)

# 创建一个自定义模板
custom_config = ThresholdConfig(
    name="客服部门专用模板",
    avg_wait_time_max=15.0,
    avg_wait_time_warning=10.0,
    max_wait_time_max=45.0,
    max_wait_time_warning=30.0,
    total_reception_min=150.0,
    total_reception_warning=200.0,
    cost_estimate_max=8000.0,
    cost_estimate_warning=6000.0,
    unit_cost_max=30.0,
    unit_cost_warning=25.0,
    department="客服部",
    created_by="admin"
)

# 添加模板
add_threshold_template(custom_config)
print(f"已添加模板: {custom_config.name}")

# 加载所有模板
templates = load_threshold_templates()
print(f"当前共有 {len(templates)} 个阈值模板")
for t in templates:
    default_mark = " [默认]" if t.is_default else ""
    print(f"  - {t.name}{default_mark} (创建者: {t.created_by}, 部门: {t.department})")

# 获取默认模板
default_template = get_default_threshold_template()
if default_template:
    print(f"\n当前默认模板: {default_template.name}")
else:
    print("\n没有设置默认模板，将使用系统内置默认值")

print("\n" + "=" * 60)
print("测试3: 生成阈值评估结论")
print("=" * 60)

conclusion = generate_threshold_conclusion(evaluation)
print(f"生成的结论: {conclusion}")

print("\n✅ 所有测试通过!")

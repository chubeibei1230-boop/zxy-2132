import streamlit as st
import sys
import os
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import SimulationParams, ThresholdConfig
from core.simulation import run_simulation, compare_results, evaluate_threshold, calculate_unit_cost
from data.persistence import (
    load_schedule_data,
    load_simulation_params,
    save_simulation_params,
    load_simulation_results,
    save_simulation_results,
    export_results_to_csv,
    export_detailed_results,
    ensure_dirs,
    load_threshold_templates,
    get_default_threshold_template,
    get_threshold_template_by_id
)


st.set_page_config(page_title="模拟面板", page_icon="⚙️", layout="wide")


def check_permission(permission: str) -> bool:
    auth_manager = st.session_state.get("auth_manager")
    if auth_manager is None:
        return False
    return auth_manager.has_permission(permission)


def main():
    st.title("⚙️ 模拟面板")
    st.markdown("---")
    
    if not check_permission("simulate"):
        st.warning("⚠️ 您没有权限访问此页面。请使用普通用户或管理员账户登录。")
        return
    
    ensure_dirs()
    
    if "current_params_list" not in st.session_state:
        st.session_state.current_params_list = []
    if "current_results" not in st.session_state:
        st.session_state.current_results = []
    if "loaded_params" not in st.session_state:
        st.session_state.loaded_params = None
    if "num_schemes_loaded" not in st.session_state:
        st.session_state.num_schemes_loaded = None
    if "current_threshold" not in st.session_state:
        default_template = get_default_threshold_template()
        st.session_state.current_threshold = default_template
        st.session_state.threshold_template_id = default_template.id if default_template else ""
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.subheader("📂 已保存方案")
        saved_params = load_simulation_params()
        if saved_params:
            selected = st.multiselect(
                "选择方案进行对比",
                options=[f"{p.name} ({p.created_at[:16]})" for p in saved_params],
                default=[]
            )
            if st.button("加载选中方案", use_container_width=True):
                indices = [i for i, p in enumerate(saved_params) if f"{p.name} ({p.created_at[:16]})" in selected]
                if indices:
                    loaded_params = [saved_params[i] for i in indices]
                    st.session_state.loaded_params = loaded_params
                    st.session_state.num_schemes_loaded = len(loaded_params)
                    st.success(f"已加载 {len(loaded_params)} 个方案，参数已同步到左侧")
                    st.rerun()
        else:
            st.info("暂无保存的方案")
        
        st.markdown("---")
        st.subheader("🎯 目标阈值设置")
        
        templates = load_threshold_templates()
        template_options = [(t.id, f"{t.name} {'(默认)' if t.is_default else ''}") for t in templates]
        template_ids = [t[0] for t in template_options]
        template_labels = [t[1] for t in template_options]
        
        current_template_idx = 0
        if st.session_state.threshold_template_id in template_ids:
            current_template_idx = template_ids.index(st.session_state.threshold_template_id)
        
        selected_template_label = st.selectbox(
            "选择阈值模板",
            options=template_labels,
            index=current_template_idx
        )
        
        selected_template_id = template_ids[template_labels.index(selected_template_label)]
        selected_template = get_threshold_template_by_id(selected_template_id)
        
        if selected_template and selected_template_id != st.session_state.threshold_template_id:
            st.session_state.threshold_template_id = selected_template_id
            st.session_state.current_threshold = selected_template
            st.rerun()
        
        with st.expander("📊 调整阈值参数", expanded=False):
            current_th = st.session_state.current_threshold
            if current_th:
                st.markdown("**⏱️ 等待时长阈值（越小越好）**")
                col_w1, col_w2 = st.columns(2)
                with col_w1:
                    avg_wait_warn = st.number_input(
                        "平均等待预警值(分钟)",
                        min_value=0.1,
                        max_value=120.0,
                        value=current_th.avg_wait_time_warning,
                        step=0.5,
                        key="th_avg_wait_warn"
                    )
                with col_w2:
                    avg_wait_max = st.number_input(
                        "平均等待最大值(分钟)",
                        min_value=avg_wait_warn,
                        max_value=180.0,
                        value=current_th.avg_wait_time_max,
                        step=0.5,
                        key="th_avg_wait_max"
                    )
                
                col_mw1, col_mw2 = st.columns(2)
                with col_mw1:
                    max_wait_warn = st.number_input(
                        "最大等待预警值(分钟)",
                        min_value=0.1,
                        max_value=300.0,
                        value=current_th.max_wait_time_warning,
                        step=1.0,
                        key="th_max_wait_warn"
                    )
                with col_mw2:
                    max_wait_max = st.number_input(
                        "最大等待最大值(分钟)",
                        min_value=max_wait_warn,
                        max_value=600.0,
                        value=current_th.max_wait_time_max,
                        step=1.0,
                        key="th_max_wait_max"
                    )
                
                st.markdown("**👥 接待量阈值（越大越好）**")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    total_recep_min = st.number_input(
                        "总接待最小值(人)",
                        min_value=1.0,
                        max_value=2000.0,
                        value=current_th.total_reception_min,
                        step=10.0,
                        key="th_total_recep_min"
                    )
                with col_r2:
                    total_recep_warn = st.number_input(
                        "总接待目标值(人)",
                        min_value=total_recep_min,
                        max_value=5000.0,
                        value=current_th.total_reception_warning,
                        step=10.0,
                        key="th_total_recep_warn"
                    )
                
                st.markdown("**💰 成本阈值（越小越好）**")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    cost_warn = st.number_input(
                        "预估成本预警值(元)",
                        min_value=100.0,
                        max_value=100000.0,
                        value=current_th.cost_estimate_warning,
                        step=100.0,
                        key="th_cost_warn"
                    )
                with col_c2:
                    cost_max = st.number_input(
                        "预估成本最大值(元)",
                        min_value=cost_warn,
                        max_value=200000.0,
                        value=current_th.cost_estimate_max,
                        step=100.0,
                        key="th_cost_max"
                    )
                
                col_uc1, col_uc2 = st.columns(2)
                with col_uc1:
                    unit_cost_warn = st.number_input(
                        "单位成本预警值(元/人)",
                        min_value=0.1,
                        max_value=500.0,
                        value=current_th.unit_cost_warning,
                        step=1.0,
                        key="th_unit_cost_warn"
                    )
                with col_uc2:
                    unit_cost_max = st.number_input(
                        "单位成本最大值(元/人)",
                        min_value=unit_cost_warn,
                        max_value=1000.0,
                        value=current_th.unit_cost_max,
                        step=1.0,
                        key="th_unit_cost_max"
                    )
                
                if st.button("✅ 应用临时调整", use_container_width=True):
                    st.session_state.current_threshold = ThresholdConfig(
                        id="temp",
                        name="临时调整阈值",
                        avg_wait_time_max=avg_wait_max,
                        avg_wait_time_warning=avg_wait_warn,
                        max_wait_time_max=max_wait_max,
                        max_wait_time_warning=max_wait_warn,
                        total_reception_min=total_recep_min,
                        total_reception_warning=total_recep_warn,
                        cost_estimate_max=cost_max,
                        cost_estimate_warning=cost_warn,
                        unit_cost_max=unit_cost_max,
                        unit_cost_warning=unit_cost_warn
                    )
                    st.success("已应用临时阈值调整！")
                    st.rerun()
    
    with col1:
        st.subheader("📝 参数设置")
        
        default_num = 2
        if st.session_state.num_schemes_loaded is not None:
            default_num = st.session_state.num_schemes_loaded
        
        num_schemes = st.number_input("方案数量", min_value=1, max_value=5, value=default_num, step=1)
        
        if st.session_state.loaded_params is not None:
            for i, p in enumerate(st.session_state.loaded_params):
                if i < int(num_schemes):
                    st.session_state[f"name_{i}"] = p.name
                    st.session_state[f"reception_{i}"] = p.reception_capacity
                    st.session_state[f"duration_{i}"] = p.service_duration
                    st.session_state[f"break_{i}"] = p.break_interval
                    st.session_state[f"peak_{i}"] = p.peak_factor
        
        params_list = []
        
        for i in range(int(num_schemes)):
            with st.expander(f"方案 {i+1} 参数设置", expanded=True):
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    name_val = st.session_state.get(f"name_{i}", f"方案{i+1}")
                    reception_val = st.session_state.get(f"reception_{i}", 5 + i * 2)
                    name = st.text_input(f"方案名称", value=name_val, key=f"name_{i}")
                    reception = st.number_input(f"接待人数(人)", min_value=1, max_value=50, value=reception_val, key=f"reception_{i}")
                
                with col_b:
                    duration_val = st.session_state.get(f"duration_{i}", 15.0)
                    break_val = st.session_state.get(f"break_{i}", 60.0)
                    duration = st.number_input(f"单次耗时(分钟)", min_value=1.0, max_value=120.0, value=duration_val, step=1.0, key=f"duration_{i}")
                    break_int = st.number_input(f"休息间隔(分钟)", min_value=10.0, max_value=240.0, value=break_val, step=10.0, key=f"break_{i}")
                
                with col_c:
                    peak_val = st.session_state.get(f"peak_{i}", 1.5 + i * 0.2)
                    peak = st.slider(f"高峰系数", min_value=1.0, max_value=3.0, value=peak_val, step=0.1, key=f"peak_{i}")
                
                params = SimulationParams(
                    name=name,
                    reception_capacity=int(reception),
                    service_duration=float(duration),
                    break_interval=float(break_int),
                    peak_factor=float(peak)
                )
                params_list.append(params)
        
        st.session_state.current_params_list = params_list
        
        if st.session_state.loaded_params is not None:
            st.session_state.loaded_params = None
            st.session_state.num_schemes_loaded = None
        
        col_run, col_save_hist, col_save_scheme, col_clear = st.columns([1.2, 1.2, 1, 1])
        with col_run:
            if st.button("▶️ 运行模拟", use_container_width=True, type="primary"):
                run_simulations(params_list, save_to_history=False)
        
        with col_save_hist:
            if st.button("📌 保存结果到历史", use_container_width=True, disabled=len(st.session_state.current_results) == 0):
                save_current_results_to_history()
                st.success("已保存到历史报告！")
        
        with col_save_scheme:
            if st.button("💾 保存方案", use_container_width=True):
                save_current_schemes(params_list)
        
        with col_clear:
            if st.button("🗑️ 清空结果", use_container_width=True):
                st.session_state.current_results = []
                st.rerun()
    
    st.markdown("---")
    
    if st.session_state.current_results:
        show_results(st.session_state.current_results)


def run_simulations(params_list, save_to_history=False):
    schedule_data = load_schedule_data()
    staff_counts = [r.staff_count for r in schedule_data] if schedule_data else None
    
    threshold = st.session_state.get("current_threshold")
    threshold_template_id = st.session_state.get("threshold_template_id", "")
    threshold_template_name = ""
    
    if threshold_template_id and threshold_template_id != "temp":
        template = get_threshold_template_by_id(threshold_template_id)
        if template:
            threshold_template_name = template.name
    elif threshold:
        threshold_template_name = threshold.name
    
    results = []
    for params in params_list:
        result = run_simulation(params, staff_counts, ma_window=10)
        result.threshold_template_id = threshold_template_id
        result.threshold_template_name = threshold_template_name
        
        if threshold:
            evaluation = evaluate_threshold(result, threshold)
            result.threshold_evaluation = evaluation
        
        results.append(result)
    
    st.session_state.current_results = results
    
    if save_to_history:
        save_current_results_to_history()


def get_current_username():
    auth_manager = st.session_state.get("auth_manager")
    if auth_manager and auth_manager.get_current_user():
        return auth_manager.get_current_user().username
    return ""


def save_current_results_to_history():
    if st.session_state.current_results:
        username = get_current_username()
        for result in st.session_state.current_results:
            if not result.created_by:
                result.created_by = username
            if not result.department:
                result.department = "default"
        
        all_results = load_simulation_results()
        all_results.extend(st.session_state.current_results)
        save_simulation_results(all_results)


def save_current_schemes(params_list):
    saved = load_simulation_params()
    saved.extend(params_list)
    save_simulation_params(saved)
    st.success("方案已保存！")


def show_results(results):
    st.subheader("📊 模拟结果")
    
    comparison = compare_results(results)
    
    has_evaluation = any(r.threshold_evaluation is not None for r in results)
    
    if has_evaluation:
        st.subheader("🎯 阈值评估概览")
        status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
        
        eval_cols = st.columns(len(results))
        for i, result in enumerate(results):
            with eval_cols[i]:
                if result.threshold_evaluation:
                    eval_obj = result.threshold_evaluation
                    status = eval_obj.overall_status
                    st.metric(
                        label=f"{result.params_name}",
                        value=f"{status_colors.get(status, '⚪')} {status}",
                        delta=f"评分: {eval_obj.overall_score:.1f}"
                    )
                    st.caption(eval_obj.conclusion_summary)
    
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    for i, name in enumerate(comparison["names"]):
        with col1 if i % 4 == 0 else col2 if i % 4 == 1 else col3 if i % 4 == 2 else col4:
            st.metric(
                label=f"{name} - 平均等待",
                value=f"{comparison['avg_wait_times'][i]:.2f} 分钟"
            )
    
    st.markdown("---")
    
    comp_data = {
        "方案": comparison["names"],
        "平均等待时长(分钟)": [round(x, 2) for x in comparison["avg_wait_times"]],
        "最大等待时长(分钟)": [round(x, 2) for x in comparison["max_wait_times"]],
        "总接待量": [round(x, 2) for x in comparison["total_receptions"]],
        "预估成本(元)": [round(x, 2) for x in comparison["cost_estimates"]]
    }
    
    if has_evaluation:
        status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
        comp_data["评估状态"] = []
        comp_data["评估评分"] = []
        comp_data["推荐优先级"] = []
        for r in results:
            if r.threshold_evaluation:
                comp_data["评估状态"].append(f"{status_colors.get(r.threshold_evaluation.overall_status, '⚪')} {r.threshold_evaluation.overall_status}")
                comp_data["评估评分"].append(round(r.threshold_evaluation.overall_score, 1))
                comp_data["推荐优先级"].append(r.threshold_evaluation.recommendation_priority)
            else:
                comp_data["评估状态"].append("-")
                comp_data["评估评分"].append("-")
                comp_data["推荐优先级"].append("-")
    
    comp_df = pd.DataFrame(comp_data)
    
    st.subheader("📋 方案对比表")
    st.dataframe(comp_df, use_container_width=True, hide_index=True)
    
    if has_evaluation:
        st.markdown("---")
        st.subheader("🎯 详细阈值评估")
        
        for i, result in enumerate(results):
            if result.threshold_evaluation:
                eval_obj = result.threshold_evaluation
                status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
                
                with st.expander(f"📊 {result.params_name} - {status_colors.get(eval_obj.overall_status, '⚪')} {eval_obj.overall_status} (评分: {eval_obj.overall_score:.1f})", expanded=True):
                    col_metrics = st.columns(5)
                    
                    metrics_config = [
                        ("平均等待时长", eval_obj.avg_wait_time_status, eval_obj.avg_wait_time_reason),
                        ("最大等待时长", eval_obj.max_wait_time_status, eval_obj.max_wait_time_reason),
                        ("总接待量", eval_obj.total_reception_status, eval_obj.total_reception_reason),
                        ("预估成本", eval_obj.cost_estimate_status, eval_obj.cost_estimate_reason),
                        ("单位成本", eval_obj.unit_cost_status, eval_obj.unit_cost_reason)
                    ]
                    
                    for j, (metric_name, status, reason) in enumerate(metrics_config):
                        with col_metrics[j]:
                            color = status_colors.get(status, "⚪")
                            st.markdown(f"**{metric_name}**")
                            st.markdown(f"{color} **{status}**")
                            st.caption(reason)
                    
                    st.markdown("---")
                    st.markdown("**🔑 关键问题说明**")
                    for idx, reason in enumerate(eval_obj.key_reasons, 1):
                        st.write(f"{idx}. {reason}")
    
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["等待时长趋势", "接待量趋势", "多指标对比"])
    
    with tab1:
        st.subheader("⏱️ 等待时长趋势 (含移动平均线)")
        fig_wait = go.Figure()
        colors = px.colors.qualitative.Plotly
        
        for i, result in enumerate(results):
            color = colors[i % len(colors)]
            fig_wait.add_trace(go.Scatter(
                x=result.timestamps,
                y=result.wait_times,
                mode='lines',
                line=dict(color=color, width=1, dash='dash'),
                name=f"{result.params_name} - 原始",
                opacity=0.5
            ))
            fig_wait.add_trace(go.Scatter(
                x=result.timestamps,
                y=result.wait_time_ma,
                mode='lines',
                line=dict(color=color, width=3),
                name=f"{result.params_name} - MA平滑"
            ))
        
        fig_wait.update_layout(
            xaxis_title="时间 (分钟)",
            yaxis_title="等待时长 (分钟)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_wait, use_container_width=True)
    
    with tab2:
        st.subheader("📈 接待量趋势 (含移动平均线)")
        fig_recep = go.Figure()
        
        for i, result in enumerate(results):
            color = colors[i % len(colors)]
            fig_recep.add_trace(go.Scatter(
                x=result.timestamps,
                y=result.reception_volumes,
                mode='lines',
                line=dict(color=color, width=1, dash='dash'),
                name=f"{result.params_name} - 原始",
                opacity=0.5
            ))
            fig_recep.add_trace(go.Scatter(
                x=result.timestamps,
                y=result.reception_ma,
                mode='lines',
                line=dict(color=color, width=3),
                name=f"{result.params_name} - MA平滑"
            ))
        
        fig_recep.update_layout(
            xaxis_title="时间 (分钟)",
            yaxis_title="接待量 (人/分钟)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_recep, use_container_width=True)
    
    with tab3:
        st.subheader("📊 多指标对比")
        col_a, col_b = st.columns(2)
        
        with col_a:
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=comparison["names"],
                y=comparison["avg_wait_times"],
                name="平均等待时长",
                marker_color='indianred'
            ))
            fig_bar.update_layout(title="平均等待时长对比", yaxis_title="分钟")
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col_b:
            fig_bar2 = go.Figure()
            fig_bar2.add_trace(go.Bar(
                x=comparison["names"],
                y=comparison["total_receptions"],
                name="总接待量",
                marker_color='lightsalmon'
            ))
            fig_bar2.update_layout(title="总接待量对比", yaxis_title="人数")
            st.plotly_chart(fig_bar2, use_container_width=True)
    
    st.markdown("---")
    st.subheader("💾 导出结果")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        if st.button("📤 导出对比汇总 (CSV)", use_container_width=True):
            filepath = export_results_to_csv(results)
            if filepath:
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    st.download_button(
                        label="⬇️ 下载汇总报告",
                        data=f.read(),
                        file_name=os.path.basename(filepath),
                        mime="text/csv",
                        use_container_width=True
                    )
    
    with col_exp2:
        selected_for_detail = st.selectbox("选择方案导出详细数据", options=[r.params_name for r in results])
        if st.button("📤 导出详细数据 (CSV)", use_container_width=True):
            idx = [r.params_name for r in results].index(selected_for_detail)
            filepath = export_detailed_results(results[idx])
            if filepath:
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    st.download_button(
                        label="⬇️ 下载详细数据",
                        data=f.read(),
                        file_name=os.path.basename(filepath),
                        mime="text/csv",
                        use_container_width=True
                    )


if __name__ == "__main__":
    main()

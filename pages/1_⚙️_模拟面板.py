import streamlit as st
import sys
import os
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import SimulationParams
from core.simulation import run_simulation, compare_results
from data.persistence import (
    load_schedule_data,
    load_simulation_params,
    save_simulation_params,
    load_simulation_results,
    save_simulation_results,
    export_results_to_csv,
    export_detailed_results,
    ensure_dirs
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
    
    results = []
    for params in params_list:
        result = run_simulation(params, staff_counts, ma_window=10)
        results.append(result)
    
    st.session_state.current_results = results
    
    if save_to_history:
        save_current_results_to_history()


def save_current_results_to_history():
    if st.session_state.current_results:
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
    
    col1, col2, col3, col4 = st.columns(4)
    
    for i, name in enumerate(comparison["names"]):
        with col1 if i % 4 == 0 else col2 if i % 4 == 1 else col3 if i % 4 == 2 else col4:
            st.metric(
                label=f"{name} - 平均等待",
                value=f"{comparison['avg_wait_times'][i]:.2f} 分钟"
            )
    
    st.markdown("---")
    
    comp_df = pd.DataFrame({
        "方案": comparison["names"],
        "平均等待时长(分钟)": [round(x, 2) for x in comparison["avg_wait_times"]],
        "最大等待时长(分钟)": [round(x, 2) for x in comparison["max_wait_times"]],
        "总接待量": [round(x, 2) for x in comparison["total_receptions"]],
        "预估成本(元)": [round(x, 2) for x in comparison["cost_estimates"]]
    })
    
    st.subheader("📋 方案对比表")
    st.dataframe(comp_df, use_container_width=True, hide_index=True)
    
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

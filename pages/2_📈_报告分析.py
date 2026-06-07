import streamlit as st
import sys
import os
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.simulation import compare_results
from data.persistence import (
    load_simulation_results,
    load_simulation_params,
    export_results_to_csv,
    export_detailed_results,
    ensure_dirs
)


st.set_page_config(page_title="报告分析", page_icon="📈", layout="wide")


def check_permission(permission: str) -> bool:
    auth_manager = st.session_state.get("auth_manager")
    if auth_manager is None:
        return False
    return auth_manager.has_permission(permission)


def main():
    st.title("📈 报告分析")
    st.markdown("---")
    
    if not check_permission("view_reports"):
        st.warning("⚠️ 您没有权限访问此页面。请登录后查看。")
        return
    
    ensure_dirs()
    
    try:
        results = load_simulation_results()
    except Exception as e:
        st.error(f"加载模拟结果失败: {e}")
        results = []
    
    try:
        params = load_simulation_params()
    except Exception as e:
        params = []
    
    if not results:
        st.info("📭 暂无模拟结果数据。请先到「模拟面板」运行模拟。")
        return
    
    st.subheader("📋 历史模拟结果列表")
    
    result_items = []
    for i, r in enumerate(results):
        try:
            result_items.append({
                "index": i,
                "name": r.params_name,
                "created_at": r.created_at[:19] if r.created_at else "",
                "avg_wait": round(r.avg_wait_time, 2) if r.avg_wait_time else 0,
                "max_wait": round(r.max_wait_time, 2) if r.max_wait_time else 0,
                "total_recep": round(r.total_reception, 2) if r.total_reception else 0,
                "cost": round(r.cost_estimate, 2) if r.cost_estimate else 0
            })
        except Exception:
            continue
    
    if not result_items:
        st.info("📭 暂无有效的模拟结果数据。")
        return
    
    df_results = pd.DataFrame(result_items)
    df_results.columns = ["序号", "方案名称", "创建时间", "平均等待(分)", "最大等待(分)", "总接待量", "预估成本(元)"]
    
    event = st.dataframe(
        df_results,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row"
    )
    
    selected_indices = []
    if event.selection and hasattr(event.selection, 'rows') and event.selection.rows is not None:
        selected_indices = event.selection.rows
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("📊 分析选中方案", use_container_width=True, disabled=len(selected_indices) == 0):
            st.session_state.selected_results = [results[i] for i in selected_indices]
    
    with col2:
        if st.button("📤 导出选中方案CSV", use_container_width=True, disabled=len(selected_indices) == 0):
            selected_results = [results[i] for i in selected_indices]
            filepath = export_results_to_csv(selected_results)
            if filepath:
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    st.download_button(
                        label="⬇️ 下载报告",
                        data=f.read(),
                        file_name=os.path.basename(filepath),
                        mime="text/csv",
                        use_container_width=True
                    )
    
    if "selected_results" in st.session_state and st.session_state.selected_results:
        st.markdown("---")
        show_analysis(st.session_state.selected_results)
    elif len(results) >= 2:
        st.markdown("---")
        st.info("💡 提示：选择2个以上方案进行对比分析")
        show_analysis(results[-2:])


def show_analysis(results):
    st.subheader("📊 方案分析详情")
    
    comparison = compare_results(results)
    
    metrics_col = st.columns(4)
    metrics = [
        ("平均等待时长", comparison["avg_wait_times"], "分钟"),
        ("最大等待时长", comparison["max_wait_times"], "分钟"),
        ("总接待量", comparison["total_receptions"], "人"),
        ("预估成本", comparison["cost_estimates"], "元")
    ]
    
    for i, (metric_name, values, unit) in enumerate(metrics):
        with metrics_col[i]:
            st.metric(
                label=metric_name,
                value=f"{values[0]:.2f} {unit}" if len(values) > 0 else "-",
                delta=f"{values[-1] - values[0]:.2f} {unit}" if len(values) >= 2 else None
            )
    
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["等待时长趋势", "接待量趋势", "成本效益分析", "详细数据"])
    
    colors = px.colors.qualitative.Plotly
    
    with tab1:
        st.subheader("⏱️ 等待时长趋势分析 (移动平均线)")
        fig = go.Figure()
        
        for i, result in enumerate(results):
            color = colors[i % len(colors)]
            fig.add_trace(go.Scatter(
                x=result.timestamps,
                y=result.wait_time_ma,
                mode='lines',
                line=dict(color=color, width=3),
                name=f"{result.params_name} - 等待MA"
            ))
        
        fig.update_layout(
            xaxis_title="时间 (分钟)",
            yaxis_title="等待时长 (分钟)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.info("📌 **移动平均线 (MA)**: 通过滑动窗口平均算法平滑原始数据，更好地展示整体趋势，减少随机波动干扰。")
    
    with tab2:
        st.subheader("📈 接待量趋势分析 (移动平均线)")
        fig = go.Figure()
        
        for i, result in enumerate(results):
            color = colors[i % len(colors)]
            fig.add_trace(go.Scatter(
                x=result.timestamps,
                y=result.reception_ma,
                mode='lines',
                line=dict(color=color, width=3),
                name=f"{result.params_name} - 接待MA"
            ))
        
        fig.update_layout(
            xaxis_title="时间 (分钟)",
            yaxis_title="接待量 (人/分钟)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("💰 成本效益分析")
        col_a, col_b = st.columns(2)
        
        with col_a:
            cost_efficiency = []
            for r in results:
                if r.total_reception > 0:
                    efficiency = r.cost_estimate / r.total_reception
                else:
                    efficiency = 0
                cost_efficiency.append(efficiency)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=comparison["names"],
                y=cost_efficiency,
                marker_color=colors[:len(results)],
                text=[f"¥{x:.2f}/人" for x in cost_efficiency],
                textposition='auto'
            ))
            fig.update_layout(
                title="单位接待成本",
                yaxis_title="元/人",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col_b:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=comparison["cost_estimates"],
                y=comparison["avg_wait_times"],
                mode='markers+text',
                marker=dict(size=15, color=colors[:len(results)]),
                text=comparison["names"],
                textposition="top center"
            ))
            fig.update_layout(
                title="成本 vs 平均等待时长",
                xaxis_title="预估成本 (元)",
                yaxis_title="平均等待时长 (分钟)",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("📋 详细数据对比")
        
        detail_df = pd.DataFrame({
            "方案名称": comparison["names"],
            "平均等待时长(分钟)": [round(x, 2) for x in comparison["avg_wait_times"]],
            "最大等待时长(分钟)": [round(x, 2) for x in comparison["max_wait_times"]],
            "总接待量": [round(x, 2) for x in comparison["total_receptions"]],
            "预估成本(元)": [round(x, 2) for x in comparison["cost_estimates"]],
            "单位成本(元/人)": [round(c / t if t > 0 else 0, 2) for c, t in zip(comparison["cost_estimates"], comparison["total_receptions"])]
        })
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
        
        st.subheader("📥 单方案详细数据导出")
        selected = st.selectbox("选择方案导出详细数据", options=[r.params_name for r in results])
        if st.button("导出详细数据"):
            idx = [r.params_name for r in results].index(selected)
            filepath = export_detailed_results(results[idx])
            if filepath:
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    st.download_button(
                        label="⬇️ 下载详细CSV",
                        data=f.read(),
                        file_name=os.path.basename(filepath),
                        mime="text/csv"
                    )


if __name__ == "__main__":
    main()

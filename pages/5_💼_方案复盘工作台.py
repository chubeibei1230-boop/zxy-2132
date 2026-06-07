import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import BaselineScheme, ReviewRecord, SimulationResult, ThresholdConfig
from core.simulation import perform_review_comparison, calculate_unit_cost, evaluate_threshold, generate_review_threshold_conclusion
from data.persistence import (
    load_simulation_results,
    load_baseline_schemes,
    add_baseline_scheme,
    get_baseline_by_id,
    load_review_records,
    add_review_record,
    update_review_record,
    delete_review_record,
    get_review_by_id,
    export_review_report,
    ensure_dirs,
    load_threshold_templates,
    get_threshold_template_by_id,
    get_default_threshold_template
)


st.set_page_config(page_title="方案复盘工作台", page_icon="💼", layout="wide")


def check_permission(permission: str) -> bool:
    auth_manager = st.session_state.get("auth_manager")
    if auth_manager is None:
        return False
    return auth_manager.has_permission(permission)


def get_current_username() -> str:
    auth_manager = st.session_state.get("auth_manager")
    if auth_manager and auth_manager.get_current_user():
        return auth_manager.get_current_user().username
    return ""


def get_current_user_role() -> str:
    auth_manager = st.session_state.get("auth_manager")
    if auth_manager and auth_manager.get_current_user():
        return auth_manager.get_current_user().role
    return ""


def can_create_review() -> bool:
    role = get_current_user_role()
    if role == "admin":
        return True
    if role == "user" and check_permission("create_review"):
        return True
    return False


def can_view_all_reviews() -> bool:
    role = get_current_user_role()
    return role in ["admin", "auditor"]


def can_manage_own_review(review_creator: str) -> bool:
    role = get_current_user_role()
    if role == "admin":
        return True
    if role == "user" and review_creator == get_current_username():
        return True
    return False


def main():
    st.title("💼 方案复盘工作台")
    st.markdown("---")
    
    if not check_permission("view_reports"):
        st.warning("⚠️ 您没有权限访问此页面。请登录后查看。")
        return
    
    ensure_dirs()
    
    tab1, tab2, tab3 = st.tabs([
        "🚀 复盘工作流",
        "📋 复盘记录管理",
        "📊 复盘数据分析"
    ])
    
    with tab1:
        show_review_workflow()
    
    with tab2:
        show_review_records_management()
    
    with tab3:
        show_review_analytics()


def show_workflow_guide():
    st.info("""
    ### 📋 复盘工作流程
    
    **完整闭环：** 运行模拟 → 查看报告 → 设置基线 → 生成复盘 → 导出结论
    
    **步骤说明：**
    1. **选择基线方案** - 从已设置的基线方案中选择一个作为对比基准
    2. **选择对比方案** - 批量选择多个待对比的历史模拟方案
    3. **配置复盘参数** - 设置复盘名称、备注、阈值模板等
    4. **生成复盘结果** - 系统自动计算各方案相对基线的指标差异
    5. **查看对比详情** - 分析各方案在等待时长、接待量、成本等方面的表现
    6. **保存复盘记录** - 将复盘结果保存以便后续查看和审计
    7. **导出复盘报告** - 导出CSV格式的复盘报告
    """)


def show_review_workflow():
    st.subheader("🚀 复盘工作流")
    
    show_workflow_guide()
    
    st.markdown("---")
    
    can_create = can_create_review()
    
    if not can_create:
        st.info("🔒 您只有查看权限，无法发起新的复盘。如有需要请联系管理员或普通用户。")
    
    try:
        all_results = load_simulation_results()
    except Exception as e:
        st.error(f"加载模拟结果失败: {e}")
        all_results = []
    
    try:
        baselines = load_baseline_schemes()
    except Exception as e:
        st.error(f"加载基线方案失败: {e}")
        baselines = []
    
    active_baselines = [b for b in baselines if b.is_active]
    current_user = get_current_username()
    current_role = get_current_user_role()
    
    if current_role != "admin":
        active_baselines = [b for b in active_baselines if b.created_by == current_user or current_role == "auditor"]
    
    if not active_baselines:
        st.warning("⚠️ 暂无可用的基线方案。请先到「基线方案复盘」→「基线方案管理」中设置基线。")
        return
    
    if len(all_results) < 2:
        st.warning("⚠️ 历史模拟结果不足，无法进行多方案对比。请先运行模拟并保存结果。")
        return
    
    st.markdown("### 第1步：选择基线方案")
    
    col_bl1, col_bl2 = st.columns([2, 1])
    
    with col_bl1:
        baseline_options = []
        for b in active_baselines:
            snapshot = b.result_snapshot or {}
            label = f"🎯 {b.name} (创建人: {b.created_by}, 平均等待: {snapshot.get('avg_wait_time', 0):.2f}分)"
            baseline_options.append((label, b))
        
        selected_bl_label = st.selectbox(
            "选择作为基准的基线方案",
            options=[opt[0] for opt in baseline_options],
            key="workflow_baseline_select"
        )
        
        selected_baseline = None
        for label, b in baseline_options:
            if label == selected_bl_label:
                selected_baseline = b
                break
    
    baseline_result = None
    if selected_baseline:
        for r in all_results:
            if r.id == selected_baseline.result_id:
                baseline_result = r
                break
        
        if baseline_result is None:
            st.error("❌ 基线对应的原始模拟结果已被删除，无法进行复盘。请重新设置基线。")
            return
        
        with col_bl2:
            st.markdown("**基线方案概览**")
            bl_snapshot = selected_baseline.result_snapshot or {}
            st.caption(f"部门: {selected_baseline.department}")
            st.caption(f"创建时间: {selected_baseline.created_at[:19] if selected_baseline.created_at else ''}")
            if selected_baseline.description:
                st.caption(f"描述: {selected_baseline.description}")
    
    if baseline_result:
        st.markdown("### 第2步：选择对比方案")
        
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        
        with col_filter1:
            departments = sorted(list(set([r.department for r in all_results if r.department])))
            departments = ["全部"] + departments
            dept_filter = st.selectbox("按部门筛选方案", options=departments, key="workflow_dept_filter")
        
        with col_filter2:
            date_options = ["全部", "最近7天", "最近30天", "最近90天"]
            date_filter = st.selectbox("按时间筛选方案", options=date_options, key="workflow_date_filter")
        
        with col_filter3:
            templates = load_threshold_templates()
            template_options = [(t.id, f"{t.name} {'(默认)' if t.is_default else ''}") for t in templates]
            template_ids = [t[0] for t in template_options]
            template_labels = [t[1] for t in template_options]
            
            default_template = get_default_threshold_template()
            default_idx = 0
            if default_template and default_template.id in template_ids:
                default_idx = template_ids.index(default_template.id)
            
            selected_template_label = st.selectbox(
                "选择阈值模板用于评估",
                options=template_labels,
                index=default_idx,
                key="workflow_threshold_template"
            )
            selected_template_id = template_ids[template_labels.index(selected_template_label)]
            selected_threshold = get_threshold_template_by_id(selected_template_id)
        
        filtered_results = [r for r in all_results if r.id != baseline_result.id]
        
        if dept_filter != "全部":
            filtered_results = [r for r in filtered_results if r.department == dept_filter]
        
        if date_filter != "全部":
            days_map = {"最近7天": 7, "最近30天": 30, "最近90天": 90}
            days = days_map.get(date_filter, 0)
            if days > 0:
                cutoff = datetime.now() - timedelta(days=days)
                filtered_results = [
                    r for r in filtered_results
                    if r.created_at and datetime.fromisoformat(r.created_at) >= cutoff
                ]
        
        name_keyword = st.text_input(
            "🔍 按方案名称搜索",
            placeholder="输入方案名称关键词进行筛选...",
            key="workflow_name_search"
        )
        if name_keyword:
            filtered_results = [
                r for r in filtered_results
                if name_keyword.lower() in r.params_name.lower()
            ]
        
        if not filtered_results:
            st.info("📭 没有符合筛选条件的模拟结果（基线方案已自动排除）。")
            return
        
        status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
        result_display = []
        for r in filtered_results:
            status_display = "-"
            score_display = "-"
            if r.threshold_evaluation:
                status = r.threshold_evaluation.overall_status
                status_display = f"{status_colors.get(status, '⚪')} {status}"
                score_display = f"{r.threshold_evaluation.overall_score:.1f}"
            
            result_display.append({
                "id": r.id,
                "方案名称": r.params_name,
                "创建时间": r.created_at[:19] if r.created_at else "",
                "创建人": r.created_by or "-",
                "部门": r.department or "-",
                "平均等待": f"{r.avg_wait_time:.2f}分",
                "总接待量": f"{r.total_reception:.0f}人",
                "预估成本": f"{r.cost_estimate:.2f}元",
                "评估状态": status_display,
                "评估评分": score_display
            })
        
        df_results = pd.DataFrame(result_display)
        df_show = df_results.drop(columns=["id"])
        
        st.markdown(f"**共找到 {len(filtered_results)} 个可对比方案，请选择要复盘的方案（支持多选）：**")
        
        event = st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key="workflow_result_select"
        )
        
        selected_indices = []
        if event.selection and hasattr(event.selection, 'rows') and event.selection.rows is not None:
            selected_indices = event.selection.rows
        
        selected_results = [filtered_results[i] for i in selected_indices]
        
        if selected_results:
            st.success(f"✅ 已选择 {len(selected_results)} 个方案进行对比复盘")
        else:
            st.info("💡 请在上方表格中选择至少一个方案进行对比")
        
        st.markdown("### 第3步：配置复盘信息")
        
        col_cfg1, col_cfg2 = st.columns(2)
        
        with col_cfg1:
            default_review_name = f"复盘-{selected_baseline.name}-{datetime.now().strftime('%Y%m%d')}"
            review_name = st.text_input(
                "复盘名称 *",
                value=default_review_name,
                placeholder="请输入本次复盘的名称",
                key="workflow_review_name"
            )
        
        with col_cfg2:
            review_remarks = st.text_input(
                "备注（可选）",
                placeholder="添加复盘备注说明...",
                key="workflow_review_remarks"
            )
        
        st.markdown("### 第4步：生成复盘结果")
        
        generate_disabled = not selected_results or not baseline_result or not review_name or not can_create
        
        if st.button(
            "🔍 开始生成复盘对比",
            use_container_width=True,
            type="primary",
            disabled=generate_disabled,
            key="workflow_generate_btn"
        ):
            if can_create and selected_results and baseline_result and review_name:
                with st.spinner("正在生成复盘对比结果..."):
                    comparison_items = perform_review_comparison(baseline_result, selected_results)
                    
                    if selected_threshold:
                        for item in comparison_items:
                            result_for_eval = None
                            for r in selected_results:
                                if r.id == item.result_id:
                                    result_for_eval = r
                                    break
                            
                            if result_for_eval:
                                evaluation = evaluate_threshold(result_for_eval, selected_threshold)
                                item.threshold_evaluation = evaluation
                                item.threshold_conclusion = generate_review_threshold_conclusion(item, evaluation)
                    
                    st.session_state.workflow_review_items = comparison_items
                    st.session_state.workflow_review_baseline = selected_baseline
                    st.session_state.workflow_review_baseline_result = baseline_result
                    st.session_state.workflow_review_name = review_name
                    st.session_state.workflow_review_remarks = review_remarks
                    st.session_state.workflow_review_threshold = selected_threshold
                    st.success("✅ 复盘对比结果已生成！")
            elif not can_create:
                st.warning("⚠️ 您没有权限发起复盘对比。")
        
        if "workflow_review_items" in st.session_state and st.session_state.workflow_review_items:
            st.markdown("---")
            show_workflow_review_results()


def show_workflow_review_results():
    st.subheader("📈 复盘对比结果")
    
    items = st.session_state.workflow_review_items
    baseline = st.session_state.workflow_review_baseline
    baseline_result = st.session_state.workflow_review_baseline_result
    threshold = st.session_state.get("workflow_review_threshold")
    
    if not items:
        return
    
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.info(f"🎯 **基线方案**: {baseline.name}")
    with col_info2:
        st.info(f"📊 **对比方案数**: {len(items)} 个")
    with col_info3:
        if threshold:
            st.info(f"⚙️ **阈值模板**: {threshold.name}")
    
    baseline_unit_cost = calculate_unit_cost(baseline_result)
    
    st.markdown("#### 📊 基线方案核心指标")
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    with col_m1:
        st.metric("平均等待", f"{baseline_result.avg_wait_time:.2f} 分钟")
    with col_m2:
        st.metric("最大等待", f"{baseline_result.max_wait_time:.2f} 分钟")
    with col_m3:
        st.metric("总接待量", f"{baseline_result.total_reception:.0f} 人")
    with col_m4:
        st.metric("预估成本", f"{baseline_result.cost_estimate:.2f} 元")
    with col_m5:
        st.metric("单位成本", f"{baseline_unit_cost:.2f} 元/人")
    
    st.markdown("---")
    st.markdown("#### 📋 方案对比总表")
    
    has_threshold = any(item.threshold_evaluation is not None for item in items)
    status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
    
    comparison_data = []
    for rank, item in enumerate(items, 1):
        conclusion_color = {
            "更优": "🟢",
            "持平": "🟡",
            "退化": "🔴"
        }.get(item.conclusion, "⚪")
        
        row_data = {
            "排名": rank,
            "方案名称": item.result_name,
            "平均等待差异": f"{item.avg_wait_time_diff:+.2f}分",
            "平均等待变化": f"{item.avg_wait_time_change_rate:+.2%}",
            "最大等待差异": f"{item.max_wait_time_diff:+.2f}分",
            "最大等待变化": f"{item.max_wait_time_change_rate:+.2%}",
            "总接待量差异": f"{item.total_reception_diff:+.0f}人",
            "总接待量变化": f"{item.total_reception_change_rate:+.2%}",
            "成本差异": f"{item.cost_estimate_diff:+.2f}元",
            "成本变化": f"{item.cost_estimate_change_rate:+.2%}",
            "单位成本差异": f"{item.unit_cost_diff:+.2f}元/人",
            "单位成本变化": f"{item.unit_cost_change_rate:+.2%}",
            "综合结论": f"{conclusion_color} {item.conclusion}",
            "综合评分": f"{item.score:.2f}"
        }
        
        if has_threshold:
            if item.threshold_evaluation:
                row_data["阈值状态"] = f"{status_colors.get(item.threshold_evaluation.overall_status, '⚪')} {item.threshold_evaluation.overall_status}"
                row_data["阈值评分"] = f"{item.threshold_evaluation.overall_score:.1f}"
                row_data["复盘结论"] = item.threshold_conclusion or "-"
            else:
                row_data["阈值状态"] = "-"
                row_data["阈值评分"] = "-"
                row_data["复盘结论"] = "-"
        
        comparison_data.append(row_data)
    
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("#### 🔍 各方案详细分析")
    
    for rank, item in enumerate(items, 1):
        conclusion_emoji = {
            "更优": "🟢",
            "持平": "🟡",
            "退化": "🔴"
        }.get(item.conclusion, "⚪")
        
        expander_title = f"#{rank} {item.result_name} - {conclusion_emoji} {item.conclusion} (综合评分: {item.score:.2f})"
        
        if item.threshold_evaluation:
            threshold_status = item.threshold_evaluation.overall_status
            expander_title += f" | {status_colors.get(threshold_status, '⚪')} 阈值: {threshold_status}"
        
        with st.expander(expander_title, expanded=(rank == 1)):
            if item.threshold_conclusion:
                st.markdown("### 📊 阈值复盘结论")
                st.success(f"**{item.threshold_conclusion}**")
                st.markdown("---")
            
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                st.markdown("**⏱️ 等待时长表现**")
                wait_text = "✅ 减少" if item.avg_wait_time_diff < 0 else "⚠️ 增加" if item.avg_wait_time_diff > 0 else "➖ 持平"
                st.info(f"{wait_text} {abs(item.avg_wait_time_diff):.2f} 分钟 ({item.avg_wait_time_change_rate:+.2%})")
                max_wait_text = "✅ 减少" if item.max_wait_time_diff < 0 else "⚠️ 增加" if item.max_wait_time_diff > 0 else "➖ 持平"
                st.info(f"最大等待 {max_wait_text} {abs(item.max_wait_time_diff):.2f} 分钟")
            
            with col_b:
                st.markdown("**👥 接待能力表现**")
                recep_text = "✅ 提升" if item.total_reception_diff > 0 else "⚠️ 下降" if item.total_reception_diff < 0 else "➖ 持平"
                st.success(f"总接待量 {recep_text} {abs(item.total_reception_diff):.0f} 人 ({item.total_reception_change_rate:+.2%})")
            
            with col_c:
                st.markdown("**💰 成本效益表现**")
                cost_text = "✅ 降低" if item.cost_estimate_diff < 0 else "⚠️ 增加" if item.cost_estimate_diff > 0 else "➖ 持平"
                st.warning(f"总成本 {cost_text} {abs(item.cost_estimate_diff):.2f} 元")
                unit_text = "✅ 降低" if item.unit_cost_diff < 0 else "⚠️ 增加" if item.unit_cost_diff > 0 else "➖ 持平"
                st.warning(f"单位成本 {unit_text} {abs(item.unit_cost_diff):.2f} 元/人")
            
            if item.threshold_evaluation:
                st.markdown("---")
                st.markdown("**🎯 阈值评估详情**")
                col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)
                
                eval_obj = item.threshold_evaluation
                threshold_metrics = [
                    ("平均等待", eval_obj.avg_wait_time_status, eval_obj.avg_wait_time_reason),
                    ("最大等待", eval_obj.max_wait_time_status, eval_obj.max_wait_time_reason),
                    ("总接待量", eval_obj.total_reception_status, eval_obj.total_reception_reason),
                    ("预估成本", eval_obj.cost_estimate_status, eval_obj.cost_estimate_reason),
                    ("单位成本", eval_obj.unit_cost_status, eval_obj.unit_cost_reason)
                ]
                
                for j, (metric_name, status, reason) in enumerate(threshold_metrics):
                    with [col_t1, col_t2, col_t3, col_t4, col_t5][j]:
                        color = status_colors.get(status, "⚪")
                        st.markdown(f"**{metric_name}**")
                        st.markdown(f"{color} **{status}**")
                        st.caption(reason)
    
    st.markdown("---")
    st.markdown("### 第5步：保存与导出")
    
    col_save, col_export, col_clear = st.columns(3)
    
    with col_save:
        if can_create_review():
            if st.button("💾 保存复盘记录", use_container_width=True, key="workflow_save_btn"):
                review_name = st.session_state.get("workflow_review_name", "")
                review_remarks = st.session_state.get("workflow_review_remarks", "")
                
                if review_name:
                    new_review = ReviewRecord(
                        name=review_name,
                        baseline_id=baseline.id,
                        baseline_name=baseline.name,
                        comparison_items=items,
                        created_by=get_current_username(),
                        department=baseline.department,
                        remarks=review_remarks,
                        status="已完成"
                    )
                    
                    if add_review_record(new_review):
                        st.success("✅ 复盘记录已保存！可在「复盘记录管理」中查看")
                    else:
                        st.error("保存复盘记录失败，请重试。")
        else:
            st.info("🔒 您没有权限保存复盘记录。")
    
    with col_export:
        if check_permission("export"):
            if st.button("📤 导出复盘报告", use_container_width=True, key="workflow_export_btn"):
                review_name = st.session_state.get("workflow_review_name", "未命名复盘")
                review_remarks = st.session_state.get("workflow_review_remarks", "")
                
                temp_review = ReviewRecord(
                    name=review_name,
                    baseline_id=baseline.id,
                    baseline_name=baseline.name,
                    comparison_items=items,
                    created_by=get_current_username(),
                    department=baseline.department,
                    remarks=review_remarks
                )
                
                filepath = export_review_report(temp_review)
                if filepath:
                    with open(filepath, "r", encoding="utf-8-sig") as f:
                        st.download_button(
                            label="⬇️ 下载复盘报告CSV",
                            data=f.read(),
                            file_name=os.path.basename(filepath),
                            mime="text/csv",
                            use_container_width=True
                        )
        else:
            st.info("🔒 您没有权限导出报告。")
    
    with col_clear:
        if st.button("🗑️ 清除当前复盘结果", use_container_width=True, key="workflow_clear_btn"):
            for key in ["workflow_review_items", "workflow_review_baseline", "workflow_review_baseline_result", 
                        "workflow_review_name", "workflow_review_remarks", "workflow_review_threshold"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()


def show_review_records_management():
    st.subheader("📋 复盘记录管理")
    
    current_user = get_current_username()
    current_role = get_current_user_role()
    can_view_all = can_view_all_reviews()
    
    try:
        reviews = load_review_records()
    except Exception as e:
        st.error(f"加载复盘记录失败: {e}")
        reviews = []
    
    if not can_view_all:
        reviews = [r for r in reviews if r.created_by == current_user]
    
    st.markdown("### 🔍 筛选条件")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        creators = sorted(list(set([r.created_by for r in reviews if r.created_by])))
        creators = ["全部"] + creators
        creator_filter = st.selectbox("按创建人筛选", options=creators, key="record_creator_filter")
    
    with col_f2:
        date_options = ["全部", "最近7天", "最近30天", "最近90天"]
        date_filter = st.selectbox("按创建时间筛选", options=date_options, key="record_date_filter")
    
    with col_f3:
        name_keyword = st.text_input("按方案名称搜索", placeholder="输入复盘名称关键词...", key="record_name_filter")
    
    with col_f4:
        status_options = ["全部", "已完成", "草稿"]
        status_filter = st.selectbox("按复盘状态筛选", options=status_options, key="record_status_filter")
    
    filtered_reviews = reviews.copy()
    
    if creator_filter != "全部":
        filtered_reviews = [r for r in filtered_reviews if r.created_by == creator_filter]
    
    if date_filter != "全部":
        days_map = {"最近7天": 7, "最近30天": 30, "最近90天": 90}
        days = days_map.get(date_filter, 0)
        if days > 0:
            cutoff = datetime.now() - timedelta(days=days)
            filtered_reviews = [
                r for r in filtered_reviews
                if r.created_at and datetime.fromisoformat(r.created_at) >= cutoff
            ]
    
    if name_keyword:
        filtered_reviews = [
            r for r in filtered_reviews
            if name_keyword.lower() in r.name.lower() or name_keyword.lower() in r.baseline_name.lower()
        ]
    
    if status_filter != "全部":
        filtered_reviews = [
            r for r in filtered_reviews
            if getattr(r, 'status', '已完成') == status_filter
        ]
    
    if not filtered_reviews:
        st.info("📭 暂无符合条件的复盘记录。")
        return
    
    st.markdown(f"**共找到 {len(filtered_reviews)} 条复盘记录**")
    
    review_data = []
    for r in filtered_reviews:
        review_status = getattr(r, 'status', '已完成')
        status_color = "✅" if review_status == "已完成" else "📝"
        
        review_data.append({
            "id": r.id,
            "复盘名称": r.name,
            "基线方案": r.baseline_name,
            "对比方案数": len(r.comparison_items),
            "创建人": r.created_by,
            "创建时间": r.created_at[:19] if r.created_at else "",
            "部门": r.department,
            "状态": f"{status_color} {review_status}",
            "备注": r.remarks or "-"
        })
    
    df_reviews = pd.DataFrame(review_data)
    df_show = df_reviews.drop(columns=["id"])
    
    event = st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="records_table_select"
    )
    
    selected_idx = None
    if event.selection and hasattr(event.selection, 'rows') and event.selection.rows:
        selected_idx = event.selection.rows[0]
    
    if selected_idx is not None and 0 <= selected_idx < len(filtered_reviews):
        selected_review = filtered_reviews[selected_idx]
        st.markdown("---")
        show_review_detail(selected_review)


def show_review_detail(review: ReviewRecord):
    st.markdown(f"### 📄 复盘详情: {review.name}")
    
    col_info1, col_info2, col_info3, col_info4 = st.columns(4)
    with col_info1:
        st.info(f"🎯 基线方案: {review.baseline_name}")
    with col_info2:
        st.info(f"👤 创建人: {review.created_by}")
    with col_info3:
        st.info(f"📅 创建时间: {review.created_at[:19] if review.created_at else ''}")
    with col_info4:
        review_status = getattr(review, 'status', '已完成')
        st.info(f"📊 状态: {review_status}")
    
    if review.remarks:
        st.info(f"📝 备注: {review.remarks}")
    
    can_edit = can_manage_own_review(review.created_by)
    
    if can_edit:
        with st.expander("✏️ 编辑备注", expanded=False):
            new_remarks = st.text_area(
                "修改备注",
                value=review.remarks or "",
                key=f"edit_remarks_{review.id}"
            )
            if st.button("💾 保存备注", key=f"save_remarks_{review.id}"):
                if update_review_record(review.id, remarks=new_remarks):
                    st.success("✅ 备注已更新！")
                    st.rerun()
                else:
                    st.error("保存失败，请重试。")
    
    st.markdown("#### 📊 对比结果汇总")
    
    status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
    has_threshold = any(item.threshold_evaluation is not None for item in review.comparison_items)
    
    detail_data = []
    for rank, item in enumerate(review.comparison_items, 1):
        conclusion_color = {
            "更优": "🟢",
            "持平": "🟡",
            "退化": "🔴"
        }.get(item.conclusion, "⚪")
        
        row_data = {
            "排名": rank,
            "方案名称": item.result_name,
            "平均等待差异": f"{item.avg_wait_time_diff:+.2f}分",
            "平均等待变化": f"{item.avg_wait_time_change_rate:+.2%}",
            "总接待量差异": f"{item.total_reception_diff:+.0f}人",
            "总接待量变化": f"{item.total_reception_change_rate:+.2%}",
            "成本差异": f"{item.cost_estimate_diff:+.2f}元",
            "单位成本差异": f"{item.unit_cost_diff:+.2f}元/人",
            "综合结论": f"{conclusion_color} {item.conclusion}",
            "综合评分": f"{item.score:.2f}"
        }
        
        if has_threshold:
            if item.threshold_evaluation:
                row_data["阈值状态"] = f"{status_colors.get(item.threshold_evaluation.overall_status, '⚪')} {item.threshold_evaluation.overall_status}"
                row_data["复盘结论"] = item.threshold_conclusion or "-"
            else:
                row_data["阈值状态"] = "-"
                row_data["复盘结论"] = "-"
        
        detail_data.append(row_data)
    
    df_detail = pd.DataFrame(detail_data)
    st.dataframe(df_detail, use_container_width=True, hide_index=True)
    
    if has_threshold:
        st.markdown("#### 🎯 阈值评估详情")
        for rank, item in enumerate(review.comparison_items, 1):
            if item.threshold_evaluation:
                eval_obj = item.threshold_evaluation
                with st.expander(f"#{rank} {item.result_name} - {status_colors.get(eval_obj.overall_status, '⚪')} {eval_obj.overall_status}"):
                    if item.threshold_conclusion:
                        st.success(f"**复盘结论**: {item.threshold_conclusion}")
                    
                    col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)
                    threshold_metrics = [
                        ("平均等待", eval_obj.avg_wait_time_status, eval_obj.avg_wait_time_reason),
                        ("最大等待", eval_obj.max_wait_time_status, eval_obj.max_wait_time_reason),
                        ("总接待量", eval_obj.total_reception_status, eval_obj.total_reception_reason),
                        ("预估成本", eval_obj.cost_estimate_status, eval_obj.cost_estimate_reason),
                        ("单位成本", eval_obj.unit_cost_status, eval_obj.unit_cost_reason)
                    ]
                    
                    for j, (metric_name, status, reason) in enumerate(threshold_metrics):
                        with [col_t1, col_t2, col_t3, col_t4, col_t5][j]:
                            color = status_colors.get(status, "⚪")
                            st.markdown(f"**{metric_name}**")
                            st.markdown(f"{color} **{status}**")
                            st.caption(reason)
    
    st.markdown("---")
    
    col_export2, col_del = st.columns(2)
    with col_export2:
        if check_permission("export"):
            if st.button("📤 导出此复盘报告", use_container_width=True, key=f"export_{review.id}"):
                filepath = export_review_report(review)
                if filepath:
                    with open(filepath, "r", encoding="utf-8-sig") as f:
                        st.download_button(
                            label="⬇️ 下载报告CSV",
                            data=f.read(),
                            file_name=os.path.basename(filepath),
                            mime="text/csv",
                            use_container_width=True
                        )
        else:
            st.info("🔒 您没有权限导出报告。")
    
    with col_del:
        if get_current_user_role() == "admin" or (get_current_user_role() == "user" and review.created_by == get_current_username()):
            if st.button("🗑️ 删除此复盘", use_container_width=True, key=f"delete_{review.id}", type="secondary"):
                if delete_review_record(review.id):
                    st.success("复盘记录已删除")
                    st.rerun()


def show_review_analytics():
    st.subheader("📊 复盘数据分析")
    
    try:
        reviews = load_review_records()
    except Exception as e:
        st.error(f"加载复盘记录失败: {e}")
        reviews = []
    
    if not reviews:
        st.info("📭 暂无复盘记录，无法进行数据分析。")
        return
    
    current_user = get_current_username()
    if not can_view_all_reviews():
        reviews = [r for r in reviews if r.created_by == current_user]
    
    if not reviews:
        st.info("📭 您暂无复盘记录。")
        return
    
    st.markdown("### 📈 复盘概览统计")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        st.metric("复盘总次数", len(reviews))
    
    with col_stat2:
        total_schemes = sum(len(r.comparison_items) for r in reviews)
        st.metric("累计对比方案数", total_schemes)
    
    with col_stat3:
        unique_creators = len(set(r.created_by for r in reviews))
        st.metric("参与复盘人数", unique_creators)
    
    with col_stat4:
        if reviews:
            latest = max(r.created_at for r in reviews if r.created_at)
            st.metric("最近复盘时间", latest[:19] if latest else "-")
    
    st.markdown("---")
    st.markdown("### 🏆 方案表现排行分析")
    
    all_items = []
    for r in reviews:
        for item in r.comparison_items:
            all_items.append({
                "scheme_name": item.result_name,
                "baseline_name": r.baseline_name,
                "conclusion": item.conclusion,
                "score": item.score,
                "avg_wait_change": item.avg_wait_time_change_rate,
                "total_recep_change": item.total_reception_change_rate,
                "cost_change": item.cost_estimate_change_rate,
                "unit_cost_change": item.unit_cost_change_rate
            })
    
    if all_items:
        df_analytics = pd.DataFrame(all_items)
        
        col_analysis1, col_analysis2 = st.columns(2)
        
        with col_analysis1:
            st.markdown("**综合评分 Top 10 方案**")
            top_schemes = df_analytics.groupby("scheme_name")["score"].mean().sort_values(ascending=False).head(10)
            df_top = pd.DataFrame({
                "方案名称": top_schemes.index,
                "平均综合评分": [f"{x:.2f}" for x in top_schemes.values]
            })
            st.dataframe(df_top, use_container_width=True, hide_index=True)
        
        with col_analysis2:
            st.markdown("**复盘结论分布**")
            conclusion_counts = df_analytics["conclusion"].value_counts()
            df_conclusion = pd.DataFrame({
                "结论类型": conclusion_counts.index,
                "次数": conclusion_counts.values
            })
            st.dataframe(df_conclusion, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("**📊 各方案指标平均改善率**")
        
        avg_metrics = df_analytics.groupby("scheme_name").agg({
            "avg_wait_change": "mean",
            "total_recep_change": "mean",
            "cost_change": "mean",
            "unit_cost_change": "mean"
        }).sort_values("total_recep_change", ascending=False)
        
        avg_metrics_display = []
        for name, row in avg_metrics.iterrows():
            avg_metrics_display.append({
                "方案名称": name,
                "平均等待变化": f"{row['avg_wait_change']:+.2%}",
                "总接待量变化": f"{row['total_recep_change']:+.2%}",
                "成本变化": f"{row['cost_change']:+.2%}",
                "单位成本变化": f"{row['unit_cost_change']:+.2%}"
            })
        
        df_avg_metrics = pd.DataFrame(avg_metrics_display)
        st.dataframe(df_avg_metrics, use_container_width=True, hide_index=True)
        
        st.info("💡 **分析说明**：正的变化率表示该指标相对基线有所改善（等待时间减少为负表示改善，接待量增加为正表示改善，成本减少为负表示改善）")
    else:
        st.info("📭 暂无足够的对比数据进行分析。")


if __name__ == "__main__":
    main()

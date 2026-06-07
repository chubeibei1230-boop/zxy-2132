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
    delete_baseline_scheme,
    update_baseline_scheme,
    get_baseline_by_id,
    load_review_records,
    add_review_record,
    delete_review_record,
    export_review_report,
    ensure_dirs,
    load_threshold_templates,
    save_threshold_templates,
    add_threshold_template,
    update_threshold_template,
    delete_threshold_template,
    get_threshold_template_by_id,
    get_default_threshold_template
)


st.set_page_config(page_title="基线方案复盘", page_icon="🔍", layout="wide")


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


def can_manage_baseline() -> bool:
    role = get_current_user_role()
    if role == "admin":
        return True
    if role == "user" and check_permission("set_own_baseline"):
        return True
    return False


def can_view_all_baselines() -> bool:
    role = get_current_user_role()
    return role in ["admin", "auditor"]


def can_manage_review() -> bool:
    role = get_current_user_role()
    if role == "admin":
        return True
    if role == "user" and check_permission("create_review"):
        return True
    return False


def main():
    st.title("🔍 基线方案复盘")
    st.markdown("---")
    
    if not check_permission("view_reports"):
        st.warning("⚠️ 您没有权限访问此页面。请登录后查看。")
        return
    
    ensure_dirs()
    
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 基线方案管理", "📊 方案对比复盘", "📋 历史复盘记录", "⚙️ 阈值模板管理"])
    
    with tab1:
        manage_baseline_schemes()
    
    with tab2:
        perform_scheme_review()
    
    with tab3:
        view_review_history()
    
    with tab4:
        manage_threshold_templates()


def manage_baseline_schemes():
    st.subheader("🎯 基线方案管理")
    
    can_manage = can_manage_baseline()
    can_view_all = can_view_all_baselines()
    current_user = get_current_username()
    
    try:
        all_results = load_simulation_results()
    except Exception as e:
        st.error(f"加载模拟结果失败: {e}")
        all_results = []
    
    try:
        all_baselines = load_baseline_schemes()
        baselines = all_baselines.copy()
    except Exception as e:
        st.error(f"加载基线方案失败: {e}")
        all_baselines = []
        baselines = []
    
    if not can_view_all:
        baselines = [b for b in baselines if b.created_by == current_user]
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### ➕ 新建基线方案")
        
        if not all_results:
            st.info("📭 暂无历史模拟结果，请先运行模拟并保存结果。")
        elif not can_manage:
            st.info("🔒 您没有权限设置基线方案。")
        else:
            result_options = []
            for r in all_results:
                label = f"{r.params_name} ({r.created_at[:19] if r.created_at else ''})"
                result_options.append((label, r))
            
            selected_label = st.selectbox(
                "选择历史模拟结果",
                options=[opt[0] for opt in result_options]
            )
            
            selected_result = None
            for label, r in result_options:
                if label == selected_label:
                    selected_result = r
                    break
            
            baseline_name = st.text_input(
                "基线方案名称",
                value=f"基线-{selected_result.params_name}" if selected_result else "",
                placeholder="请输入基线方案名称"
            )
            
            baseline_desc = st.text_area(
                "基线描述（可选）",
                placeholder="描述该基线方案的背景和参考价值..."
            )
            
            department = st.text_input("部门", value="default")
            
            name_duplicate = False
            name_duplicate_detail = ""
            result_already_baseline = False
            result_baseline_detail = ""
            
            if baseline_name:
                for b in all_baselines:
                    if b.name.strip().lower() == baseline_name.strip().lower():
                        name_duplicate = True
                        name_duplicate_detail = f"创建人: {b.created_by}, 创建时间: {b.created_at[:19] if b.created_at else '未知'}"
                        break
            
            if selected_result:
                for b in all_baselines:
                    if b.result_id == selected_result.id:
                        result_already_baseline = True
                        result_baseline_detail = f"基线名称: {b.name}, 创建人: {b.created_by}"
                        break
            
            if name_duplicate:
                st.warning(f"⚠️ 已存在同名基线方案（不区分大小写）：{baseline_name}")
                st.caption(f"   详情：{name_duplicate_detail}")
            
            if result_already_baseline:
                st.warning(f"⚠️ 该模拟结果已被设置为基线方案")
                st.caption(f"   详情：{result_baseline_detail}")
            
            submit_disabled = not selected_result or not baseline_name or name_duplicate or result_already_baseline
            
            if st.button("✅ 设为基线方案", use_container_width=True, disabled=submit_disabled):
                if selected_result and baseline_name and not name_duplicate and not result_already_baseline:
                        result_snapshot = {
                            "avg_wait_time": selected_result.avg_wait_time,
                            "max_wait_time": selected_result.max_wait_time,
                            "total_reception": selected_result.total_reception,
                            "cost_estimate": selected_result.cost_estimate,
                            "unit_cost": calculate_unit_cost(selected_result)
                        }
                        
                        new_baseline = BaselineScheme(
                            name=baseline_name,
                            result_id=selected_result.id,
                            result_snapshot=result_snapshot,
                            created_by=current_user,
                            department=department,
                            description=baseline_desc,
                            is_active=True
                        )
                        
                        if add_baseline_scheme(new_baseline):
                            st.success(f"✅ 基线方案 '{baseline_name}' 设置成功！")
                            st.rerun()
                        else:
                            st.error("设置基线方案失败，请重试。")
    
    with col2:
        st.markdown("#### 📋 现有基线方案")
        
        if not baselines:
            st.info("📭 暂无基线方案。")
        else:
            baseline_data = []
            for b in baselines:
                snapshot = b.result_snapshot or {}
                baseline_data.append({
                    "id": b.id,
                    "名称": b.name,
                    "创建人": b.created_by,
                    "创建时间": b.created_at[:19] if b.created_at else "",
                    "部门": b.department,
                    "平均等待": f"{snapshot.get('avg_wait_time', 0):.2f}分",
                    "总接待量": f"{snapshot.get('total_reception', 0):.0f}人",
                    "预估成本": f"{snapshot.get('cost_estimate', 0):.2f}元",
                    "状态": "启用" if b.is_active else "停用",
                    "描述": b.description
                })
            
            df_baselines = pd.DataFrame(baseline_data)
            df_display = df_baselines.drop(columns=["id"])
            
            event = st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            selected_idx = None
            if event.selection and hasattr(event.selection, 'rows') and event.selection.rows:
                selected_idx = event.selection.rows[0]
            
            if selected_idx is not None and 0 <= selected_idx < len(baselines):
                selected_baseline = baselines[selected_idx]
                st.markdown("---")
                
                col_act1, col_act2 = st.columns([1, 1])
                
                with col_act1:
                    if can_manage and (get_current_user_role() == "admin" or selected_baseline.created_by == current_user):
                        new_status = not selected_baseline.is_active
                        status_label = "停用" if selected_baseline.is_active else "启用"
                        if st.button(f"🔄 {status_label}基线", use_container_width=True):
                            if update_baseline_scheme(selected_baseline.id, is_active=new_status):
                                st.success(f"基线方案已{status_label}")
                                st.rerun()
                
                with col_act2:
                    if get_current_user_role() == "admin":
                        if st.button("🗑️ 删除基线", use_container_width=True, type="secondary"):
                            if delete_baseline_scheme(selected_baseline.id):
                                st.success("基线方案已删除")
                                st.rerun()
                
                st.info(f"💡 **基线描述**: {selected_baseline.description or '无'}")


def perform_scheme_review():
    st.subheader("📊 方案对比复盘")
    
    can_create = can_manage_review()
    can_export = check_permission("export")
    current_user = get_current_username()
    current_role = get_current_user_role()
    
    if not can_create:
        st.info("🔒 您只有查看权限，无法发起新的复盘对比。如有需要请联系管理员或普通用户。")
    
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
    
    if current_role != "admin":
        active_baselines = [b for b in active_baselines if b.created_by == current_user or current_role == "auditor"]
    
    if not active_baselines:
        st.warning("⚠️ 暂无可用的基线方案。请先在「基线方案管理」中设置基线。")
        return
    
    if len(all_results) < 1:
        st.warning("⚠️ 暂无历史模拟结果，无法进行复盘对比。")
        return
    
    if len(all_results) < 2:
        st.info("💡 目前仅有1条模拟结果，仅可查看基线详情。建议积累更多方案后进行多方案对比。")
    
    st.markdown("#### 🔧 复盘配置")
    
    col_cfg1, col_cfg2, col_cfg3, col_cfg4 = st.columns([1.2, 1, 1, 1])
    
    with col_cfg1:
        baseline_options = []
        for b in active_baselines:
            label = f"{b.name} (创建人: {b.created_by})"
            baseline_options.append((label, b))
        
        selected_bl_label = st.selectbox(
            "选择基线方案",
            options=[opt[0] for opt in baseline_options]
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
    
    with col_cfg2:
        templates = load_threshold_templates()
        template_options = [(t.id, f"{t.name} {'(默认)' if t.is_default else ''}") for t in templates]
        template_ids = [t[0] for t in template_options]
        template_labels = [t[1] for t in template_options]
        
        selected_template_label = st.selectbox(
            "选择阈值模板",
            options=template_labels
        )
        selected_template_id = template_ids[template_labels.index(selected_template_label)]
        selected_threshold = get_threshold_template_by_id(selected_template_id)
    
    with col_cfg3:
        departments = sorted(list(set([r.department for r in all_results if r.department])))
        departments = ["全部"] + departments
        dept_filter = st.selectbox("按部门筛选", options=departments)
    
    with col_cfg4:
        date_options = ["全部", "最近7天", "最近30天", "最近90天"]
        date_filter = st.selectbox("按时间筛选", options=date_options)
    
    filtered_results = all_results
    
    if baseline_result:
        filtered_results = [r for r in filtered_results if r.id != baseline_result.id]
    
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
    
    name_keyword = st.text_input("🔍 按方案名称搜索", placeholder="输入方案名称关键词...")
    if name_keyword:
        filtered_results = [
            r for r in filtered_results
            if name_keyword.lower() in r.params_name.lower()
        ]
    
    if not filtered_results:
        st.info("📭 没有符合筛选条件的模拟结果（基线方案已自动排除）。")
        return
    
    st.markdown("#### 📋 选择对比方案")
    
    status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
    result_display = []
    for r in filtered_results:
        status_display = "-"
        if r.threshold_evaluation:
            status = r.threshold_evaluation.overall_status
            status_display = f"{status_colors.get(status, '⚪')} {status}"
        
        result_display.append({
            "id": r.id,
            "方案名称": r.params_name,
            "创建时间": r.created_at[:19] if r.created_at else "",
            "部门": r.department,
            "平均等待": f"{r.avg_wait_time:.2f}分",
            "总接待量": f"{r.total_reception:.0f}人",
            "预估成本": f"{r.cost_estimate:.2f}元",
            "状态": status_display
        })
    
    df_results = pd.DataFrame(result_display)
    df_show = df_results.drop(columns=["id"])
    
    event = st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row"
    )
    
    selected_indices = []
    if event.selection and hasattr(event.selection, 'rows') and event.selection.rows is not None:
        selected_indices = event.selection.rows
    
    selected_results = [filtered_results[i] for i in selected_indices]
    
    col_act1, col_act2 = st.columns([1, 1])
    
    with col_act1:
        review_name = st.text_input(
            "复盘名称",
            value=f"复盘-{selected_baseline.name}-{datetime.now().strftime('%Y%m%d')}" if selected_baseline else "",
            placeholder="请输入本次复盘的名称"
        )
    
    with col_act2:
        review_remarks = st.text_input("备注（可选）", placeholder="添加复盘备注...")
    
    if st.button(
        "🔍 开始复盘对比",
        use_container_width=True,
        type="primary",
        disabled=not selected_results or not baseline_result or not review_name or not can_create
    ):
        if can_create and selected_results and baseline_result and review_name:
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
            
            st.session_state.current_review_items = comparison_items
            st.session_state.current_review_baseline = selected_baseline
            st.session_state.current_review_baseline_result = baseline_result
            st.session_state.current_review_name = review_name
            st.session_state.current_review_remarks = review_remarks
            st.session_state.current_review_threshold = selected_threshold
        elif not can_create:
            st.warning("⚠️ 您没有权限发起复盘对比。")
    
    if "current_review_items" in st.session_state and st.session_state.current_review_items:
        st.markdown("---")
        show_review_results()


def show_review_results():
    st.subheader("📈 复盘对比结果")
    
    items = st.session_state.current_review_items
    baseline = st.session_state.current_review_baseline
    baseline_result = st.session_state.current_review_baseline_result
    threshold = st.session_state.get("current_review_threshold")
    
    if not items:
        return
    
    st.info(f"🎯 **基线方案**: {baseline.name}")
    if threshold:
        st.caption(f"📊 使用阈值模板: {threshold.name}")
    
    baseline_unit_cost = calculate_unit_cost(baseline_result)
    
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    with col_m1:
        st.metric("基线平均等待", f"{baseline_result.avg_wait_time:.2f} 分钟")
    with col_m2:
        st.metric("基线最大等待", f"{baseline_result.max_wait_time:.2f} 分钟")
    with col_m3:
        st.metric("基线总接待量", f"{baseline_result.total_reception:.0f} 人")
    with col_m4:
        st.metric("基线预估成本", f"{baseline_result.cost_estimate:.2f} 元")
    with col_m5:
        st.metric("基线单位成本", f"{baseline_unit_cost:.2f} 元/人")
    
    st.markdown("---")
    
    has_threshold = any(item.threshold_evaluation is not None for item in items)
    
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
            "预估成本差异": f"{item.cost_estimate_diff:+.2f}元",
            "预估成本变化": f"{item.cost_estimate_change_rate:+.2%}",
            "单位成本差异": f"{item.unit_cost_diff:+.2f}元/人",
            "单位成本变化": f"{item.unit_cost_change_rate:+.2%}",
            "综合结论": f"{conclusion_color} {item.conclusion}",
            "综合评分": f"{item.score:.2f}"
        }
        
        if has_threshold:
            status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
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
    
    st.subheader("💡 综合结论与推荐排序")
    
    status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
    
    for rank, item in enumerate(items, 1):
        conclusion_emoji = {
            "更优": "🟢",
            "持平": "🟡",
            "退化": "🔴"
        }.get(item.conclusion, "⚪")
        
        expander_title = f"#{rank} {item.result_name} - {conclusion_emoji} {item.conclusion} (评分: {item.score:.2f})"
        
        if item.threshold_evaluation:
            threshold_status = item.threshold_evaluation.overall_status
            expander_title += f" | {status_colors.get(threshold_status, '⚪')} 阈值: {threshold_status}"
        
        with st.expander(expander_title, expanded=True):
            if item.threshold_conclusion:
                st.markdown(f"### 📊 阈值复盘结论")
                st.success(f"**{item.threshold_conclusion}**")
                st.markdown("---")
            
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                st.markdown("**⏱️ 等待时长表现**")
                wait_text = "减少" if item.avg_wait_time_diff < 0 else "增加" if item.avg_wait_time_diff > 0 else "持平"
                st.info(f"平均等待 {wait_text} {abs(item.avg_wait_time_diff):.2f} 分钟 ({item.avg_wait_time_change_rate:+.2%})")
                max_wait_text = "减少" if item.max_wait_time_diff < 0 else "增加" if item.max_wait_time_diff > 0 else "持平"
                st.info(f"最大等待 {max_wait_text} {abs(item.max_wait_time_diff):.2f} 分钟")
            
            with col_b:
                st.markdown("**👥 接待能力表现**")
                recep_text = "提升" if item.total_reception_diff > 0 else "下降" if item.total_reception_diff < 0 else "持平"
                st.success(f"总接待量 {recep_text} {abs(item.total_reception_diff):.0f} 人 ({item.total_reception_change_rate:+.2%})")
            
            with col_c:
                st.markdown("**💰 成本效益表现**")
                cost_text = "降低" if item.cost_estimate_diff < 0 else "增加" if item.cost_estimate_diff > 0 else "持平"
                st.warning(f"总成本 {cost_text} {abs(item.cost_estimate_diff):.2f} 元")
                unit_text = "降低" if item.unit_cost_diff < 0 else "增加" if item.unit_cost_diff > 0 else "持平"
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
    
    col_save, col_export = st.columns([1, 1])
    
    with col_save:
        if can_manage_review():
            if st.button("💾 保存复盘记录", use_container_width=True):
                review_name = st.session_state.get("current_review_name", "")
                review_remarks = st.session_state.get("current_review_remarks", "")
                
                if review_name:
                    new_review = ReviewRecord(
                        name=review_name,
                        baseline_id=baseline.id,
                        baseline_name=baseline.name,
                        comparison_items=items,
                        created_by=get_current_username(),
                        department=baseline.department,
                        remarks=review_remarks
                    )
                    
                    if add_review_record(new_review):
                        st.success("✅ 复盘记录已保存！")
                    else:
                        st.error("保存复盘记录失败，请重试。")
        else:
            st.info("🔒 您没有权限保存复盘记录。")
    
    with col_export:
        if check_permission("export"):
            if st.button("📤 导出简版报告", use_container_width=True):
                review_name = st.session_state.get("current_review_name", "未命名复盘")
                review_remarks = st.session_state.get("current_review_remarks", "")
                
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
                            label="⬇️ 下载复盘报告",
                            data=f.read(),
                            file_name=os.path.basename(filepath),
                            mime="text/csv",
                            use_container_width=True
                        )
        else:
            st.info("🔒 您没有权限导出报告。")


def view_review_history():
    st.subheader("📋 历史复盘记录")
    
    current_user = get_current_username()
    current_role = get_current_user_role()
    can_view_all = check_permission("view_all_reviews")
    
    try:
        reviews = load_review_records()
    except Exception as e:
        st.error(f"加载复盘记录失败: {e}")
        reviews = []
    
    if not can_view_all:
        reviews = [r for r in reviews if r.created_by == current_user]
    
    if not reviews:
        st.info("📭 暂无复盘记录。")
        return
    
    st.markdown(f"共找到 {len(reviews)} 条复盘记录")
    
    review_data = []
    for r in reviews:
        review_data.append({
            "id": r.id,
            "复盘名称": r.name,
            "基线方案": r.baseline_name,
            "对比方案数": len(r.comparison_items),
            "创建人": r.created_by,
            "创建时间": r.created_at[:19] if r.created_at else "",
            "部门": r.department,
            "备注": r.remarks
        })
    
    df_reviews = pd.DataFrame(review_data)
    df_show = df_reviews.drop(columns=["id"])
    
    event = st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    selected_idx = None
    if event.selection and hasattr(event.selection, 'rows') and event.selection.rows:
        selected_idx = event.selection.rows[0]
    
    if selected_idx is not None and 0 <= selected_idx < len(reviews):
        selected_review = reviews[selected_idx]
        st.markdown("---")
        st.markdown(f"### 📄 复盘详情: {selected_review.name}")
        
        col_info1, col_info2, col_info3 = st.columns([2, 1, 1])
        with col_info1:
            st.info(f"🎯 基线方案: {selected_review.baseline_name}")
        with col_info2:
            st.info(f"👤 创建人: {selected_review.created_by}")
        with col_info3:
            st.info(f"📅 创建时间: {selected_review.created_at[:19] if selected_review.created_at else ''}")
        
        if selected_review.remarks:
            st.info(f"📝 备注: {selected_review.remarks}")
        
        st.markdown("#### 📊 对比结果")
        
        status_colors = {"达标": "🟢", "预警": "🟡", "未达标": "🔴"}
        has_threshold = any(item.threshold_evaluation is not None for item in selected_review.comparison_items)
        
        detail_data = []
        for rank, item in enumerate(selected_review.comparison_items, 1):
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
                "预估成本差异": f"{item.cost_estimate_diff:+.2f}元",
                "单位成本差异": f"{item.unit_cost_diff:+.2f}元/人",
                "综合结论": f"{conclusion_color} {item.conclusion}",
                "综合评分": f"{item.score:.2f}"
            }
            
            if has_threshold:
                if item.threshold_evaluation:
                    row_data["阈值状态"] = f"{status_colors.get(item.threshold_evaluation.overall_status, '⚪')} {item.threshold_evaluation.overall_status}"
                    row_data["阈值复盘结论"] = item.threshold_conclusion or "-"
                else:
                    row_data["阈值状态"] = "-"
                    row_data["阈值复盘结论"] = "-"
            
            detail_data.append(row_data)
        
        df_detail = pd.DataFrame(detail_data)
        st.dataframe(df_detail, use_container_width=True, hide_index=True)
        
        if has_threshold:
            st.markdown("#### 🎯 阈值评估详情")
            for rank, item in enumerate(selected_review.comparison_items, 1):
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
        
        col_export2, col_del = st.columns([1, 1])
        with col_export2:
            if check_permission("export"):
                if st.button("📤 导出此复盘报告", use_container_width=True):
                    filepath = export_review_report(selected_review)
                    if filepath:
                        with open(filepath, "r", encoding="utf-8-sig") as f:
                            st.download_button(
                                label="⬇️ 下载报告",
                                data=f.read(),
                                file_name=os.path.basename(filepath),
                                mime="text/csv",
                                use_container_width=True
                            )
            else:
                st.info("🔒 您没有权限导出报告。")
        
        with col_del:
            if current_role == "admin" or (current_role == "user" and selected_review.created_by == current_user):
                if st.button("🗑️ 删除此复盘", use_container_width=True):
                    if delete_review_record(selected_review.id):
                        st.success("复盘记录已删除")
                        st.rerun()


def manage_threshold_templates():
    st.subheader("⚙️ 阈值模板管理")
    
    current_role = get_current_user_role()
    can_manage = check_permission("manage_threshold_templates")
    
    if not can_manage:
        st.info("🔒 您只有查看权限，无法管理阈值模板。如需创建或修改模板，请联系管理员。")
    
    try:
        templates = load_threshold_templates()
    except Exception as e:
        st.error(f"加载阈值模板失败: {e}")
        templates = []
    
    col_create, col_list = st.columns([1, 2])
    
    with col_create:
        st.markdown("#### ➕ 创建/编辑模板")
        
        template_name = st.text_input("模板名称", placeholder="请输入模板名称")
        department = st.text_input("适用部门", value="default")
        
        st.markdown("**⏱️ 等待时长阈值**")
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            avg_wait_warn = st.number_input("平均等待预警值(分钟)", min_value=0.1, max_value=120.0, value=7.0, step=0.5)
        with col_w2:
            avg_wait_max = st.number_input("平均等待最大值(分钟)", min_value=avg_wait_warn, max_value=180.0, value=10.0, step=0.5)
        
        col_mw1, col_mw2 = st.columns(2)
        with col_mw1:
            max_wait_warn = st.number_input("最大等待预警值(分钟)", min_value=0.1, max_value=300.0, value=20.0, step=1.0)
        with col_mw2:
            max_wait_max = st.number_input("最大等待最大值(分钟)", min_value=max_wait_warn, max_value=600.0, value=30.0, step=1.0)
        
        st.markdown("**👥 接待量阈值**")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            total_recep_min = st.number_input("总接待最小值(人)", min_value=1.0, max_value=2000.0, value=200.0, step=10.0)
        with col_r2:
            total_recep_warn = st.number_input("总接待目标值(人)", min_value=total_recep_min, max_value=5000.0, value=250.0, step=10.0)
        
        st.markdown("**💰 成本阈值**")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            cost_warn = st.number_input("预估成本预警值(元)", min_value=100.0, max_value=100000.0, value=4000.0, step=100.0)
        with col_c2:
            cost_max = st.number_input("预估成本最大值(元)", min_value=cost_warn, max_value=200000.0, value=5000.0, step=100.0)
        
        col_uc1, col_uc2 = st.columns(2)
        with col_uc1:
            unit_cost_warn = st.number_input("单位成本预警值(元/人)", min_value=0.1, max_value=500.0, value=15.0, step=1.0)
        with col_uc2:
            unit_cost_max = st.number_input("单位成本最大值(元/人)", min_value=unit_cost_warn, max_value=1000.0, value=20.0, step=1.0)
        
        is_default = st.checkbox("设为默认模板")
        
        create_disabled = not can_manage or not template_name
        
        if st.button("✅ 保存模板", use_container_width=True, disabled=create_disabled):
            if template_name:
                new_template = ThresholdConfig(
                    name=template_name,
                    avg_wait_time_max=avg_wait_max,
                    avg_wait_time_warning=avg_wait_warn,
                    max_wait_time_max=max_wait_max,
                    max_wait_time_warning=max_wait_warn,
                    total_reception_min=total_recep_min,
                    total_reception_warning=total_recep_warn,
                    cost_estimate_max=cost_max,
                    cost_estimate_warning=cost_warn,
                    unit_cost_max=unit_cost_max,
                    unit_cost_warning=unit_cost_warn,
                    is_default=is_default,
                    created_by=get_current_username(),
                    department=department
                )
                
                if add_threshold_template(new_template):
                    st.success(f"✅ 模板 '{template_name}' 创建成功！")
                    st.rerun()
                else:
                    st.error("创建模板失败，请重试。")
    
    with col_list:
        st.markdown("#### 📋 现有模板列表")
        
        if not templates:
            st.info("📭 暂无阈值模板。")
        else:
            template_data = []
            for t in templates:
                template_data.append({
                    "id": t.id,
                    "模板名称": t.name,
                    "默认": "✅" if t.is_default else "-",
                    "创建人": t.created_by,
                    "创建时间": t.created_at[:19] if t.created_at else "",
                    "部门": t.department,
                    "平均等待预警": f"{t.avg_wait_time_warning}分",
                    "平均等待最大": f"{t.avg_wait_time_max}分",
                    "总接待目标": f"{t.total_reception_warning}人",
                    "成本预警": f"{t.cost_estimate_warning}元"
                })
            
            df_templates = pd.DataFrame(template_data)
            df_show = df_templates.drop(columns=["id"])
            
            event = st.dataframe(
                df_show,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            selected_idx = None
            if event.selection and hasattr(event.selection, 'rows') and event.selection.rows:
                selected_idx = event.selection.rows[0]
            
            if selected_idx is not None and 0 <= selected_idx < len(templates):
                selected_template = templates[selected_idx]
                st.markdown("---")
                
                col_act1, col_act2 = st.columns([1, 1])
                
                with col_act1:
                    if can_manage and not selected_template.is_default:
                        if st.button("⭐ 设为默认", use_container_width=True):
                            if update_threshold_template(selected_template.id, is_default=True):
                                st.success("已设为默认模板")
                                st.rerun()
                    elif selected_template.is_default:
                        st.info("⭐ 当前为默认模板")
                
                with col_act2:
                    if can_manage and current_role == "admin":
                        if st.button("🗑️ 删除模板", use_container_width=True, type="secondary"):
                            if delete_threshold_template(selected_template.id):
                                st.success("模板已删除")
                                st.rerun()
                
                with st.expander("📊 查看模板详情", expanded=True):
                    col_d1, col_d2, col_d3 = st.columns(3)
                    
                    with col_d1:
                        st.markdown("**⏱️ 等待时长**")
                        st.write(f"平均等待预警: {selected_template.avg_wait_time_warning} 分钟")
                        st.write(f"平均等待最大: {selected_template.avg_wait_time_max} 分钟")
                        st.write(f"最大等待预警: {selected_template.max_wait_time_warning} 分钟")
                        st.write(f"最大等待最大: {selected_template.max_wait_time_max} 分钟")
                    
                    with col_d2:
                        st.markdown("**👥 接待量**")
                        st.write(f"总接待最小值: {selected_template.total_reception_min} 人")
                        st.write(f"总接待目标值: {selected_template.total_reception_warning} 人")
                    
                    with col_d3:
                        st.markdown("**💰 成本**")
                        st.write(f"预估成本预警: {selected_template.cost_estimate_warning} 元")
                        st.write(f"预估成本最大: {selected_template.cost_estimate_max} 元")
                        st.write(f"单位成本预警: {selected_template.unit_cost_warning} 元/人")
                        st.write(f"单位成本最大: {selected_template.unit_cost_max} 元/人")


if __name__ == "__main__":
    main()

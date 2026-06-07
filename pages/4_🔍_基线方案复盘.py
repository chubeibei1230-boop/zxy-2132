import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import BaselineScheme, ReviewRecord, SimulationResult
from core.simulation import perform_review_comparison, calculate_unit_cost
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
    ensure_dirs
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
    
    tab1, tab2, tab3 = st.tabs(["🎯 基线方案管理", "📊 方案对比复盘", "📋 历史复盘记录"])
    
    with tab1:
        manage_baseline_schemes()
    
    with tab2:
        perform_scheme_review()
    
    with tab3:
        view_review_history()


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
        baselines = load_baseline_schemes()
    except Exception as e:
        st.error(f"加载基线方案失败: {e}")
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
            
            duplicate_names = [b.name for b in baselines if b.name == baseline_name and baseline_name]
            
            if duplicate_names:
                st.warning(f"⚠️ 已存在同名基线方案：{baseline_name}，建议使用不同名称。")
            
            department = st.text_input("部门", value="default")
            
            if st.button("✅ 设为基线方案", use_container_width=True, disabled=not selected_result or not baseline_name):
                if selected_result and baseline_name:
                    if duplicate_names:
                        st.error(f"基线方案名称 '{baseline_name}' 已存在，请使用其他名称。")
                    else:
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
    current_user = get_current_username()
    current_role = get_current_user_role()
    
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
        st.info("💡 目前仅有1条模拟结果，仅可查看与基线的单方案对比。建议积累更多方案后进行多方案对比。")
    
    st.markdown("#### 🔧 复盘配置")
    
    col_cfg1, col_cfg2, col_cfg3 = st.columns([1, 1, 1])
    
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
        departments = sorted(list(set([r.department for r in all_results if r.department])))
        departments = ["全部"] + departments
        dept_filter = st.selectbox("按部门筛选", options=departments)
    
    with col_cfg3:
        date_options = ["全部", "最近7天", "最近30天", "最近90天"]
        date_filter = st.selectbox("按时间筛选", options=date_options)
    
    filtered_results = all_results
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
        st.info("📭 没有符合筛选条件的模拟结果。")
        return
    
    st.markdown("#### 📋 选择对比方案")
    
    result_display = []
    for r in filtered_results:
        result_display.append({
            "id": r.id,
            "方案名称": r.params_name,
            "创建时间": r.created_at[:19] if r.created_at else "",
            "部门": r.department,
            "平均等待": f"{r.avg_wait_time:.2f}分",
            "总接待量": f"{r.total_reception:.0f}人",
            "预估成本": f"{r.cost_estimate:.2f}元"
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
        disabled=not selected_results or not baseline_result or not review_name
    ):
        if selected_results and baseline_result and review_name:
            comparison_items = perform_review_comparison(baseline_result, selected_results)
            st.session_state.current_review_items = comparison_items
            st.session_state.current_review_baseline = selected_baseline
            st.session_state.current_review_baseline_result = baseline_result
            st.session_state.current_review_name = review_name
            st.session_state.current_review_remarks = review_remarks
    
    if "current_review_items" in st.session_state and st.session_state.current_review_items:
        st.markdown("---")
        show_review_results()


def show_review_results():
    st.subheader("📈 复盘对比结果")
    
    items = st.session_state.current_review_items
    baseline = st.session_state.current_review_baseline
    baseline_result = st.session_state.current_review_baseline_result
    
    if not items:
        return
    
    st.info(f"🎯 **基线方案**: {baseline.name}")
    
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
    
    comparison_data = []
    for rank, item in enumerate(items, 1):
        conclusion_color = {
            "更优": "🟢",
            "持平": "🟡",
            "退化": "🔴"
        }.get(item.conclusion, "⚪")
        
        comparison_data.append({
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
        })
    
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    st.subheader("💡 综合结论与推荐排序")
    
    for rank, item in enumerate(items, 1):
        conclusion_emoji = {
            "更优": "🟢",
            "持平": "🟡",
            "退化": "🔴"
        }.get(item.conclusion, "⚪")
        
        with st.expander(f"#{rank} {item.result_name} - {conclusion_emoji} {item.conclusion} (评分: {item.score:.2f})", expanded=True):
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
        
        detail_data = []
        for rank, item in enumerate(selected_review.comparison_items, 1):
            conclusion_color = {
                "更优": "🟢",
                "持平": "🟡",
                "退化": "🔴"
            }.get(item.conclusion, "⚪")
            
            detail_data.append({
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
            })
        
        df_detail = pd.DataFrame(detail_data)
        st.dataframe(df_detail, use_container_width=True, hide_index=True)
        
        col_export2, col_del = st.columns([1, 1])
        with col_export2:
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
        
        with col_del:
            if current_role == "admin" or (current_role == "user" and selected_review.created_by == current_user):
                if st.button("🗑️ 删除此复盘", use_container_width=True):
                    if delete_review_record(selected_review.id):
                        st.success("复盘记录已删除")
                        st.rerun()


if __name__ == "__main__":
    main()

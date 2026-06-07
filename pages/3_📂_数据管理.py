import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.persistence import (
    load_schedule_data,
    save_schedule_data,
    parse_uploaded_schedule,
    load_simulation_params,
    save_simulation_params,
    load_simulation_results,
    save_simulation_results,
    load_baseline_schemes,
    save_baseline_schemes,
    load_review_records,
    save_review_records,
    ensure_dirs
)


st.set_page_config(page_title="数据管理", page_icon="📂", layout="wide")


def check_permission(permission: str) -> bool:
    auth_manager = st.session_state.get("auth_manager")
    if auth_manager is None:
        return False
    return auth_manager.has_permission(permission)


def main():
    st.title("📂 数据管理")
    st.markdown("---")
    
    if not check_permission("upload_schedule"):
        st.warning("⚠️ 您没有权限访问此页面。请使用管理员账户登录。")
        return
    
    ensure_dirs()
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 排班数据管理", "⚙️ 模拟方案管理", "📊 模拟结果管理", "🗑️ 数据清理"])
    
    with tab1:
        manage_schedule_data()
    
    with tab2:
        manage_simulation_params()
    
    with tab3:
        manage_simulation_results()
    
    with tab4:
        manage_data_cleanup()


def manage_schedule_data():
    st.subheader("📋 排班数据管理")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📤 上传排班数据")
        uploaded_file = st.file_uploader(
            "选择CSV文件",
            type=["csv"],
            help="支持中英文列名：date/日期, time_slot/时段, staff_count/排班人数, department/部门"
        )
        
        if uploaded_file is not None:
            file_content = uploaded_file.read()
            records = parse_uploaded_schedule(file_content)
            
            if records:
                st.success(f"✅ 成功解析 {len(records)} 条排班记录")
                
                save_mode = st.radio(
                    "保存方式",
                    ["追加到现有数据", "覆盖现有数据", "去重后追加（按日期+时段）"],
                    index=2
                )
                
                if st.button("保存到系统", use_container_width=True):
                    existing = load_schedule_data()
                    
                    if save_mode == "覆盖现有数据":
                        final_records = records
                        st.info("已覆盖原有数据")
                    elif save_mode == "去重后追加（按日期+时段）":
                        existing_keys = set()
                        for r in existing:
                            key = (r.date, r.time_slot, r.department)
                            existing_keys.add(key)
                        
                        new_records = []
                        duplicate_count = 0
                        for r in records:
                            key = (r.date, r.time_slot, r.department)
                            if key not in existing_keys:
                                new_records.append(r)
                                existing_keys.add(key)
                            else:
                                duplicate_count += 1
                        
                        final_records = existing + new_records
                        if duplicate_count > 0:
                            st.info(f"已跳过 {duplicate_count} 条重复记录（相同日期+时段+部门）")
                    else:
                        final_records = existing + records
                    
                    if save_schedule_data(final_records):
                        st.success("数据已保存！")
                        st.rerun()
                    else:
                        st.error("保存失败")
            else:
                st.error("无法解析文件，请检查格式")
        
        st.markdown("#### 📄 示例文件格式")
        example_data = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
            "time_slot": ["09:00-12:00", "14:00-17:00", "09:00-12:00"],
            "staff_count": [5, 4, 6],
            "department": ["客服中心", "客服中心", "客服中心"]
        })
        st.dataframe(example_data, use_container_width=True, hide_index=True)
        
        csv_data = example_data.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="⬇️ 下载示例CSV",
            data=csv_data,
            file_name="schedule_example.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        st.markdown("#### 📊 当前排班数据")
        records = load_schedule_data()
        
        if records:
            data = []
            for r in records:
                data.append({
                    "日期": r.date,
                    "时段": r.time_slot,
                    "排班人数": r.staff_count,
                    "部门": r.department
                })
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, height=400)
            
            st.info(f"共 {len(records)} 条记录")
            
            if st.button("🗑️ 清空所有排班数据", use_container_width=True):
                if save_schedule_data([]):
                    st.success("已清空排班数据")
                    st.rerun()
        else:
            st.info("暂无排班数据，请上传CSV文件")


def manage_simulation_params():
    st.subheader("⚙️ 模拟方案管理")
    
    params_list = load_simulation_params()
    
    if params_list:
        data = []
        for p in params_list:
            data.append({
                "方案名称": p.name,
                "接待人数": p.reception_capacity,
                "单次耗时(分)": p.service_duration,
                "休息间隔(分)": p.break_interval,
                "高峰系数": p.peak_factor,
                "创建时间": p.created_at[:19] if p.created_at else "",
                "创建人": p.created_by,
                "部门": p.department
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        
        st.info(f"共 {len(params_list)} 个保存的方案")
        
        col_del1, col_del2 = st.columns([1, 1])
        with col_del1:
            if st.button("🗑️ 删除所有方案", use_container_width=True):
                if save_simulation_params([]):
                    st.success("已清空所有方案")
                    st.rerun()
    else:
        st.info("暂无保存的模拟方案")


def manage_simulation_results():
    st.subheader("📊 模拟结果管理")
    
    results = load_simulation_results()
    
    if results:
        data = []
        for r in results:
            data.append({
                "方案名称": r.params_name,
                "平均等待(分)": round(r.avg_wait_time, 2),
                "最大等待(分)": round(r.max_wait_time, 2),
                "总接待量": round(r.total_reception, 0),
                "预估成本(元)": round(r.cost_estimate, 2),
                "创建时间": r.created_at[:19] if r.created_at else "",
                "创建人": r.created_by,
                "部门": r.department
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        
        st.info(f"共 {len(results)} 条模拟结果")
        
        col_del1, col_del2 = st.columns([1, 1])
        with col_del1:
            if st.button("🗑️ 删除所有模拟结果", use_container_width=True):
                if save_simulation_results([]):
                    st.success("已清空所有模拟结果")
                    st.rerun()
    else:
        st.info("暂无模拟结果数据")


def manage_data_cleanup():
    st.subheader("🗑️ 数据清理")
    
    col_a, col_b, col_c = st.columns([1, 1, 1])
    
    with col_a:
        results_count = len(load_simulation_results())
        st.metric("历史模拟结果数", results_count)
        
        if results_count > 0:
            if st.button("清空所有模拟结果", use_container_width=True):
                if save_simulation_results([]):
                    st.success("已清空所有模拟结果")
                    st.rerun()
    
    with col_b:
        params_count = len(load_simulation_params())
        st.metric("保存的方案数", params_count)
        
        if params_count > 0:
            if st.button("清空所有方案", use_container_width=True):
                if save_simulation_params([]):
                    st.success("已清空所有方案")
                    st.rerun()
    
    with col_c:
        schedule_count = len(load_schedule_data())
        st.metric("排班数据记录数", schedule_count)
        
        if schedule_count > 0:
            if st.button("清空所有排班数据", use_container_width=True):
                if save_schedule_data([]):
                    st.success("已清空排班数据")
                    st.rerun()
    
    st.markdown("---")
    
    col_d, col_e = st.columns([1, 1])
    
    with col_d:
        baseline_count = len(load_baseline_schemes())
        st.metric("基线方案数", baseline_count)
        
        if baseline_count > 0:
            if st.button("清空所有基线方案", use_container_width=True):
                if save_baseline_schemes([]):
                    st.success("已清空所有基线方案")
                    st.rerun()
    
    with col_e:
        review_count = len(load_review_records())
        st.metric("复盘记录数", review_count)
        
        if review_count > 0:
            if st.button("清空所有复盘记录", use_container_width=True):
                if save_review_records([]):
                    st.success("已清空所有复盘记录")
                    st.rerun()
    
    st.markdown("---")
    st.warning("⚠️ 注意：数据删除后无法恢复，请谨慎操作！")


if __name__ == "__main__":
    main()

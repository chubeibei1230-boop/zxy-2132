import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth.roles import AuthManager


st.set_page_config(
    page_title="排班数据可视化分析工具",
    page_icon="📊",
    layout="wide"
)


if "auth_manager" not in st.session_state:
    st.session_state.auth_manager = AuthManager()


def main():
    st.title("📊 排班数据可视化分析工具")
    st.markdown("---")
    
    auth_manager: AuthManager = st.session_state.auth_manager
    current_user = auth_manager.get_current_user()
    
    if current_user is None:
        show_login_page(auth_manager)
    else:
        show_main_content(auth_manager)


def show_login_page(auth_manager: AuthManager):
    st.subheader("🔐 用户登录")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("用户名", placeholder="请输入用户名")
            password = st.text_input("密码", type="password", placeholder="请输入密码")
            submit = st.form_submit_button("登录", use_container_width=True)
            
            if submit:
                if auth_manager.login(username, password):
                    st.success(f"登录成功！欢迎 {auth_manager.get_current_role_name()}")
                    st.rerun()
                else:
                    st.error("用户名或密码错误")
        
        st.info("""
        **示例账户：**
        - 管理员: `admin` / `admin123`
        - 普通用户: `user` / `user123`
        - 审计员: `auditor` / `auditor123`
        """)


def show_main_content(auth_manager: AuthManager):
    with st.sidebar:
        st.success(f"✅ 已登录: {auth_manager.get_current_user().username}")
        st.info(f"🎭 角色: {auth_manager.get_current_role_name()}")
        
        st.markdown("---")
        if st.button("🚪 退出登录", use_container_width=True):
            auth_manager.logout()
            st.rerun()
        
        st.markdown("---")
        st.subheader("📋 可用权限")
        perms = auth_manager.list_available_permissions()
        perm_map = {
            "upload_schedule": "📤 上传排班数据",
            "simulate": "⚙️ 运行模拟",
            "view_reports": "📈 查看报告",
            "export": "💾 导出数据",
            "manage_users": "👥 用户管理",
            "manage_baseline": "🎯 管理基线方案",
            "manage_review": "📝 管理复盘记录",
            "view_all_reviews": "👁️ 查看所有复盘",
            "create_review": "✍️ 创建复盘",
            "view_own_reviews": "👁️ 查看自己的复盘",
            "set_own_baseline": "🎯 设置自己的基线",
            "view_baseline": "👁️ 查看基线方案",
            "manage_threshold_templates": "⚙️ 管理阈值模板",
            "view_threshold_templates": "👁️ 查看阈值模板",
            "apply_threshold_template": "🎯 应用阈值模板"
        }
        for p in perms:
            st.write(f"- {perm_map.get(p, p)}")
    
    st.info(f"👋 欢迎使用排班数据可视化分析工具！请在左侧选择功能页面。")
    
    st.markdown("### 📖 功能说明")
    st.markdown("""
    本工具提供以下核心功能：
    
    1. **模拟面板** - 设置接待人数、单次耗时、休息间隔和高峰系数，运行多方案对比模拟
    2. **报告分析** - 查看历史模拟结果，分析等待时长和接待量的平滑趋势（移动平均线）
    3. **数据管理** - 管理员可上传和管理排班数据
    
    **核心技术亮点：**
    - 移动平均线 (Moving Average) 展示平滑趋势
    - 基于排队论的模拟算法
    - 多方案参数对比分析
    - 支持CSV数据导出
    """)


if __name__ == "__main__":
    main()

from typing import Optional, Dict, List
from models.schemas import User, ROLE_PERMISSIONS, ROLES


class AuthManager:
    def __init__(self):
        self.users: Dict[str, User] = {
            "admin": User(username="admin", role="admin", password="admin123"),
            "user": User(username="user", role="user", password="user123"),
            "auditor": User(username="auditor", role="auditor", password="auditor123"),
        }
        self.current_user: Optional[User] = None

    def login(self, username: str, password: str) -> bool:
        if username in self.users:
            user = self.users[username]
            if user.password == password:
                self.current_user = user
                return True
        return False

    def logout(self) -> None:
        self.current_user = None

    def get_current_user(self) -> Optional[User]:
        return self.current_user

    def has_permission(self, permission: str) -> bool:
        if self.current_user is None:
            return False
        user_permissions = ROLE_PERMISSIONS.get(self.current_user.role, [])
        return permission in user_permissions

    def get_role_name(self, role_key: str) -> str:
        return ROLES.get(role_key, role_key)

    def get_current_role_name(self) -> str:
        if self.current_user:
            return self.get_role_name(self.current_user.role)
        return "未登录"

    def list_available_permissions(self) -> List[str]:
        if self.current_user:
            return ROLE_PERMISSIONS.get(self.current_user.role, [])
        return []

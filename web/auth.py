from functools import wraps
from flask import session, redirect, url_for, flash

from models.user import UserRole


def login_required(role: UserRole | None = None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Tafadhali ingia kwanza.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role.value:
                flash("Huna ruhusa ya kufungua ukurasa huu.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def role_dashboard(role: str) -> str:
    return {
        UserRole.BOSS.value: "pro_dashboard",
        UserRole.MANAGER.value: "pro_dashboard",
        UserRole.EMPLOYEE.value: "pro_dashboard",
    }.get(role, "login")
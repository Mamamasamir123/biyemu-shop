import uuid
from datetime import datetime
from typing import Optional

from models.staff_connection import ConnectionStatus, StaffConnection
from models.user import User, UserRole
from storage.json_storage import JsonStorage


class ConnectionService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get_all(self) -> list[StaffConnection]:
        return self.storage.load_list("staff_connections", StaffConnection.from_dict)

    def find_between(self, user_a: str, user_b: str) -> Optional[StaffConnection]:
        pair = {user_a, user_b}
        for conn in self.get_all():
            if {conn.requester_id, conn.target_id} == pair:
                return conn
        return None

    def same_shop_auto(self, user: User, other: User) -> bool:
        if not user or not other or user.id == other.id:
            return False
        if not user.shop_id or not other.shop_id:
            return False
        return user.shop_id == other.shop_id and user.active and other.active

    def is_connected(self, user: User, other: User) -> bool:
        if not user or not other or user.id == other.id or not other.active:
            return False
        if self.same_shop_auto(user, other):
            return True
        conn = self.find_between(user.id, other.id)
        return bool(conn and conn.status == ConnectionStatus.APPROVED)

    def connection_state(self, user: User, other: User) -> str:
        """none | approved | pending_out | pending_in | rejected"""
        if not user or not other or user.id == other.id:
            return "none"
        if self.same_shop_auto(user, other):
            return "approved"
        conn = self.find_between(user.id, other.id)
        if not conn:
            return "none"
        if conn.status == ConnectionStatus.APPROVED:
            return "approved"
        if conn.status == ConnectionStatus.REJECTED:
            return "rejected"
        if conn.requester_id == user.id:
            return "pending_out"
        return "pending_in"

    def request_connection(self, requester: User, target: User) -> StaffConnection:
        if not target.active or requester.id == target.id:
            raise ValueError("invalid_target")
        if self.is_connected(requester, target):
            raise ValueError("already_connected")
        existing = self.find_between(requester.id, target.id)
        if existing:
            if existing.status == ConnectionStatus.PENDING:
                raise ValueError("already_pending")
            if existing.status == ConnectionStatus.REJECTED:
                items = self.get_all()
                for i, conn in enumerate(items):
                    if conn.id == existing.id:
                        items[i].status = ConnectionStatus.PENDING
                        items[i].requester_id = requester.id
                        items[i].target_id = target.id
                        items[i].created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                        items[i].responded_at = ""
                        self.storage.save_list("staff_connections", items)
                        return items[i]
            raise ValueError("already_pending")
        conn = StaffConnection(
            id=str(uuid.uuid4())[:8],
            requester_id=requester.id,
            target_id=target.id,
            status=ConnectionStatus.PENDING,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        items = self.get_all()
        items.append(conn)
        self.storage.save_list("staff_connections", items)
        return conn

    def respond(self, conn_id: str, responder_id: str, approve: bool) -> StaffConnection:
        items = self.get_all()
        for i, conn in enumerate(items):
            if conn.id != conn_id:
                continue
            if conn.target_id != responder_id:
                raise ValueError("not_allowed")
            if conn.status != ConnectionStatus.PENDING:
                raise ValueError("not_pending")
            items[i].status = (
                ConnectionStatus.APPROVED if approve else ConnectionStatus.REJECTED
            )
            items[i].responded_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.storage.save_list("staff_connections", items)
            return items[i]
        raise ValueError("not_found")

    def get_pending_incoming_count(self, user_id: str) -> int:
        return sum(
            1
            for c in self.get_all()
            if c.target_id == user_id and c.status == ConnectionStatus.PENDING
        )

    def allowed_shop_ids_for_user(self, user: User, all_users: list[User]) -> set[str]:
        shop_ids: set[str] = set()
        if user.shop_id:
            shop_ids.add(user.shop_id)
        for other in all_users:
            if other.id == user.id or not other.shop_id:
                continue
            if self.is_connected(user, other):
                shop_ids.add(other.shop_id)
        return shop_ids

    def directory_users(self, user: User, all_users: list[User]) -> list[User]:
        return [
            u
            for u in all_users
            if u.id != user.id
            and u.active
            and u.role in (UserRole.BOSS, UserRole.MANAGER, UserRole.EMPLOYEE)
        ]
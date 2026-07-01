import uuid
from datetime import datetime
from typing import Optional

from models.approval import ApprovalRequest, ApprovalStatus, ApprovalType
from storage.json_storage import JsonStorage


class ApprovalService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get_all(self, status: Optional[ApprovalStatus] = None) -> list[ApprovalRequest]:
        requests = self.storage.load_list("approvals", ApprovalRequest.from_dict)
        if status:
            return [r for r in requests if r.status == status]
        return requests

    def get_pending(self) -> list[ApprovalRequest]:
        return self.get_all(ApprovalStatus.PENDING)

    def get_pending_for_boss(self) -> list[ApprovalRequest]:
        return [r for r in self.get_pending() if r.approver_role == "boss"]

    def get_pending_for_manager(self, shop_id: str) -> list[ApprovalRequest]:
        return [
            r for r in self.get_pending()
            if r.approver_role == "manager" and r.shop_id == shop_id
        ]

    def has_pending_delete(self, product_id: str) -> bool:
        return any(
            r.approval_type == ApprovalType.DELETE_PRODUCT
            and r.status == ApprovalStatus.PENDING
            and r.target_id == product_id
            for r in self.get_all()
        )

    def has_pending_delete_sale(self, sale_id: str) -> bool:
        return any(
            r.approval_type == ApprovalType.DELETE_SALE
            and r.status == ApprovalStatus.PENDING
            and r.target_id == sale_id
            for r in self.get_all()
        )

    def get_pending_delete_sale_ids(self, shop_id: str | None = None) -> set[str]:
        ids: set[str] = set()
        for req in self.get_pending():
            if req.approval_type != ApprovalType.DELETE_SALE:
                continue
            if shop_id and req.shop_id != shop_id:
                continue
            if req.target_id:
                ids.add(req.target_id)
        return ids

    def get_pending_delete_ids(self, shop_id: str | None = None) -> set[str]:
        ids: set[str] = set()
        for req in self.get_pending():
            if req.approval_type != ApprovalType.DELETE_PRODUCT:
                continue
            if shop_id and req.shop_id != shop_id:
                continue
            if req.target_id:
                ids.add(req.target_id)
        return ids

    def create_request(
        self,
        approval_type: ApprovalType,
        requested_by: str,
        requester_name: str,
        shop_id: str,
        details: str,
        target_id: str,
        *,
        approver_role: str = "boss",
        payload: str = "",
    ) -> ApprovalRequest:
        if approval_type == ApprovalType.DELETE_PRODUCT and target_id:
            if self.has_pending_delete(target_id):
                raise ValueError("pending_delete")
        request = ApprovalRequest(
            id=str(uuid.uuid4())[:8],
            approval_type=approval_type,
            requested_by=requested_by,
            requester_name=requester_name,
            shop_id=shop_id,
            details=details,
            target_id=target_id,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            approver_role=approver_role,
            payload=payload,
        )
        requests = self.get_all()
        requests.append(request)
        self.storage.save_list("approvals", requests)
        return request

    def approve(self, request_id: str, boss_note: str = "") -> ApprovalRequest:
        return self._update_status(request_id, ApprovalStatus.APPROVED, boss_note)

    def reject(self, request_id: str, boss_note: str = "") -> ApprovalRequest:
        return self._update_status(request_id, ApprovalStatus.REJECTED, boss_note)

    def cancel(self, request_id: str, note: str = "") -> ApprovalRequest:
        return self._update_status(request_id, ApprovalStatus.CANCELLED, note)

    def delete_request(self, request_id: str) -> None:
        requests = self.get_all()
        filtered = [r for r in requests if r.id != request_id]
        if len(filtered) == len(requests):
            raise ValueError("Ombi la idhini halijapatikana.")
        self.storage.save_list("approvals", filtered)

    def get_by_id(self, request_id: str) -> Optional[ApprovalRequest]:
        return next((r for r in self.get_all() if r.id == request_id), None)

    def _update_status(
        self, request_id: str, status: ApprovalStatus, boss_note: str
    ) -> ApprovalRequest:
        requests = self.get_all()
        for i, req in enumerate(requests):
            if req.id == request_id:
                requests[i].status = status
                requests[i].boss_note = boss_note
                self.storage.save_list("approvals", requests)
                return requests[i]
        raise ValueError("Ombi la idhini halijapatikana.")
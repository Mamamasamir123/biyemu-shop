import base64
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from werkzeug.utils import secure_filename

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app import BiyeMuApp
from seed_data import seed_if_empty
from models.user import UserRole, EmployeePermissions
from models.approval import ApprovalRequest, ApprovalType, ApprovalStatus
from models.cash_remittance import CashRemittance, RemittanceStatus
from models.notification import NotificationType, NOTIFICATION_PREF_KEYS, DEFAULT_NOTIFICATION_PREFS
from web.auth import login_required, role_dashboard
from web.i18n import t, get_language, role_label, brand_title, brand_tagline, SUPPORTED, TRANSLATIONS
from ui.swahili import aina_ombi, hali_ombi, AINA_OMBII

app = BiyeMuApp()
seed_if_empty(app.storage)

CURRENCY_LABEL = "Fbi"


def _money_str(value) -> str:
    try:
        return f"{float(value):,.0f} {CURRENCY_LABEL}"
    except (TypeError, ValueError):
        return f"0 {CURRENCY_LABEL}"


def _normalize_amount_display(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return _money_str(value)
    text = str(value).strip()
    if not text:
        return ""
    upper = text.upper()
    for suffix in (f" {CURRENCY_LABEL}", " TZS"):
        if upper.endswith(suffix.upper()):
            text = text[: -len(suffix)].strip()
            break
    try:
        return _money_str(float(text.replace(",", "")))
    except ValueError:
        return str(value).strip()

UPLOAD_DIR = ROOT / "static" / "uploads" / "profiles"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SHOP_LOGO_DIR = ROOT / "static" / "uploads" / "shops" / "logos"
SHOP_COVER_DIR = ROOT / "static" / "uploads" / "shops" / "covers"
SHOP_LOGO_DIR.mkdir(parents=True, exist_ok=True)
SHOP_COVER_DIR.mkdir(parents=True, exist_ok=True)
BANNER_DIR = ROOT / "static" / "uploads" / "banners"
BANNER_DIR.mkdir(parents=True, exist_ok=True)
PRODUCT_IMAGE_DIR = ROOT / "static" / "uploads" / "products"
PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_PHOTO = {"png", "jpg", "jpeg", "webp", "gif"}

flask_app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
)
flask_app.secret_key = os.environ.get(
    "SECRET_KEY", "biyemu-dev-key-change-in-production"
)
flask_app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
if os.environ.get("RENDER"):
    flask_app.config["SESSION_COOKIE_SECURE"] = True
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def _lang() -> str:
    # Strongly prefer session lang (set when user changes it)
    if "lang" in session:
        return session.get("lang")
    user = None
    if "user_id" in session:
        user = app.user_service.get_by_id(session["user_id"])
        if user and user.language:
            session["lang"] = user.language
            return user.language
    return get_language()


def _msg(key: str) -> str:
    return t(key, _lang())


def _can_manage_shop(user, shop_id: str) -> bool:
    if user.role == UserRole.BOSS:
        return True
    return user.role == UserRole.MANAGER and user.shop_id == shop_id


_PRODUCT_APPROVAL_TYPES = {ApprovalType.ADD_PRODUCT, ApprovalType.DELETE_PRODUCT}


def _is_product_approval(req) -> bool:
    return req.approval_type in _PRODUCT_APPROVAL_TYPES


def _can_approve_request(req, user) -> bool:
    if req.approver_role == UserRole.BOSS.value:
        return user.role == UserRole.BOSS
    if req.approver_role == UserRole.MANAGER.value:
        return user.role == UserRole.MANAGER and user.shop_id == req.shop_id
    return False


def _can_user_sell(user) -> bool:
    if not user or not user.shop_id:
        return False
    if user.role == UserRole.MANAGER:
        return True
    if user.role == UserRole.EMPLOYEE:
        return user.permissions.can_sell and user.permissions.can_record_sales
    return False


def _can_user_add_product(user) -> bool:
    return bool(user and user.shop_id and user.role == UserRole.MANAGER)


def _can_manage_product_approval(req, user) -> bool:
    if req.status != ApprovalStatus.PENDING or not _is_product_approval(req):
        return False
    if req.requested_by == user.id:
        return True
    return _can_approve_request(req, user)


def _process_approval_bulk(user, req_ids: list[str], action: str, note: str) -> int:
    done = 0
    lang = _lang()
    for req_id in req_ids:
        req = app.approval_service.get_by_id(req_id)
        if not req:
            continue
        if action in ("approve", "reject"):
            if not _can_approve_request(req, user):
                continue
            if user.role == UserRole.BOSS and req.approver_role != UserRole.BOSS.value:
                continue
            if user.role == UserRole.MANAGER and (
                req.approver_role != UserRole.MANAGER.value
                or req.shop_id != user.shop_id
            ):
                continue
            if action == "approve":
                app.approval_service.approve(req_id, note or t("approved", lang))
                _execute_approval(req, user.id, user.full_name)
                _notify_approval_result(req, "approved")
            else:
                app.approval_service.reject(req_id, note or t("rejected", lang))
                _notify_approval_result(req, "rejected")
            done += 1
        elif action == "cancel":
            if not _can_manage_product_approval(req, user):
                continue
            app.approval_service.cancel(req_id, note or t("approval_suspended", lang))
            _notify_approval_result(req, "cancelled")
            done += 1
    return done


def _chat_directory(user, shops: dict) -> list[dict]:
    if not user:
        return []
    all_users = app.user_service.get_all()
    conn_svc = app.connection_service
    entries = []
    for contact in conn_svc.directory_users(user, all_users):
        state = conn_svc.connection_state(user, contact)
        last = app.chat_service.get_last_message_between(user.id, contact.id)
        unread = app.chat_service.get_unread_count_from(user.id, contact.id)
        conn = conn_svc.find_between(user.id, contact.id)
        entries.append(
            {
                "user": contact,
                "shop_name": shops.get(contact.shop_id, ""),
                "connection_state": state,
                "can_chat": state == "approved",
                "connection_id": conn.id if conn else "",
                "last_message": last,
                "unread": unread if state == "approved" else 0,
            }
        )

    def sort_key(item: dict):
        state_rank = {
            "approved": 3,
            "pending_in": 2,
            "pending_out": 1,
            "none": 0,
            "rejected": 0,
        }
        last = item["last_message"]
        ts = last.created_at if last else ""
        return (
            item["unread"] > 0,
            state_rank.get(item["connection_state"], 0),
            ts,
            item["user"].full_name.lower(),
        )

    return sorted(entries, key=sort_key, reverse=True)


def _people_sidebar_entries(user) -> list[dict]:
    if not user:
        return []
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    all_users = app.user_service.get_all()
    entries = []
    for person in app.connection_service.directory_users(user, all_users):
        state = app.connection_service.connection_state(user, person)
        entries.append(
            {
                "user": person,
                "shop_name": shops.get(person.shop_id, ""),
                "connection_state": state,
            }
        )
    return sorted(entries, key=lambda e: e["user"].full_name.lower())


def _profile_shop_url(viewer, shop) -> str | None:
    if not viewer or not shop:
        return None
    if viewer.role == UserRole.BOSS:
        return url_for("boss_shop_view", shop_id=shop.id)
    if viewer.role == UserRole.MANAGER and viewer.shop_id == shop.id:
        return url_for("manager_shop_view")
    if viewer.role == UserRole.EMPLOYEE and viewer.shop_id == shop.id:
        return url_for("employee_products")
    return None


def _build_profile_context(viewer, profile_user: "User") -> dict:
    is_own = viewer.id == profile_user.id
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    shop = None
    shop_products = []
    display_shop_name = shops.get(profile_user.shop_id, "")
    connection_state = (
        "approved" if is_own else app.connection_service.connection_state(viewer, profile_user)
    )
    conn = (
        None
        if is_own
        else app.connection_service.find_between(viewer.id, profile_user.id)
    )
    can_view_shop = is_own or app.connection_service.is_connected(viewer, profile_user)
    if profile_user.shop_id and can_view_shop:
        shop = app.shop_service.get_by_id(profile_user.shop_id)
        if shop:
            display_shop_name = shop.name
            shop_products = [
                p
                for p in app.product_service.get_all(profile_user.shop_id)
                if p.quantity > 0
            ]
    return {
        "profile_user": profile_user,
        "is_own_profile": is_own,
        "shop": shop,
        "profile_shop_name": display_shop_name,
        "profile_shop_url": _profile_shop_url(viewer, shop) if shop else None,
        "shop_products": shop_products,
        "can_view_shop": can_view_shop,
        "connection_state": connection_state,
        "connection_id": conn.id if conn else "",
        "can_chat": is_own or connection_state == "approved",
    }


def _can_chat_with(user, partner) -> bool:
    if not user or not partner or user.id == partner.id or not partner.active:
        return False
    return app.connection_service.is_connected(user, partner)


def _execute_approval(req, approver_id: str, approver_name: str):
    if req.approval_type == ApprovalType.DELETE_PRODUCT:
        product = app.product_service.get_by_id(req.target_id)
        if product:
            app.trash_service.archive_product(
                product, approver_id, approver_name, req.details
            )
            app.product_service.delete_product(req.target_id)
    elif req.approval_type == ApprovalType.ADD_PRODUCT:
        data = json.loads(req.payload) if req.payload else {}
        if data:
            app.product_service.add_product(
                name=data["name"],
                price=float(data["price"]),
                quantity=int(data["quantity"]),
                shop_id=data["shop_id"],
                cost_price=float(data.get("cost_price", 0)),
                category=data.get("category", ""),
                image=data.get("image", ""),
            )
    elif req.approval_type == ApprovalType.DELETE_SALE:
        sale = app.sale_service.get_by_id(req.target_id)
        if sale:
            product = app.product_service.get_by_id(sale.product_id)
            if product:
                app.product_service.update_product(
                    sale.product_id,
                    quantity=product.quantity + sale.quantity,
                )
            app.sale_service.delete_sale(sale.id)


def _user_lang(user) -> str:
    if user and user.language in SUPPORTED:
        return user.language
    return "sw"


def _translate(lang: str, key: str, **kwargs) -> str:
    current = lang if lang in SUPPORTED else "sw"
    text = TRANSLATIONS.get(current, TRANSLATIONS["sw"]).get(
        key, TRANSLATIONS["sw"].get(key, key)
    )
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def _approval_link_for(user) -> str:
    if user.role == UserRole.BOSS:
        return url_for("boss_approvals")
    if user.role == UserRole.MANAGER:
        return url_for("manager_approvals")
    return url_for("notifications_list")


def _sales_link_for(user, shop_id: str) -> str:
    if user.role == UserRole.BOSS:
        return url_for("boss_shop_sales", shop_id=shop_id)
    if user.role == UserRole.MANAGER:
        return url_for("manager_shop_sales")
    return url_for("employee_sales")


def _products_link_for(user, shop_id: str) -> str:
    if user.role == UserRole.BOSS:
        return url_for("boss_shop_products", shop_id=shop_id)
    if user.role == UserRole.MANAGER:
        return url_for("manager_shop_products")
    return url_for("employee_products")


def _cash_link_for(user) -> str:
    if user.role == UserRole.BOSS:
        return url_for("boss_cash")
    if user.role == UserRole.MANAGER:
        return url_for("manager_cash")
    return url_for("employee_cash")


def _cash_handover_link_for(user) -> str:
    if user.role == UserRole.MANAGER:
        return url_for("manager_submit_cash")
    return url_for("employee_cash")


def _notify_cash_submitted(remittance) -> None:
    shop = app.shop_service.get_by_id(remittance.shop_id)
    shop_name = shop.name if shop else remittance.shop_id
    receiver = app.user_service.get_by_id(remittance.receiver_id)
    if not receiver:
        return
    lang = _user_lang(receiver)
    msg_key = (
        "notif_cash_manager_submitted_msg"
        if remittance.remittance_kind == "from_manager"
        else "notif_cash_submitted_msg"
    )
    cash_meta = {
        "variant": (
            "manager_submitted"
            if remittance.remittance_kind == "from_manager"
            else "submitted"
        ),
        "remittance_id": remittance.id,
        "employee_name": remittance.employee_name,
        "amount": _money_str(remittance.amount),
        "shop_id": remittance.shop_id,
        "shop_name": shop_name,
        "shop_logo": shop.logo if shop else "",
    }
    app.notification_service.send(
        remittance.receiver_id,
        NotificationType.CASH_REMITTANCE.value,
        _translate(lang, "notif_cash_submitted_title"),
        _translate(
            lang,
            msg_key,
            employee=remittance.employee_name,
            manager=remittance.employee_name,
            amount=cash_meta["amount"],
            shop=shop_name,
        ),
        _cash_link_for(receiver),
        meta=cash_meta,
    )


def _notify_cash_rejected(remittance) -> None:
    submitter = app.user_service.get_by_id(remittance.employee_id)
    if not submitter:
        return
    lang = _user_lang(submitter)
    link = (
        url_for("manager_submit_cash")
        if remittance.remittance_kind == "from_manager"
        else url_for("employee_cash")
    )
    app.notification_service.send(
        remittance.employee_id,
        NotificationType.CASH_REMITTANCE.value,
        _translate(lang, "notif_cash_rejected_title"),
        _translate(
            lang,
            "notif_cash_rejected_msg",
            name=remittance.confirmed_by_name,
            amount=_money_str(remittance.amount),
            reason=remittance.note or _translate(lang, "reject_reason"),
        ),
        link,
        meta={
            "variant": "rejected",
            "name": remittance.confirmed_by_name,
            "amount": _money_str(remittance.amount),
            "reason": remittance.note or "",
        },
    )


def _notify_cash_confirmed(remittance) -> None:
    submitter = app.user_service.get_by_id(remittance.employee_id)
    if not submitter:
        return
    lang = _user_lang(submitter)
    link = (
        url_for("manager_submit_cash")
        if remittance.remittance_kind == "from_manager"
        else url_for("employee_cash")
    )
    cash_meta = {
        "variant": "confirmed",
        "name": remittance.confirmed_by_name,
        "amount": _money_str(remittance.amount),
    }
    app.notification_service.send(
        remittance.employee_id,
        NotificationType.CASH_REMITTANCE.value,
        _translate(lang, "notif_cash_confirmed_title"),
        _translate(
            lang,
            "notif_cash_confirmed_msg",
            name=remittance.confirmed_by_name,
            amount=cash_meta["amount"],
        ),
        link,
        meta=cash_meta,
    )


def _notify_approval_created(req) -> None:
    shop = app.shop_service.get_by_id(req.shop_id)
    shop_name = shop.name if shop else req.shop_id
    type_label = aina_ombi(req.approval_type)
    recipients = app.notification_service.recipients_for_approval(
        req.approver_role, req.shop_id
    )
    for uid in recipients:
        if uid == req.requested_by:
            continue
        user = app.user_service.get_by_id(uid)
        if not user:
            continue
        lang = _user_lang(user)
        app.notification_service.send(
            uid,
            NotificationType.APPROVAL_INCOMING.value,
            _translate(lang, "notif_approval_incoming_title"),
            _translate(
                lang,
                "notif_approval_incoming_msg",
                name=req.requester_name,
                type=type_label,
                shop=shop_name,
            ),
            _approval_link_for(user),
            meta={
                "approval_id": req.id,
                "name": req.requester_name,
                "approval_type": req.approval_type.value,
                "shop_id": req.shop_id,
                "shop_name": shop_name,
                "shop_logo": shop.logo if shop else "",
            },
        )


def _notify_approval_result(req, result: str) -> None:
    user = app.user_service.get_by_id(req.requested_by)
    if not user:
        return
    lang = _user_lang(user)
    keys = {
        "approved": ("notif_approval_approved_title", "notif_approval_approved_msg"),
        "rejected": ("notif_approval_rejected_title", "notif_approval_rejected_msg"),
        "cancelled": ("notif_approval_cancelled_title", "notif_approval_cancelled_msg"),
    }
    title_key, msg_key = keys[result]
    type_label = aina_ombi(req.approval_type)
    app.notification_service.send(
        req.requested_by,
        NotificationType.APPROVAL_RESULT.value,
        _translate(lang, title_key),
        _translate(lang, msg_key, type=type_label, details=req.details),
        _approval_link_for(user),
        meta={
            "result": result,
            "approval_type": req.approval_type.value,
            "details": req.details,
        },
    )


def _notify_sale(sale) -> None:
    shop = app.shop_service.get_by_id(sale.shop_id)
    shop_name = shop.name if shop else sale.shop_id
    product = app.product_service.get_by_id(sale.product_id)
    sale_meta = {
        "shop_id": sale.shop_id,
        "shop_logo": shop.logo if shop else "",
        "shop_name": shop_name,
        "employee_name": sale.employee_name,
        "employee_id": sale.employee_id,
        "product_id": sale.product_id,
        "product_name": sale.product_name,
        "product_image": product.image if product else "",
        "qty": sale.quantity,
        "amount": _money_str(sale.total_amount),
    }
    recipients = app.notification_service.recipients_for_shop_managers(sale.shop_id)
    for uid in recipients:
        user = app.user_service.get_by_id(uid)
        if not user:
            continue
        lang = _user_lang(user)
        app.notification_service.send(
            uid,
            NotificationType.SALE_NEW.value,
            _translate(lang, "notif_sale_title"),
            _translate(
                lang,
                "notif_sale_msg",
                employee=sale.employee_name,
                product=sale.product_name,
                qty=sale.quantity,
                amount=_money_str(sale.total_amount),
                shop=shop_name,
            ),
            _sales_link_for(user, sale.shop_id),
            meta=sale_meta,
        )


def _notify_low_stock(product) -> None:
    if product.quantity > app.notification_service.LOW_STOCK_THRESHOLD:
        return
    shop = app.shop_service.get_by_id(product.shop_id)
    shop_name = shop.name if shop else product.shop_id
    recipients = app.notification_service.recipients_for_shop_managers(product.shop_id)
    for uid in recipients:
        user = app.user_service.get_by_id(uid)
        if not user:
            continue
        lang = _user_lang(user)
        app.notification_service.send(
            uid,
            NotificationType.LOW_STOCK.value,
            _translate(lang, "notif_low_stock_title"),
            _translate(
                lang,
                "notif_low_stock_msg",
                product=product.name,
                qty=product.quantity,
                shop=shop_name,
            ),
            _products_link_for(user, product.shop_id),
            meta={
                "product_name": product.name,
                "qty": product.quantity,
                "shop_id": product.shop_id,
                "shop_name": shop_name,
                "shop_logo": shop.logo if shop else "",
            },
        )


def _notify_staff_event(
    shop_id: str | None,
    title_key: str,
    msg_key: str,
    *,
    name: str,
    exclude_user_id: str | None = None,
) -> None:
    shop = app.shop_service.get_by_id(shop_id) if shop_id else None
    shop_name = shop.name if shop else _translate("sw", "shops")
    if shop_id:
        recipients = app.notification_service.recipients_for_shop_managers(shop_id)
    else:
        recipients = [u.id for u in app.user_service.get_all() if u.role == UserRole.BOSS]
    for uid in recipients:
        if uid == exclude_user_id:
            continue
        user = app.user_service.get_by_id(uid)
        if not user:
            continue
        lang = _user_lang(user)
        link = url_for("boss_staff") if user.role == UserRole.BOSS else url_for("manager_employees")
        variant = "added" if "added" in msg_key else "removed"
        app.notification_service.send(
            uid,
            NotificationType.STAFF.value,
            _translate(lang, title_key),
            _translate(lang, msg_key, name=name, shop=shop_name),
            link,
            meta={
                "variant": variant,
                "name": name,
                "shop_id": shop_id or "",
                "shop_name": shop_name,
                "shop_logo": shop.logo if shop else "",
            },
        )


NOTIFICATION_ICONS = {
    NotificationType.APPROVAL_INCOMING.value: "✅",
    NotificationType.APPROVAL_RESULT.value: "📋",
    NotificationType.SALE_NEW.value: "💰",
    NotificationType.LOW_STOCK.value: "⚠️",
    NotificationType.STAFF.value: "👥",
    NotificationType.CASH_REMITTANCE.value: "💵",
}

_SALE_MSG_RE = re.compile(
    r"^(.+?)\s+(?:ameuza|sold|yagurishije)\s+(.+?)\s+x(\d+)\s+—\s+([\d,]+)\s+(?:TZS|Fbi)",
    re.IGNORECASE,
)
_SHOP_NAME_RE = re.compile(r"\(([^)]+)\)\s*$")
_CASH_SUBMITTED_RE = re.compile(
    r"^(.+?)\s+(?:amewasilisha|submitted|yohereje)\s+([\d,]+)\s+(?:TZS|Fbi)\s+—\s+(.+)$",
    re.IGNORECASE,
)
_CASH_MANAGER_RE = re.compile(
    r"^(.+?)\s+(?:amewasilisha|submitted|yohereje)\s+([\d,]+)\s+(?:TZS|Fbi)(?:\s+ya duka|\s+shop cash|\s+y'iduka)\s+—\s+(.+)$",
    re.IGNORECASE,
)
_CASH_CONFIRMED_RE = re.compile(
    r"^(.+?)\s+(?:amethibitisha kupokea|confirmed receiving your|yemeje kwakira)\s+([\d,]+)\s+(?:TZS|Fbi)",
    re.IGNORECASE,
)
_LOW_STOCK_RE = re.compile(
    r"^(.+?)\s+(?:inabaki|has only|isigaye)\s+(\d+)\s+(?:tu kwenye|left in|gusa muri)\s+(.+)$",
    re.IGNORECASE,
)
_APPROVAL_INCOMING_RE = re.compile(
    r"^(.+?)\s+(?:ametuma ombi la|sent a|yohereje icyifuzo cya)\s+(.+?)\s+—\s+(.+)$",
    re.IGNORECASE,
)
_STAFF_ADDED_RE = re.compile(
    r"^(.+?)\s+(?:amesajiliwa kwenye|was registered at|yanditswe muri)\s+(.+)$",
    re.IGNORECASE,
)
_STAFF_REMOVED_RE = re.compile(
    r"^(.+?)\s+(?:ameondolewa kutoka|was removed from|yakuweho muri)\s+(.+)$",
    re.IGNORECASE,
)
_APPROVAL_TYPE_FROM_SW = {label: kind.value for kind, label in AINA_OMBII.items()}


def _approval_type_label(approval_type: str, lang: str) -> str:
    if not approval_type:
        return ""
    key = f"approval_type_{approval_type}"
    label = _translate(lang, key)
    if label != key:
        return label
    try:
        return aina_ombi(ApprovalType(approval_type))
    except ValueError:
        return approval_type


def _time_ago(created_at: str, lang: str) -> str:
    if not created_at:
        return ""
    try:
        dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M")
    except ValueError:
        return created_at
    delta = datetime.now() - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return _translate(lang, "time_ago_now")
    minutes = seconds // 60
    if minutes < 60:
        return _translate(lang, "time_ago_minutes", n=minutes)
    hours = minutes // 60
    if hours < 24:
        return _translate(lang, "time_ago_hours", n=hours)
    days = hours // 24
    if days < 7:
        return _translate(lang, "time_ago_days", n=days)
    weeks = days // 7
    if weeks < 5:
        return _translate(lang, "time_ago_weeks", n=weeks)
    return created_at


def _shop_logo_url(logo: str) -> str:
    if logo:
        return url_for("static", filename=f"uploads/shops/logos/{logo}")
    return ""


def _product_image_url(image: str) -> str:
    if image:
        return url_for("static", filename=f"uploads/products/{image}")
    return ""


def _resolve_shop_logo(shop_id: str = "", shop_name: str = "") -> tuple[str, str]:
    shop = None
    if shop_id:
        shop = app.shop_service.get_by_id(shop_id)
    elif shop_name:
        for s in app.shop_service.get_all():
            if s.name == shop_name:
                shop = s
                break
    if not shop:
        return "", shop_name or "?"
    letter = shop.name.replace("BiyeMu ", "")[0].upper() if shop.name else "?"
    return _shop_logo_url(shop.logo), letter


def _parse_sale_from_message(message: str) -> dict:
    employee = ""
    product = ""
    shop_name = ""
    qty = ""
    amount = ""
    m = _SALE_MSG_RE.match(message.strip())
    if m:
        employee = m.group(1).strip()
        product = m.group(2).strip()
        qty = m.group(3).strip()
        amount = m.group(4).strip()
    sm = _SHOP_NAME_RE.search(message)
    if sm:
        shop_name = sm.group(1).strip()
    return {
        "employee_name": employee,
        "product_name": product,
        "shop_name": shop_name,
        "qty": qty,
        "amount": amount,
    }


def _parse_notification_meta(note) -> dict:
    meta = dict(note.meta or {})
    msg = (note.message or "").strip()
    ntype = note.notification_type

    if ntype == NotificationType.SALE_NEW.value:
        parsed = _parse_sale_from_message(msg)
        for key, value in parsed.items():
            meta.setdefault(key, value)
    elif ntype == NotificationType.CASH_REMITTANCE.value:
        if "variant" not in meta:
            m = _CASH_CONFIRMED_RE.match(msg)
            if m:
                meta.setdefault("variant", "confirmed")
                meta.setdefault("name", m.group(1).strip())
                meta.setdefault("amount", m.group(2).strip())
            else:
                m = _CASH_MANAGER_RE.match(msg)
                if m:
                    meta.setdefault("variant", "manager_submitted")
                    meta.setdefault("employee_name", m.group(1).strip())
                    meta.setdefault("amount", m.group(2).strip())
                    meta.setdefault("shop_name", m.group(3).strip())
                else:
                    m = _CASH_SUBMITTED_RE.match(msg)
                    if m:
                        meta.setdefault("variant", "submitted")
                        meta.setdefault("employee_name", m.group(1).strip())
                        meta.setdefault("amount", m.group(2).strip())
                        meta.setdefault("shop_name", m.group(3).strip())
    elif ntype == NotificationType.LOW_STOCK.value:
        m = _LOW_STOCK_RE.match(msg)
        if m:
            meta.setdefault("product_name", m.group(1).strip())
            meta.setdefault("qty", int(m.group(2)))
            meta.setdefault("shop_name", m.group(3).strip())
    elif ntype == NotificationType.APPROVAL_INCOMING.value:
        m = _APPROVAL_INCOMING_RE.match(msg)
        if m:
            meta.setdefault("name", m.group(1).strip())
            type_text = m.group(2).strip()
            meta.setdefault("approval_type", _APPROVAL_TYPE_FROM_SW.get(type_text, ""))
            meta.setdefault("approval_type_text", type_text)
            meta.setdefault("shop_name", m.group(3).strip())
    elif ntype == NotificationType.APPROVAL_RESULT.value:
        if "result" not in meta:
            title = (note.title or "").lower()
            if any(w in title for w in ("approved", "idhinishwa", "emewe")):
                meta.setdefault("result", "approved")
            elif any(w in title for w in ("rejected", "kataliwa", "yanzwe")):
                meta.setdefault("result", "rejected")
            elif any(w in title for w in ("suspended", "simamishwa", "hagaritswe", "cancelled")):
                meta.setdefault("result", "cancelled")
        if "details" not in meta and ":" in msg:
            meta.setdefault("details", msg.split(":", 1)[1].strip())
        if "approval_type" not in meta:
            for sw_label, kind in _APPROVAL_TYPE_FROM_SW.items():
                if sw_label.lower() in msg.lower():
                    meta.setdefault("approval_type", kind)
                    break
    elif ntype == NotificationType.STAFF.value:
        if "variant" not in meta:
            m = _STAFF_ADDED_RE.match(msg)
            if m:
                meta.setdefault("variant", "added")
                meta.setdefault("name", m.group(1).strip())
                meta.setdefault("shop_name", m.group(2).strip())
            else:
                m = _STAFF_REMOVED_RE.match(msg)
                if m:
                    meta.setdefault("variant", "removed")
                    meta.setdefault("name", m.group(1).strip())
                    meta.setdefault("shop_name", m.group(2).strip())

    if meta.get("amount"):
        meta["amount"] = _normalize_amount_display(meta["amount"])

    return meta


def _rebuild_notification_text(note, lang: str, meta: dict) -> dict:
    ntype = note.notification_type

    if ntype == NotificationType.SALE_NEW.value:
        employee = meta.get("employee_name", "")
        product = meta.get("product_name", "")
        amount = meta.get("amount", "")
        shop = meta.get("shop_name", "")
        detail = (
            _translate(lang, "notif_sale_fb_detail", amount=amount, shop=shop)
            if amount and shop
            else ""
        )
        return {
            "is_sale": True,
            "actor_name": employee,
            "highlight": product,
            "detail": detail,
            "headline": "",
            "body": "",
        }

    if ntype == NotificationType.CASH_REMITTANCE.value:
        variant = meta.get("variant", "submitted")
        amount = meta.get("amount", "")
        if variant == "confirmed":
            headline = _translate(lang, "notif_cash_confirmed_title")
            body = _translate(
                lang,
                "notif_cash_confirmed_msg",
                name=meta.get("name", ""),
                amount=amount,
            )
        elif variant == "manager_submitted":
            headline = _translate(lang, "notif_cash_submitted_title")
            body = _translate(
                lang,
                "notif_cash_manager_submitted_msg",
                manager=meta.get("employee_name", ""),
                amount=amount,
                shop=meta.get("shop_name", ""),
            )
        else:
            headline = _translate(lang, "notif_cash_submitted_title")
            body = _translate(
                lang,
                "notif_cash_submitted_msg",
                employee=meta.get("employee_name", ""),
                amount=amount,
                shop=meta.get("shop_name", ""),
            )
        return {"is_sale": False, "headline": headline, "body": body, "detail": ""}

    if ntype == NotificationType.LOW_STOCK.value:
        headline = _translate(lang, "notif_low_stock_title")
        body = _translate(
            lang,
            "notif_low_stock_msg",
            product=meta.get("product_name", ""),
            qty=meta.get("qty", ""),
            shop=meta.get("shop_name", ""),
        )
        return {"is_sale": False, "headline": headline, "body": body, "detail": ""}

    if ntype == NotificationType.APPROVAL_INCOMING.value:
        type_label = _approval_type_label(
            meta.get("approval_type", ""),
            lang,
        ) or meta.get("approval_type_text", "")
        headline = _translate(lang, "notif_approval_incoming_title")
        body = _translate(
            lang,
            "notif_approval_incoming_msg",
            name=meta.get("name", ""),
            type=type_label,
            shop=meta.get("shop_name", ""),
        )
        return {"is_sale": False, "headline": headline, "body": body, "detail": ""}

    if ntype == NotificationType.APPROVAL_RESULT.value:
        result = meta.get("result", "approved")
        keys = {
            "approved": ("notif_approval_approved_title", "notif_approval_approved_msg"),
            "rejected": ("notif_approval_rejected_title", "notif_approval_rejected_msg"),
            "cancelled": ("notif_approval_cancelled_title", "notif_approval_cancelled_msg"),
        }
        title_key, msg_key = keys.get(result, keys["approved"])
        type_label = _approval_type_label(meta.get("approval_type", ""), lang)
        headline = _translate(lang, title_key)
        body = _translate(
            lang,
            msg_key,
            type=type_label,
            details=meta.get("details", ""),
        )
        return {"is_sale": False, "headline": headline, "body": body, "detail": ""}

    if ntype == NotificationType.STAFF.value:
        variant = meta.get("variant", "added")
        if variant == "removed":
            headline = _translate(lang, "notif_staff_removed_title")
            body = _translate(
                lang,
                "notif_staff_removed_msg",
                name=meta.get("name", ""),
                shop=meta.get("shop_name", ""),
            )
        else:
            headline = _translate(lang, "notif_staff_added_title")
            body = _translate(
                lang,
                "notif_staff_added_msg",
                name=meta.get("name", ""),
                shop=meta.get("shop_name", ""),
            )
        return {"is_sale": False, "headline": headline, "body": body, "detail": ""}

    return {
        "is_sale": False,
        "headline": note.title,
        "body": note.message,
        "detail": "",
    }


def _notification_view(note, lang: str) -> dict:
    meta = _parse_notification_meta(note)
    text = _rebuild_notification_text(note, lang, meta)
    icon = NOTIFICATION_ICONS.get(note.notification_type, "🔔")
    avatar_url = ""
    avatar_letter = "?"
    thumb_url = ""

    shop_id = meta.get("shop_id", "")
    shop_name = meta.get("shop_name", "")
    shop_logo = meta.get("shop_logo", "")
    if shop_logo:
        avatar_url = _shop_logo_url(shop_logo)
        avatar_letter = shop_name.replace("BiyeMu ", "")[0].upper() if shop_name else "?"
    elif shop_id or shop_name:
        avatar_url, avatar_letter = _resolve_shop_logo(shop_id, shop_name)

    actor_name = meta.get("employee_name") or meta.get("name", "")
    if text.get("is_sale"):
        if not avatar_url and actor_name:
            avatar_letter = actor_name[0].upper()
        thumb_url = _product_image_url(meta.get("product_image", ""))
    elif not avatar_url:
        if actor_name:
            avatar_letter = actor_name[0].upper()
        else:
            avatar_letter = icon

    return {
        "id": note.id,
        "read": note.read,
        "link": note.link,
        "notification_type": note.notification_type,
        "time_ago": _time_ago(note.created_at, lang),
        "avatar_url": avatar_url,
        "avatar_letter": avatar_letter,
        "thumb_url": thumb_url,
        "actor_name": text.get("actor_name", ""),
        "highlight": text.get("highlight", ""),
        "headline": text.get("headline", ""),
        "body": text.get("body", ""),
        "detail": text.get("detail", ""),
        "is_sale": text.get("is_sale", False),
        "icon": icon,
    }


def _shop_dashboard_ctx(shop_id: str):
    shop = app.shop_service.get_by_id(shop_id)
    if not shop:
        return None, None
    dashboard = app.finance_service.get_shop_dashboard(shop_id)
    recent_sales = app.sale_service.get_all(shop_id)
    return shop, dict(
        dashboard=dashboard,
        recent_sales=recent_sales,
        pending_delete_sale_ids=_pending_delete_sale_ids(shop_id),
    )


def _shop_layout_ctx(shop, user, active_tab: str):
    can_edit = _can_manage_shop(user, shop.id)
    if user.role == UserRole.BOSS:
        shop_urls = {
            "overview": url_for("boss_shop_view", shop_id=shop.id),
            "products": url_for("boss_shop_products", shop_id=shop.id),
            "sales": url_for("boss_shop_sales", shop_id=shop.id),
            "staff": url_for("boss_shop_staff", shop_id=shop.id),
            "edit": url_for("boss_shop_edit", shop_id=shop.id),
        }
        back_url = url_for("boss_shops")
    else:
        shop_urls = {
            "overview": url_for("manager_shop_view"),
            "products": url_for("manager_shop_products"),
            "sales": url_for("manager_shop_sales"),
            "staff": None,
            "edit": url_for("manager_shop_edit"),
        }
        back_url = url_for("manager_dashboard")
    return dict(
        shop=shop,
        shop_urls=shop_urls,
        active_tab=active_tab,
        back_url=back_url,
        can_edit=can_edit,
    )


@flask_app.context_processor
def inject_globals():
    user = None
    shop_name = ""
    lang = _lang()
    if "user_id" in session:
        user = app.user_service.get_by_id(session["user_id"])
        if user:
            lang = get_language(user.language)
            session["lang"] = lang
            if user.shop_id:
                shop = app.shop_service.get_by_id(user.shop_id)
                shop_name = shop.name if shop else ""
    pending = 0
    pending_cash = 0
    held_cash = 0
    unread_notifications = 0
    unread_chat_messages = 0
    pending_connections = 0
    if user and user.role == UserRole.BOSS:
        pending = len(app.approval_service.get_pending_for_boss())
    notification_prefs = dict(DEFAULT_NOTIFICATION_PREFS)
    if user:
        unread_notifications = app.notification_service.get_unread_count(user.id)
        unread_chat_messages = app.chat_service.get_unread_count(user.id)
        pending_connections = app.connection_service.get_pending_incoming_count(user.id)
        notification_prefs = app.notification_service.get_user_prefs(user)
        if user.role in (UserRole.BOSS, UserRole.MANAGER):
            pending_cash = app.cash_remittance_service.count_pending_for_user(user)
        if user.role == UserRole.EMPLOYEE:
            held_cash = app.cash_remittance_service.get_held_total(user.id)
        elif user.role == UserRole.MANAGER and user.shop_id:
            held_cash = app.cash_remittance_service.get_shop_manager_held_total(user.shop_id)

    if lang not in SUPPORTED:
        lang = "sw"

    user_can_sell = _can_user_sell(user) if user else False
    user_can_add_product = _can_user_add_product(user) if user else False
    people_sidebar = _people_sidebar_entries(user) if user else []
    profile_view_id = ""
    if user and request.endpoint == "profile_view":
        profile_view_id = user.id
    elif user and request.endpoint == "profile_user_view":
        profile_view_id = request.view_args.get("user_id", "") if request.view_args else ""

    return dict(
        current_user=user,
        shop_name=shop_name,
        current_lang=lang,
        pending=pending,
        pending_cash=pending_cash,
        held_cash=held_cash,
        unread_notifications=unread_notifications,
        unread_chat_messages=unread_chat_messages,
        pending_connections=pending_connections,
        notification_prefs=notification_prefs,
        notification_pref_keys=NOTIFICATION_PREF_KEYS,
        user_can_sell=user_can_sell,
        user_can_add_product=user_can_add_product,
        people_sidebar=people_sidebar,
        profile_view_id=profile_view_id,
        app_brand_title=brand_title(lang),
        app_brand_tagline=brand_tagline(lang),
        t=lambda key, *args, **kwargs: t(key, args[0] if args else lang, **kwargs),
        role_label=lambda role: role_label(role, lang),
        jukumu=lambda role: role_label(role.value if hasattr(role, "value") else role, lang),
    )


def fmt_money(value: float) -> str:
    return _money_str(value)


flask_app.jinja_env.filters["money"] = fmt_money
flask_app.jinja_env.filters["abs"] = abs


@flask_app.template_filter("from_json")
def from_json_filter(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


@flask_app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("home_feed"))
    return redirect(url_for("login"))


@flask_app.route("/lugha", methods=["POST"])
def set_language():
    lang = request.form.get("language", "sw")
    if lang in SUPPORTED:
        session["lang"] = lang
        if "user_id" in session:
            app.user_service.update_profile(session["user_id"], language=lang)
    return redirect(request.referrer or url_for("login"))


@flask_app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = app.auth_service.login(username, password)
        if user:
            session["user_id"] = user.id
            session["role"] = user.role.value
            session["full_name"] = user.full_name
            session["lang"] = user.language or "sw"
            flash(f"{_msg('welcome')}, {user.full_name}!", "success")
            return redirect(url_for("home_feed"))
        flash(_msg("login_failed"), "danger")
    return render_template("login.html")


@flask_app.route("/logout")
def logout():
    lang = session.get("lang", "sw")
    session.clear()
    session["lang"] = lang
    flash(t("logged_out", lang), "info")
    return redirect(url_for("login"))


def _shop_search_profile_url(viewer, shop, all_users: list) -> str:
    if viewer.shop_id == shop.id:
        return url_for("profile_view") + "#profile-shop-card"
    for person in app.connection_service.directory_users(viewer, all_users):
        if person.shop_id == shop.id:
            return url_for("profile_user_view", user_id=person.id) + "#profile-shop-card"
    return url_for("home_feed")


def _searchable_people(viewer, all_users: list) -> list:
    """Watu wote wanaoweza kutafutwa — wafanyakazi wote + mtumiaji aliyeingia."""
    people = list(app.connection_service.directory_users(viewer, all_users))
    if viewer and viewer.active and not any(p.id == viewer.id for p in people):
        people.append(viewer)
    return people


def _person_search_haystack(person, shops_map: dict, lang: str) -> str:
    shop_name = ""
    if person.shop_id and person.shop_id in shops_map:
        shop_name = shops_map[person.shop_id].name
    role_label = t(f"role_{person.role.value}", lang)
    return " ".join(
        filter(
            None,
            [
                person.full_name,
                person.username,
                shop_name,
                role_label,
                person.bio,
                person.phone,
                person.email,
            ],
        )
    ).lower()


def _global_search_results(user, query: str, search_type: str = "all") -> dict:
    q = (query or "").strip().lower()
    all_users = app.user_service.get_all()
    shops_map = {s.id: s for s in app.shop_service.get_all()}
    allowed_shop_ids = app.connection_service.allowed_shop_ids_for_user(
        user, all_users
    )
    results = {"products": [], "people": [], "shops": []}
    if not q:
        return results

    lang = _user_lang(user)

    if search_type in ("all", "people"):
        for person in _searchable_people(user, all_users):
            shop_name = shops_map.get(person.shop_id).name if person.shop_id and person.shop_id in shops_map else ""
            if q in _person_search_haystack(person, shops_map, lang):
                profile_url = (
                    url_for("profile_view")
                    if person.id == user.id
                    else url_for("profile_user_view", user_id=person.id)
                )
                results["people"].append(
                    {
                        "user": person,
                        "shop_name": shop_name,
                        "url": profile_url,
                    }
                )

    if search_type in ("all", "shops"):
        for shop_id in allowed_shop_ids:
            shop = shops_map.get(shop_id)
            if not shop:
                continue
            haystack = " ".join(
                filter(
                    None,
                    [shop.name, shop.shop_type, shop.location, shop.description],
                )
            ).lower()
            if q in haystack:
                results["shops"].append(
                    {
                        "shop": shop,
                        "url": _shop_search_profile_url(user, shop, all_users),
                    }
                )

    if search_type in ("all", "products"):
        for shop_id in allowed_shop_ids:
            shop = shops_map.get(shop_id)
            if not shop:
                continue
            for product in app.product_service.get_all(shop_id):
                if product.quantity <= 0:
                    continue
                haystack = " ".join(
                    filter(None, [product.name, product.category, shop.name])
                ).lower()
                if q in haystack:
                    results["products"].append(
                        {
                            "product": product,
                            "shop": shop,
                            "url": _shop_search_profile_url(user, shop, all_users),
                        }
                    )

    return results


def _build_home_feed(user) -> list:
    all_users = app.user_service.get_all()
    allowed_shop_ids = app.connection_service.allowed_shop_ids_for_user(user, all_users)
    feed = []
    for shop in app.shop_service.get_all():
        if shop.id not in allowed_shop_ids:
            continue
        products = [p for p in app.product_service.get_all(shop.id) if p.quantity > 0]
        if products:
            feed.append(
                {
                    "shop": shop,
                    "products": products,
                    "is_own_shop": shop.id == (user.shop_id or ""),
                }
            )
    own_first = sorted(feed, key=lambda item: (not item["is_own_shop"], item["shop"].name))
    return own_first


def _dashboard_section_period(user_id: str, section: str) -> str:
    return app.dashboard_control_service.get_period_start(user_id, section)


def _filter_sales(sales, period: str):
    return app.dashboard_control_service.filter_sales(sales, period)


def _dashboard_preview_cards(user, ctx: dict) -> list[dict]:
    from services.dashboard_control_service import SECTION_ICONS

    dcs = app.dashboard_control_service
    pending = {r.section for r in dcs.get_pending_for_user(user.id)}
    resets = ctx.get("dashboard_resets", {})
    order = dcs.display_order_for_role(user.role.value)
    money_sections: set[str] = set()

    if user.role == UserRole.EMPLOYEE:
        values = {
            "cash_held": ctx.get("held_total", 0),
            "cash_pending": ctx.get("pending_total", 0),
            "cash_confirmed": ctx.get("confirmed_total", 0),
            "my_sales": ctx.get("my_sales_count", 0),
        }
        money_sections = {"cash_held", "cash_pending", "cash_confirmed"}
    elif user.role == UserRole.MANAGER:
        report = ctx.get("report")
        values = {
            "products": ctx.get("products_count", 0),
            "staff": ctx.get("employees_count", 0),
            "revenue": report.total_revenue if report else 0,
            "cash_shop_available": ctx.get("shop_available", 0),
        }
        money_sections = {"revenue", "cash_shop_available"}
    elif user.role == UserRole.BOSS:
        company = ctx.get("company")
        report = ctx.get("report")
        values = {
            "capital": company.total_capital if company else 0,
            "revenue": company.total_revenue if company else 0,
            "profit": company.total_profit if company else 0,
            "staff": ctx.get("staff_count", 0),
            "approvals": ctx.get("pending", 0),
            "net_profit": abs(report.net_profit) if report else 0,
        }
        money_sections = {"capital", "revenue", "profit", "net_profit"}
    else:
        return []

    cards = []
    for section in order:
        if section not in values:
            continue
        card = {
            "section": section,
            "icon": SECTION_ICONS.get(section, ""),
            "value": values[section],
            "is_money": section in money_sections,
            "reset_since": resets.get(section, ""),
            "pending": section in pending,
        }
        if section == "profit" and user.role == UserRole.BOSS:
            card["profit_negative"] = bool(company and company.total_profit < 0)
        if section == "approvals":
            card["is_highlight"] = True
        cards.append(card)
    return cards


def _staff_dashboard_entry(staff_user) -> dict:
    preview_ctx = _pro_dashboard_context(staff_user)
    shop_name = ""
    if staff_user.shop_id:
        shop = app.shop_service.get_by_id(staff_user.shop_id)
        shop_name = shop.name if shop else ""
    cards = _dashboard_preview_cards(staff_user, preview_ctx)
    return {
        "user": staff_user,
        "shop_id": staff_user.shop_id or "",
        "shop_name": shop_name,
        "role": staff_user.role.value,
        "sections_count": len(cards),
        "resets": preview_ctx.get("dashboard_resets", {}),
        "cards": cards,
    }


def _pro_dashboard_context(user):
    dcs = app.dashboard_control_service
    resets = dcs.get_user_resets(user.id)
    sections = dcs.sections_for_role(user.role.value)
    ctx = {
        "low_stock": [],
        "permissions": user.permissions,
        "dashboard_sections": sections,
        "dashboard_resets": resets,
        "pending_dashboard_resets": dcs.get_pending_for_user(user.id),
        "dashboard_staff": [],
        "boss_preview_cards": [],
    }
    if user.role == UserRole.BOSS:
        shops = app.shop_service.get_all()
        all_sales = app.sale_service.get_all()
        all_products = app.product_service.get_all()
        all_users = [u for u in app.user_service.get_all() if u.role != UserRole.BOSS]

        cap_period = _dashboard_section_period(user.id, "capital")
        rev_period = _dashboard_section_period(user.id, "revenue")
        profit_period = _dashboard_section_period(user.id, "profit")
        staff_period = _dashboard_section_period(user.id, "staff")
        appr_period = _dashboard_section_period(user.id, "approvals")
        net_period = _dashboard_section_period(user.id, "net_profit")

        products = dcs.filter_by_created_at(all_products, cap_period)
        staff_users = dcs.filter_by_created_at(all_users, staff_period)

        rev_sales = _filter_sales(all_sales, rev_period)
        profit_sales = _filter_sales(all_sales, profit_period)
        net_sales = _filter_sales(all_sales, net_period)

        confirmed_rev = [s for s in rev_sales if s.cash_status == "confirmed"]
        confirmed_profit = [s for s in profit_sales if s.cash_status == "confirmed"]
        confirmed_net = [s for s in net_sales if s.cash_status == "confirmed"]

        total_profit = sum(s.profit for s in confirmed_profit)
        salaries = sum(
            u.salary
            for u in staff_users
            if u.role in (UserRole.EMPLOYEE, UserRole.MANAGER)
        )
        net_profit = sum(s.profit for s in confirmed_net) - salaries

        pending_approvals = app.approval_service.get_pending_for_boss()
        if appr_period:
            pending_approvals = [
                a for a in pending_approvals if a.created_at >= appr_period
            ]

        company = type(
            "CompanyDash",
            (),
            {
                "shops_count": len(shops),
                "total_capital": sum(p.cost_price * p.quantity for p in products),
                "total_revenue": sum(s.total_amount for s in confirmed_rev),
                "total_profit": total_profit,
                "sales_count": len(confirmed_rev),
                "units_sold": sum(s.quantity for s in rev_sales),
                "held_revenue": 0.0,
                "pending_revenue": 0.0,
            },
        )()
        report = type(
            "FinanceDash",
            (),
            {
                "net_profit": net_profit,
                "total_revenue": company.total_revenue,
                "total_profit": total_profit,
            },
        )()
        ctx.update(
            report=report,
            company=company,
            pending=len(pending_approvals),
            pending_cash=app.cash_remittance_service.count_pending_for_user(user),
            staff_count=len(staff_users),
            shop_available=0,
        )
    elif user.role == UserRole.MANAGER:
        products = app.product_service.get_all(user.shop_id)
        employees = app.user_service.get_employees(user.shop_id)
        shop_sales = app.sale_service.get_all(user.shop_id)

        prod_period = _dashboard_section_period(user.id, "products")
        staff_period = _dashboard_section_period(user.id, "staff")
        rev_period = _dashboard_section_period(user.id, "revenue")
        cash_period = _dashboard_section_period(user.id, "cash_shop_available")

        products = dcs.filter_by_created_at(products, prod_period)
        employees = dcs.filter_by_created_at(employees, staff_period)
        rev_sales = _filter_sales(shop_sales, rev_period)
        cash_sales = _filter_sales(shop_sales, cash_period)

        confirmed_rev = [s for s in rev_sales if s.cash_status == "confirmed"]
        report = type(
            "ShopReport",
            (),
            {"total_revenue": sum(s.total_amount for s in confirmed_rev)},
        )()
        ctx.update(
            report=report,
            products_count=len(products),
            employees_count=len(employees),
            pending_cash=app.cash_remittance_service.count_pending_for_user(user),
            shop_available=sum(
                s.total_amount for s in cash_sales if s.cash_status == "manager_held"
            ),
            low_stock=[p for p in products if p.quantity <= 5],
            held_total=0,
            pending_total=0,
            confirmed_total=0,
            my_sales_count=0,
        )
    else:
        my_sales = [
            s
            for s in app.sale_service.get_all(user.shop_id)
            if s.employee_id == user.id
        ]
        sales_period = _dashboard_section_period(user.id, "my_sales")
        held_period = _dashboard_section_period(user.id, "cash_held")
        pending_period = _dashboard_section_period(user.id, "cash_pending")
        confirmed_period = _dashboard_section_period(user.id, "cash_confirmed")

        sales_filtered = _filter_sales(my_sales, sales_period)
        held_filtered = _filter_sales(my_sales, held_period)
        pending_filtered = _filter_sales(my_sales, pending_period)
        confirmed_filtered = _filter_sales(my_sales, confirmed_period)

        ctx.update(
            held_total=sum(
                s.total_amount for s in held_filtered if s.cash_status == "held"
            ),
            pending_total=sum(
                s.total_amount for s in pending_filtered if s.cash_status == "pending"
            ),
            confirmed_total=sum(
                s.total_amount
                for s in confirmed_filtered
                if s.cash_status == "confirmed"
            ),
            my_sales_count=len(sales_filtered),
            shop_available=0,
            report=None,
            products_count=0,
            employees_count=0,
        )
    return ctx


def _dashboard_control_context(user):
    dcs = app.dashboard_control_service
    ctx = {
        "pending_dashboard_resets": dcs.get_pending_for_user(user.id),
        "filter_shop": request.args.get("shop", "").strip(),
        "filter_q": request.args.get("q", "").strip(),
    }
    if user.is_boss():
        full = _pro_dashboard_context(user)
        staff_users = [
            u
            for u in app.user_service.get_all()
            if u.role != UserRole.BOSS and u.active
        ]
        ctx.update(
            dashboard_resets=full.get("dashboard_resets", {}),
            boss_preview_cards=_dashboard_preview_cards(user, full),
            dashboard_staff=[_staff_dashboard_entry(u) for u in staff_users],
            dashboard_shops=app.shop_service.get_all(),
        )
    return ctx


def _redirect_dashboard_control():
    shop = request.form.get("filter_shop", "").strip()
    q = request.form.get("filter_q", "").strip()
    params = {}
    if shop:
        params["shop"] = shop
    if q:
        params["q"] = q
    return redirect(url_for("dashboard_control", **params))


def _search_page_context(user, query: str, search_type: str) -> dict:
    if search_type not in ("all", "products", "people", "shops"):
        search_type = "all"
    results = _global_search_results(user, query, search_type)
    return {
        "query": query,
        "search_type": search_type,
        "results": results,
        "has_results": any(results[k] for k in results),
    }


@flask_app.route("/tafuta")
@login_required()
def global_search():
    user = app.user_service.get_by_id(session["user_id"])
    query = request.args.get("q", "").strip()
    search_type = request.args.get("type", "all").strip().lower()
    ctx = _search_page_context(user, query, search_type)
    if request.args.get("partial"):
        return render_template("search/_results.html", **ctx)
    return render_template("search/index.html", **ctx)


@flask_app.route("/nyumbani")
@login_required()
def home_feed():
    user = app.user_service.get_by_id(session["user_id"])
    promo_cards = app.banner_service.get_feed_cards()
    add_product_url = ""
    if _can_user_add_product(user):
        add_product_url = url_for("manager_add_product")
    return render_template(
        "home/feed.html",
        feed=_build_home_feed(user),
        promo_cards=promo_cards,
        my_shop_id=user.shop_id or "",
        add_product_url=add_product_url,
    )


@flask_app.route("/dashibodi")
@login_required()
def pro_dashboard():
    user = app.user_service.get_by_id(session["user_id"])
    return render_template("dashboard/pro.html", **_pro_dashboard_context(user))


@flask_app.route("/dashibodi/udhibiti")
@login_required()
def dashboard_control():
    user = app.user_service.get_by_id(session["user_id"])
    return render_template("dashboard/control.html", **_dashboard_control_context(user))


@flask_app.route("/wasifu")
@login_required()
def profile_view():
    user = app.user_service.get_by_id(session["user_id"])
    boss_ctx = {}
    if user.is_boss():
        boss_ctx = dict(
            notifications_muted=app.boss_settings_service.is_notifications_muted(),
            notifications_muted_at=app.boss_settings_service.get_notifications_muted_at(),
            archived_notifications=app.notification_service.get_archived_for_user(user.id),
        )
    return render_template(
        "profile/view.html",
        active="profile",
        **_build_profile_context(user, user),
        **boss_ctx,
    )


@flask_app.route("/wasifu/<user_id>")
@login_required()
def profile_user_view(user_id):
    viewer = app.user_service.get_by_id(session["user_id"])
    target = app.user_service.get_by_id(user_id)
    if not target or not target.active:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("home_feed"))
    if target.id == viewer.id:
        return redirect(url_for("profile_view"))
    all_users = app.user_service.get_all()
    visible = {u.id for u in app.connection_service.directory_users(viewer, all_users)}
    if target.id not in visible:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("home_feed"))
    return render_template(
        "profile/view.html",
        active="profile",
        **_build_profile_context(viewer, target),
    )


@flask_app.route("/wasifu/hariri", methods=["GET", "POST"])
@login_required()
def profile_edit():
    user = app.user_service.get_by_id(session["user_id"])
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "save":
            app.user_service.update_profile(
                user.id,
                full_name=request.form.get("full_name", "").strip(),
                phone=request.form.get("phone", "").strip(),
                email=request.form.get("email", "").strip(),
                bio=request.form.get("bio", "").strip(),
                whatsapp=request.form.get("whatsapp", "").strip(),
                facebook=request.form.get("facebook", "").strip(),
                tiktok=request.form.get("tiktok", "").strip(),
            )
            session["full_name"] = request.form.get("full_name", "").strip()
            flash(_msg("profile_saved"), "success")
            return redirect(url_for("profile_view"))
        elif action == "password":
            old = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            if not old or not new:
                flash(_msg("wrong_password"), "warning")
            elif app.user_service.change_password(user.id, old, new):
                flash(_msg("password_changed"), "success")
            else:
                flash(_msg("wrong_password"), "danger")
            return redirect(url_for("profile_edit"))
    return render_template("profile/edit.html")


@flask_app.route("/wasifu/picha", methods=["POST"])
@login_required()
def profile_upload_photo():
    user = app.user_service.get_by_id(session["user_id"])
    file = request.files.get("photo")
    if not file or not file.filename:
        return redirect(url_for("profile_edit"))

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_PHOTO:
        flash("PNG, JPG, WEBP tu.", "danger")  # TODO: translate if needed
        return redirect(url_for("profile_edit"))

    filename = secure_filename(f"{user.id}.{ext}")
    file.save(UPLOAD_DIR / filename)
    app.user_service.update_profile(user.id, profile_picture=filename)
    flash(_msg("photo_saved"), "success")
    return redirect(url_for("profile_edit"))


@flask_app.route("/wasifu/mipangilio")
@login_required()
def profile_settings():
    return redirect(url_for("profile_view"))


def _notify_dashboard_reset_request(req) -> None:
    lang = _lang()
    section_label = t(f"dashboard_section_{req.section}", lang)
    app.notification_service.send(
        req.target_user_id,
        NotificationType.STAFF.value,
        t("dashboard_reset_request_title", lang),
        t(
            "dashboard_reset_request_msg",
            lang,
            boss=req.requester_name,
            section=section_label,
        ),
        link=url_for("dashboard_control"),
        meta={"dashboard_reset_id": req.id, "section": req.section},
    )


def _notify_dashboard_reset_response(req, *, approved: bool) -> None:
    lang = _lang()
    section_label = t(f"dashboard_section_{req.section}", lang)
    if approved:
        title = t("dashboard_reset_approved_title", lang)
        msg = t(
            "dashboard_reset_approved_msg",
            lang,
            name=req.target_user_name,
            section=section_label,
        )
    else:
        title = t("dashboard_reset_rejected_title", lang)
        msg = t(
            "dashboard_reset_rejected_msg",
            lang,
            name=req.target_user_name,
            section=section_label,
        )
    app.notification_service.send(
        req.requested_by,
        NotificationType.STAFF.value,
        title,
        msg,
        link=url_for("dashboard_control"),
        meta={
            "dashboard_reset_id": req.id,
            "section": req.section,
            "result": "approved" if approved else "rejected",
        },
    )


@flask_app.route("/dashibodi/anza/<section>", methods=["POST"])
@login_required(UserRole.BOSS)
def dashboard_reset_section(section):
    user = app.user_service.get_by_id(session["user_id"])
    if not app.dashboard_control_service.is_valid_section(user, section):
        flash(t("dashboard_section_invalid", _lang()), "danger")
        return _redirect_dashboard_control()
    app.dashboard_control_service.reset_section(user.id, section)
    flash(
        t("dashboard_section_reset_done", _lang(), section=t(f"dashboard_section_{section}")),
        "success",
    )
    return _redirect_dashboard_control()


@flask_app.route("/dashibodi/omba-reset", methods=["POST"])
@login_required(UserRole.BOSS)
def dashboard_request_reset():
    boss = app.user_service.get_by_id(session["user_id"])
    target_id = request.form.get("target_user_id", "").strip()
    section = request.form.get("section", "").strip()
    target = app.user_service.get_by_id(target_id)
    lang = _lang()
    if not target or target.is_boss():
        flash(t("dashboard_reset_target_invalid", lang), "danger")
        return _redirect_dashboard_control()
    try:
        req = app.dashboard_control_service.create_reset_request(
            target=target,
            section=section,
            boss=boss,
        )
        _notify_dashboard_reset_request(req)
        flash(
            t(
                "dashboard_reset_request_sent",
                lang,
                name=target.full_name,
                section=t(f"dashboard_section_{section}", lang),
            ),
            "success",
        )
    except ValueError as exc:
        key = {
            "invalid_section": "dashboard_section_invalid",
            "already_pending": "dashboard_reset_already_pending",
            "cannot_target_boss": "dashboard_reset_target_invalid",
        }.get(str(exc), "error")
        flash(t(key, lang), "warning")
    return _redirect_dashboard_control()


@flask_app.route("/dashibodi/jibu-reset/<request_id>", methods=["POST"])
@login_required()
def dashboard_respond_reset(request_id):
    user = app.user_service.get_by_id(session["user_id"])
    action = request.form.get("action", "")
    lang = _lang()
    req = app.dashboard_control_service.get_by_id(request_id)
    if not req or req.target_user_id != user.id:
        flash(t("error", lang), "danger")
        return redirect(url_for("dashboard_control"))
    try:
        updated = app.dashboard_control_service.respond_request(
            request_id,
            user.id,
            approve=action == "approve",
            note=request.form.get("note", ""),
        )
        _notify_dashboard_reset_response(updated, approved=action == "approve")
        if action == "approve":
            flash(
                t(
                    "dashboard_reset_you_approved",
                    lang,
                    section=t(f"dashboard_section_{updated.section}", lang),
                ),
                "success",
            )
        else:
            flash(
                t(
                    "dashboard_reset_you_rejected",
                    lang,
                    section=t(f"dashboard_section_{updated.section}", lang),
                ),
                "info",
            )
    except ValueError:
        flash(t("error", lang), "danger")
    return redirect(url_for("dashboard_control"))


@flask_app.route("/wasifu/boss/sitisha-arifa", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_mute_notifications():
    user = app.user_service.get_by_id(session["user_id"])
    app.notification_service.archive_user_notifications(user.id)
    app.boss_settings_service.mute_notifications()
    flash(t("boss_mute_notifications_done", _lang()), "success")
    return redirect(url_for("profile_view"))


@flask_app.route("/wasifu/boss/washa-arifa", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_unmute_notifications():
    app.boss_settings_service.unmute_notifications()
    flash(t("boss_unmute_notifications_done", _lang()), "success")
    return redirect(url_for("profile_view"))


@flask_app.route("/arifa")
@login_required()
def notifications_list():
    user = app.user_service.get_by_id(session["user_id"])
    lang = _user_lang(user)
    notes = app.notification_service.get_for_user(user.id)
    notif_views = [_notification_view(n, lang) for n in notes]
    return render_template(
        "notifications/index.html",
        notifications=notes,
        notif_views=notif_views,
        unread_count=app.notification_service.get_unread_count(user.id),
        notif_icons=NOTIFICATION_ICONS,
    )


def _product_for_notification(meta: dict, shop_id: str = ""):
    product_id = meta.get("product_id")
    if product_id:
        return app.product_service.get_by_id(product_id)
    sid = shop_id or meta.get("shop_id", "")
    product_name = meta.get("product_name", "")
    if sid and product_name:
        for p in app.product_service.get_all(sid):
            if p.name == product_name:
                return p
    return None


def _find_pending_remittance(meta: dict, user) -> CashRemittance | None:
    rid = meta.get("remittance_id")
    if rid:
        remittance = app.cash_remittance_service.get_by_id(rid)
        if (
            remittance
            and remittance.status == RemittanceStatus.PENDING
            and app.cash_remittance_service.can_confirm(remittance, user)
        ):
            return remittance
    for remittance in app.cash_remittance_service.get_pending_for_user(user):
        amount = meta.get("amount", "")
        if amount and _money_str(remittance.amount) != amount and f"{remittance.amount:,.0f}" != amount.replace(" Fbi", "").replace(",", "").strip():
            continue
        employee = meta.get("employee_name", "")
        if employee and remittance.employee_name != employee:
            continue
        shop_id = meta.get("shop_id", "")
        if shop_id and remittance.shop_id != shop_id:
            continue
        if app.cash_remittance_service.can_confirm(remittance, user):
            return remittance
    return None


def _find_pending_approval(meta: dict, user) -> ApprovalRequest | None:
    aid = meta.get("approval_id")
    if aid:
        req = app.approval_service.get_by_id(aid)
        if (
            req
            and req.status == ApprovalStatus.PENDING
            and _can_approve_request(req, user)
        ):
            return req
    if user.role == UserRole.BOSS:
        pending = app.approval_service.get_pending_for_boss()
    elif user.role == UserRole.MANAGER and user.shop_id:
        pending = app.approval_service.get_pending_for_manager(user.shop_id)
    else:
        return None
    name = meta.get("name", "")
    shop_id = meta.get("shop_id", "")
    for req in pending:
        if name and req.requester_name != name:
            continue
        if shop_id and req.shop_id != shop_id:
            continue
        if _can_approve_request(req, user):
            return req
    return None


def _notification_action_context(note, user, meta: dict) -> dict:
    ctx = {
        "can_act": False,
        "action_type": "",
        "remittance": None,
        "approval": None,
        "remittance_sales": [],
    }
    if note.notification_type == NotificationType.CASH_REMITTANCE.value:
        variant = meta.get("variant", "")
        if variant in ("submitted", "manager_submitted"):
            remittance = _find_pending_remittance(meta, user)
            if remittance:
                ctx["can_act"] = True
                ctx["action_type"] = "cash"
                ctx["remittance"] = remittance
                ctx["remittance_sales"] = app.sale_service.get_by_ids(remittance.sale_ids)
    elif note.notification_type == NotificationType.APPROVAL_INCOMING.value:
        req = _find_pending_approval(meta, user)
        if req:
            ctx["can_act"] = True
            ctx["action_type"] = "approval"
            ctx["approval"] = req
    return ctx


def _shop_for_notification(meta: dict):
    shop_id = meta.get("shop_id", "")
    if shop_id:
        return app.shop_service.get_by_id(shop_id)
    shop_name = meta.get("shop_name", "")
    if shop_name:
        for s in app.shop_service.get_all():
            if s.name == shop_name:
                return s
    return None


@flask_app.route("/arifa/<note_id>")
@login_required()
def notification_detail(note_id):
    user = app.user_service.get_by_id(session["user_id"])
    lang = _user_lang(user)
    notes = app.notification_service.get_for_user(user.id)
    note = next((n for n in notes if n.id == note_id), None)
    if not note:
        flash(_translate(lang, "notifications_empty"), "error")
        return redirect(url_for("notifications_list"))
    app.notification_service.mark_read(note_id, user.id)
    meta = _parse_notification_meta(note)
    view = _notification_view(note, lang)
    shop = _shop_for_notification(meta)
    product = None
    if note.notification_type == NotificationType.SALE_NEW.value:
        product = _product_for_notification(meta, shop.id if shop else "")
    action_ctx = _notification_action_context(note, user, meta)
    approval_req = action_ctx.get("approval")
    return render_template(
        "notifications/detail.html",
        view=view,
        meta=meta,
        shop=shop,
        product=product,
        is_sale=note.notification_type == NotificationType.SALE_NEW.value,
        is_cash=note.notification_type == NotificationType.CASH_REMITTANCE.value,
        is_approval=note.notification_type == NotificationType.APPROVAL_INCOMING.value,
        action_ctx=action_ctx,
        approval_req=approval_req,
        aina_ombi=aina_ombi,
    )


@flask_app.route("/arifa/<note_id>/hatua", methods=["POST"])
@login_required()
def notification_action(note_id):
    user = app.user_service.get_by_id(session["user_id"])
    lang = _user_lang(user)
    notes = app.notification_service.get_for_user(user.id)
    note = next((n for n in notes if n.id == note_id), None)
    if not note:
        flash(_translate(lang, "not_found"), "danger")
        return redirect(url_for("notifications_list"))
    meta = _parse_notification_meta(note)
    ctx = _notification_action_context(note, user, meta)
    action = request.form.get("action", "").strip()
    note_text = request.form.get("note", "").strip()

    if not ctx["can_act"]:
        flash(_translate(lang, "not_found"), "danger")
        return redirect(url_for("notification_detail", note_id=note_id))

    try:
        if ctx["action_type"] == "cash":
            remittance = ctx["remittance"]
            if action == "approve":
                remittance = app.cash_remittance_service.confirm(
                    remittance.id, user, note_text
                )
                _notify_cash_confirmed(remittance)
                flash(
                    _translate(
                        lang,
                        "cash_confirmed_msg",
                        amount=_money_str(remittance.amount),
                        name=remittance.employee_name,
                    ),
                    "success",
                )
            elif action == "reject":
                if not note_text:
                    flash(_translate(lang, "reject_reason_required"), "danger")
                    return redirect(url_for("notification_detail", note_id=note_id))
                remittance = app.cash_remittance_service.reject(
                    remittance.id, user, note_text
                )
                _notify_cash_rejected(remittance)
                flash(_translate(lang, "cash_rejected_msg"), "info")
            else:
                flash(_translate(lang, "error"), "danger")
        elif ctx["action_type"] == "approval":
            req = ctx["approval"]
            if action == "approve":
                app.approval_service.approve(
                    req.id, note_text or _translate(lang, "approved")
                )
                _execute_approval(req, user.id, user.full_name)
                _notify_approval_result(req, "approved")
                flash(_translate(lang, "approved"), "success")
            elif action == "reject":
                if not note_text:
                    flash(_translate(lang, "reject_reason_required"), "danger")
                    return redirect(url_for("notification_detail", note_id=note_id))
                app.approval_service.reject(req.id, note_text)
                _notify_approval_result(req, "rejected")
                flash(_translate(lang, "rejected"), "info")
            else:
                flash(_translate(lang, "error"), "danger")
        else:
            flash(_translate(lang, "error"), "danger")
    except ValueError:
        flash(_translate(lang, "error"), "danger")

    return redirect(url_for("notifications_list"))


@flask_app.route("/arifa/<note_id>/fungua")
@login_required()
def notification_open(note_id):
    return redirect(url_for("notification_detail", note_id=note_id))


@flask_app.route("/arifa/mipangilio", methods=["POST"])
@login_required()
def notification_settings():
    user = app.user_service.get_by_id(session["user_id"])
    prefs = {
        key: key in request.form for key in NOTIFICATION_PREF_KEYS
    }
    app.notification_service.update_user_prefs(user.id, prefs)
    flash(t("notification_settings_saved", _lang()), "success")
    return redirect(url_for("notifications_list"))


@flask_app.route("/arifa/<note_id>/soma", methods=["POST"])
@login_required()
def notification_mark_read(note_id):
    app.notification_service.mark_read(note_id, session["user_id"])
    return redirect(url_for("notifications_list"))


@flask_app.route("/arifa/soma-zote", methods=["POST"])
@login_required()
def notifications_mark_all_read():
    app.notification_service.mark_all_read(session["user_id"])
    return redirect(url_for("notifications_list"))


@flask_app.route("/dashboard")
@login_required()
def dashboard():
    return redirect(url_for("pro_dashboard"))


# ── Mkuu (Boss) ──────────────────────────────────────────────

@flask_app.route("/boss")
@login_required(UserRole.BOSS)
def boss_dashboard():
    return redirect(url_for("pro_dashboard"))


@flask_app.route("/boss/maduka")
@login_required(UserRole.BOSS)
def boss_shops():
    shops = app.shop_service.get_all()
    shop_stats = {s.id: app.finance_service.get_shop_dashboard(s.id) for s in shops}
    promo_cards = app.banner_service.get_admin_cards()
    return render_template(
        "boss/maduka.html",
        shops=shops,
        shop_stats=shop_stats,
        promo_cards=promo_cards,
    )


def _save_promo_cropped_image(cropped: str, card_id: str) -> str | None:
    if not cropped or "," not in cropped:
        return None
    header, encoded = cropped.split(",", 1)
    ext = "jpg"
    if "png" in header:
        ext = "png"
    elif "webp" in header:
        ext = "webp"
    image_filename = secure_filename(f"promo_{card_id}_{uuid.uuid4().hex[:8]}.{ext}")
    with open(BANNER_DIR / image_filename, "wb") as f:
        f.write(base64.b64decode(encoded))
    return image_filename


@flask_app.route("/boss/maduka/promo/ongeza", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_add_promo_card():
    name = request.form.get("name", "").strip()
    cropped = request.form.get("cropped_image", "").strip()
    if not name:
        flash(t("promo_new_need_name", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    card = app.banner_service.add_card()
    image_filename = None
    try:
        image_filename = _save_promo_cropped_image(cropped, card.id)
    except Exception:
        app.banner_service.delete_card(card.id)
        flash(t("error", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    if not image_filename:
        app.banner_service.delete_card(card.id)
        flash(t("promo_new_need_image", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    app.banner_service.update_card(card.id, name=name, image_filename=image_filename)
    flash(t("promo_card_added", _lang()), "success")
    return redirect(url_for("boss_shops"))


@flask_app.route("/boss/maduka/promo/<card_id>", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_upload_promo_card(card_id: str):
    name = request.form.get("name", "").strip()
    cropped = request.form.get("cropped_image", "").strip()
    image_filename = None
    if cropped and "," in cropped:
        try:
            image_filename = _save_promo_cropped_image(cropped, card_id)
        except Exception:
            flash(t("error", _lang()), "danger")
            return redirect(url_for("boss_shops"))
    elif not name:
        flash(t("promo_card_need_image_or_name", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    try:
        app.banner_service.update_card(card_id, name=name, image_filename=image_filename)
        flash(t("promo_card_saved", _lang()), "success")
    except ValueError:
        flash(t("not_found", _lang()), "danger")
    return redirect(url_for("boss_shops"))


@flask_app.route("/boss/maduka/promo/<card_id>/futa", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_delete_promo_card(card_id: str):
    if app.banner_service.delete_card(card_id):
        flash(t("promo_card_deleted", _lang()), "success")
    else:
        flash(t("not_found", _lang()), "danger")
    return redirect(url_for("boss_shops"))


@flask_app.route("/boss/maduka/<shop_id>")
@login_required(UserRole.BOSS)
def boss_shop_view(shop_id):
    user = app.user_service.get_by_id(session["user_id"])
    shop, ctx = _shop_dashboard_ctx(shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    return render_template(
        "shops/view.html",
        **_shop_layout_ctx(shop, user, "overview"),
        bulk_delete_sales_url=url_for("boss_bulk_delete_sales", shop_id=shop_id),
        **ctx,
    )


@flask_app.route("/boss/maduka/<shop_id>/bidhaa")
@login_required(UserRole.BOSS)
def boss_shop_products(shop_id):
    user = app.user_service.get_by_id(session["user_id"])
    shop = app.shop_service.get_by_id(shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    products = app.product_service.get_all(shop_id)
    dashboard = app.finance_service.get_shop_dashboard(shop_id)
    return render_template(
        "shops/products.html",
        **_shop_layout_ctx(shop, user, "products"),
        products=products,
        dashboard=dashboard,
        product_hint=t("boss_product_approval_hint", _lang()),
        add_product_url=url_for("boss_shop_request_add_product", shop_id=shop_id),
        pending_delete_ids=_pending_delete_product_ids(shop_id),
        product_image_url=url_for("boss_shop_upload_product_image", shop_id=shop_id, product_id="__ID__"),
        bulk_delete_products_url=url_for("boss_bulk_delete_products", shop_id=shop_id),
    )


@flask_app.route("/boss/maduka/<shop_id>/bidhaa/omba-ongeza", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_shop_request_add_product(shop_id):
    user = app.user_service.get_by_id(session["user_id"])
    try:
        data = _product_payload_from_form(shop_id)
        if not data["name"]:
            flash(t("fill_all_fields", _lang()), "warning")
            return redirect(url_for("boss_shop_products", shop_id=shop_id))
        payload = json.dumps(data)
        req = app.approval_service.create_request(
            ApprovalType.ADD_PRODUCT,
            user.id,
            user.full_name,
            shop_id,
            t("add_product_request", _lang(), name=data["name"]),
            "",
            approver_role=UserRole.MANAGER.value,
            payload=payload,
        )
        _notify_approval_created(req)
        flash(t("approval_sent_manager", _lang()), "info")
    except ValueError as e:
        if str(e) == "invalid_image":
            flash(t("invalid_image", _lang()), "danger")
        else:
            flash(t("invalid_data", _lang()), "danger")
    except TypeError:
        flash(t("invalid_data", _lang()), "danger")
    return redirect(url_for("boss_shop_products", shop_id=shop_id))


@flask_app.route("/boss/maduka/<shop_id>/bidhaa/omba-futa/<product_id>", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_shop_request_delete_product(shop_id, product_id):
    user = app.user_service.get_by_id(session["user_id"])
    product = app.product_service.get_by_id(product_id)
    if not product or product.shop_id != shop_id:
        flash(t("product_not_found", _lang()), "danger")
        return redirect(url_for("boss_shop_products", shop_id=shop_id))
    if app.approval_service.has_pending_delete(product_id):
        flash(t("delete_cancel_first", _lang()), "warning")
        return redirect(url_for("boss_shop_products", shop_id=shop_id))
    try:
        req = app.approval_service.create_request(
            ApprovalType.DELETE_PRODUCT,
            user.id,
            user.full_name,
            shop_id,
            t("delete_request", _lang(), name=product.name),
            product_id,
            approver_role=UserRole.MANAGER.value,
        )
        _notify_approval_created(req)
        flash(t("approval_sent_manager", _lang()), "info")
    except ValueError as e:
        if str(e) == "pending_delete":
            flash(t("delete_cancel_first", _lang()), "warning")
        else:
            flash(t("invalid_data", _lang()), "danger")
    return redirect(url_for("boss_shop_products", shop_id=shop_id))


@flask_app.route("/boss/maduka/<shop_id>/bidhaa/<product_id>/picha", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_shop_upload_product_image(shop_id, product_id):
    product = app.product_service.get_by_id(product_id)
    if not product or product.shop_id != shop_id:
        flash(t("product_not_found", _lang()), "danger")
        return redirect(url_for("boss_shop_products", shop_id=shop_id))
    try:
        filename = _save_product_image(request.files.get("image"), product_id)
        if filename:
            app.product_service.update_product(product_id, image=filename)
            flash(t("product_image_saved", _lang()), "success")
    except ValueError:
        flash(t("invalid_image", _lang()), "danger")
    return redirect(url_for("boss_shop_products", shop_id=shop_id))


@flask_app.route("/boss/maduka/<shop_id>/mauzo")
@login_required(UserRole.BOSS)
def boss_shop_sales(shop_id):
    user = app.user_service.get_by_id(session["user_id"])
    shop = app.shop_service.get_by_id(shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    _, ctx = _shop_dashboard_ctx(shop_id)
    sales = app.sale_service.get_all(shop_id)
    shop_available = app.cash_remittance_service.get_shop_manager_held_total(shop_id)
    boss_pending_total = sum(s.total_amount for s in sales if s.cash_status == "boss_pending")
    return render_template(
        "shops/sales.html",
        **_shop_layout_ctx(shop, user, "sales"),
        sales=sales,
        shop_available=shop_available,
        boss_pending_total=boss_pending_total,
        submit_cash_url=None,
        bulk_delete_sales_url=url_for("boss_bulk_delete_sales", shop_id=shop_id),
        **ctx,
    )


@flask_app.route("/boss/maduka/<shop_id>/mauzo/futa", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_bulk_delete_sales(shop_id):
    user = app.user_service.get_by_id(session["user_id"])
    sale_ids = request.form.getlist("item_ids")
    return _request_delete_sales(
        user,
        shop_id,
        sale_ids,
        redirect_url=url_for("boss_shop_sales", shop_id=shop_id),
    )


@flask_app.route("/boss/maduka/<shop_id>/bidhaa/futa-teuzi", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_bulk_delete_products(shop_id):
    user = app.user_service.get_by_id(session["user_id"])
    product_ids = request.form.getlist("item_ids")
    return _request_delete_products(
        user,
        shop_id,
        product_ids,
        redirect_url=url_for("boss_shop_products", shop_id=shop_id),
    )


@flask_app.route("/boss/maduka/<shop_id>/wafanyakazi")
@login_required(UserRole.BOSS)
def boss_shop_staff(shop_id):
    user = app.user_service.get_by_id(session["user_id"])
    shop = app.shop_service.get_by_id(shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    staff = [u for u in app.user_service.get_by_shop(shop_id) if u.role != UserRole.BOSS]
    return render_template(
        "shops/staff.html",
        **_shop_layout_ctx(shop, user, "staff"),
        staff=staff,
    )


@flask_app.route("/boss/maduka/<shop_id>/hariri", methods=["GET", "POST"])
@login_required(UserRole.BOSS)
def boss_shop_edit(shop_id):
    shop = app.shop_service.get_by_id(shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("boss_shops"))
    if request.method == "POST":
        app.shop_service.update_shop(
            shop_id,
            name=request.form.get("name", "").strip(),
            shop_type=request.form.get("shop_type", "").strip(),
            location=request.form.get("location", "").strip(),
            description=request.form.get("description", "").strip(),
        )
        flash(t("shop_saved", _lang()), "success")
        return redirect(url_for("boss_shop_view", shop_id=shop_id))
    user = app.user_service.get_by_id(session["user_id"])
    return render_template(
        "shops/edit.html",
        **_shop_layout_ctx(shop, user, "edit"),
        save_url=url_for("boss_shop_edit", shop_id=shop_id),
        logo_url=url_for("boss_shop_upload_logo", shop_id=shop_id),
        cover_url=url_for("boss_shop_upload_cover", shop_id=shop_id),
    )


@flask_app.route("/boss/maduka/<shop_id>/logo", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_shop_upload_logo(shop_id):
    return _shop_upload_image(shop_id, "logo", SHOP_LOGO_DIR, "logo")


@flask_app.route("/boss/maduka/<shop_id>/cover", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_shop_upload_cover(shop_id):
    return _shop_upload_image(shop_id, "cover", SHOP_COVER_DIR, "cover_image")


@flask_app.route("/boss/maduka/ongeza", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_add_shop():
    name = request.form.get("name", "").strip()
    shop_type = request.form.get("shop_type", "").strip()
    location = request.form.get("location", "").strip()
    if name and shop_type:
        shop = app.shop_service.add_shop(name, shop_type, location)
        flash(t("shop_added", _lang(), name=shop.name), "success")
    else:
        flash(t("fill_all_fields", _lang()), "warning")
    return redirect(url_for("boss_shops"))


@flask_app.route("/boss/bidhaa")
@login_required(UserRole.BOSS)
def boss_products():
    flash(t("products_in_shop", _lang()), "info")
    return redirect(url_for("boss_shops"))


@flask_app.route("/boss/bidhaa/omba-ongeza", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_request_add_product():
    user = app.user_service.get_by_id(session["user_id"])
    shop_id = request.form.get("shop_id", "").strip()
    name = request.form.get("name", "").strip()
    if not shop_id or not name:
        flash(t("fill_all_fields", _lang()), "warning")
        return redirect(url_for("boss_products"))
    try:
        payload = json.dumps({
            "name": name,
            "price": float(request.form.get("price", 0)),
            "quantity": int(request.form.get("quantity", 0)),
            "shop_id": shop_id,
            "cost_price": float(request.form.get("cost_price", 0)),
            "category": request.form.get("category", "").strip(),
        })
        req = app.approval_service.create_request(
            ApprovalType.ADD_PRODUCT,
            user.id,
            user.full_name,
            shop_id,
            t("add_product_request", _lang(), name=name),
            "",
            approver_role=UserRole.MANAGER.value,
            payload=payload,
        )
        _notify_approval_created(req)
        flash(t("approval_sent_manager", _lang()), "info")
    except (ValueError, TypeError):
        flash(t("invalid_data", _lang()), "danger")
    return redirect(url_for("boss_products"))


@flask_app.route("/boss/bidhaa/omba-futa/<product_id>", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_request_delete_product(product_id):
    user = app.user_service.get_by_id(session["user_id"])
    product = app.product_service.get_by_id(product_id)
    if not product:
        flash(t("product_not_found", _lang()), "danger")
        return redirect(url_for("boss_products"))
    if app.approval_service.has_pending_delete(product_id):
        flash(t("delete_cancel_first", _lang()), "warning")
        return redirect(url_for("boss_shop_products", shop_id=product.shop_id))
    try:
        req = app.approval_service.create_request(
            ApprovalType.DELETE_PRODUCT,
            user.id,
            user.full_name,
            product.shop_id,
            t("delete_request", _lang(), name=product.name),
            product_id,
            approver_role=UserRole.MANAGER.value,
        )
        _notify_approval_created(req)
        flash(t("approval_sent_manager", _lang()), "info")
    except ValueError as e:
        if str(e) == "pending_delete":
            flash(t("delete_cancel_first", _lang()), "warning")
        else:
            flash(t("invalid_data", _lang()), "danger")
    return redirect(url_for("boss_shop_products", shop_id=product.shop_id))


def _notify_connection_request(requester, target) -> None:
    lang = get_language(target.language)
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    shop_name = shops.get(requester.shop_id, "")
    app.notification_service.send(
        target.id,
        NotificationType.STAFF.value,
        t("connection_request_title", lang),
        t(
            "connection_request_msg",
            lang,
            name=requester.full_name,
            role=role_label(requester.role.value, lang),
            shop=shop_name or "-",
        ),
        url_for("staff_chat", na=requester.id),
        {"connection_request": True, "requester_id": requester.id},
    )


def _notify_connection_result(requester, target, approved: bool) -> None:
    lang = get_language(requester.language)
    key = "connection_approved_msg" if approved else "connection_rejected_msg"
    app.notification_service.send(
        requester.id,
        NotificationType.STAFF.value,
        t("connection_result_title", lang),
        t(key, lang, name=target.full_name),
        url_for("staff_chat", na=target.id),
        {"connection_result": approved, "target_id": target.id},
    )


@flask_app.route("/mazungumzo")
@login_required()
def staff_chat():
    user = app.user_service.get_by_id(session["user_id"])
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    all_shops = app.shop_service.get_all()
    directory = _chat_directory(user, shops)
    partner_id = request.args.get("na", "").strip()
    partner = app.user_service.get_by_id(partner_id) if partner_id else None
    partner_state = "none"
    partner_connection_id = ""
    messages = []
    if partner:
        if partner.id == user.id or not partner.active:
            partner = None
        else:
            partner_state = app.connection_service.connection_state(user, partner)
            conn = app.connection_service.find_between(user.id, partner.id)
            partner_connection_id = conn.id if conn else ""
            if partner_state == "approved":
                app.chat_service.mark_read(user.id, partner.id)
                messages = app.chat_service.get_conversation(user.id, partner.id)
    return render_template(
        "chat/index.html",
        directory=directory,
        partner=partner,
        partner_state=partner_state,
        partner_connection_id=partner_connection_id,
        messages=messages,
        shops=shops,
        all_shops=all_shops,
        active="chat",
    )


@flask_app.route("/mazungumzo/tuma", methods=["POST"])
@login_required()
def staff_chat_send():
    user = app.user_service.get_by_id(session["user_id"])
    receiver_id = request.form.get("receiver_id", "").strip()
    body = request.form.get("body", "").strip()
    partner = app.user_service.get_by_id(receiver_id)
    if not partner or not _can_chat_with(user, partner):
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("staff_chat"))
    try:
        app.chat_service.send_message(user.id, partner.id, body)
    except ValueError:
        flash(t("chat_empty_message", _lang()), "warning")
    return redirect(url_for("staff_chat", na=partner.id))


@flask_app.route("/mazungumzo/ruhusa/omba", methods=["POST"])
@login_required()
def staff_connection_request():
    user = app.user_service.get_by_id(session["user_id"])
    target_id = request.form.get("target_id", "").strip()
    target = app.user_service.get_by_id(target_id)
    if not target or target.id == user.id or not target.active:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("staff_chat"))
    try:
        app.connection_service.request_connection(user, target)
        _notify_connection_request(user, target)
        flash(t("connection_request_sent", _lang()), "success")
    except ValueError as e:
        code = str(e)
        if code == "already_connected":
            flash(t("connection_already", _lang()), "info")
        elif code == "already_pending":
            flash(t("connection_pending", _lang()), "warning")
        else:
            flash(t("not_found", _lang()), "danger")
    next_url = request.form.get("next", "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("staff_chat", na=target.id))


@flask_app.route("/mazungumzo/ruhusa/<conn_id>/idhinisha", methods=["POST"])
@login_required()
def staff_connection_approve(conn_id):
    user = app.user_service.get_by_id(session["user_id"])
    requester_id = ""
    try:
        conn = app.connection_service.respond(conn_id, user.id, True)
        requester_id = conn.requester_id
        requester = app.user_service.get_by_id(conn.requester_id)
        if requester:
            _notify_connection_result(requester, user, True)
        flash(t("connection_approved", _lang()), "success")
    except ValueError:
        flash(t("not_found", _lang()), "danger")
    next_url = request.form.get("next", "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    if requester_id:
        return redirect(url_for("staff_chat", na=requester_id))
    return redirect(url_for("staff_chat"))


@flask_app.route("/mazungumzo/ruhusa/<conn_id>/kataa", methods=["POST"])
@login_required()
def staff_connection_reject(conn_id):
    user = app.user_service.get_by_id(session["user_id"])
    requester_id = ""
    try:
        conn = app.connection_service.respond(conn_id, user.id, False)
        requester_id = conn.requester_id
        requester = app.user_service.get_by_id(conn.requester_id)
        if requester:
            _notify_connection_result(requester, user, False)
        flash(t("connection_rejected", _lang()), "info")
    except ValueError:
        flash(t("not_found", _lang()), "danger")
    next_url = request.form.get("next", "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("staff_chat", na=requester_id) if requester_id else url_for("staff_chat"))


@flask_app.route("/api/arifa/muhtasari")
@login_required()
def alerts_summary():
    user = app.user_service.get_by_id(session["user_id"])
    return jsonify(
        {
            "unread_notifications": app.notification_service.get_unread_count(user.id),
            "unread_chat": app.chat_service.get_unread_count(user.id),
            "pending_connections": app.connection_service.get_pending_incoming_count(
                user.id
            ),
        }
    )


@flask_app.route("/mazungumzo/api/<partner_id>")
@login_required()
def staff_chat_api(partner_id):
    user = app.user_service.get_by_id(session["user_id"])
    partner = app.user_service.get_by_id(partner_id)
    if not partner or not _can_chat_with(user, partner):
        return jsonify({"error": "not_found"}), 404
    app.chat_service.mark_read(user.id, partner.id)
    messages = app.chat_service.get_conversation(user.id, partner.id)
    return jsonify(
        {
            "messages": [
                {
                    "id": m.id,
                    "sender_id": m.sender_id,
                    "body": m.body,
                    "created_at": m.created_at,
                    "read_at": m.read_at,
                    "mine": m.sender_id == user.id,
                }
                for m in messages
            ]
        }
    )


@flask_app.route("/boss/wafanyakazi")
@login_required(UserRole.BOSS)
def boss_staff():
    users = [u for u in app.user_service.get_all() if u.role != UserRole.BOSS]
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    all_shops = app.shop_service.get_all()
    return render_template(
        "boss/wafanyakazi.html",
        staff=users,
        shops=shops,
        all_shops=all_shops,
        manager_count=len([u for u in users if u.role == UserRole.MANAGER]),
        employee_count=len([u for u in users if u.role == UserRole.EMPLOYEE]),
        active_count=len([u for u in users if u.active]),
        suspended_count=len([u for u in users if not u.active]),
    )


@flask_app.route("/boss/wafanyakazi/ongeza", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_add_staff():
    role = request.form.get("role", "")
    shop_id = request.form.get("shop_id") or None
    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    try:
        salary = float(request.form.get("salary", 0))
    except ValueError:
        salary = 0

    role_map = {"manager": UserRole.MANAGER, "employee": UserRole.EMPLOYEE}
    if role not in role_map or not all([full_name, username, password]):
        flash(t("fill_all_fields", _lang()), "warning")
        return redirect(url_for("boss_staff"))

    try:
        user = app.user_service.add_user(
            username, password, role_map[role], full_name, shop_id, salary
        )
        _notify_staff_event(
            shop_id,
            "notif_staff_added_title",
            "notif_staff_added_msg",
            name=user.full_name,
            exclude_user_id=session["user_id"],
        )
        flash(
            t(
                "staff_added",
                _lang(),
                role=role_label(user.role.value, _lang()),
                name=user.full_name,
            ),
            "success",
        )
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("boss_staff"))


@flask_app.route("/boss/wafanyakazi/<user_id>/simamisha", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_suspend_staff(user_id):
    user = app.user_service.get_by_id(user_id)
    if not user or user.role == UserRole.BOSS:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("boss_staff"))
    try:
        app.user_service.deactivate_user(user_id)
        flash(t("staff_suspended", _lang(), name=user.full_name), "warning")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("boss_staff"))


@flask_app.route("/boss/wafanyakazi/<user_id>/amsha", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_activate_staff(user_id):
    user = app.user_service.get_by_id(user_id)
    if not user or user.role == UserRole.BOSS:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("boss_staff"))
    try:
        app.user_service.activate_user(user_id)
        flash(t("staff_activated", _lang(), name=user.full_name), "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("boss_staff"))


@flask_app.route("/boss/wafanyakazi/<user_id>/onyo", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_warn_staff(user_id):
    user = app.user_service.get_by_id(user_id)
    if not user or user.role == UserRole.BOSS:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("boss_staff"))
    action = request.form.get("action", "add")
    try:
        if action == "clear":
            app.user_service.clear_warning(user_id)
            flash(t("warning_cleared", _lang(), name=user.full_name), "info")
        else:
            app.user_service.add_warning(user_id)
            flash(t("warning_added", _lang(), name=user.full_name), "warning")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("boss_staff"))


@flask_app.route("/boss/wafanyakazi/<user_id>/futa", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_remove_staff(user_id):
    boss = app.user_service.get_by_id(session["user_id"])
    target = app.user_service.get_by_id(user_id)
    if not target or target.role == UserRole.BOSS:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("boss_staff"))
    app.trash_service.archive_user(
        target,
        boss.id,
        boss.full_name,
        t("removed_by_boss", _lang()),
    )
    shop_id = target.shop_id
    app.user_service.remove_user(user_id)
    _notify_staff_event(
        shop_id,
        "notif_staff_removed_title",
        "notif_staff_removed_msg",
        name=target.full_name,
        exclude_user_id=boss.id,
    )
    flash(t("staff_removed", _lang(), name=target.full_name), "warning")
    return redirect(url_for("boss_staff"))


@flask_app.route("/boss/idhini")
@login_required(UserRole.BOSS)
def boss_approvals():
    user = app.user_service.get_by_id(session["user_id"])
    pending_requests = app.approval_service.get_pending_for_boss()
    my_requests = [r for r in app.approval_service.get_all() if r.requested_by == user.id]
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    products_by_id = {p.id: p for p in app.product_service.get_all()}
    return render_template(
        "boss/idhini.html",
        pending_requests=pending_requests,
        my_requests=my_requests,
        shops=shops,
        products_by_id=products_by_id,
        aina_ombi=aina_ombi,
        hali_ombi=hali_ombi,
    )


@flask_app.route("/boss/idhini/<req_id>/<action>", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_approval_action(req_id, action):
    note = request.form.get("note", "").strip()
    user = app.user_service.get_by_id(session["user_id"])
    req = app.approval_service.get_by_id(req_id)
    if not req:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("boss_approvals"))

    if action in ("approve", "reject"):
        if not _can_approve_request(req, user) or req.approver_role != UserRole.BOSS.value:
            flash(t("not_found", _lang()), "danger")
            return redirect(url_for("boss_approvals"))
        if action == "approve":
            app.approval_service.approve(req_id, note or t("approved", _lang()))
            _execute_approval(req, user.id, user.full_name)
            _notify_approval_result(req, "approved")
            flash(t("approved", _lang()), "success")
        else:
            app.approval_service.reject(req_id, note or t("rejected", _lang()))
            _notify_approval_result(req, "rejected")
            flash(t("rejected", _lang()), "info")
    elif action in ("cancel", "delete"):
        if not _can_manage_product_approval(req, user):
            flash(t("not_found", _lang()), "danger")
            return redirect(url_for("boss_approvals"))
        if action == "cancel":
            app.approval_service.cancel(req_id, note or t("approval_suspended", _lang()))
            _notify_approval_result(req, "cancelled")
            flash(t("approval_suspended", _lang()), "warning")
        else:
            app.approval_service.delete_request(req_id)
            flash(t("approval_deleted", _lang()), "info")
    else:
        flash(t("not_found", _lang()), "danger")
    return redirect(url_for("boss_approvals"))


@flask_app.route("/boss/idhini/bulk", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_approval_bulk():
    action = request.form.get("action", "").strip()
    req_ids = request.form.getlist("req_ids")
    note = request.form.get("note", "").strip()
    if action not in ("approve", "reject", "cancel") or not req_ids:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("boss_approvals"))
    user = app.user_service.get_by_id(session["user_id"])
    done = _process_approval_bulk(user, req_ids, action, note)
    if done:
        flash(t("approval_bulk_done", _lang(), n=done), "success")
    else:
        flash(t("not_found", _lang()), "danger")
    return redirect(url_for("boss_approvals"))


@flask_app.route("/boss/takataka")
@login_required(UserRole.BOSS)
def boss_trash():
    products = app.trash_service.get_all(item_type="product")
    users = app.trash_service.get_all(item_type="user")
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    return render_template(
        "trash/view.html",
        deleted_products=products,
        deleted_users=users,
        shops=shops,
        back_url=url_for("boss_dashboard"),
        can_delete_trash=True,
    )


@flask_app.route("/boss/takataka/<item_id>/futa", methods=["POST"])
@login_required(UserRole.BOSS)
def boss_delete_trash_item(item_id):
    item = app.trash_service.get_by_id(item_id)
    if not item:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("boss_trash"))
    name = item.data.get("name") or item.data.get("full_name") or item.id
    app.trash_service.delete_permanently(item_id)
    flash(t("trash_deleted_permanently", _lang(), name=name), "success")
    return redirect(url_for("boss_trash"))


@flask_app.route("/boss/ripoti")
@login_required(UserRole.BOSS)
def boss_finance():
    report = app.finance_service.get_company_summary()
    shops = app.shop_service.get_all()
    shop_reports = {s.id: app.finance_service.get_shop_report(s.id) for s in shops}
    return render_template("boss/ripoti.html", report=report, shops=shops, shop_reports=shop_reports)


@flask_app.route("/boss/mauzo")
@login_required(UserRole.BOSS)
def boss_sales():
    flash(t("sales_in_shop", _lang()), "info")
    return redirect(url_for("boss_shops"))


def _pending_delete_product_ids(shop_id: str | None = None) -> set[str]:
    return app.approval_service.get_pending_delete_ids(shop_id)


def _pending_delete_sale_ids(shop_id: str | None = None) -> set[str]:
    return app.approval_service.get_pending_delete_sale_ids(shop_id)


def _request_delete_sales(user, shop_id: str, sale_ids: list[str], *, redirect_url: str):
    lang = _lang()
    sent = 0
    skipped = 0
    for sale_id in sale_ids:
        sale = app.sale_service.get_by_id(sale_id)
        if not sale or sale.shop_id != shop_id:
            skipped += 1
            continue
        if app.approval_service.has_pending_delete_sale(sale_id):
            skipped += 1
            continue
        try:
            req = app.approval_service.create_request(
                ApprovalType.DELETE_SALE,
                user.id,
                user.full_name,
                shop_id,
                t(
                    "delete_sale_request",
                    lang,
                    product=sale.product_name,
                    qty=sale.quantity,
                    amount=_money_str(sale.total_amount),
                ),
                sale_id,
                approver_role=UserRole.BOSS.value
                if user.role == UserRole.MANAGER
                else UserRole.MANAGER.value,
            )
            _notify_approval_created(req)
            sent += 1
        except ValueError:
            skipped += 1
    if sent:
        flash(t("sales_delete_requests_sent", lang, count=sent), "success")
    elif skipped:
        flash(t("sales_delete_none_sent", lang), "warning")
    return redirect(redirect_url)


def _request_delete_products(user, shop_id: str, product_ids: list[str], *, redirect_url: str):
    lang = _lang()
    sent = 0
    skipped = 0
    approver = (
        UserRole.BOSS.value
        if user.role == UserRole.MANAGER
        else UserRole.MANAGER.value
    )
    for product_id in product_ids:
        product = app.product_service.get_by_id(product_id)
        if not product or product.shop_id != shop_id:
            skipped += 1
            continue
        if app.approval_service.has_pending_delete(product_id):
            skipped += 1
            continue
        try:
            req = app.approval_service.create_request(
                ApprovalType.DELETE_PRODUCT,
                user.id,
                user.full_name,
                shop_id,
                t("delete_request", lang, name=product.name),
                product_id,
                approver_role=approver,
            )
            _notify_approval_created(req)
            sent += 1
        except ValueError:
            skipped += 1
    if sent:
        flash(t("products_delete_requests_sent", lang, count=sent), "success")
    elif skipped:
        flash(t("products_delete_none_sent", lang), "warning")
    return redirect(redirect_url)


def _save_cropped_image_data(cropped: str, dest_dir: Path, prefix: str) -> str:
    if not cropped or "," not in cropped:
        raise ValueError("invalid_image")
    header, encoded = cropped.split(",", 1)
    ext = "jpg"
    if "png" in header:
        ext = "png"
    elif "webp" in header:
        ext = "webp"
    filename = secure_filename(f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}")
    with open(dest_dir / filename, "wb") as f:
        f.write(base64.b64decode(encoded))
    return filename


def _save_product_image(file, prefix: str = "product") -> str:
    if not file or not file.filename:
        return ""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_PHOTO:
        raise ValueError("invalid_image")
    filename = secure_filename(f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}")
    file.save(PRODUCT_IMAGE_DIR / filename)
    return filename


def _product_payload_from_form(shop_id: str) -> dict:
    image = ""
    cropped = request.form.get("cropped_image", "")
    if cropped and "," in cropped:
        image = _save_cropped_image_data(cropped, PRODUCT_IMAGE_DIR, "new")
    else:
        file = request.files.get("image")
        if file and file.filename:
            image = _save_product_image(file, "new")
    cost_price = float(request.form.get("cost_price", 0) or 0)
    price = float(request.form.get("price", 0) or 0) or cost_price
    return {
        "name": request.form.get("name", "").strip(),
        "price": price,
        "quantity": int(request.form.get("quantity", 0)),
        "shop_id": shop_id,
        "cost_price": cost_price,
        "category": request.form.get("category", "").strip(),
        "image": image,
    }


def _shop_upload_image(shop_id: str, field: str, upload_dir: Path, attr: str):
    shop = app.shop_service.get_by_id(shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("boss_shops"))

    user = app.user_service.get_by_id(session["user_id"])
    if not _can_manage_shop(user, shop_id):
        flash(t("no_permission", _lang()), "danger")
        return redirect(url_for("dashboard"))

    file = request.files.get(field)
    if not file or not file.filename:
        return redirect(request.referrer or url_for("boss_shops"))

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_PHOTO:
        flash(t("invalid_image", _lang()), "danger")
        return redirect(request.referrer or url_for("boss_shops"))

    filename = secure_filename(f"{shop_id}_{field}.{ext}")
    file.save(upload_dir / filename)
    app.shop_service.update_shop(shop_id, **{attr: filename})
    flash(t("shop_image_saved", _lang()), "success")

    if user.role == UserRole.MANAGER:
        return redirect(url_for("manager_shop_edit"))
    return redirect(url_for("boss_shop_edit", shop_id=shop_id))


# ── Meneja (Manager) ─────────────────────────────────────────

@flask_app.route("/meneja/duka")
@login_required(UserRole.MANAGER)
def manager_shop_view():
    user = app.user_service.get_by_id(session["user_id"])
    shop, ctx = _shop_dashboard_ctx(user.shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("manager_dashboard"))
    return render_template(
        "shops/view.html",
        **_shop_layout_ctx(shop, user, "overview"),
        bulk_delete_sales_url=url_for("manager_bulk_delete_sales"),
        **ctx,
    )


@flask_app.route("/meneja/duka/bidhaa")
@login_required(UserRole.MANAGER)
def manager_shop_products():
    user = app.user_service.get_by_id(session["user_id"])
    shop = app.shop_service.get_by_id(user.shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("manager_dashboard"))
    products = app.product_service.get_all(user.shop_id)
    dashboard = app.finance_service.get_shop_dashboard(user.shop_id)
    return render_template(
        "shops/products.html",
        **_shop_layout_ctx(shop, user, "products"),
        products=products,
        dashboard=dashboard,
        product_hint=t("manager_product_approval_hint", _lang()),
        add_product_url=url_for("manager_add_product"),
        pending_delete_ids=_pending_delete_product_ids(user.shop_id),
        product_image_url=url_for("manager_upload_product_image", product_id="__ID__"),
        bulk_delete_products_url=url_for("manager_bulk_delete_products"),
    )


@flask_app.route("/meneja/duka/mauzo")
@login_required(UserRole.MANAGER)
def manager_shop_sales():
    user = app.user_service.get_by_id(session["user_id"])
    shop = app.shop_service.get_by_id(user.shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("manager_dashboard"))
    _, ctx = _shop_dashboard_ctx(user.shop_id)
    sales = app.sale_service.get_all(user.shop_id)
    shop_available = app.cash_remittance_service.get_shop_manager_held_total(user.shop_id)
    boss_pending_total = sum(s.total_amount for s in sales if s.cash_status == "boss_pending")
    return render_template(
        "shops/sales.html",
        **_shop_layout_ctx(shop, user, "sales"),
        sales=sales,
        shop_available=shop_available,
        boss_pending_total=boss_pending_total,
        submit_cash_url=url_for("manager_submit_cash"),
        bulk_delete_sales_url=url_for("manager_bulk_delete_sales"),
        **ctx,
    )


@flask_app.route("/meneja/duka/mauzo/futa", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_bulk_delete_sales():
    user = app.user_service.get_by_id(session["user_id"])
    sale_ids = request.form.getlist("item_ids")
    return _request_delete_sales(
        user,
        user.shop_id,
        sale_ids,
        redirect_url=url_for("manager_shop_sales"),
    )


@flask_app.route("/meneja/duka/bidhaa/futa-teuzi", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_bulk_delete_products():
    user = app.user_service.get_by_id(session["user_id"])
    product_ids = request.form.getlist("item_ids")
    return _request_delete_products(
        user,
        user.shop_id,
        product_ids,
        redirect_url=url_for("manager_shop_products"),
    )


@flask_app.route("/meneja/duka/hariri", methods=["GET", "POST"])
@login_required(UserRole.MANAGER)
def manager_shop_edit():
    user = app.user_service.get_by_id(session["user_id"])
    shop = app.shop_service.get_by_id(user.shop_id)
    if not shop:
        flash(t("shop_not_found", _lang()), "danger")
        return redirect(url_for("manager_dashboard"))
    if request.method == "POST":
        app.shop_service.update_shop(
            shop.id,
            shop_type=request.form.get("shop_type", "").strip(),
            location=request.form.get("location", "").strip(),
            description=request.form.get("description", "").strip(),
        )
        flash(t("shop_saved", _lang()), "success")
        return redirect(url_for("manager_shop_view"))
    return render_template(
        "shops/edit.html",
        **_shop_layout_ctx(shop, user, "edit"),
        save_url=url_for("manager_shop_edit"),
        logo_url=url_for("manager_shop_upload_logo"),
        cover_url=url_for("manager_shop_upload_cover"),
        manager_mode=True,
    )


@flask_app.route("/meneja/duka/logo", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_shop_upload_logo():
    user = app.user_service.get_by_id(session["user_id"])
    return _shop_upload_image(user.shop_id, "logo", SHOP_LOGO_DIR, "logo")


@flask_app.route("/meneja/duka/cover", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_shop_upload_cover():
    user = app.user_service.get_by_id(session["user_id"])
    return _shop_upload_image(user.shop_id, "cover", SHOP_COVER_DIR, "cover_image")


@flask_app.route("/meneja")
@login_required(UserRole.MANAGER)
def manager_dashboard():
    return redirect(url_for("pro_dashboard"))


@flask_app.route("/meneja/bidhaa")
@login_required(UserRole.MANAGER)
def manager_products():
    return redirect(url_for("manager_shop_products"))


@flask_app.route("/meneja/bidhaa/ongeza", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_add_product():
    user = app.user_service.get_by_id(session["user_id"])
    try:
        data = _product_payload_from_form(user.shop_id)
        if not data["name"]:
            flash(t("fill_all_fields", _lang()), "warning")
            return redirect(url_for("manager_shop_products"))
        payload = json.dumps(data)
        req = app.approval_service.create_request(
            ApprovalType.ADD_PRODUCT,
            user.id,
            user.full_name,
            user.shop_id,
            t("add_product_request", _lang(), name=data["name"]),
            "",
            approver_role=UserRole.BOSS.value,
            payload=payload,
        )
        _notify_approval_created(req)
        flash(t("approval_sent_boss", _lang()), "info")
    except ValueError as e:
        if str(e) == "invalid_image":
            flash(t("invalid_image", _lang()), "danger")
        else:
            flash(t("invalid_data", _lang()), "danger")
    except TypeError:
        flash(t("invalid_data", _lang()), "danger")
    return redirect(url_for("manager_shop_products"))


@flask_app.route("/meneja/bidhaa/hariri/<product_id>", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_edit_product(product_id):
    user = app.user_service.get_by_id(session["user_id"])
    product = app.product_service.get_by_id(product_id)
    if not product or product.shop_id != user.shop_id:
        flash(t("product_not_found", _lang()), "danger")
        return redirect(url_for("manager_shop_products"))
    try:
        app.product_service.update_product(
            product_id,
            name=request.form.get("name", product.name),
            price=float(request.form.get("price", product.price)),
            cost_price=float(request.form.get("cost_price", product.cost_price)),
            quantity=int(request.form.get("quantity", product.quantity)),
            category=request.form.get("category", product.category),
        )
        flash(t("product_updated", _lang()), "success")
    except (ValueError, TypeError):
        flash(t("invalid_data", _lang()), "danger")
    return redirect(url_for("manager_shop_products"))


@flask_app.route("/meneja/bidhaa/futa/<product_id>", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_delete_product(product_id):
    user = app.user_service.get_by_id(session["user_id"])
    product = app.product_service.get_by_id(product_id)
    if not product or product.shop_id != user.shop_id:
        flash("Bidhaa haijapatikana.", "danger")
        return redirect(url_for("manager_shop_products"))
    if app.approval_service.has_pending_delete(product_id):
        flash(t("delete_cancel_first", _lang()), "warning")
        return redirect(url_for("manager_shop_products"))
    try:
        req = app.approval_service.create_request(
            ApprovalType.DELETE_PRODUCT,
            user.id,
            user.full_name,
            user.shop_id,
            t("delete_request", _lang(), name=product.name),
            product_id,
            approver_role=UserRole.BOSS.value,
        )
        _notify_approval_created(req)
        flash(t("approval_sent_boss", _lang()), "info")
    except ValueError as e:
        if str(e) == "pending_delete":
            flash(t("delete_cancel_first", _lang()), "warning")
        else:
            flash(t("invalid_data", _lang()), "danger")
    return redirect(url_for("manager_shop_products"))


@flask_app.route("/meneja/bidhaa/picha/<product_id>", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_upload_product_image(product_id):
    user = app.user_service.get_by_id(session["user_id"])
    product = app.product_service.get_by_id(product_id)
    if not product or product.shop_id != user.shop_id:
        flash(t("product_not_found", _lang()), "danger")
        return redirect(url_for("manager_shop_products"))
    try:
        filename = _save_product_image(request.files.get("image"), product_id)
        if filename:
            app.product_service.update_product(product_id, image=filename)
            flash(t("product_image_saved", _lang()), "success")
    except ValueError:
        flash(t("invalid_image", _lang()), "danger")
    return redirect(url_for("manager_shop_products"))


@flask_app.route("/meneja/wafanyakazi")
@login_required(UserRole.MANAGER)
def manager_employees():
    user = app.user_service.get_by_id(session["user_id"])
    employees = app.user_service.get_employees(user.shop_id)
    return render_template("manager/wafanyakazi.html", employees=employees)


@flask_app.route("/meneja/wafanyakazi/ongeza", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_add_employee():
    user = app.user_service.get_by_id(session["user_id"])
    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    try:
        salary = float(request.form.get("salary", 0))
    except ValueError:
        salary = 0
    if not all([full_name, username, password]):
        flash(t("fill_all_fields", _lang()), "warning")
        return redirect(url_for("manager_employees"))
    try:
        emp = app.user_service.add_user(
            username, password, UserRole.EMPLOYEE, full_name, user.shop_id, salary
        )
        flash(t("staff_added", _lang(), role=t("role_employee", _lang()), name=emp.full_name), "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("manager_employees"))


@flask_app.route("/meneja/wafanyakazi/futa/<emp_id>", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_remove_employee(emp_id):
    user = app.user_service.get_by_id(session["user_id"])
    emp = app.user_service.get_by_id(emp_id)
    if not emp or emp.role != UserRole.EMPLOYEE or emp.shop_id != user.shop_id:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("manager_employees"))
    app.trash_service.archive_user(emp, user.id, user.full_name, t("removed_by_manager", _lang()))
    app.user_service.remove_user(emp_id)
    flash(t("employee_removed", _lang(), name=emp.full_name), "warning")
    return redirect(url_for("manager_employees"))


@flask_app.route("/meneja/wafanyakazi/ruhusa/<emp_id>", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_set_permissions(emp_id):
    perms = EmployeePermissions(
        can_view_products="can_view_products" in request.form,
        can_sell="can_sell" in request.form,
        can_record_sales="can_record_sales" in request.form,
        can_view_sales_history="can_view_sales_history" in request.form,
    )
    app.user_service.update_permissions(emp_id, perms)
    flash(t("permissions_updated", _lang()) or "Ruhusa zimebadilishwa.", "success")
    return redirect(url_for("manager_employees"))


@flask_app.route("/meneja/mauzo")
@login_required(UserRole.MANAGER)
def manager_sales():
    return redirect(url_for("manager_shop_sales"))


@flask_app.route("/meneja/ripoti")
@login_required(UserRole.MANAGER)
def manager_finance():
    user = app.user_service.get_by_id(session["user_id"])
    report = app.finance_service.get_shop_report(user.shop_id)
    return render_template("manager/ripoti.html", report=report)


@flask_app.route("/meneja/idhini")
@login_required(UserRole.MANAGER)
def manager_approvals():
    user = app.user_service.get_by_id(session["user_id"])
    mine = [r for r in app.approval_service.get_all() if r.requested_by == user.id]
    pending_requests = app.approval_service.get_pending_for_manager(user.shop_id)
    products_by_id = {p.id: p for p in app.product_service.get_all()}
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    return render_template(
        "manager/idhini.html",
        approvals=mine,
        pending_requests=pending_requests,
        products_by_id=products_by_id,
        shops=shops,
        aina_ombi=aina_ombi,
        hali_ombi=hali_ombi,
    )


@flask_app.route("/meneja/idhini/<req_id>/<action>", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_approval_action(req_id, action):
    note = request.form.get("note", "").strip()
    user = app.user_service.get_by_id(session["user_id"])
    req = app.approval_service.get_by_id(req_id)
    if not req:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("manager_approvals"))

    if action in ("approve", "reject"):
        if (
            not _can_approve_request(req, user)
            or req.approver_role != UserRole.MANAGER.value
            or req.shop_id != user.shop_id
        ):
            flash(t("not_found", _lang()), "danger")
            return redirect(url_for("manager_approvals"))
        if action == "approve":
            app.approval_service.approve(req_id, note or t("approved", _lang()))
            _execute_approval(req, user.id, user.full_name)
            _notify_approval_result(req, "approved")
            flash(t("approved", _lang()), "success")
        else:
            app.approval_service.reject(req_id, note or t("rejected", _lang()))
            _notify_approval_result(req, "rejected")
            flash(t("rejected", _lang()), "info")
    elif action in ("cancel", "delete"):
        if not _can_manage_product_approval(req, user):
            flash(t("not_found", _lang()), "danger")
            return redirect(url_for("manager_approvals"))
        if action == "cancel":
            app.approval_service.cancel(req_id, note or t("approval_suspended", _lang()))
            _notify_approval_result(req, "cancelled")
            flash(t("approval_suspended", _lang()), "warning")
        else:
            app.approval_service.delete_request(req_id)
            flash(t("approval_deleted", _lang()), "info")
    else:
        flash(t("not_found", _lang()), "danger")
    return redirect(url_for("manager_approvals"))


@flask_app.route("/meneja/idhini/bulk", methods=["POST"])
@login_required(UserRole.MANAGER)
def manager_approval_bulk():
    action = request.form.get("action", "").strip()
    req_ids = request.form.getlist("req_ids")
    note = request.form.get("note", "").strip()
    if action not in ("approve", "reject", "cancel") or not req_ids:
        flash(t("not_found", _lang()), "danger")
        return redirect(url_for("manager_approvals"))
    user = app.user_service.get_by_id(session["user_id"])
    done = _process_approval_bulk(user, req_ids, action, note)
    if done:
        flash(t("approval_bulk_done", _lang(), n=done), "success")
    else:
        flash(t("not_found", _lang()), "danger")
    return redirect(url_for("manager_approvals"))


@flask_app.route("/meneja/takataka")
@login_required(UserRole.MANAGER)
def manager_trash():
    user = app.user_service.get_by_id(session["user_id"])
    products = app.trash_service.get_all(shop_id=user.shop_id, item_type="product")
    users = app.trash_service.get_all(shop_id=user.shop_id, item_type="user")
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    return render_template(
        "trash/view.html",
        deleted_products=products,
        deleted_users=users,
        shops=shops,
        back_url=url_for("manager_dashboard"),
        can_delete_trash=False,
    )


# ── Mfanyakazi (Employee) ────────────────────────────────────

@flask_app.route("/mfanyakazi")
@login_required(UserRole.EMPLOYEE)
def employee_dashboard():
    return redirect(url_for("pro_dashboard"))


@flask_app.route("/mfanyakazi/bidhaa")
@login_required(UserRole.EMPLOYEE)
def employee_products():
    user = app.user_service.get_by_id(session["user_id"])
    if not user.permissions.can_view_products:
        flash(t("no_permission", _lang()), "danger")
        return redirect(url_for("employee_dashboard"))
    products = [p for p in app.product_service.get_all(user.shop_id) if p.quantity > 0]
    return render_template("employee/bidhaa.html", products=products)


def _parse_sale_unit_price(raw: str, fallback: float) -> float:
    try:
        value = float((raw or "").strip().replace(",", ""))
        return value if value > 0 else fallback
    except ValueError:
        return fallback


def _process_sale(
    user,
    product_id: str,
    quantity: int,
    unit_price: float | None = None,
):
    product = app.product_service.get_by_id(product_id)
    if not product or product.shop_id != user.shop_id:
        raise ValueError("not_found")
    if quantity <= 0:
        raise ValueError("invalid_quantity")
    price = unit_price if unit_price and unit_price > 0 else product.price
    if price <= product.cost_price:
        raise ValueError("sell_price_too_low")
    app.product_service.reduce_stock(product_id, quantity)
    sale = app.sale_service.record_sale(
        product_id=product.id,
        product_name=product.name,
        shop_id=user.shop_id,
        employee_id=user.id,
        employee_name=user.full_name,
        quantity=quantity,
        unit_price=price,
        cost_price=product.cost_price,
    )
    updated = app.product_service.get_by_id(product_id)
    _notify_sale(sale)
    if updated:
        _notify_low_stock(updated)
    return sale


@flask_app.route("/mfanyakazi/uza", methods=["GET", "POST"])
@flask_app.route("/uza", methods=["GET", "POST"])
@login_required()
def employee_sell():
    user = app.user_service.get_by_id(session["user_id"])
    if not _can_user_sell(user):
        flash(t("no_permission_sell", _lang()), "danger")
        return redirect(url_for("pro_dashboard"))

    products = [p for p in app.product_service.get_all(user.shop_id) if p.quantity > 0]
    redirect_to = request.form.get("redirect_to", "").strip()

    if request.method == "POST":
        product_id = request.form.get("product_id", "")
        try:
            quantity = int(request.form.get("quantity", 0))
        except ValueError:
            quantity = 0
        product = app.product_service.get_by_id(product_id)
        if product and quantity > 0:
            unit_price = _parse_sale_unit_price(
                request.form.get("unit_price", ""),
                product.price,
            )
            try:
                sale = _process_sale(
                    user,
                    product_id,
                    quantity,
                    unit_price,
                )
                flash(
                    t("sale_success", _lang(), amount=_money_str(sale.total_amount)),
                    "success",
                )
                if redirect_to == "home":
                    return redirect(url_for("home_feed"))
                return redirect(url_for("employee_sell"))
            except ValueError as e:
                if str(e) == "not_found":
                    flash(t("not_found", _lang()), "danger")
                elif str(e) == "sell_price_too_low":
                    flash(t("sell_price_too_low", _lang()), "danger")
                else:
                    flash(str(e), "danger")
        if redirect_to == "home":
            return redirect(url_for("home_feed"))

    return render_template("employee/uza.html", products=products)


@flask_app.route("/mfanyakazi/mauzo")
@login_required(UserRole.EMPLOYEE)
def employee_sales():
    user = app.user_service.get_by_id(session["user_id"])
    if not user.permissions.can_view_sales_history:
        flash(t("no_permission", _lang()), "danger")
        return redirect(url_for("employee_dashboard"))
    sales = [s for s in app.sale_service.get_all(user.shop_id) if s.employee_id == user.id]
    return render_template("employee/mauzo.html", sales=sales[-30:])


@flask_app.route("/mfanyakazi/pesa", methods=["GET", "POST"])
@login_required(UserRole.EMPLOYEE)
def employee_cash():
    user = app.user_service.get_by_id(session["user_id"])
    period = request.values.get("period", "all")
    if period not in ("all", "today", "week", "month"):
        period = "all"

    if request.method == "POST" and request.form.get("action") == "submit":
        note = request.form.get("note", "").strip()
        submit_mode = request.form.get("submit_mode", "selected")
        try:
            if submit_mode == "amount":
                raw_amount = request.form.get("amount", "").strip().replace(",", "")
                amount = float(raw_amount)
                remittance = app.cash_remittance_service.create_remittance_from_amount(
                    user, amount, note
                )
            else:
                sale_ids = request.form.getlist("sale_ids")
                remittance = app.cash_remittance_service.create_remittance(
                    user, note, sale_ids=sale_ids or None
                )
            _notify_cash_submitted(remittance)
            flash(
                t("cash_submitted", _lang(), name=remittance.receiver_name),
                "success",
            )
        except ValueError as e:
            err_keys = {
                "no_held_sales": "cash_no_held",
                "no_selection": "cash_no_selection",
                "invalid_sales": "cash_no_selection",
                "invalid_amount": "cash_invalid_amount",
                "amount_exceeds_held": "cash_amount_exceeds",
            }
            flash(t(err_keys.get(str(e), "error"), _lang()), "warning")
        return redirect(url_for("employee_cash", period=period))

    held_sales = app.cash_remittance_service.get_held_sales(user.id, period)
    held_total = app.cash_remittance_service.get_held_total(user.id)
    my_sales = [s for s in app.sale_service.get_all(user.shop_id) if s.employee_id == user.id]
    pending_total = sum(s.total_amount for s in my_sales if s.cash_status == "pending")
    confirmed_total = sum(s.total_amount for s in my_sales if s.cash_status == "confirmed")
    try:
        _, receiver_name, receiver_role = app.cash_remittance_service.resolve_receiver(
            user.shop_id
        )
    except ValueError:
        receiver_name = ""
        receiver_role = ""
    history = app.cash_remittance_service.get_employee_remittances(user.id)
    filtered_total = sum(s.total_amount for s in held_sales)
    return render_template(
        "employee/pesa.html",
        held_sales=held_sales,
        held_total=held_total,
        filtered_total=filtered_total,
        period=period,
        pending_total=pending_total,
        confirmed_total=confirmed_total,
        receiver_name=receiver_name,
        receiver_role=receiver_role,
        history=history,
    )


def _cash_confirm_page(user, confirm_url: str):
    pending = app.cash_remittance_service.get_pending_for_user(user)
    for remittance in pending:
        remittance.sales = app.sale_service.get_by_ids(remittance.sale_ids)
    shops = {s.id: s.name for s in app.shop_service.get_all()}
    return render_template(
        "cash/confirm.html",
        pending=pending,
        confirm_url=confirm_url,
        shops=shops,
    )


@flask_app.route("/meneja/toa-pesa", methods=["GET", "POST"])
@login_required(UserRole.MANAGER)
def manager_submit_cash():
    user = app.user_service.get_by_id(session["user_id"])
    period = request.values.get("period", "all")
    if period not in ("all", "today", "week", "month"):
        period = "all"

    if request.method == "POST" and request.form.get("action") == "submit":
        note = request.form.get("note", "").strip()
        submit_mode = request.form.get("submit_mode", "selected")
        try:
            if submit_mode == "amount":
                raw_amount = request.form.get("amount", "").strip().replace(",", "")
                amount = float(raw_amount)
                remittance = app.cash_remittance_service.create_manager_remittance_from_amount(
                    user, amount, note
                )
            else:
                sale_ids = request.form.getlist("sale_ids")
                remittance = app.cash_remittance_service.create_manager_remittance(
                    user, note, sale_ids=sale_ids or None
                )
            _notify_cash_submitted(remittance)
            flash(
                t("cash_submitted", _lang(), name=remittance.receiver_name),
                "success",
            )
        except ValueError as e:
            err_keys = {
                "no_held_sales": "cash_no_shop_cash",
                "no_selection": "cash_no_selection",
                "invalid_sales": "cash_no_selection",
                "invalid_amount": "cash_invalid_amount",
                "amount_exceeds_held": "cash_amount_exceeds",
            }
            flash(t(err_keys.get(str(e), "error"), _lang()), "warning")
        return redirect(url_for("manager_submit_cash", period=period))

    held_sales = app.cash_remittance_service.get_shop_manager_held_sales(
        user.shop_id, period
    )
    held_total = app.cash_remittance_service.get_shop_manager_held_total(user.shop_id)
    shop_sales = app.sale_service.get_all(user.shop_id)
    pending_total = sum(s.total_amount for s in shop_sales if s.cash_status == "boss_pending")
    confirmed_total = sum(s.total_amount for s in shop_sales if s.cash_status == "confirmed")
    try:
        _, receiver_name, receiver_role = app.cash_remittance_service.resolve_boss_receiver()
    except ValueError:
        receiver_name = ""
        receiver_role = "boss"
    history = [
        r
        for r in app.cash_remittance_service.get_submitter_remittances(user.id)
        if r.remittance_kind == "from_manager"
    ]
    filtered_total = sum(s.total_amount for s in held_sales)
    return render_template(
        "manager/toa_pesa.html",
        held_sales=held_sales,
        held_total=held_total,
        filtered_total=filtered_total,
        period=period,
        pending_total=pending_total,
        confirmed_total=confirmed_total,
        receiver_name=receiver_name,
        receiver_role=receiver_role,
        history=history,
    )


@flask_app.route("/meneja/pesa", methods=["GET", "POST"])
@login_required(UserRole.MANAGER)
def manager_cash():
    user = app.user_service.get_by_id(session["user_id"])
    if request.method == "POST":
        remittance_id = request.form.get("remittance_id", "").strip()
        note = request.form.get("note", "").strip()
        try:
            remittance = app.cash_remittance_service.confirm(remittance_id, user, note)
            _notify_cash_confirmed(remittance)
            flash(
                t(
                    "cash_confirmed_msg",
                    _lang(),
                    amount=_money_str(remittance.amount),
                    name=remittance.employee_name,
                ),
                "success",
            )
        except ValueError:
            flash(t("error", _lang()), "danger")
        return redirect(url_for("manager_cash"))
    return _cash_confirm_page(user, url_for("manager_cash"))


@flask_app.route("/boss/pesa", methods=["GET", "POST"])
@login_required(UserRole.BOSS)
def boss_cash():
    user = app.user_service.get_by_id(session["user_id"])
    if request.method == "POST":
        remittance_id = request.form.get("remittance_id", "").strip()
        note = request.form.get("note", "").strip()
        try:
            remittance = app.cash_remittance_service.confirm(remittance_id, user, note)
            _notify_cash_confirmed(remittance)
            flash(
                t(
                    "cash_confirmed_msg",
                    _lang(),
                    amount=_money_str(remittance.amount),
                    name=remittance.employee_name,
                ),
                "success",
            )
        except ValueError:
            flash(t("error", _lang()), "danger")
        return redirect(url_for("boss_cash"))
    return _cash_confirm_page(user, url_for("boss_cash"))


# ── DESIGN PREVIEW / MUONEKANO (for testing phone + custom theming) ──
@flask_app.route("/preview")
def design_preview():
    return render_template("preview.html")


def _local_lan_ip() -> str:
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _all_ipv4_addresses() -> list[str]:
    import socket

    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    try:
        primary = _local_lan_ip()
        if primary and not primary.startswith("127."):
            ips.add(primary)
    except OSError:
        pass
    return sorted(ips)


def run():
    host = "0.0.0.0"
    port = 5000
    print(f"  PC:    http://127.0.0.1:{port}")
    lan_ips = _all_ipv4_addresses()
    if lan_ips:
        print("  Simu — jaribu mojawapo (Wi-Fi/Hotspot sawa na PC):")
        for ip in lan_ips:
            print(f"         http://{ip}:{port}")
    else:
        print("  Simu:  hakuna IP ya mtandao — tumia Hotspot (tazama run_mobile.py)")
    print("  USB internet pekee mara nyingi HAIWEZI — tumia Hotspot ya simu")
    flask_app.run(host=host, debug=True, port=port, use_reloader=False)
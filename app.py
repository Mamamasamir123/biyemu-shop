from pathlib import Path

from storage.json_storage import JsonStorage
from services.auth_service import AuthService
from services.shop_service import ShopService
from services.product_service import ProductService
from services.sale_service import SaleService
from services.approval_service import ApprovalService
from services.user_service import UserService
from services.finance_service import FinanceService
from services.trash_service import TrashService
from services.banner_service import BannerService
from services.notification_service import NotificationService
from services.cash_remittance_service import CashRemittanceService
from services.boss_settings_service import BossSettingsService
from services.dashboard_control_service import DashboardControlService
from services.chat_service import ChatService
from services.connection_service import ConnectionService


class BiyeMuApp:
    """Programu kuu — inaunganisha huduma zote."""

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.storage = JsonStorage(data_dir)

        self.auth_service = AuthService(self.storage)
        self.shop_service = ShopService(self.storage)
        self.product_service = ProductService(self.storage)
        self.sale_service = SaleService(self.storage)
        self.approval_service = ApprovalService(self.storage)
        self.user_service = UserService(self.storage)
        self.trash_service = TrashService(self.storage)
        self.banner_service = BannerService(self.storage)
        self.boss_settings_service = BossSettingsService(self.storage)
        self.dashboard_control_service = DashboardControlService(self.storage)
        self.chat_service = ChatService(self.storage)
        self.connection_service = ConnectionService(self.storage)
        self.notification_service = NotificationService(
            self.storage, self.user_service, self.boss_settings_service
        )
        self.cash_remittance_service = CashRemittanceService(
            self.storage, self.sale_service, self.user_service
        )
        self.finance_service = FinanceService(
            self.sale_service,
            self.user_service,
            self.product_service,
        )
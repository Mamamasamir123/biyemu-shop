"""Data ya mwanzo kwa mfumo wa BiyeMu."""

from models.user import User, UserRole, EmployeePermissions
from models.shop import Shop
from models.product import Product
from models.sale import Sale
from storage.json_storage import JsonStorage


def seed_if_empty(storage: JsonStorage) -> None:
    if storage.exists("users"):
        return

    shops = [
        Shop(id="shop001", name="BiyeMu Nguo", shop_type="Nguo", location="Dar es Salaam"),
        Shop(id="shop002", name="BiyeMu Electronics", shop_type="Electronics", location="Arusha"),
        Shop(id="shop003", name="BiyeMu Studio", shop_type="Studio", location="Dodoma"),
    ]

    users = [
        User(
            id="boss001",
            username="boss",
            password="boss123",
            role=UserRole.BOSS,
            full_name="BiyeMu Admin",
            salary=0,
        ),
        User(
            id="mgr001",
            username="manager_nguo",
            password="mgr123",
            role=UserRole.MANAGER,
            full_name="Asha Mwangi",
            shop_id="shop001",
            salary=800_000,
        ),
        User(
            id="mgr002",
            username="manager_elec",
            password="mgr123",
            role=UserRole.MANAGER,
            full_name="John Komba",
            shop_id="shop002",
            salary=900_000,
        ),
        User(
            id="emp001",
            username="mfanyakazi1",
            password="emp123",
            role=UserRole.EMPLOYEE,
            full_name="Neema Juma",
            shop_id="shop001",
            salary=450_000,
            permissions=EmployeePermissions(
                can_view_products=True,
                can_sell=True,
                can_record_sales=True,
                can_view_sales_history=False,
            ),
        ),
        User(
            id="emp002",
            username="mfanyakazi2",
            password="emp123",
            role=UserRole.EMPLOYEE,
            full_name="Peter Mushi",
            shop_id="shop002",
            salary=500_000,
            permissions=EmployeePermissions(
                can_view_products=True,
                can_sell=True,
                can_record_sales=True,
                can_view_sales_history=True,
            ),
        ),
    ]

    products = [
        Product(id="prod001", name="Shati la Kijani", price=35_000, quantity=50, shop_id="shop001", cost_price=20_000, category="Mavazi"),
        Product(id="prod002", name="Suruali ya Jean", price=55_000, quantity=30, shop_id="shop001", cost_price=35_000, category="Mavazi"),
        Product(id="prod003", name="Simu Samsung A15", price=450_000, quantity=15, shop_id="shop002", cost_price=380_000, category="Simu"),
        Product(id="prod004", name="Earphones Bluetooth", price=25_000, quantity=40, shop_id="shop002", cost_price=12_000, category="Vifaa"),
        Product(id="prod005", name="Kamera ya Video", price=1_200_000, quantity=5, shop_id="shop003", cost_price=950_000, category="Studio"),
        Product(id="prod006", name="Mic ya Podcast", price=180_000, quantity=10, shop_id="shop003", cost_price=120_000, category="Studio"),
    ]

    sales = [
        Sale(
            id="sale001",
            product_id="prod001",
            product_name="Shati la Kijani",
            shop_id="shop001",
            employee_id="emp001",
            employee_name="Neema Juma",
            quantity=2,
            unit_price=35_000,
            total_amount=70_000,
            cost_price=20_000,
            date="2026-06-28 10:30",
        ),
        Sale(
            id="sale002",
            product_id="prod004",
            product_name="Earphones Bluetooth",
            shop_id="shop002",
            employee_id="emp002",
            employee_name="Peter Mushi",
            quantity=3,
            unit_price=25_000,
            total_amount=75_000,
            cost_price=12_000,
            date="2026-06-29 14:15",
        ),
    ]

    storage.save_list("shops", shops)
    storage.save_list("users", users)
    storage.save_list("products", products)
    storage.save_list("sales", sales)
    storage.save_list("approvals", [])
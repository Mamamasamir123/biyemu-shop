from models.approval import ApprovalType
from models.user import EmployeePermissions
from ui.helpers import print_header, print_table, input_float, input_int, input_yes_no
from ui.swahili import aina_ombi, hali_ombi


class ManagerMenu:
    def __init__(self, app, user):
        self.app = app
        self.user = user

    def run(self) -> None:
        shop = self.app.shop_service.get_by_id(self.user.shop_id)
        shop_name = shop.name if shop else "Duka Lisilojulikana"

        while True:
            print_header(f"Paneli ya Meneja — {self.user.full_name}")
            print(f"\n  Duka lako: {shop_name}")
            print("\n  1. Angalia bidhaa za duka")
            print("  2. Ongeza bidhaa mpya")
            print("  3. Rekebisha bidhaa")
            print("  4. Omba kufuta bidhaa (inahitaji idhini ya mkuu)")
            print("  5. Angalia wafanyakazi wa duka")
            print("  6. Weka ruhusa za mfanyakazi")
            print("  7. Angalia mauzo ya duka")
            print("  8. Ripoti ya faida na hasara")
            print("  9. Ombi zangu za idhini")
            print("  0. Ondoka (toka kwenye akaunti)")

            choice = input("\n  Chagua namba: ").strip()

            actions = {
                "1": self.view_products,
                "2": self.add_product,
                "3": self.edit_product,
                "4": self.request_delete_product,
                "5": self.view_employees,
                "6": self.set_permissions,
                "7": self.view_sales,
                "8": self.finance_report,
                "9": self.my_approvals,
            }

            if choice == "0":
                print("\n  Umeondoka kwenye akaunti ya meneja.")
                return
            if choice in actions:
                actions[choice]()
            else:
                print("  [!] Umechagua kibaya. Ingiza namba kutoka 0 hadi 9.")
            input("\n  Bonyeza Enter kurudi kwenye menyu...")

    def view_products(self) -> None:
        print_header("Bidhaa za Duka Lako")
        products = self.app.product_service.get_all(self.user.shop_id)
        rows = [
            [p.id, p.name, f"{p.price:,.0f}", f"{p.cost_price:,.0f}", p.quantity, p.category or "-"]
            for p in products
        ]
        print_table(
            ["Nambari", "Bidhaa", "Bei Uuzaji", "Gharama", "Idadi Iliyopo", "Aina"],
            rows,
        )

    def add_product(self) -> None:
        print_header("Ongeza Bidhaa Mpya")
        name = input("  Jina la bidhaa: ").strip()
        price = input_float("  Bei ya kuuza (TZS): ")
        cost = input_float("  Gharama ya kununua (TZS): ")
        quantity = input_int("  Idadi iliyopo (hifadhi): ")
        category = input("  Aina/kategoria (si lazima): ").strip()

        product = self.app.product_service.add_product(
            name, price, quantity, self.user.shop_id, cost, category
        )
        print(f"\n  ✓ Bidhaa '{product.name}' imeongezwa. Nambari: {product.id}")

    def edit_product(self) -> None:
        print_header("Rekebisha Taarifa za Bidhaa")
        self.view_products()
        product_id = input("\n  Nambari ya bidhaa: ").strip()
        product = self.app.product_service.get_by_id(product_id)
        if not product or product.shop_id != self.user.shop_id:
            print("  [!] Bidhaa haijapatikana katika duka lako.")
            return

        print(f"\n  Unarekebisha: {product.name}")
        print("  (Acha tupu ili kubaki na thamani ya sasa)")

        name = input(f"  Jina [{product.name}]: ").strip() or product.name
        price_str = input(f"  Bei ya kuuza [{product.price}]: ").strip()
        price = float(price_str) if price_str else product.price
        cost_str = input(f"  Gharama ya kununua [{product.cost_price}]: ").strip()
        cost = float(cost_str) if cost_str else product.cost_price
        qty_str = input(f"  Idadi iliyopo [{product.quantity}]: ").strip()
        quantity = int(qty_str) if qty_str else product.quantity
        category = input(f"  Aina/kategoria [{product.category}]: ").strip() or product.category

        self.app.product_service.update_product(
            product_id, name=name, price=price, cost_price=cost, quantity=quantity, category=category
        )
        print("\n  ✓ Taarifa za bidhaa zimebadilishwa kikamilifu.")

    def request_delete_product(self) -> None:
        print_header("Omba Ruhusa ya Kufuta Bidhaa")
        self.view_products()
        product_id = input("\n  Nambari ya bidhaa unayotaka kufuta: ").strip()
        product = self.app.product_service.get_by_id(product_id)
        if not product or product.shop_id != self.user.shop_id:
            print("  [!] Bidhaa haijapatikana.")
            return

        if not input_yes_no(f"  Una uhakika unataka kufuta '{product.name}'? (ndio/hapana): "):
            print("  Umeghairi ombi la kufuta bidhaa.")
            return

        req = self.app.approval_service.create_request(
            ApprovalType.DELETE_PRODUCT,
            self.user.id,
            self.user.full_name,
            self.user.shop_id,
            f"Ombi la kufuta bidhaa: {product.name} (idadi iliyopo: {product.quantity})",
            product_id,
        )
        print(f"\n  ✓ Ombi lako limepelekwa kwa mkuu. Nambari ya ombi: {req.id}")
        print("    Subiri idhini ya mkuu kabla ya bidhaa kufutwa.")

    def view_employees(self) -> None:
        print_header("Wafanyakazi wa Duka Lako")
        employees = self.app.user_service.get_employees(self.user.shop_id)
        if not employees:
            print("  Hakuna wafanyakazi katika duka hili bado.")
            return
        rows = [
            [
                e.full_name,
                f"{e.salary:,.0f}",
                "Ndiyo" if e.permissions.can_sell else "Hapana",
                "Ndiyo" if e.permissions.can_view_products else "Hapana",
            ]
            for e in employees
        ]
        print_table(["Jina", "Mshahara (TZS)", "Anaweza Kuuza", "Anaona Bidhaa"], rows)

    def set_permissions(self) -> None:
        print_header("Weka Ruhusa za Mfanyakazi")
        employees = self.app.user_service.get_employees(self.user.shop_id)
        if not employees:
            print("  Hakuna wafanyakazi katika duka hili.")
            return

        print("\n  Chagua mfanyakazi:")
        for i, e in enumerate(employees, 1):
            print(f"    {i}. {e.full_name}")

        idx = input_int("\n  Ingiza namba ya mfanyakazi: ") - 1
        if idx < 0 or idx >= len(employees):
            print("  [!] Umechagua kibaya.")
            return

        emp = employees[idx]
        perms = emp.permissions
        print(f"\n  Ruhusa za sasa za {emp.full_name}:")
        print(f"    • Kuona bidhaa:       {'Ndiyo' if perms.can_view_products else 'Hapana'}")
        print(f"    • Kuuza bidhaa:       {'Ndiyo' if perms.can_sell else 'Hapana'}")
        print(f"    • Kurekodi mauzo:     {'Ndiyo' if perms.can_record_sales else 'Hapana'}")
        print(f"    • Kuona historia:     {'Ndiyo' if perms.can_view_sales_history else 'Hapana'}")

        print("\n  Weka ruhusa mpya:")
        new_perms = EmployeePermissions(
            can_view_products=input_yes_no("  Ruhusu kuona bidhaa? (ndio/hapana): "),
            can_sell=input_yes_no("  Ruhusu kuuza bidhaa? (ndio/hapana): "),
            can_record_sales=input_yes_no("  Ruhusu kurekodi mauzo? (ndio/hapana): "),
            can_view_sales_history=input_yes_no("  Ruhusu kuona historia ya mauzo? (ndio/hapana): "),
        )
        self.app.user_service.update_permissions(emp.id, new_perms)
        print(f"\n  ✓ Ruhusa za {emp.full_name} zimebadilishwa.")

    def view_sales(self) -> None:
        print_header("Mauzo ya Duka Lako")
        sales = self.app.sale_service.get_all(self.user.shop_id)
        if not sales:
            print("  Hakuna mauzo yaliyorekodiwa bado.")
            return
        rows = [
            [s.date, s.product_name, s.quantity, f"{s.total_amount:,.0f}", s.employee_name]
            for s in sales[-20:]
        ]
        print_table(["Tarehe", "Bidhaa", "Idadi", "Jumla (TZS)", "Aliyeuza"], rows)
        if len(sales) > 20:
            print(f"\n  (Inaonyesha mauzo 20 ya mwisho kati ya {len(sales)})")

    def finance_report(self) -> None:
        print_header("Ripoti ya Faida na Hasara — Duka Lako")
        report = self.app.finance_service.get_shop_report(self.user.shop_id)
        print(f"\n  Mapato ya mauzo:        {report.total_revenue:>15,.0f} TZS")
        print(f"  Gharama ya bidhaa:      {report.total_cost:>15,.0f} TZS")
        print(f"  Faida kabla ya mishahara:{report.total_profit:>15,.0f} TZS")
        print(f"  Mishahara ya wafanyakazi:{report.total_salaries:>15,.0f} TZS")
        print(f"  {'─' * 45}")
        status = "FAIDA HALISI" if report.net_profit >= 0 else "HASARA HALISI"
        print(f"  {status}:          {abs(report.net_profit):>15,.0f} TZS")

    def my_approvals(self) -> None:
        print_header("Ombi Zangu za Idhini")
        all_reqs = self.app.approval_service.get_all()
        mine = [r for r in all_reqs if r.requested_by == self.user.id]
        if not mine:
            print("  Hujawahi kutuma ombi lolote la idhini.")
            return
        rows = [
            [
                r.id,
                aina_ombi(r.approval_type),
                hali_ombi(r.status),
                r.created_at,
                r.boss_note or "-",
            ]
            for r in mine
        ]
        print_table(["Nambari", "Aina ya Ombi", "Hali", "Tarehe", "Maoni ya Mkuu"], rows)
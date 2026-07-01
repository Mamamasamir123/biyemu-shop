from models.user import UserRole
from ui.helpers import print_header, print_table, input_float, input_int, input_yes_no
from ui.swahili import jukumu, aina_ombi


class BossMenu:
    def __init__(self, app, user):
        self.app = app
        self.user = user

    def run(self) -> None:
        while True:
            print_header(f"Paneli ya Mkuu - {self.user.full_name}")
            pending = len(self.app.approval_service.get_pending())
            print(f"\n  Ombi zinazosubiri idhini: {pending}")
            print("\n  1. Angalia maduka yote")
            print("  2. Ongeza duka jipya")
            print("  3. Angalia bidhaa (maduka yote)")
            print("  4. Ongeza meneja")
            print("  5. Ongeza mfanyakazi")
            print("  6. Angalia wafanyakazi na mishahara")
            print("  7. Badilisha mshahara")
            print("  8. Idhinisha au kataa mabadiliko")
            print("  9. Ripoti ya faida na hasara")
            print("  10. Angalia mauzo")
            print("  0. Ondoka (toka kwenye akaunti)")

            choice = input("\n  Chagua namba: ").strip()

            actions = {
                "1": self.view_shops,
                "2": self.add_shop,
                "3": self.view_all_products,
                "4": self.add_manager,
                "5": self.add_employee,
                "6": self.view_staff,
                "7": self.update_salary,
                "8": self.handle_approvals,
                "9": self.finance_report,
                "10": self.view_sales,
            }

            if choice == "0":
                print("\n  Umeondoka kwenye akaunti ya mkuu.")
                return
            if choice in actions:
                actions[choice]()
            else:
                print("  [!] Umechagua kibaya. Ingiza namba kutoka 0 hadi 10.")
            input("\n  Bonyeza Enter kurudi kwenye menyu...")

    def view_shops(self) -> None:
        print_header("Orodha ya Maduka Yote")
        shops = self.app.shop_service.get_all()
        rows = [[s.id, s.name, s.shop_type, s.location or "-"] for s in shops]
        print_table(["Nambari", "Jina la Duka", "Aina", "Mahali"], rows)

    def add_shop(self) -> None:
        print_header("Ongeza Duka Jipya")
        name = input("  Jina la duka (mfano: Nguo): ").strip()
        shop_type = input("  Aina ya duka (mfano: Nguo, Vifaa vya Umeme): ").strip()
        location = input("  Mahali/Mji: ").strip()
        shop = self.app.shop_service.add_shop(name, shop_type, location)
        print(f"\n  ✓ Duka '{shop.name}' limeongezwa kikamilifu. Nambari: {shop.id}")

    def view_all_products(self) -> None:
        print_header("Bidhaa Zote — Maduka Yote")
        products = self.app.product_service.get_all()
        shops = {s.id: s.name for s in self.app.shop_service.get_all()}
        rows = [
            [p.id, p.name, f"{p.price:,.0f}", p.quantity, shops.get(p.shop_id, "?")]
            for p in products
        ]
        print_table(["Nambari", "Bidhaa", "Bei (TZS)", "Idadi Iliyopo", "Duka"], rows)

    def add_manager(self) -> None:
        print_header("Ongeza Meneja wa Duka")
        shops = self.app.shop_service.get_all()
        if not shops:
            print("  [!] Hakuna maduka bado. Ongeza duka kwanza.")
            return

        print("\n  Maduka yaliyopo:")
        for s in shops:
            print(f"    {s.id} — {s.name}")

        shop_id = input("\n  Nambari ya duka: ").strip()
        if not self.app.shop_service.get_by_id(shop_id):
            print("  [!] Duka halijapatikana. Angalia nambari uliyoingiza.")
            return

        full_name = input("  Jina kamili la meneja: ").strip()
        username = input("  Jina la mtumiaji (kwa kuingia): ").strip()
        password = input("  Nenosiri: ").strip()
        salary = input_float("  Mshahara wa kila mwezi (TZS): ")

        try:
            user = self.app.user_service.add_user(
                username, password, UserRole.MANAGER, full_name, shop_id, salary
            )
            print(f"\n  ✓ Meneja '{user.full_name}' ameongezwa kikamilifu.")
        except ValueError as e:
            print(f"  [!] {e}")

    def add_employee(self) -> None:
        print_header("Ongeza Mfanyakazi")
        shops = self.app.shop_service.get_all()
        if not shops:
            print("  [!] Hakuna maduka bado.")
            return

        print("\n  Maduka yaliyopo:")
        for s in shops:
            print(f"    {s.id} — {s.name}")

        shop_id = input("\n  Nambari ya duka: ").strip()
        if not self.app.shop_service.get_by_id(shop_id):
            print("  [!] Duka halijapatikana.")
            return

        full_name = input("  Jina kamili la mfanyakazi: ").strip()
        username = input("  Jina la mtumiaji (kwa kuingia): ").strip()
        password = input("  Nenosiri: ").strip()
        salary = input_float("  Mshahara wa kila mwezi (TZS): ")

        try:
            user = self.app.user_service.add_user(
                username, password, UserRole.EMPLOYEE, full_name, shop_id, salary
            )
            print(f"\n  ✓ Mfanyakazi '{user.full_name}' ameongezwa kikamilifu.")
        except ValueError as e:
            print(f"  [!] {e}")

    def view_staff(self) -> None:
        print_header("Wafanyakazi na Mishahara")
        users = self.app.user_service.get_all()
        shops = {s.id: s.name for s in self.app.shop_service.get_all()}
        staff = [u for u in users if u.role != UserRole.BOSS]
        rows = [
            [
                u.id,
                u.full_name,
                jukumu(u.role),
                shops.get(u.shop_id, "-"),
                f"{u.salary:,.0f}",
                "Anafanya kazi" if u.active else "Amesimamishwa",
            ]
            for u in staff
        ]
        print_table(["Nambari", "Jina", "Jukumu", "Duka", "Mshahara (TZS)", "Hali"], rows)

    def update_salary(self) -> None:
        print_header("Badilisha Mshahara wa Mfanyakazi")
        self.view_staff()
        user_id = input("\n  Nambari au jina la mfanyakazi: ").strip()

        users = self.app.user_service.get_all()
        user = next((u for u in users if u.id == user_id), None)
        if not user:
            user = next((u for u in users if u.full_name.lower() == user_id.lower()), None)
        if not user:
            print("  [!] Mfanyakazi hajapatikana. Angalia orodha hapo juu.")
            return

        print(f"\n  Mfanyakazi: {user.full_name}")
        print(f"  Mshahara wa sasa: {user.salary:,.0f} TZS")
        new_salary = input_float("  Mshahara mpya (TZS): ")
        self.app.user_service.update_salary(user.id, new_salary)
        print(f"\n  ✓ Mshahara wa {user.full_name} umebadilishwa kuwa {new_salary:,.0f} TZS.")

    def handle_approvals(self) -> None:
        print_header("Ombi za Idhini Zinazosubiri")
        pending = self.app.approval_service.get_pending()
        if not pending:
            print("  Hakuna ombi lolote linalosubiri idhini yako.")
            return

        shops = {s.id: s.name for s in self.app.shop_service.get_all()}
        for req in pending:
            print(f"\n  ── Ombi Nambari: {req.id} ──")
            print(f"  Aina ya ombi:    {aina_ombi(req.approval_type)}")
            print(f"  Aliomba:         {req.requester_name}")
            print(f"  Duka:            {shops.get(req.shop_id, req.shop_id)}")
            print(f"  Maelezo:         {req.details}")
            print(f"  Tarehe:          {req.created_at}")

            if input_yes_no("  Je, unaidhinishe ombi hili? (ndio/hapana): "):
                self.app.approval_service.approve(req.id, "Imeidhinishwa na Mkuu")
                if req.approval_type.value == "delete_product":
                    self.app.product_service.delete_product(req.target_id)
                    print("  ✓ Bidhaa imefutwa kikamilifu.")
                print("  ✓ Ombi limeidhinishwa.")
            else:
                note = input("  Andika sababu ya kukataa (si lazima): ").strip()
                self.app.approval_service.reject(req.id, note or "Imekataliwa na Mkuu")
                print("  ✓ Ombi limekataliwa.")

    def finance_report(self) -> None:
        print_header("Ripoti ya Faida na Hasara — Kampuni Yote")
        report = self.app.finance_service.get_company_summary()
        shops = self.app.shop_service.get_all()

        print(f"\n  Mapato ya mauzo:        {report.total_revenue:>15,.0f} TZS")
        print(f"  Gharama ya bidhaa:      {report.total_cost:>15,.0f} TZS")
        print(f"  Faida kabla ya mishahara:{report.total_profit:>15,.0f} TZS")
        print(f"  Jumla ya mishahara:      {report.total_salaries:>15,.0f} TZS")
        print(f"  {'─' * 45}")
        status = "FAIDA HALISI" if report.net_profit >= 0 else "HASARA HALISI"
        print(f"  {status}:          {abs(report.net_profit):>15,.0f} TZS")
        print(f"  Jumla ya mauzo:          {report.sales_count:>15}")

        print("\n  Muhtasari kwa kila duka:")
        for shop in shops:
            shop_report = self.app.finance_service.get_shop_report(shop.id)
            net = shop_report.net_profit
            label = "Faida" if net >= 0 else "Hasara"
            print(
                f"    • {shop.name}: Mauzo {shop_report.total_revenue:,.0f} TZS | "
                f"{label} {abs(net):,.0f} TZS"
            )

    def view_sales(self) -> None:
        print_header("Historia ya Mauzo — Maduka Yote")
        sales = self.app.sale_service.get_all()
        shops = {s.id: s.name for s in self.app.shop_service.get_all()}
        rows = [
            [
                s.date,
                s.product_name,
                s.quantity,
                f"{s.total_amount:,.0f}",
                s.employee_name,
                shops.get(s.shop_id, "?"),
            ]
            for s in sales[-20:]
        ]
        print_table(["Tarehe", "Bidhaa", "Idadi", "Jumla (TZS)", "Aliyeuza", "Duka"], rows)
        if len(sales) > 20:
            print(f"\n  (Inaonyesha mauzo 20 ya mwisho kati ya {len(sales)} yote)")
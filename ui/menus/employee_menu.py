from ui.helpers import print_header, print_table, input_int


class EmployeeMenu:
    def __init__(self, app, user):
        self.app = app
        self.user = user

    def run(self) -> None:
        shop = self.app.shop_service.get_by_id(self.user.shop_id)
        shop_name = shop.name if shop else "Duka Lisilojulikana"
        perms = self.user.permissions

        while True:
            print_header(f"Paneli ya Mfanyakazi — {self.user.full_name}")
            print(f"\n  Duka lako: {shop_name}")
            print(f"  Mshahara wako: {self.user.salary:,.0f} TZS kwa mwezi")

            options = []
            if perms.can_view_products:
                options.append(("1", "Angalia bidhaa zinazopatikana", self.view_products))
            if perms.can_sell and perms.can_record_sales:
                options.append(("2", "Uza bidhaa na rekodi mauzo", self.sell_product))
            if perms.can_view_sales_history:
                options.append(("3", "Angalia mauzo yangu", self.view_sales))

            options.append(("0", "Ondoka (toka kwenye akaunti)", None))

            print()
            for num, label, _ in options:
                print(f"  {num}. {label}")

            if len(options) == 1:
                print("\n  [!] Huna ruhusa ya kufanya kazi yoyote. Wasiliana na meneja wako.")

            choice = input("\n  Chagua namba: ").strip()
            if choice == "0":
                print("\n  Umeondoka kwenye akaunti ya mfanyakazi.")
                return

            action = next((fn for num, _, fn in options if num == choice), None)
            if action:
                action()
            else:
                print("  [!] Umechagua kibaya au huna ruhusa ya kufanya hivyo.")
            input("\n  Bonyeza Enter kurudi kwenye menyu...")

    def view_products(self) -> None:
        if not self.user.permissions.can_view_products:
            print("  [!] Huna ruhusa ya kuona bidhaa. Uliza meneja wako.")
            return

        print_header("Bidhaa Zinazopatikana Kwa Uuzaji")
        products = self.app.product_service.get_all(self.user.shop_id)
        available = [p for p in products if p.quantity > 0]
        if not available:
            print("  Hakuna bidhaa zenye idadi iliyopo kwa sasa.")
            return
        rows = [
            [p.id, p.name, f"{p.price:,.0f}", p.quantity]
            for p in available
        ]
        print_table(["Nambari", "Bidhaa", "Bei (TZS)", "Idadi Iliyopo"], rows)

    def sell_product(self) -> None:
        if not self.user.permissions.can_sell or not self.user.permissions.can_record_sales:
            print("  [!] Huna ruhusa ya kuuza bidhaa. Uliza meneja wako.")
            return

        print_header("Uza Bidhaa")
        products = self.app.product_service.get_all(self.user.shop_id)
        available = [p for p in products if p.quantity > 0]

        if not available:
            print("  Hakuna bidhaa zenye idadi iliyopo. Haiwezekani kuuza.")
            return

        rows = [[p.id, p.name, f"{p.price:,.0f}", p.quantity] for p in available]
        print_table(["Nambari", "Bidhaa", "Bei (TZS)", "Idadi Iliyopo"], rows)

        product_id = input("\n  Nambari ya bidhaa unayouza: ").strip()
        product = self.app.product_service.get_by_id(product_id)
        if not product or product.shop_id != self.user.shop_id:
            print("  [!] Bidhaa haijapatikana. Angalia nambari uliyoingiza.")
            return
        if product.quantity <= 0:
            print("  [!] Bidhaa hii haina idadi iliyopo. Haiwezi kuuzwa.")
            return

        quantity = input_int(f"  Idadi ya kuuza (kiwango cha juu: {product.quantity}): ")
        if quantity <= 0 or quantity > product.quantity:
            print("  [!] Idadi uliyoingiza si sahihi.")
            return

        try:
            self.app.product_service.reduce_stock(product_id, quantity)
            sale = self.app.sale_service.record_sale(
                product_id=product.id,
                product_name=product.name,
                shop_id=self.user.shop_id,
                employee_id=self.user.id,
                employee_name=self.user.full_name,
                quantity=quantity,
                unit_price=product.price,
                cost_price=product.cost_price,
            )
            print(f"\n  ✓ Mauzo yamefanikiwa!")
            print(f"  Bidhaa:     {sale.product_name} × {sale.quantity}")
            print(f"  Jumla:      {sale.total_amount:,.0f} TZS")
            print(f"  Faida:      {sale.profit:,.0f} TZS")
        except ValueError as e:
            print(f"  [!] {e}")

    def view_sales(self) -> None:
        if not self.user.permissions.can_view_sales_history:
            print("  [!] Huna ruhusa ya kuona historia ya mauzo.")
            return

        print_header("Mauzo Yangu")
        sales = [
            s
            for s in self.app.sale_service.get_all(self.user.shop_id)
            if s.employee_id == self.user.id
        ]
        if not sales:
            print("  Hujarekodi mauzo yoyote bado.")
            return
        rows = [
            [s.date, s.product_name, s.quantity, f"{s.total_amount:,.0f}"]
            for s in sales[-15:]
        ]
        print_table(["Tarehe", "Bidhaa", "Idadi", "Jumla (TZS)"], rows)
        if len(sales) > 15:
            print(f"\n  (Inaonyesha mauzo 15 ya mwisho kati ya {len(sales)})")
from models.user import UserRole
from ui.helpers import clear_screen, print_header
from ui.menus.boss_menu import BossMenu
from ui.menus.manager_menu import ManagerMenu
from ui.menus.employee_menu import EmployeeMenu
from ui.swahili import jukumu


class ConsoleUI:
    def __init__(self, app):
        self.app = app

    def run(self) -> None:
        while True:
            clear_screen()
            self._show_welcome()
            user = self._login()
            if user is None:
                if input("\n  Unataka kuondoka kwenye programu? (ndio/hapana): ").strip().lower() in (
                    "ndio", "nd",
                ):
                    print("\n  Kwaheri! Asante kwa kutumia Mfumo wa BiyeMu.\n")
                    break
                continue

            self._route_to_menu(user)

    def _show_welcome(self) -> None:
        print_header("Mfumo wa Kudhibiti Maduka ya BiyeMu")
        print("\n  Karibu! Dhibiti maduka, bidhaa, mauzo na wafanyakazi wako.")
        print("  ─────────────────────────────────────────────────────")

    def _login(self):
        print("\n  INGIA KWENYE MFUMO")
        username = input("  Jina la mtumiaji: ").strip()
        if not username:
            return None
        password = input("  Nenosiri: ").strip()

        user = self.app.auth_service.login(username, password)
        if user:
            print(f"\n  ✓ Karibu, {user.full_name}! Umeingia kama {jukumu(user.role)}.")
            input("  Bonyeza Enter kuendelea...")
            return user

        print("\n  [!] Jina la mtumiaji au nenosiri si sahihi. Jaribu tena.")
        return None

    def _route_to_menu(self, user) -> None:
        if user.role == UserRole.BOSS:
            BossMenu(self.app, user).run()
        elif user.role == UserRole.MANAGER:
            ManagerMenu(self.app, user).run()
        elif user.role == UserRole.EMPLOYEE:
            EmployeeMenu(self.app, user).run()
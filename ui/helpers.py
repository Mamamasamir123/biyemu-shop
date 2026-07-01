def clear_screen() -> None:
    import os
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title: str) -> None:
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)


def print_table(headers: list[str], rows: list[list], widths: list[int] | None = None) -> None:
    if not rows:
        print("  (Hakuna data)")
        return

    if widths is None:
        widths = []
        for i, header in enumerate(headers):
            col_values = [str(row[i]) for row in rows] + [header]
            widths.append(min(max(len(v) for v in col_values) + 2, 30))

    header_line = "".join(h.ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("-" * sum(widths))

    for row in rows:
        line = ""
        for val, w in zip(row, widths):
            text = str(val)
            if len(text) > w:
                text = text[: w - 3] + "..."
            line += text.ljust(w)
        print(line)


def input_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("  [!] Tafadhali ingiza namba halali.")


def input_int(prompt: str) -> int:
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            print("  [!] Tafadhali ingiza namba kamili.")


def input_yes_no(prompt: str) -> bool:
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("ndio", "n", "nd"):
            return True
        if answer in ("hapana", "h", "la"):
            return False
        print("  [!] Tafadhali andika 'ndio' au 'hapana'.")
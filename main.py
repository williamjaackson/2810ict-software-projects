from datetime import time

from comparison_dashboard import embed_dashboard
from src.data_ingestion import DataIngestion
from src.tariff_calculators import EnergyBillCalculator

TARIFF_FIELDS = [
    ("fixed_fee", "Fixed fee ($)", "30.00"),
    ("flat_rate", "Flat rate ($/kWh)", "0.30"),
    ("peak_rate", "Peak rate ($/kWh)", "0.45"),
    ("shoulder_rate", "Shoulder rate ($/kWh)", "0.28"),
    ("off_peak_rate", "Off-peak rate ($/kWh)", "0.18"),
    ("peak_hours", "Peak hours", "18:00-22:00"),
    ("off_peak_hours", "Off-peak hours", "22:00-07:00"),
    ("tier_limit", "Tier 1 limit (kWh)", "100"),
    ("tier_1_rate", "Tier 1 rate ($/kWh)", "0.25"),
    ("tier_2_rate", "Tier 2 rate ($/kWh)", "0.35"),
]
LABELS = {key: label for key, label, _ in TARIFF_FIELDS}
DEFAULT_FORM = {key: default for key, _, default in TARIFF_FIELDS}


def parse_tariffs(form):
    def number(key):
        try:
            return float(form[key])
        except ValueError:
            raise ValueError(f"{LABELS[key]} must be a number") from None

    def hours(key):
        try:
            start, end = form[key].split("-")
            return time.fromisoformat(start.strip()), time.fromisoformat(end.strip())
        except ValueError:
            raise ValueError(f"{LABELS[key]} must look like 18:00-22:00") from None

    return {
        "fixed_fee": number("fixed_fee"),
        "flat_rate": number("flat_rate"),
        "tou_rates": {"peak": number("peak_rate"), "shoulder": number("shoulder_rate"), "off_peak": number("off_peak_rate")},
        "tou_windows": {"peak": hours("peak_hours"), "off_peak": hours("off_peak_hours")},
        "tiers": [
            {"limit": number("tier_limit"), "rate": number("tier_1_rate")},
            {"limit": float("inf"), "rate": number("tier_2_rate")},
        ],
    }


def run_pipeline(file_path, tariffs):
    records, warnings = DataIngestion(file_path).run()
    calculator = EnergyBillCalculator(records)
    fixed_fee = tariffs["fixed_fee"]

    bills = [
        calculator.calculate_flat_rate(tariffs["flat_rate"], fixed_fee),
        calculator.calculate_tou_rate(tariffs["tou_rates"], tariffs["tou_windows"], fixed_fee),
        calculator.calculate_tiered_rate(tariffs["tiers"], fixed_fee),
    ]

    bill_results = {
        bill["model"]: {"fixed": bill["fixed_fee"], "variable": bill["energy_fee"], "total": bill["total_bill"]}
        for bill in bills
    }

    return bill_results, warnings


def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("XPower Tariff Comparison")
    dashboard = None

    controls = ttk.Frame(root, padding=8)
    controls.pack(fill="x")

    file_path = tk.StringVar()
    ttk.Label(controls, text="Usage file").grid(row=0, column=0, sticky="w")
    ttk.Entry(controls, textvariable=file_path, width=40).grid(row=0, column=1, sticky="ew")

    def browse():
        path = filedialog.askopenfilename(filetypes=[("Usage data", "*.csv *.xlsx *.xls")])
        if path:
            file_path.set(path)

    ttk.Button(controls, text="Browse...", command=browse).grid(row=0, column=2, padx=(4, 0))

    fields = {}
    for row, (key, label, default) in enumerate(TARIFF_FIELDS, 1):
        fields[key] = tk.StringVar(value=default)
        ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(controls, textvariable=fields[key]).grid(row=row, column=1, sticky="ew")

    def compare():
        nonlocal dashboard
        if not file_path.get():
            messagebox.showerror("No file selected", "Choose a usage file first.")
            return

        try:
            tariffs = parse_tariffs({key: var.get() for key, var in fields.items()})
            bill_results, warnings = run_pipeline(file_path.get(), tariffs)
        except Exception as error:
            messagebox.showerror("Could not compare tariffs", str(error))
            return

        if warnings:
            messagebox.showwarning("Some rows were skipped", f"{len(warnings)} rows skipped, e.g. {warnings[0]}")

        if dashboard is not None:
            dashboard.destroy()
        dashboard = embed_dashboard(root, bill_results)

    ttk.Button(controls, text="Compare", command=compare).grid(row=len(TARIFF_FIELDS) + 1, column=1, pady=(8, 0))
    root.mainloop()


if __name__ == "__main__":
    launch_gui()

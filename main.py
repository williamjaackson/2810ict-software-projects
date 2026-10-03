from datetime import time

from comparison_dashboard import embed_dashboard
from src.data_ingestion import DataIngestion
from src.tariff_calculators import EnergyBillCalculator

# Placeholder tariffs until the GUI lets the user enter their own
FLAT_RATE = 0.30
TIERED_TIERS = [{"limit": 100, "rate": 0.25}, {"limit": float("inf"), "rate": 0.35}]
TOU_RATES = {"peak": 0.45, "off_peak": 0.18, "shoulder": 0.28}
TOU_WINDOWS = {"peak": (time(16), time(21)), "off_peak": (time(22), time(7))}
FIXED_FEE = 30.00


def run_pipeline(file_path):
    records, warnings = DataIngestion(file_path).run()
    calculator = EnergyBillCalculator(records)

    bills = [
        calculator.calculate_flat_rate(FLAT_RATE, FIXED_FEE),
        calculator.calculate_tou_rate(TOU_RATES, TOU_WINDOWS, FIXED_FEE),
        calculator.calculate_tiered_rate(TIERED_TIERS, FIXED_FEE),
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

    def open_file():
        nonlocal dashboard
        file_path = filedialog.askopenfilename(filetypes=[("Usage data", "*.csv *.xlsx *.xls")])
        if not file_path:
            return

        try:
            bill_results, warnings = run_pipeline(file_path)
        except (FileNotFoundError, ValueError, KeyError) as error:
            messagebox.showerror("Could not process file", str(error))
            return

        if warnings:
            messagebox.showwarning("Some rows were skipped", f"{len(warnings)} rows skipped, e.g. {warnings[0]}")

        if dashboard is not None:
            dashboard.destroy()
        dashboard = embed_dashboard(root, bill_results)

    ttk.Button(root, text="Open usage file...", command=open_file).pack(pady=8)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()

"""
comparison_dashboard.py
WBS 1.4.4 - Bill Breakdown & Comparison Dashboard
Closes issue #7

This file builds the comparison dashboard for the XPower Household Tariff
Analysis System project. It takes the bill results dictionary (comes from
main.py after data_ingestion.py + the calculation engines run) and:

1. draws a bar chart comparing the total bill for each plan (Flat Rate,
   Time-of-Use, Tiered)
2. draws a stacked bar chart showing fixed vs variable charges per plan
3. figures out which plan is cheapest and how much you'd save
4. can be embedded into the Tkinter GUI (see embed_dashboard below)

expected input looks like this:

    bill_results = {
        "Flat Rate":    {"fixed": <float>, "variable": <float>, "total": <float>},
        "Time-of-Use":  {"fixed": <float>, "variable": <float>, "total": <float>},
        "Tiered":       {"fixed": <float>, "variable": <float>, "total": <float>},
    }

"""

import time

import matplotlib
matplotlib.use("Agg")  # non-GUI backend so this works without a display, switched later for the real GUI
import matplotlib.pyplot as plt

RENDER_TIME_WARNING_THRESHOLD_SECONDS = 1.5


def find_cheapest_plan(bill_results):
    """
    Goes through bill_results and finds whichever plan has the lowest
    total, and works out how much cheaper it is than the most expensive
    one. Returns a tuple like (plan_name, savings).

    Raises ValueError if the dict is empty, and KeyError if a plan is
    missing the "total" field (can't compare without it).
    """

    if not bill_results:
        raise ValueError("bill_results cannot be empty")

    
    for plan in bill_results:
        data = bill_results[plan]
        if "total" not in data:
            raise KeyError(f"Plan '{plan}' is missing a 'total' value")

    cheapest_plan = min(bill_results, key=lambda p: bill_results[p]["total"])

    most_expensive_total = 0
    for plan in bill_results:
        this_total = bill_results[plan]["total"]
        if this_total > most_expensive_total:
            most_expensive_total = this_total

    cheapest_total = bill_results[cheapest_plan]["total"]
    savings = round(most_expensive_total - cheapest_total, 2)

    return cheapest_plan, savings


def build_comparison_figure(bill_results):
    """
    Makes the matplotlib Figure for the dashboard - a total bill
    comparison chart on the left and a fixed/variable breakdown chart on
    the right. Highlights the cheapest plan in green.

    Raises ValueError on empty input, KeyError if fixed/variable/total
    are missing from any plan.
    """

    if not bill_results:
        raise ValueError("bill_results cannot be empty")

    required_fields = ["fixed", "variable", "total"]
    for plan in bill_results:
        data = bill_results[plan]
        for field in required_fields:
            if field not in data:
                raise KeyError(f"Plan '{plan}' is missing a '{field}' value")

    plans = list(bill_results.keys())
    totals = []
    fixed = []
    variable = []
    for p in plans:
        totals.append(bill_results[p]["total"])
        fixed.append(bill_results[p]["fixed"])
        variable.append(bill_results[p]["variable"])

    cheapest_plan, savings = find_cheapest_plan(bill_results)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))

    # --- left chart: total bill per plan, cheapest one is green ---
    bar_colors = []
    for p in plans:
        if p == cheapest_plan:
            bar_colors.append("#2ecc71")  # green = winner
        else:
            bar_colors.append("#3498db")  # blue = everyone else

    ax1.bar(plans, totals, color=bar_colors)
    ax1.set_title("Total Bill by Tariff Plan")
    ax1.set_ylabel("Bill ($)")
    top = max(totals) if totals else 0
    for i, v in enumerate(totals):
        ax1.text(i, v + top * 0.02, f"${v:.2f}", ha="center", fontsize=8)

    # --- right chart: fixed charge stacked under variable charge ---
    ax2.bar(plans, fixed, label="Fixed Supply Charge", color="#95a5a6")
    ax2.bar(plans, variable, bottom=fixed, label="Variable Usage Charge", color="#e67e22")
    ax2.set_title("Fixed vs Variable Cost Breakdown")
    ax2.set_ylabel("Bill ($)")
    ax2.legend(fontsize=8)

    # banner text at the top of the whole figure
    if savings > 0:
        banner_text = f"Recommended: {cheapest_plan}  —  saves ${savings:.2f} vs. the most expensive plan"
    else:
        # edge case - if everything is tied there's no "savings" to brag about
        banner_text = f"All plans cost the same (${bill_results[cheapest_plan]['total']:.2f})"
    fig.suptitle(banner_text, fontsize=10, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    return fig


def embed_dashboard(parent, bill_results):
    """
    Sticks the dashboard into a Tkinter frame so it can go inside the
    main app window. Call this from main.py once you have bill_results,
    e.g.

        from comparison_dashboard import embed_dashboard
        embed_dashboard(root, bill_results)

    Returns the ttk.Frame (already packed into parent).
    """
 
    import tkinter as tk
    from tkinter import ttk
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    start = time.perf_counter()

    cheapest_plan, savings = find_cheapest_plan(bill_results)

    frame = ttk.Frame(parent)

    banner = ttk.Label(
        frame,
        text=f"✔ Recommended: {cheapest_plan}   |   Save up to ${savings:.2f}",
        font=("Segoe UI", 12, "bold"),
        foreground="#1b7a3d",
    )
    banner.pack(pady=(8, 4))

    fig = build_comparison_figure(bill_results)
    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

    frame.pack(fill="both", expand=True)

    elapsed = time.perf_counter() - start
    print(f"[debug] embed_dashboard rendered in {elapsed:.3f}s")  # TODO: remove before submitting?
    if elapsed > RENDER_TIME_WARNING_THRESHOLD_SECONDS:
        print(f"[warning] Dashboard render took {elapsed:.2f}s "
              f"(exceeds {RENDER_TIME_WARNING_THRESHOLD_SECONDS}s target)")

    return frame


if __name__ == "__main__":
    sample_results = {
        "Flat Rate":   {"fixed": 10.00, "variable": 75.00, "total": 85.00},
        "Time-of-Use": {"fixed": 8.00,  "variable": 84.00, "total": 92.00},
        "Tiered":      {"fixed": 12.00, "variable": 98.00, "total": 110.00},
    }

    import tkinter as tk
    root = tk.Tk()
    root.title("XPower Tariff Comparison Dashboard — Preview")
    embed_dashboard(root, sample_results)
    root.mainloop()

"""contractor_check.py - flag contractors with weak liquidity.

Usage:  python contractor_check.py [contractors.csv] [flags.json]
Test:   pytest contractor_check.py
"""
import csv
import json
import sys
from collections import defaultdict

# ---- Block 1: thresholds and columns ---------------------------------------
RATIO_FLOOR = 1.2        # flag if current ratio is below this
WC_DROP_LIMIT = -0.20    # flag if working capital falls more than 20% QoQ
FIELDS = ["current_assets", "current_liabilities", "total_equity", "revenue"]


# ---- Block 2: safe math helpers ---------------------------------------------
def to_float(value):
    """Convert a CSV cell to float; blanks or junk become None."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def current_ratio(assets, liabilities):
    """Current assets / current liabilities. None if missing or liabilities == 0."""
    if assets is None or liabilities is None or liabilities == 0:
        return None
    return assets / liabilities


def working_capital(assets, liabilities):
    """Current assets - current liabilities. None if either is missing."""
    if assets is None or liabilities is None:
        return None
    return assets - liabilities


def pct_change(new, old):
    """QoQ change as a fraction. None if either side is missing or old == 0."""
    if new is None or old is None or old == 0:
        return None
    return (new - old) / abs(old)


# ---- Block 3: load and group -------------------------------------------------
def load_rows(path):
    """Read the CSV and group rows by contractor, sorted by quarter."""
    by_contractor = defaultdict(list)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            record = {"quarter": row["quarter"]}
            record.update({k: to_float(row.get(k)) for k in FIELDS})
            by_contractor[row["contractor"]].append(record)
    for rows in by_contractor.values():
        rows.sort(key=lambda r: r["quarter"])
    return by_contractor


# ---- Block 4: compute metrics and flags --------------------------------------
def rnd(x, places=3):
    return None if x is None else round(x, places)


def analyze(by_contractor):
    """Add metrics to every quarter; return (flags, data_issues)."""
    flags, issues = [], []
    for name, rows in by_contractor.items():
        prev = None
        for r in rows:
            ca, cl = r["current_assets"], r["current_liabilities"]
            r["working_capital"] = working_capital(ca, cl)
            r["current_ratio"] = current_ratio(ca, cl)
            r["wc_change"] = pct_change(r["working_capital"], prev["working_capital"]) if prev else None
            r["ratio_change"] = pct_change(r["current_ratio"], prev["current_ratio"]) if prev else None
            prev = r

            if ca is None or cl is None:
                issues.append({"contractor": name, "quarter": r["quarter"],
                               "issue": "missing current assets or liabilities"})
            elif cl == 0:
                issues.append({"contractor": name, "quarter": r["quarter"],
                               "issue": "current liabilities are zero; ratio undefined"})

            reasons = []
            if r["current_ratio"] is not None and r["current_ratio"] < RATIO_FLOOR:
                reasons.append(f"current ratio {r['current_ratio']:.2f} below {RATIO_FLOOR}")
            if r["wc_change"] is not None and r["wc_change"] < WC_DROP_LIMIT:
                reasons.append(f"working capital down {abs(r['wc_change']):.1%} QoQ")
            if reasons:
                flags.append({
                    "contractor": name,
                    "quarter": r["quarter"],
                    "reasons": reasons,
                    "current_ratio": rnd(r["current_ratio"]),
                    "working_capital": rnd(r["working_capital"], 1),
                    "wc_change_pct": rnd(r["wc_change"] * 100 if r["wc_change"] is not None else None, 1),
                    "ratio_change_pct": rnd(r["ratio_change"] * 100 if r["ratio_change"] is not None else None, 1),
                })
    return flags, issues


# ---- Block 5: entry point -----------------------------------------------------
def main(csv_path="contractors.csv", out_path="flags.json"):
    flags, issues = analyze(load_rows(csv_path))
    with open(out_path, "w") as f:
        json.dump({"flags": flags, "data_issues": issues}, f, indent=2)
    print(f"{len(flags)} flag(s), {len(issues)} data issue(s) -> {out_path}")
    for fl in flags:
        print(f"  {fl['contractor']} {fl['quarter']}: {'; '.join(fl['reasons'])}")


# ---- Block 6: pytest test -----------------------------------------------------
def test_current_ratio():
    assert current_ratio(150, 100) == 1.5
    assert current_ratio(100, 0) is None      # zero denominator
    assert current_ratio(None, 100) is None   # missing value


if __name__ == "__main__":
    main(*sys.argv[1:3])

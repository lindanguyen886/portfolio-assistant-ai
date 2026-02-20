# agents/allocation_agent.py

from agents.data_loader import load_holdings

# ==============================
# TARGET ROBO ALLOCATION (B)
# ==============================

TARGET_ALLOCATION = {
    "cash": 0.20,
    "bonds": 0.25,
    "canada_equity": 0.35,
    "us_equity": 0.10,
    "global_equity": 0.10
}


# ==============================
# TICKER → ASSET CLASS MAP
# Expand anytime
# ==============================

ASSET_CLASS_MAP = {

    # Cash / HISA ETFs
    "SAFE.TO": "cash",
    "CASH.TO": "cash",

    # Bonds
    "ZAG.TO": "bonds",
    "VAB.TO": "bonds",
    "XBB.TO": "bonds",

    # Canada equity
    "XIU.TO": "canada_equity",
    "VCN.TO": "canada_equity",
    "BCE.TO": "canada_equity",
    "ENB.TO": "canada_equity",
    "TD.TO": "canada_equity",
    "BNS.TO": "canada_equity",
    "FTS.TO": "canada_equity",

    # US equity
    "VTI": "us_equity",
    "XUU.TO": "us_equity",

    # Global equity
    "XAW.TO": "global_equity",
    "XEQT.TO": "global_equity",
    "VGRO.TO": "global_equity",
    "VBAL.TO": "global_equity"
}


# ==============================
# CLASSIFY HOLDINGS
# ==============================

def classify_ticker(ticker):

    if isinstance(ticker, dict):
        ticker = ticker.get("ticker")

    return ASSET_CLASS_MAP.get(ticker, "unknown")


# ==============================
# CALCULATE CURRENT ALLOCATION
# Equal-weight for now (later: use dollar value)
# ==============================

def calculate_allocation(holdings):

    if not holdings:
        return {}

    allocation = {
        "cash": 0,
        "bonds": 0,
        "canada_equity": 0,
        "us_equity": 0,
        "global_equity": 0,
        "unknown": 0
    }

    weight = 1 / len(holdings)

    for item in holdings:

        # support both formats
        if isinstance(item, dict):
            ticker = item.get("ticker")
            shares = item.get("shares", 1)
        else:
            ticker = item
            shares = 1

        asset_class = classify_ticker(ticker)
        allocation[asset_class] += weight

    return allocation


# ==============================
# COMPARE VS TARGET
# ==============================

def detect_drift(current):

    drift = {}

    for asset in TARGET_ALLOCATION:
        target = TARGET_ALLOCATION[asset]
        actual = current.get(asset, 0)

        diff = actual - target

        drift[asset] = diff

    return drift


# ==============================
# GENERATE REBALANCE SUGGESTIONS
# ==============================

def rebalance_suggestions(drift):

    suggestions = []

    for asset, diff in drift.items():

        if diff > 0.05:
            suggestions.append(f"Reduce exposure to {asset} (overweight by {round(diff*100)}%)")

        elif diff < -0.05:
            suggestions.append(f"Add exposure to {asset} (underweight by {round(abs(diff)*100)}%)")

    return suggestions


# ==============================
# MAIN ENGINE
# ==============================

def analyze_portfolio_allocation():

    holdings = load_holdings()

    if not holdings:
        return "No holdings available."

    current = calculate_allocation(holdings)
    drift = detect_drift(current)
    suggestions = rebalance_suggestions(drift)

    report = "\n📊 PORTFOLIO ALLOCATION ANALYSIS\n\n"

    report += "Current allocation:\n"

    for asset, value in current.items():
        report += f"- {asset}: {round(value*100)}%\n"

    report += "\nDrift vs target:\n"

    for asset, value in drift.items():
        report += f"- {asset}: {round(value*100)}%\n"

    report += "\nRebalance suggestions:\n"

    if suggestions:
        for s in suggestions:
            report += f"- {s}\n"
    else:
        report += "- Portfolio aligned with target allocation.\n"

    return report

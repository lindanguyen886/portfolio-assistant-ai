from agents.data_loader import load_holdings
from agents.allocation_agent import classify_ticker, TARGET_ALLOCATION


# Use one canonical target allocation shared across agents.
TARGET = TARGET_ALLOCATION


def analyze_rebalance():

    holdings = load_holdings()

    if not holdings:
        return "No holdings data."

    # -------------------------
    # 1) Calculate current allocation
    # -------------------------
    allocation = {
        "cash": 0,
        "bonds": 0,
        "canada_equity": 0,
        "us_equity": 0,
        "global_equity": 0,
        "unknown": 0
    }

    total_positions = len(holdings)

    for h in holdings:
        ticker = h.get("ticker") if isinstance(h, dict) else h
        asset_class = classify_ticker(ticker)

        if asset_class in allocation:
            allocation[asset_class] += 1
        else:
            allocation["unknown"] += 1

    for k in allocation:
        allocation[k] = round(allocation[k] / total_positions, 2)

    # -------------------------
    # 2) Drift vs target
    # -------------------------
    drift = {}

    for k in TARGET:
        drift[k] = round(allocation.get(k, 0) - TARGET[k], 2)

    # -------------------------
    # 3) Build actions
    # -------------------------
    actions = []

    for asset, value in drift.items():

        if value > 0.10:
            actions.append(f"Reduce exposure to {asset}")

        elif value < -0.10:
            actions.append(f"Add exposure to {asset}")

    if allocation.get("unknown", 0) > 0:
        actions.append("Classify unknown tickers to improve rebalance accuracy")

    # -------------------------
    # 4) Return output
    # -------------------------
    return {
        "allocation": allocation,
        "drift": drift,
        "actions": actions
    }

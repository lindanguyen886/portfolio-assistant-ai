import json
import os
from config import HOLDINGS_FILE, WATCHLIST_FILE

DATA_PATH = "data"


def load_holdings():
    if not os.path.exists(HOLDINGS_FILE):
        return []

    with open(HOLDINGS_FILE, "r") as f:
        data = json.load(f)

    # Support both legacy {"holdings": [...]} and plain list formats.
    if isinstance(data, dict):
        return data.get("holdings", [])

    return data


def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        return []

    with open(WATCHLIST_FILE, "r") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return data.get("watchlist", [])

    return data


def save_holdings(holdings):
    # Standardize on plain list to match current holdings.json structure.
    with open(HOLDINGS_FILE, "w") as f:
        json.dump(holdings, f, indent=4)


def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump({"watchlist": watchlist}, f, indent=4)

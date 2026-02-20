from agents.data_loader import load_watchlist, save_watchlist


# ==============================
# HELPER — normalize ticker
# ==============================

def normalize_ticker(ticker):
    """
    Ensure ticker format consistency:
    safe.to → SAFE.TO
    xiU.to → XIU.TO
    """
    if not ticker:
        return None

    return ticker.upper().strip()


# ==============================
# SAFE LOAD
# ==============================

def _safe_watchlist():
    """
    Ensure watchlist always returns a list
    even if JSON structure changes
    """

    watchlist = load_watchlist()

    # Case 1: already list
    if isinstance(watchlist, list):
        return watchlist

    # Case 2: saved as {"watchlist": [...]}
    if isinstance(watchlist, dict):
        return watchlist.get("watchlist", [])

    return []


# ==============================
# ADD TICKERS
# ==============================

def add_to_watchlist(tickers):
    """
    Add tickers (ETF or stock) to watchlist safely
    """

    watchlist = _safe_watchlist()

    for ticker in tickers:

        ticker = normalize_ticker(ticker)

        # skip empty or invalid values
        if not ticker:
            continue

        if ticker not in watchlist:
            watchlist.append(ticker)

    save_watchlist(watchlist)

    return watchlist


# ==============================
# REMOVE TICKER
# ==============================

def remove_from_watchlist(ticker):

    watchlist = _safe_watchlist()

    ticker = normalize_ticker(ticker)

    if ticker in watchlist:
        watchlist.remove(ticker)

    save_watchlist(watchlist)

    return watchlist


# ==============================
# VIEW WATCHLIST
# ==============================

def get_watchlist():

    return _safe_watchlist()
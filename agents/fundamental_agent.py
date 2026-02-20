"""
Fundamental Analysis Agent
Evaluates company/ETF strength using basic financial logic.
Designed for conservative–moderate portfolio decisions.
"""

def analyze_fundamental(ticker):
    """
    Returns a simplified fundamental assessment.

    Output format:
    {
        "score": int (1–10),
        "summary": str,
        "signal": "bullish" | "neutral" | "bearish"
    }
    """

    ticker = str(ticker or "").upper().strip()
    base = ticker.replace(".TO", "")

    # --- ETF logic ---
    etf_defensive = ["SAFE", "ZAG", "XBB", "VAB"]
    etf_equity = ["XIU", "XAW", "VGG", "ZRE", "VCN", "VGRO", "VBAL"]

    if base in etf_defensive:
        return {
            "score": 8,
            "summary": "Defensive ETF with stable yield and low volatility.",
            "signal": "bullish"
        }

    if base in etf_equity:
        return {
            "score": 7,
            "summary": "Broad diversified equity exposure with solid fundamentals.",
            "signal": "bullish"
        }

    # --- Stock logic (basic rule-based for now) ---
    defensive_stocks = ["BCE", "MRU", "FTS", "ENB", "TD", "BNS"]
    growth_stocks = ["NVDA", "MSFT", "AAPL"]

    if base in defensive_stocks:
        return {
            "score": 8,
            "summary": "Defensive sector company with stable earnings and dividends.",
            "signal": "bullish"
        }

    if base in growth_stocks:
        return {
            "score": 7,
            "summary": "Strong growth company with solid fundamentals, but valuation sensitive.",
            "signal": "neutral"
        }

    # --- Unknown ticker fallback ---
    return {
        "score": 6,
        "summary": "No detailed financial data available. Assume neutral fundamentals.",
        "signal": "neutral"
    }

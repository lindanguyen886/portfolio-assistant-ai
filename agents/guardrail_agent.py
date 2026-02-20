from agents.allocation_agent import calculate_allocation, detect_drift, classify_ticker


# Core preference set from your stated target strategy.
CORE_TARGET_TICKERS = {"SAFE.TO", "VCN.TO", "XBB.TO", "ENB.TO", "TD.TO"}


def _normalize_ticker(ticker):
    if not ticker:
        return None
    ticker = str(ticker).upper().strip()
    if "." not in ticker and classify_ticker(f"{ticker}.TO") != "unknown":
        return f"{ticker}.TO"
    return ticker


def _asset_class(ticker):
    ticker = _normalize_ticker(ticker)
    if not ticker:
        return "unknown"
    return classify_ticker(ticker)


def _score_ticker(ticker, drift, mode="strict"):
    ticker = _normalize_ticker(ticker)
    asset = _asset_class(ticker)

    if asset == "unknown":
        return None, "unknown asset class"

    # Positive drift = overweight; negative drift = underweight.
    asset_drift = drift.get(asset, 0)

    if mode == "strict":
        # Strict rejection: do not add to clearly overweight sleeves.
        if asset_drift > 0.05:
            return None, f"overweight sleeve ({asset}, drift={round(asset_drift*100,1)}%)"

    score = 0.0

    # Strongly prefer filling underweights.
    if asset_drift < 0:
        score += abs(asset_drift) * 100.0
    elif mode == "balanced" and asset_drift > 0:
        # Soft penalty in balanced mode.
        score -= asset_drift * 40.0

    # Preference for your core strategy sleeves.
    if asset in {"bonds", "canada_equity", "cash"}:
        score += 3.0

    # Explicit bonus for your target tickers.
    if ticker in CORE_TARGET_TICKERS:
        score += 7.0

    if mode == "balanced" and score <= 0:
        return None, f"low alignment score ({round(score,2)}) in balanced mode"

    return round(score, 3), None


def apply_target_guardrails(recommendations, holdings, mode="strict"):
    """
    Strict guardrail filter and re-ranker for recommendation candidates.
    """
    if not isinstance(recommendations, dict):
        return recommendations

    mode = str(mode or "strict").lower().strip()
    if mode not in {"strict", "balanced", "off"}:
        mode = "strict"

    if mode == "off":
        out = dict(recommendations)
        out["guardrail"] = {
            "mode": "off",
            "current_allocation": calculate_allocation(holdings) if holdings else {},
            "drift": detect_drift(calculate_allocation(holdings)) if holdings else {},
            "ranked": [],
            "dropped": [],
            "note": "Guardrail disabled",
        }
        return out

    if not holdings:
        current = {}
    else:
        current = calculate_allocation(holdings)
    drift = detect_drift(current) if current else {}

    etfs = recommendations.get("etfs", []) or []
    stocks = recommendations.get("stocks", []) or []

    ranked = []
    dropped = []
    seen = set()

    for raw in etfs + stocks:
        ticker = _normalize_ticker(raw)
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)

        score, reason = _score_ticker(ticker, drift, mode=mode)
        if score is None:
            dropped.append({"ticker": ticker, "reason": reason})
            continue

        ranked.append(
            {
                "ticker": ticker,
                "score": score,
                "asset_class": _asset_class(ticker),
                "source": "etf" if raw in etfs else "stock",
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)

    filtered_etfs = [x["ticker"] for x in ranked if x["source"] == "etf"]
    filtered_stocks = [x["ticker"] for x in ranked if x["source"] == "stock"]

    out = dict(recommendations)
    out["etfs"] = filtered_etfs
    out["stocks"] = filtered_stocks
    out["guardrail"] = {
        "mode": mode,
        "current_allocation": current,
        "drift": drift,
        "ranked": ranked,
        "dropped": dropped,
    }
    return out

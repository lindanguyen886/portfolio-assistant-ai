from agents.allocation_agent import classify_ticker
from agents.price_agent import get_price
from agents.data_loader import load_holdings


def _normalize_ticker(item):
    ticker = item.get("ticker") if isinstance(item, dict) else item
    if not ticker:
        return None
    return str(ticker).upper().strip()


def _canonical_ticker(ticker):
    ticker = _normalize_ticker(ticker)
    if not ticker:
        return None

    if classify_ticker(ticker) != "unknown":
        return ticker

    # Support bare Canadian symbols: ZAG -> ZAG.TO
    if "." not in ticker and classify_ticker(f"{ticker}.TO") != "unknown":
        return f"{ticker}.TO"

    return ticker


def _ticker_asset_class(ticker):
    ticker = _canonical_ticker(ticker)
    if not ticker:
        return "unknown"

    asset_class = classify_ticker(ticker)
    if asset_class != "unknown":
        return asset_class

    # Support bare Canadian symbols in watchlist/recommendations: ZAG -> ZAG.TO
    if "." not in ticker:
        asset_class = classify_ticker(f"{ticker}.TO")
        if asset_class != "unknown":
            return asset_class

    return "unknown"


def _watch_action_weight(watch_decision):
    action = str(watch_decision or "").lower()
    if "consider entry" in action:
        return 3.0
    if "watch breakout" in action:
        return 2.0
    if "monitor" in action:
        return 1.0
    if "wait" in action:
        return -1.0
    return 0.0


def _holding_decision_weight(holding_decision):
    action = str(holding_decision or "").upper()
    if action == "ADD":
        return 4.0
    if action == "HOLD":
        return 1.0
    if action in {"TRIM", "AVOID", "WAIT"}:
        return -4.0
    return 0.0


def _max_positions(cash):
    if cash >= 2500:
        return 3
    if cash >= 1000:
        return 2
    return 1


def _score_candidates(underweights, recommendations, watchlist, holdings_decisions, watchlist_results):
    rec_list = []
    if isinstance(recommendations, dict):
        rec_list = recommendations.get("etfs", []) + recommendations.get("stocks", [])
    rec_set = {_canonical_ticker(t) for t in rec_list if _canonical_ticker(t)}
    watch_set = {_canonical_ticker(t) for t in (watchlist or []) if _canonical_ticker(t)}

    holding_decisions_map = {}
    for ticker, decision in (holdings_decisions or {}).items():
        holding_decisions_map[_canonical_ticker(ticker)] = decision

    watch_decisions_map = {}
    for ticker, data in (watchlist_results or {}).items():
        c_ticker = _canonical_ticker(ticker)
        decision = data.get("decision", {}) if isinstance(data, dict) else {}
        watch_decisions_map[c_ticker] = decision.get("decision", "")

    existing_holdings = [_canonical_ticker(h) for h in load_holdings()]
    existing_holdings = [t for t in existing_holdings if t]

    candidates = set(existing_holdings) | rec_set | watch_set | set(holding_decisions_map.keys()) | set(watch_decisions_map.keys())

    scored = []

    for ticker in candidates:
        asset_class = _ticker_asset_class(ticker)
        underweight = underweights.get(asset_class, 0)
        if underweight <= 0:
            continue

        score = 0.0
        reasons = []

        rebalance_points = underweight * 20.0
        score += rebalance_points
        reasons.append(f"rebalance({asset_class}) +{round(rebalance_points,2)}")

        if ticker in rec_set:
            score += 3.0
            reasons.append("recommended +3.0")

        if ticker in watch_set:
            score += 2.0
            reasons.append("watchlist +2.0")

        holding_points = _holding_decision_weight(holding_decisions_map.get(ticker))
        if holding_points != 0:
            score += holding_points
            reasons.append(f"holdings_decision {holding_decisions_map.get(ticker)} {holding_points:+.1f}")

        watch_points = _watch_action_weight(watch_decisions_map.get(ticker))
        if watch_points != 0:
            score += watch_points
            reasons.append(f"watch_action {watch_decisions_map.get(ticker)} {watch_points:+.1f}")

        if score > 0:
            scored.append(
                {
                    "ticker": ticker,
                    "asset_class": asset_class,
                    "score": round(score, 3),
                    "reasons": reasons,
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _build_basket(cash, ranked):
    if not ranked:
        return []

    k = min(_max_positions(cash), len(ranked))
    selected = ranked[:k]
    total_score = sum(item["score"] for item in selected)

    basket = []
    spent = 0.0

    for item in selected:
        ticker = item["ticker"]
        price = get_price(ticker)
        unit_price = price if price and price > 0 else 50
        target_cash = cash * (item["score"] / total_score) if total_score > 0 else 0
        shares = int(target_cash / unit_price)

        basket.append(
            {
                "ticker": ticker,
                "asset_class": item["asset_class"],
                "score": item["score"],
                "unit_price": unit_price,
                "shares": max(0, shares),
                "reasons": item["reasons"],
            }
        )
        spent += max(0, shares) * unit_price

    # Use leftover cash to add single shares by score priority.
    remaining = cash - spent
    while True:
        affordable = [b for b in basket if b["unit_price"] <= remaining]
        if not affordable:
            break
        best = max(affordable, key=lambda x: x["score"])
        best["shares"] += 1
        remaining -= best["unit_price"]

    basket = [b for b in basket if b["shares"] > 0]
    return basket


def deploy_capital(
    cash,
    rebalance,
    recommendations=None,
    watchlist=None,
    holdings_decisions=None,
    watchlist_results=None,
):

    if cash <= 0:
        return {"action": "WAIT", "reason": "No available cash to deploy"}

    drift = rebalance.get("drift", {}) if isinstance(rebalance, dict) else {}
    if not drift:
        return {"action": "WAIT", "reason": "No allocation drift data"}

    underweights = {asset: abs(value) for asset, value in drift.items() if value < 0}
    if not underweights:
        return {
            "action": "WAIT",
            "reason": "No underweight assets from rebalance analysis",
        }

    ranked = _score_candidates(
        underweights,
        recommendations,
        watchlist,
        holdings_decisions,
        watchlist_results,
    )
    if not ranked:
        return {
            "action": "WAIT",
            "reason": "No positive-scoring ticker matched rebalance + holdings/watchlist/recommendation criteria",
        }

    basket = _build_basket(cash, ranked)
    if not basket:
        min_price = min((b["unit_price"] for b in _build_basket(10**9, ranked)), default=0)
        return {
            "action": "WAIT",
            "reason": f"Insufficient cash to buy any selected ticker (min estimated price {round(min_price,2)})",
        }

    if len(basket) == 1:
        pick = basket[0]
        return {
            "action": "BUY",
            "ticker": pick["ticker"],
            "shares": pick["shares"],
            "reason": (
                f"Top matrix score for {pick['asset_class']} with multi-factor alignment: "
                + "; ".join(pick["reasons"])
            ),
            "matrix_top": ranked[:5],
        }

    return {
        "action": "BUY_BASKET",
        "positions": [
            {
                "ticker": b["ticker"],
                "shares": b["shares"],
                "asset_class": b["asset_class"],
            }
            for b in basket
        ],
        "reason": "Basket built from multi-factor matrix: rebalance underweights + holdings decisions + watchlist signals + today's recommendations",
        "matrix_top": ranked[:5],
    }

"""
Portfolio Assistant — Main Controller

Daily flow:
1) Run portfolio signals
2) Ask if user wants new ETF/stock ideas
3) If yes → generate recommendations
4) Ask to add to watchlist
5) Ask to add to holdings
"""
from datetime import date

from agents.signal_agent import generate_signal
from agents.data_loader import load_holdings, load_watchlist, save_holdings
from agents.watchlist_agent import add_to_watchlist
from agents.recommendation_agent import recommend_portfolio
from agents.guardrail_agent import apply_target_guardrails
from agents.allocation_agent import analyze_portfolio_allocation
from agents.decision_agent import generate_decision
from agents.decision_agent import generate_watch_decision
from agents.rebalance_agent import analyze_rebalance
from agents.capital_agent import deploy_capital
from agents.price_agent import get_price
from agents.portfolio_summary_agent import portfolio_summary
from config import assert_openai_api_key


def _format_technical(technical):
    if not isinstance(technical, dict):
        return str(technical)

    return (
        f"Trend={technical.get('trend', 'N/A')}, "
        f"Momentum={technical.get('momentum', 'N/A')}, "
        f"RSI={technical.get('rsi', 'N/A')}, "
        f"MACD={technical.get('macd', 'N/A')} vs {technical.get('macd_signal', 'N/A')}, "
        f"Entry={technical.get('entry_timing', 'N/A')}, "
        f"Signal={technical.get('signal', 'N/A')}"
    )


def _format_fundamental(fundamental):
    if not isinstance(fundamental, dict):
        return str(fundamental)

    return (
        f"Score={fundamental.get('score', 'N/A')}, "
        f"Signal={fundamental.get('signal', 'N/A')}, "
        f"Summary={fundamental.get('summary', 'N/A')}"
    )


def _parse_sentiment(sentiment):
    text = str(sentiment).strip()
    if not text:
        return "N/A", "N/A", ""

    mood = "N/A"
    confidence = "N/A"
    reasoning = ""

    for line in text.splitlines():
        clean = line.strip()
        lower = clean.lower()
        if lower.startswith("sentiment:"):
            mood = clean.split(":", 1)[1].strip()
        elif lower.startswith("confidence:"):
            confidence = clean.split(":", 1)[1].strip()
        elif lower.startswith("reasoning:"):
            reasoning = clean.split(":", 1)[1].strip()

    if mood == "N/A" and "\n" not in text:
        mood = text

    return mood, confidence, reasoning


def _pct(value):
    if value is None:
        return "N/A"
    return f"{round(value * 100, 1)}%"


def _format_rebalance(rebalance):
    if not isinstance(rebalance, dict):
        return str(rebalance)

    lines = ["♻️ REBALANCE ANALYSIS", ""]

    allocation = rebalance.get("allocation", {})
    lines.append("Current allocation:")
    for asset, value in allocation.items():
        lines.append(f"- {asset}: {_pct(value)}")

    drift = rebalance.get("drift", {})
    lines.append("")
    lines.append("Drift vs target:")
    for asset, value in drift.items():
        lines.append(f"- {asset}: {_pct(value)}")

    actions = rebalance.get("actions", [])
    lines.append("")
    lines.append("Actions:")
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- No rebalance actions needed.")

    return "\n".join(lines)


def _build_current_holdings_context():
    holdings = load_holdings()
    context = {}
    for item in holdings:
        if isinstance(item, dict):
            ticker = str(item.get("ticker", "")).upper().strip()
            shares = item.get("shares", 0)
            buy_price = item.get("buy_price", 0)
            if ticker:
                context[ticker] = f"shares={shares}, avg_cost={buy_price}"
        else:
            ticker = str(item).upper().strip()
            if ticker:
                context[ticker] = "existing position"
    return context


def _resolve_watchlist_key(selected, available_keys):
    selected = selected.upper().strip()
    if selected in available_keys:
        return selected

    if selected.endswith(".TO"):
        alt = selected.replace(".TO", "")
        if alt in available_keys:
            return alt
    else:
        alt = f"{selected}.TO"
        if alt in available_keys:
            return alt

    return None


def _run_watchlist_detail_prompt(watchlist_results):
    if not watchlist_results:
        return

    normalized = list(watchlist_results.keys())
    if not normalized:
        return

    answer = input(
        "\nDo you want detailed analysis for any watchlist stock/ETF? (y/n): "
    ).strip().lower()

    if answer != "y":
        return

    print("Watchlist tickers:", ", ".join(normalized))
    selected = input("Enter ticker (example: BCE.TO): ").strip().upper()

    resolved = _resolve_watchlist_key(selected, set(normalized))
    if not resolved:
        print("Ticker not found in current watchlist. Skipping detailed view.")
        return

    detail = watchlist_results[resolved]["result"]
    decision = watchlist_results[resolved]["decision"]
    sentiment_value, sentiment_confidence, sentiment_reasoning = _parse_sentiment(
        detail.get("sentiment", "N/A")
    )

    print(f"\n🔎 DETAILED WATCHLIST VIEW — {resolved}")
    print("Signal:", detail.get("signal", "N/A"))
    print("Technical:", _format_technical(detail.get("technical", {})))
    print("Fundamental:", _format_fundamental(detail.get("fundamental", {})))
    print(f"Sentiment: {sentiment_value} (Confidence: {sentiment_confidence})")
    if sentiment_reasoning:
        print("Sentiment reason:", sentiment_reasoning)
    print("Watch action:", decision["decision"])
    print("Reason:", ", ".join(decision["reasoning"]))


def _choose_guardrail_mode_cli():
    raw = input(
        "\nSelect guardrail mode [strict/balanced/off] (default: strict): "
    ).strip().lower()
    if raw in {"strict", "balanced", "off"}:
        return raw
    return "strict"


# ==============================
# DAILY SIGNAL ENGINE
# ==============================

def run_daily_signals():

    print("\n📊 Running daily portfolio signals...\n")

    holdings = load_holdings()
    watchlist = load_watchlist()
    holdings_decisions = {}

    # ---- HOLDINGS ----
    print("------ CURRENT HOLDINGS ------")

    if not holdings:
        print("No holdings found.\n")
    else:
        for item in holdings:

            # support both old + new formats
            ticker = item["ticker"] if isinstance(item, dict) else item

            result = generate_signal(ticker)
            sentiment_value, sentiment_confidence, sentiment_reasoning = _parse_sentiment(
                result["sentiment"]
            )

            print(f"\n{ticker}")
            print(f"Signal (market): {result['signal']}")
            print("Technical:", _format_technical(result["technical"]))
            print("Fundamental:", _format_fundamental(result["fundamental"]))
            print(f"Sentiment: {sentiment_value} (Confidence: {sentiment_confidence})")
            if sentiment_reasoning:
                print("Sentiment reason:", sentiment_reasoning)

            # 2️⃣ run decision engine
            decision = generate_decision(ticker)
            holdings_decisions[ticker.upper().strip()] = decision["decision"]

            print("Position Decision (holding):", decision["decision"])
            print("Reason:", ", ".join(decision["reasoning"]))

    # ---- WATCHLIST ----
    print("\n------ WATCHLIST ------")
    watchlist_results = {}

    if not watchlist:
        print("Watchlist empty.\n")
    else:
        for item in watchlist:

            ticker = item["ticker"] if isinstance(item, dict) else item

            ticker = ticker.upper().strip()
            result = generate_signal(ticker)

            decision = generate_watch_decision(ticker, result)
            watchlist_results[ticker] = {
                "result": result,
                "decision": decision,
            }
            sentiment_value, _, _ = _parse_sentiment(result.get("sentiment", "N/A"))

            print(f"\n{ticker}")
            print("Trend:", result.get("trend", "N/A"))
            print("Sentiment:", sentiment_value)
            print("Watch action:", decision["decision"])
            print("Reason:", ", ".join(decision["reasoning"]))

    _run_watchlist_detail_prompt(watchlist_results)
    return {
        "holdings_decisions": holdings_decisions,
        "watchlist_results": watchlist_results,
    }


# ==============================
# RECOMMENDATION MODE
# ==============================

def run_recommendation_if_requested():

    choice = input("\n🧠 Do you want new ETF/stock recommendations today? (y/n): ").lower()

    if choice != "y":
        print("Skipping recommendations today.\n")
        return None

    print("\n🧠 Generating portfolio recommendations...\n")

    current_holdings = _build_current_holdings_context()

    investor_profile = {
        "horizon": "short to medium",
        "risk": "conservative to moderate",
        "style": "balanced ETF + stocks"
    }

    capital_level = "small (<5k)"

    recommendations = recommend_portfolio(
        current_holdings,
        investor_profile,
        capital_level
    )
    guardrail_mode = _choose_guardrail_mode_cli()
    recommendations = apply_target_guardrails(
        recommendations,
        load_holdings(),
        mode=guardrail_mode,
    )

    # display report
    if isinstance(recommendations, dict):
        print(recommendations.get("report", "No report generated."))
        recommended_etfs = recommendations.get("etfs", [])
        recommended_stocks = recommendations.get("stocks", [])

        guardrail = recommendations.get("guardrail", {})
        if guardrail:
            print(f"\n🛡️ Target Guardrail ({guardrail.get('mode', 'strict')} mode)")
            ranked = guardrail.get("ranked", [])
            dropped = guardrail.get("dropped", [])
            if ranked:
                print("Ranked candidates:")
                for item in ranked:
                    print(
                        f"- {item['ticker']} | {item['asset_class']} | score={item['score']}"
                    )
            else:
                print("- No candidates passed strict guardrails.")

            if dropped:
                print("Rejected candidates:")
                for item in dropped:
                    print(f"- {item['ticker']}: {item['reason']}")
    else:
        print(recommendations)
        return

    # --------------------------
    # WATCHLIST APPROVAL
    # --------------------------

    approved_watchlist = []
    existing_holdings = load_holdings()
    existing_watchlist = load_watchlist()

    holdings_set = set()
    for item in existing_holdings:
        ticker = item.get("ticker") if isinstance(item, dict) else item
        if ticker:
            holdings_set.add(str(ticker).upper().strip())

    watchlist_set = set()
    for item in existing_watchlist:
        ticker = item.get("ticker") if isinstance(item, dict) else item
        if ticker:
            watchlist_set.add(str(ticker).upper().strip())

    print("\n📊 Add recommendations to WATCHLIST")

    seen = set()
    for ticker in recommended_etfs + recommended_stocks:
        ticker = str(ticker).upper().strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)

        if ticker in holdings_set:
            print(f"Skip {ticker}: already in holdings.")
            continue

        if ticker in watchlist_set:
            print(f"Skip {ticker}: already in watchlist.")
            continue

        choice = input(f"Add {ticker} to watchlist? (y/n): ").lower()
        if choice == "y":
            approved_watchlist.append(ticker)

    # --------------------------
    # HOLDINGS APPROVAL
    # --------------------------

    approved_holdings = []

    print("\n📈 Add recommendations to HOLDINGS")

    for ticker in approved_watchlist:
        choice = input(f"Buy and add {ticker} to holdings now? (y/n): ").lower()
        if choice == "y":
            approved_holdings.append(ticker)

    # --------------------------
    # SAVE
    # --------------------------

    if approved_watchlist:
        updated_watchlist = add_to_watchlist(approved_watchlist)
        print("\n✅ Watchlist updated:", updated_watchlist)

    if approved_holdings:
        existing_holdings = load_holdings()
        normalized_existing = []
        existing_tickers = set()

        for item in existing_holdings:
            if isinstance(item, dict):
                ticker = str(item.get("ticker", "")).upper().strip()
                if ticker:
                    existing_tickers.add(ticker)
                normalized_existing.append(item)
            else:
                ticker = str(item).upper().strip()
                if ticker:
                    existing_tickers.add(ticker)
                    normalized_existing.append({
                        "ticker": ticker,
                        "shares": 1,
                        "buy_price": get_price(ticker) or 0,
                        "buy_date": str(date.today()),
                    })

        new_positions = []
        for ticker in approved_holdings:
            ticker = str(ticker).upper().strip()
            if ticker in existing_tickers:
                continue
            new_positions.append({
                "ticker": ticker,
                "shares": 1,
                "buy_price": get_price(ticker) or 0,
                "buy_date": str(date.today()),
            })

        updated = normalized_existing + new_positions
        save_holdings(updated)
        print("📈 Holdings updated:", [p["ticker"] for p in new_positions] or "No new tickers added.")
    return recommendations

# ==============================
# CAPITAL EXECUTION LAYER
# ==============================

def run_capital_deployment(rebalance, recommendations, signals_context=None):

    print("\n💰 CAPITAL DEPLOYMENT")

    try:
        available_cash = float(input("Enter available cash to deploy: "))
    except:
        print("Invalid input — skipping capital deployment.")
        return

    watchlist = load_watchlist()
    signals_context = signals_context or {}
    decision = deploy_capital(
        available_cash,
        rebalance,
        recommendations,
        watchlist,
        signals_context.get("holdings_decisions"),
        signals_context.get("watchlist_results"),
    )

    print("\nAction:", decision["action"])

    if decision["action"] == "BUY":
        print("Ticker:", decision["ticker"])
        print("Shares:", decision["shares"])
    elif decision["action"] == "BUY_BASKET":
        print("Basket:")
        for p in decision.get("positions", []):
            print(f"- {p['ticker']}: {p['shares']} shares ({p['asset_class']})")

    print("Reason:", decision["reason"])
    if decision.get("matrix_top"):
        print("Top matrix candidates:")
        for item in decision["matrix_top"]:
            print(
                f"- {item['ticker']} | score={item['score']} | "
                + ", ".join(item.get("reasons", []))
            )


# ==============================
# MAIN ENTRY
# ==============================

from agents.rebalance_agent import analyze_rebalance

def run_portfolio_assistant():
    try:
        assert_openai_api_key()
    except RuntimeError as e:
        print(f"\n❌ Startup check failed: {e}\n")
        return

    # 0️⃣ Portfolio snapshot FIRST
    print(portfolio_summary())

    # 1️⃣ Daily signals
    signals_context = run_daily_signals()

    # 2️⃣ Portfolio structure health
    print(analyze_portfolio_allocation())

    # 3️⃣ Rebalance intelligence
    rebalance = analyze_rebalance()
    print(_format_rebalance(rebalance))

    # 4️⃣ Generate recommendations
    recommendations = run_recommendation_if_requested()

    # 5️⃣ Capital deployment LAST
    run_capital_deployment(rebalance, recommendations, signals_context)


if __name__ == "__main__":
    run_portfolio_assistant()

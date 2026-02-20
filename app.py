import altair as alt
import pandas as pd
import streamlit as st
import yfinance as yf
from datetime import date

from agents.data_loader import load_holdings, load_watchlist, save_holdings
from agents.portfolio_summary_agent import portfolio_summary
from agents.allocation_agent import calculate_allocation, TARGET_ALLOCATION, classify_ticker
from agents.rebalance_agent import analyze_rebalance
from agents.recommendation_agent import recommend_portfolio
from agents.guardrail_agent import apply_target_guardrails
from agents.signal_agent import generate_signal
from agents.decision_agent import generate_decision, generate_watch_decision
from agents.capital_agent import deploy_capital
from agents.price_agent import get_price
from agents.watchlist_agent import add_to_watchlist, remove_from_watchlist
from config import assert_openai_api_key, ENV_FILE


st.set_page_config(page_title="Portfolio Assistant", layout="wide")

try:
    assert_openai_api_key()
except RuntimeError as e:
    st.error(str(e))
    st.info(f"Set your key in `{ENV_FILE}`.")
    st.stop()


st.title("Portfolio Assistant")
st.caption("Conservative-moderate strategy dashboard for balanced ETF + stocks")


# ----------------------------
# Helpers
# ----------------------------

def _normalize_ticker(item):
    ticker = item.get("ticker") if isinstance(item, dict) else item
    if not ticker:
        return None
    return str(ticker).upper().strip()


def _parse_sentiment(sentiment):
    text = str(sentiment).strip()
    if not text:
        return "N/A", "N/A", ""

    mood = "N/A"
    confidence = "N/A"
    reasoning = ""

    for line in text.splitlines():
        line = line.strip()
        lower = line.lower()
        if lower.startswith("sentiment:"):
            mood = line.split(":", 1)[1].strip()
        elif lower.startswith("confidence:"):
            confidence = line.split(":", 1)[1].strip()
        elif lower.startswith("reasoning:"):
            reasoning = line.split(":", 1)[1].strip()

    if mood == "N/A" and "\n" not in text:
        mood = text

    return mood, confidence, reasoning


def _build_current_holdings_context(holdings):
    context = {}
    for item in holdings:
        if isinstance(item, dict):
            ticker = _normalize_ticker(item)
            if not ticker:
                continue
            context[ticker] = f"shares={item.get('shares', 0)}, avg_cost={item.get('buy_price', 0)}"
        else:
            ticker = _normalize_ticker(item)
            if ticker:
                context[ticker] = "existing position"
    return context


def _normalize_holdings_records(raw_holdings):
    records = []
    for item in raw_holdings:
        if isinstance(item, dict):
            ticker = _normalize_ticker(item)
            if not ticker:
                continue
            records.append(
                {
                    "ticker": ticker,
                    "shares": float(item.get("shares", 0) or 0),
                    "buy_price": float(item.get("buy_price", 0) or 0),
                    "buy_date": str(item.get("buy_date", str(date.today()))),
                }
            )
        else:
            ticker = _normalize_ticker(item)
            if not ticker:
                continue
            records.append(
                {
                    "ticker": ticker,
                    "shares": 1.0,
                    "buy_price": float(get_price(ticker) or 0),
                    "buy_date": str(date.today()),
                }
            )
    return records


def _portfolio_snapshot(holdings):
    rows = []
    total_cost = 0.0
    total_value = 0.0

    for item in holdings:
        if not isinstance(item, dict):
            continue

        ticker = _normalize_ticker(item)
        shares = float(item.get("shares", 0) or 0)
        buy_price = float(item.get("buy_price", 0) or 0)
        buy_date = item.get("buy_date", "N/A")

        current_price = get_price(ticker)
        position_cost = buy_price * shares
        position_value = (current_price or 0) * shares

        total_cost += position_cost
        total_value += position_value

        pnl_pct = None
        if current_price is not None and buy_price > 0:
            pnl_pct = ((current_price - buy_price) / buy_price) * 100

        rows.append(
            {
                "Ticker": ticker,
                "Asset Class": classify_ticker(ticker),
                "Shares": shares,
                "Buy Price": buy_price,
                "Current Price": current_price,
                "P/L %": round(pnl_pct, 2) if pnl_pct is not None else None,
                "Buy Date": buy_date,
            }
        )

    total_return_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
    return pd.DataFrame(rows), total_cost, total_value, round(total_return_pct, 2)


def _portfolio_value_history(holdings, period="6mo"):
    portfolio_values = {}

    for item in holdings:
        ticker = _normalize_ticker(item)
        shares = item.get("shares", 1) if isinstance(item, dict) else 1
        if not ticker:
            continue

        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty:
            continue

        portfolio_values[ticker] = hist["Close"] * shares

    if not portfolio_values:
        return pd.DataFrame()

    df = pd.DataFrame(portfolio_values)
    df["Total"] = df.sum(axis=1)
    return df


def _ticker_performance_history(holdings, period="6mo"):
    frames = []
    for item in holdings:
        ticker = _normalize_ticker(item)
        if not ticker:
            continue

        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty:
            continue

        first = float(hist["Close"].iloc[0])
        if first <= 0:
            continue

        perf = (hist["Close"] / first - 1.0) * 100.0
        df = pd.DataFrame(
            {
                "Date": hist.index,
                "Ticker": ticker,
                "Return %": perf.values,
            }
        )
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _run_signal_pipeline(holdings, watchlist):
    holdings_rows = []
    holdings_decisions = {}

    for item in holdings:
        ticker = _normalize_ticker(item)
        if not ticker:
            continue

        result = generate_signal(ticker)
        decision = generate_decision(ticker)
        sentiment_value, sentiment_conf, sentiment_reason = _parse_sentiment(result.get("sentiment", ""))

        holdings_decisions[ticker] = decision.get("decision", "HOLD")
        holdings_rows.append(
            {
                "Ticker": ticker,
                "Signal (market)": result.get("signal", "N/A"),
                "Position Decision (holding)": decision.get("decision", "N/A"),
                "Trend": result.get("trend", "N/A"),
                "Momentum": result.get("momentum", "N/A"),
                "Sentiment": sentiment_value,
                "Confidence": sentiment_conf,
                "Reason": ", ".join(decision.get("reasoning", [])),
                "_technical": result.get("technical"),
                "_fundamental": result.get("fundamental"),
                "_sentiment_reason": sentiment_reason,
            }
        )

    watch_rows = []
    watchlist_results = {}

    for item in watchlist:
        ticker = _normalize_ticker(item)
        if not ticker:
            continue

        result = generate_signal(ticker)
        watch_decision = generate_watch_decision(ticker, result)
        sentiment_value, sentiment_conf, sentiment_reason = _parse_sentiment(result.get("sentiment", ""))

        watchlist_results[ticker] = {"result": result, "decision": watch_decision}
        watch_rows.append(
            {
                "Ticker": ticker,
                "Signal (market)": result.get("signal", "N/A"),
                "Watch Action": watch_decision.get("decision", "N/A"),
                "Trend": result.get("trend", "N/A"),
                "Momentum": result.get("momentum", "N/A"),
                "Sentiment": sentiment_value,
                "Confidence": sentiment_conf,
                "Reason": ", ".join(watch_decision.get("reasoning", [])),
                "_technical": result.get("technical"),
                "_fundamental": result.get("fundamental"),
                "_sentiment_reason": sentiment_reason,
            }
        )

    return {
        "holdings_table": pd.DataFrame(holdings_rows),
        "watchlist_table": pd.DataFrame(watch_rows),
        "holdings_decisions": holdings_decisions,
        "watchlist_results": watchlist_results,
    }


def _watchlist_insights(watchlist):
    rows = []
    for item in watchlist:
        ticker = _normalize_ticker(item)
        if not ticker:
            continue

        result = generate_signal(ticker)
        watch_decision = generate_watch_decision(ticker, result)
        sentiment_value, _, _ = _parse_sentiment(result.get("sentiment", ""))

        rows.append(
            {
                "Ticker": ticker,
                "Trend": result.get("trend", "N/A"),
                "Sentiment": sentiment_value,
                "Watch Action": watch_decision.get("decision", "N/A"),
                "Reason": ", ".join(watch_decision.get("reasoning", [])),
                "Yahoo Finance": f"https://finance.yahoo.com/quote/{ticker}",
            }
        )

    return pd.DataFrame(rows)


# ----------------------------
# Sidebar controls
# ----------------------------
sidebar_watchlist = load_watchlist()
sidebar_holdings_records = _normalize_holdings_records(load_holdings())

guardrail_mode = st.sidebar.selectbox(
    "Guardrail mode",
    ["strict", "balanced", "off"],
    index=0,
    help="strict: reject overweight sleeves, balanced: soft penalties, off: no filtering",
)

period = st.sidebar.selectbox("Chart period", ["3mo", "6mo", "1y"], index=1)

st.sidebar.markdown("---")
st.sidebar.subheader("Watchlist Manager")

new_watch_ticker = st.sidebar.text_input("Add ticker", placeholder="e.g., XBB.TO")
if st.sidebar.button("Add to Watchlist"):
    ticker = (new_watch_ticker or "").upper().strip()
    if not ticker:
        st.sidebar.warning("Enter a ticker first.")
    else:
        add_to_watchlist([ticker])
        st.sidebar.success(f"Added {ticker}")
        st.rerun()

if sidebar_watchlist:
    remove_watch_ticker = st.sidebar.selectbox(
        "Remove ticker",
        options=sorted([str(t).upper().strip() for t in sidebar_watchlist]),
    )
    if st.sidebar.button("Remove from Watchlist"):
        remove_from_watchlist(remove_watch_ticker)
        st.sidebar.success(f"Removed {remove_watch_ticker}")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Holdings Manager")

add_h_ticker = st.sidebar.text_input("Holding ticker", placeholder="e.g., XIU.TO")
add_h_shares = st.sidebar.number_input("Shares", min_value=0.0, value=1.0, step=1.0)
add_h_price = st.sidebar.number_input("Buy price", min_value=0.0, value=0.0, step=0.01, format="%.2f")
add_h_date = st.sidebar.date_input("Buy date", value=date.today())

if st.sidebar.button("Add Holding"):
    ticker = (add_h_ticker or "").upper().strip()
    if not ticker:
        st.sidebar.warning("Enter a holding ticker first.")
    elif any(r["ticker"] == ticker for r in sidebar_holdings_records):
        st.sidebar.warning(f"{ticker} already exists. Use edit below.")
    else:
        sidebar_holdings_records.append(
            {
                "ticker": ticker,
                "shares": float(add_h_shares),
                "buy_price": float(add_h_price),
                "buy_date": str(add_h_date),
            }
        )
        save_holdings(sidebar_holdings_records)
        st.sidebar.success(f"Added holding {ticker}")
        st.rerun()

if sidebar_holdings_records:
    st.sidebar.markdown("### Edit / Remove Holding")
    holding_options = [r["ticker"] for r in sidebar_holdings_records]
    selected_holding = st.sidebar.selectbox("Select holding", options=holding_options)
    selected_record = next((r for r in sidebar_holdings_records if r["ticker"] == selected_holding), None)

    if selected_record:
        edit_shares = st.sidebar.number_input(
            "Edit shares",
            min_value=0.0,
            value=float(selected_record.get("shares", 0)),
            step=1.0,
            key="edit_h_shares",
        )
        edit_price = st.sidebar.number_input(
            "Edit buy price",
            min_value=0.0,
            value=float(selected_record.get("buy_price", 0)),
            step=0.01,
            format="%.2f",
            key="edit_h_price",
        )
        default_date = pd.to_datetime(selected_record.get("buy_date", str(date.today())), errors="coerce")
        edit_date = st.sidebar.date_input(
            "Edit buy date",
            value=(default_date.date() if pd.notnull(default_date) else date.today()),
            key="edit_h_date",
        )

        if st.sidebar.button("Save Holding Edits"):
            for record in sidebar_holdings_records:
                if record["ticker"] == selected_holding:
                    record["shares"] = float(edit_shares)
                    record["buy_price"] = float(edit_price)
                    record["buy_date"] = str(edit_date)
                    break
            save_holdings(sidebar_holdings_records)
            st.sidebar.success(f"Updated {selected_holding}")
            st.rerun()

        if st.sidebar.button("Remove Holding"):
            updated = [r for r in sidebar_holdings_records if r["ticker"] != selected_holding]
            save_holdings(updated)
            st.sidebar.success(f"Removed {selected_holding}")
            st.rerun()

if "analysis_ctx" not in st.session_state:
    st.session_state.analysis_ctx = None
if "recommendations" not in st.session_state:
    st.session_state.recommendations = None


# ----------------------------
# Load base data
# ----------------------------

holdings = load_holdings()
watchlist = load_watchlist()
rebalance = analyze_rebalance()

holdings_df, total_cost, total_value, total_return = _portfolio_snapshot(holdings)
allocation = calculate_allocation(holdings) if holdings else {}


# ----------------------------
# Top KPIs
# ----------------------------

k1, k2, k3, k4 = st.columns(4)
k1.metric("Holdings", len(holdings))
k2.metric("Watchlist", len(watchlist))
k3.metric("Portfolio Value", f"{round(total_value, 2)}")
k4.metric("Total Return %", f"{total_return}%")


# ----------------------------
# Tabs
# ----------------------------

tab_overview, tab_signals, tab_recs, tab_capital = st.tabs(
    ["Overview", "Signals", "Recommendations", "Capital Deployment"]
)


with tab_overview:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Current Holdings")
        if holdings_df.empty:
            st.info("No holdings yet.")
        else:
            st.dataframe(holdings_df, use_container_width=True)

        st.subheader("Portfolio Summary (Text)")
        st.code(portfolio_summary())

    with c2:
        st.subheader("Watchlist")
        if not watchlist:
            st.info("Watchlist empty.")
        else:
            watch_df = _watchlist_insights(watchlist)
            if watch_df.empty:
                st.write(watchlist)
            else:
                st.dataframe(
                    watch_df,
                    use_container_width=True,
                    column_config={
                        "Yahoo Finance": st.column_config.LinkColumn("Yahoo Finance"),
                    },
                )

        if isinstance(rebalance, dict):
            drift_df = pd.DataFrame(
                [{"Asset": k, "Drift": v} for k, v in rebalance.get("drift", {}).items()]
            )
            st.subheader("Rebalance Drift")
            drift_chart = (
                alt.Chart(drift_df)
                .mark_bar()
                .encode(
                    x=alt.X("Asset:N", sort="-y"),
                    y=alt.Y("Drift:Q", axis=alt.Axis(format="%")),
                    color=alt.condition("datum.Drift < 0", alt.value("#1f77b4"), alt.value("#d62728")),
                    tooltip=["Asset", alt.Tooltip("Drift:Q", format=".2%")],
                )
            )
            st.altair_chart(drift_chart, use_container_width=True)

    st.subheader("Allocation: Current vs Target")
    if allocation:
        alloc_rows = []
        for asset, target in TARGET_ALLOCATION.items():
            alloc_rows.append(
                {
                    "Asset": asset,
                    "Current": allocation.get(asset, 0),
                    "Target": target,
                }
            )
        alloc_df = pd.DataFrame(alloc_rows)
        alloc_long = alloc_df.melt(id_vars=["Asset"], value_vars=["Current", "Target"], var_name="Type", value_name="Weight")
        alloc_chart = (
            alt.Chart(alloc_long)
            .mark_bar()
            .encode(
                x=alt.X("Asset:N"),
                y=alt.Y("Weight:Q", axis=alt.Axis(format="%")),
                color="Type:N",
                xOffset="Type:N",
                tooltip=["Asset", "Type", alt.Tooltip("Weight:Q", format=".2%")],
            )
        )
        st.altair_chart(alloc_chart, use_container_width=True)

    st.subheader("Portfolio Value Over Time")
    history_df = _portfolio_value_history(holdings, period=period)
    if history_df.empty:
        st.info("No price history available for chart.")
    else:
        line_df = history_df.reset_index()[["Date", "Total"]]
        line_df.columns = ["Date", "Total"]
        line_chart = (
            alt.Chart(line_df)
            .mark_line(point=True)
            .encode(
                x="Date:T",
                y="Total:Q",
                tooltip=["Date:T", alt.Tooltip("Total:Q", format=".2f")],
            )
        )
        st.altair_chart(line_chart, use_container_width=True)

    st.subheader("Holding Performance by Ticker")
    perf_df = _ticker_performance_history(holdings, period=period)
    if perf_df.empty:
        st.info("No ticker-level performance data available.")
    else:
        ticker_options = ["All holdings"] + sorted(perf_df["Ticker"].unique().tolist())
        selected_perf_ticker = st.selectbox(
            "Select ticker for performance chart",
            options=ticker_options,
            index=0,
        )

        if selected_perf_ticker == "All holdings":
            plot_df = perf_df
            chart_title = "Holding Performance by Ticker"
        else:
            plot_df = perf_df[perf_df["Ticker"] == selected_perf_ticker].copy()
            chart_title = f"{selected_perf_ticker} Performance"

        perf_chart = (
            alt.Chart(plot_df)
            .mark_line()
            .encode(
                x="Date:T",
                y=alt.Y("Return %:Q", title="Return (%)"),
                color="Ticker:N",
                tooltip=["Ticker:N", "Date:T", alt.Tooltip("Return %:Q", format=".2f")],
            )
            .properties(title=chart_title)
        )
        st.altair_chart(perf_chart, use_container_width=True)


with tab_signals:
    st.subheader("Daily Portfolio Signals")

    if st.button("Run Daily Signal Analysis", type="primary"):
        with st.spinner("Running signals for holdings and watchlist..."):
            st.session_state.analysis_ctx = _run_signal_pipeline(holdings, watchlist)

    if not st.session_state.analysis_ctx:
        st.info("Run daily signal analysis to view market signals and position decisions.")
    else:
        ctx = st.session_state.analysis_ctx

        st.markdown("### Current Holdings Signals")
        htable = ctx["holdings_table"]
        if htable.empty:
            st.info("No holdings signals available.")
        else:
            show_cols = [
                "Ticker",
                "Signal (market)",
                "Position Decision (holding)",
                "Trend",
                "Momentum",
                "Sentiment",
                "Confidence",
                "Reason",
            ]
            st.dataframe(htable[show_cols], use_container_width=True)

            with st.expander("Technical / Fundamental Details"):
                for _, row in htable.iterrows():
                    st.markdown(f"**{row['Ticker']}**")
                    st.write("Technical:", row["_technical"])
                    st.write("Fundamental:", row["_fundamental"])
                    if row["_sentiment_reason"]:
                        st.write("Sentiment reason:", row["_sentiment_reason"])

        st.markdown("### Watchlist Signals")
        wtable = ctx["watchlist_table"]
        if wtable.empty:
            st.info("No watchlist signals available.")
        else:
            show_cols = [
                "Ticker",
                "Signal (market)",
                "Watch Action",
                "Trend",
                "Momentum",
                "Sentiment",
                "Confidence",
                "Reason",
            ]
            st.dataframe(wtable[show_cols], use_container_width=True)


with tab_recs:
    st.subheader("ETF / Stock Recommendations")

    if st.button("Generate Recommendations", type="primary"):
        with st.spinner("Generating recommendations..."):
            current_holdings = _build_current_holdings_context(holdings)
            investor_profile = {
                "horizon": "short to medium",
                "risk": "conservative to moderate",
                "style": "balanced ETF + stocks",
            }
            capital_level = "small (<5k)"

            rec = recommend_portfolio(current_holdings, investor_profile, capital_level)
            rec = apply_target_guardrails(rec, holdings, mode=guardrail_mode)
            st.session_state.recommendations = rec

    rec = st.session_state.recommendations
    if not rec:
        st.info("Generate recommendations to view guarded ETF/stock suggestions.")
    else:
        st.markdown(f"**Guardrail mode:** `{rec.get('guardrail', {}).get('mode', guardrail_mode)}`")

        st.markdown("### Filtered ETFs")
        st.write(rec.get("etfs", []))

        st.markdown("### Filtered Stocks")
        st.write(rec.get("stocks", []))

        guard = rec.get("guardrail", {})
        if guard:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### Ranked Candidates")
                st.dataframe(pd.DataFrame(guard.get("ranked", [])), use_container_width=True)
            with c2:
                st.markdown("### Rejected Candidates")
                st.dataframe(pd.DataFrame(guard.get("dropped", [])), use_container_width=True)

        with st.expander("Full Recommendation Report"):
            st.code(rec.get("report", "No report"))


with tab_capital:
    st.subheader("Capital Deployment")
    cash = st.number_input("Available cash to deploy", min_value=0.0, step=100.0, value=1000.0)

    if st.button("Compute Deployment Plan", type="primary"):
        signals_ctx = st.session_state.analysis_ctx or {}
        decision = deploy_capital(
            cash,
            rebalance,
            st.session_state.recommendations,
            watchlist,
            signals_ctx.get("holdings_decisions"),
            signals_ctx.get("watchlist_results"),
        )

        st.markdown(f"**Action:** `{decision.get('action', 'WAIT')}`")
        st.write("Reason:", decision.get("reason", "N/A"))

        if decision.get("action") == "BUY":
            st.write("Ticker:", decision.get("ticker"))
            st.write("Shares:", decision.get("shares"))

        if decision.get("action") == "BUY_BASKET":
            st.markdown("### Basket")
            st.dataframe(pd.DataFrame(decision.get("positions", [])), use_container_width=True)

        if decision.get("matrix_top"):
            st.markdown("### Matrix Top Candidates")
            st.dataframe(pd.DataFrame(decision.get("matrix_top", [])), use_container_width=True)

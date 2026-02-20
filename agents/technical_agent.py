import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD


def analyze_technical(ticker, tone="conservative"):

    stock = yf.Ticker(ticker)
    hist = stock.history(period="6mo")

    if hist.empty:
        return {
            "ticker": ticker,
            "trend": "unknown",
            "momentum": "unknown",
            "rsi": None,
            "macd": None,
            "macd_signal": None,
            "signal": "neutral",
            "entry_timing": "no data",
            "summary": f"No technical data available for {ticker}"
        }

    close_prices = hist["Close"]

    # RSI
    rsi = float(RSIIndicator(close=close_prices).rsi().iloc[-1])

    # MACD
    macd = MACD(close=close_prices)
    macd_value = float(macd.macd().iloc[-1])
    macd_signal = float(macd.macd_signal().iloc[-1])

    # Trend detection
    current_price = float(close_prices.iloc[-1])
    avg_price = float(close_prices.mean())

    if current_price > avg_price:
        trend = "rising"
    elif current_price < avg_price:
        trend = "falling"
    else:
        trend = "sideways"

    # Momentum interpretation
    if rsi > 65:
        momentum = "strong"
    elif rsi < 40:
        momentum = "weak"
    else:
        momentum = "neutral"

    # Entry timing
    if trend == "rising" and momentum == "strong":
        entry_timing = "acceptable for gradual entry"
    elif trend == "falling":
        entry_timing = "better to wait"
    else:
        entry_timing = "monitor for better timing"

    # Normalized signal for downstream agents.
    if trend == "rising" and momentum == "strong":
        normalized_signal = "bullish"
    elif trend == "falling" and momentum == "weak":
        normalized_signal = "bearish"
    else:
        normalized_signal = "neutral"

    if tone == "decisive":
        if normalized_signal == "bullish":
            message = "Buy zone forming"
        elif normalized_signal == "bearish":
            message = "Reduce exposure"
        else:
            message = "Hold / Observe"
    else:
        if normalized_signal == "bullish":
            message = "Consider gradual entry"
        elif trend == "falling":
            message = "Hold and monitor"
        else:
            message = "No immediate action"

    summary = (
        f"Technical Analysis for {ticker}\n"
        f"- RSI: {round(rsi, 2)}\n"
        f"- MACD vs Signal: {round(macd_value, 2)} vs {round(macd_signal, 2)}\n"
        f"- Trend: {trend}\n"
        f"- Momentum: {momentum}\n"
        f"- Entry timing: {entry_timing}\n"
        f"- Signal: {message}"
    )

    return {
        "ticker": ticker,
        "trend": trend,
        "momentum": momentum,
        "rsi": round(rsi, 2),
        "macd": round(macd_value, 2),
        "macd_signal": round(macd_signal, 2),
        "entry_timing": entry_timing,
        "signal": normalized_signal,
        "summary": summary,
    }

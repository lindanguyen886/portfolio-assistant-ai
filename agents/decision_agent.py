from agents.technical_agent import analyze_technical
from agents.fundamental_agent import analyze_fundamental
from agents.sentiment_agent import analyze_sentiment


def _parse_sentiment(sentiment):
    text = str(sentiment).lower()
    if "negative" in text or "bearish" in text:
        return "negative"
    if "positive" in text or "bullish" in text:
        return "positive"
    return "neutral"


def generate_decision(ticker):

    technical = analyze_technical(ticker)
    fundamental = analyze_fundamental(ticker)
    sentiment = analyze_sentiment(ticker)

    decision = "HOLD"
    reasoning = []

    # -------------------------
    # TECHNICAL SIGNALS
    # -------------------------
    if isinstance(technical, dict):

        trend = technical.get("trend", "")
        rsi = technical.get("rsi", 50)

        if trend == "rising" and rsi is not None and rsi < 70:
            decision = "ADD"
            reasoning.append("Positive trend with room before overbought")

        elif rsi is not None and rsi > 75:
            decision = "TRIM"
            reasoning.append("RSI indicates overbought conditions")

    # -------------------------
    # FUNDAMENTAL SIGNALS
    # -------------------------
    if isinstance(fundamental, dict):

        score = fundamental.get("score", 5)

        if score >= 8:
            reasoning.append("Strong fundamentals support long-term hold")

        elif score <= 4:
            decision = "AVOID"
            reasoning.append("Weak fundamentals")

    # -------------------------
    # SENTIMENT SIGNALS
    # -------------------------
    sentiment_signal = _parse_sentiment(sentiment)

    if sentiment_signal == "negative":
        decision = "WAIT"
        reasoning.append("Negative market sentiment")

    elif sentiment_signal == "positive":
        reasoning.append("Positive sentiment supports accumulation")

    # -------------------------
    # FINAL STRUCTURE
    # -------------------------

    if not reasoning:
        reasoning.append("No strong conflicting signals detected")

    return {
        "ticker": ticker,
        "decision": decision,
        "technical": technical,
        "fundamental": fundamental,
        "sentiment": sentiment,
        "reasoning": reasoning
    }


def generate_watch_decision(ticker, signal_data):
    """
    Decision logic ONLY for watchlist tickers.
    Does NOT affect holdings logic.
    """

    trend = signal_data.get("trend", "neutral")
    sentiment = str(signal_data.get("sentiment", "neutral")).lower()
    momentum = signal_data.get("momentum", "neutral")

    if trend == "rising" and ("positive" in sentiment or "bullish" in sentiment):
        return {
            "decision": "Consider entry",
            "reasoning": ["trend improving", "positive sentiment"]
        }

    if momentum == "strong":
        return {
            "decision": "Watch breakout",
            "reasoning": ["momentum building"]
        }

    if trend == "falling":
        return {
            "decision": "Wait",
            "reasoning": ["downtrend - avoid early entry"]
        }

    return {
        "decision": "Monitor",
        "reasoning": ["no clear entry signal yet"]
    }

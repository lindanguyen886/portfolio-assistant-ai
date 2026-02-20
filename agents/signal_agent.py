from agents.technical_agent import analyze_technical
from agents.fundamental_agent import analyze_fundamental
from agents.sentiment_agent import analyze_sentiment


def normalize_ticker(ticker):
    canadian_symbols = [
        "XIU", "ZAG", "XAW", "SAFE", "XRE", "VGG",
        "VCN", "XBB", "VAB", "VGRO", "VBAL",
        "BCE", "ENB", "TD", "BNS", "FTS",
    ]

    if ticker in canadian_symbols and ".TO" not in ticker:
        return ticker + ".TO"

    return ticker


def _extract_sentiment_signal(sentiment):
    text = str(sentiment).lower()
    if "bullish" in text or "positive" in text:
        return "positive"
    if "bearish" in text or "negative" in text:
        return "negative"
    return "neutral"


def generate_signal(ticker):

    ticker = normalize_ticker(ticker)

    technical = analyze_technical(ticker)
    fundamental = analyze_fundamental(ticker)
    sentiment = analyze_sentiment(ticker)

    score = 0

    if isinstance(technical, dict):
        tech_signal = technical.get("signal", "neutral")
        if tech_signal == "bullish":
            score += 1
        elif tech_signal == "bearish":
            score -= 1
    else:
        tech_text = str(technical).lower()
        if "bullish" in tech_text:
            score += 1
        if "bearish" in tech_text:
            score -= 1

    if isinstance(fundamental, dict):
        fund_signal = fundamental.get("signal", "neutral")
        if fund_signal == "bullish":
            score += 1
        elif fund_signal == "bearish":
            score -= 1
    else:
        fund_text = str(fundamental).lower()
        if "strong" in fund_text or "bullish" in fund_text:
            score += 1
        if "weak" in fund_text or "bearish" in fund_text:
            score -= 1

    sentiment_signal = _extract_sentiment_signal(sentiment)
    if sentiment_signal == "positive":
        score += 1
    elif sentiment_signal == "negative":
        score -= 1

    if score >= 2:
        signal = "BUY"
    elif score <= -2:
        signal = "SELL"
    else:
        signal = "HOLD"

    trend = technical.get("trend", "unknown") if isinstance(technical, dict) else "unknown"
    momentum = technical.get("momentum", "unknown") if isinstance(technical, dict) else "unknown"

    return {
        "signal": signal,
        "technical": technical,
        "fundamental": fundamental,
        "sentiment": sentiment,
        "trend": trend,
        "momentum": momentum,
    }


def watchlist_action(signal_result):
    signal = signal_result.get("signal", "").lower()

    if "strong buy" in signal or "buy" in signal:
        return "BUY_CANDIDATE"
    if "sell" in signal:
        return "REMOVE"
    if "neutral" in signal:
        return "WATCH"
    return "WAIT"

import yfinance as yf

def get_price(ticker):
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="1d")

        if hist.empty:
            return None

        return round(hist["Close"].iloc[-1], 2)
    except Exception:
        return None


def is_delisted(ticker):
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="6mo")
        return hist.empty
    except:
        return True
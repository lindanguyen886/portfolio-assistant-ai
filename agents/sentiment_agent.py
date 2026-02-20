# agents/sentiment_agent.py

from openai import OpenAI
from config import assert_openai_api_key


def analyze_sentiment(ticker):
    """
    AI sentiment analysis using news & market tone.
    Returns simple human-readable interpretation.
    """
    client = OpenAI(api_key=assert_openai_api_key())

    prompt = f"""
    You are a financial sentiment analyst.

    Analyze overall market sentiment for stock/ETF: {ticker}

    Consider:
    - investor tone
    - news direction
    - social/media buzz
    - macro environment

    Return:

    Sentiment: Bullish / Neutral / Bearish
    Confidence: Low / Medium / High
    Reasoning: short explanation
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

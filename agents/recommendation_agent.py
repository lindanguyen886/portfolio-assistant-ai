from openai import OpenAI
import re
from config import assert_openai_api_key


def recommend_portfolio(current_holdings, profile, capital_level):
    client = OpenAI(api_key=assert_openai_api_key())

    prompt = f"""
You are a portfolio strategist.

Create a recommendation using EXACTLY this structure.

1. ETFs to Add
- ticker — reason

2. Stocks to Add
- ticker — reason

3. Allocation Suggestion
(table style)

4. Reasoning
(bullet points)

5. Risk Considerations
(bullet points)

Summary:
(short paragraph)

Investor profile:
{profile}

Current holdings:
{current_holdings}

Capital level:
{capital_level}

Portfolio preference note:
- Small capital, conservative to moderate risk, 1-5 year horizon
- Keep liquidity via SAFE.TO
- Prioritize balanced ETF + stocks style
- When suitable, prioritize VCN.TO and XBB.TO ETFs
- For Canadian dividend stocks, prioritize ENB.TO and TD.TO
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    report_text = response.choices[0].message.content

    # ---------- Extract ETF tickers ----------
    etfs = re.findall(r'\b[A-Z]{2,5}\.TO\b', report_text)

    # crude separation:
    # first section before "2. Stocks"
    etf_section = report_text.split("2. Stocks to Add")[0]
    etfs = re.findall(r'\b[A-Z]{2,5}\.TO\b', etf_section)

    # ---------- Extract Stock tickers ----------
    if "2. Stocks to Add" in report_text:
        stock_section = report_text.split("2. Stocks to Add")[1]
        stock_section = stock_section.split("3. Allocation")[0]
        stocks = re.findall(r'\b[A-Z]{2,5}\.TO\b', stock_section)
    else:
        stocks = []

    return {
        "etfs": list(set(etfs)),
        "stocks": list(set(stocks)),
        "report": report_text
    }

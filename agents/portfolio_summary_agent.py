from agents.data_loader import load_holdings
from agents.price_agent import get_price


def portfolio_summary():

    holdings = load_holdings()

    if not holdings:
        return "No holdings found."

    output = "\n📊 PORTFOLIO SUMMARY\n"

    total_value = 0
    total_cost = 0

    for item in holdings:

        ticker = item["ticker"]
        shares = item.get("shares", 0)
        buy_price = item.get("buy_price", 0)
        buy_date = item.get("buy_date", "N/A")

        current_price = get_price(ticker)

        if current_price is None:
            current_price_text = "N/A"
            pnl_text = "N/A"
        else:
            position_value = current_price * shares
            cost_value = buy_price * shares

            pnl_pct = ((current_price - buy_price) / buy_price) * 100

            total_value += position_value
            total_cost += cost_value

            current_price_text = f"{current_price} CAD"
            pnl_text = f"{round(pnl_pct,2)}%"

        output += f"""
{ticker}
- Shares: {shares}
- Buy price: {buy_price} CAD
- Current price: {current_price_text}
- P/L: {pnl_text}
- Buy date: {buy_date}
"""

    if total_cost > 0:
        portfolio_return = ((total_value - total_cost) / total_cost) * 100
        output += f"\nTotal Return: {round(portfolio_return,2)}%\n"

    return output
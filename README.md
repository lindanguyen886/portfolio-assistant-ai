# Portfolio Assistant AI Agent
![AI Hedge Fund Brain Architecture](https://raw.githubusercontent.com/lindanguyen886/portfolio-assistant-ai/main/assets%3Aarchitecture.png)

An AI-powered portfolio assistant for conservative-to-moderate investors with a short-to-medium horizon (1-5 years).

This project combines:
- market signal generation (technical + fundamental + sentiment)
- position decisions for current holdings
- watchlist intelligence
- allocation/rebalance checks
- guardrailed recommendations
- matrix-based capital deployment (single buy or basket)

## Strategy Focus

Target profile:
- Horizon: short to medium
- Risk: conservative to moderate
- Style: balanced ETF + stocks

Preferred mix:
- Liquidity: `SAFE.TO`
- Bonds: `XBB.TO` (and peers)
- Canadian broad equity: `VCN.TO`
- Canadian dividend stocks: `ENB.TO`, `TD.TO`

## Core Features

- **CLI workflow** for daily operations
- **Interactive Streamlit dashboard** with tabs:
  - Overview
  - Signals
  - Recommendations
  - Capital Deployment
- **Watchlist manager** (add/remove)
- **Holdings manager** (add/edit/remove ticker, shares, buy price, buy date)
- **Guardrail modes**:
  - `strict`
  - `balanced`
  - `off`
- **Capital deployment matrix** using:
  - rebalance underweights
  - holdings decisions
  - watchlist actions
  - today’s recommendations

## Project Structure

```text
portfolio_assistant/
├── app.py                        # Streamlit dashboard
├── main.py                       # CLI orchestrator
├── config.py                     # .env loading + API key checks
├── data/
│   ├── holdings.json
│   └── watchlist.json
└── agents/
    ├── signal_agent.py
    ├── technical_agent.py
    ├── fundamental_agent.py
    ├── sentiment_agent.py
    ├── decision_agent.py
    ├── allocation_agent.py
    ├── rebalance_agent.py
    ├── recommendation_agent.py
    ├── guardrail_agent.py
    ├── capital_agent.py
    ├── data_loader.py
    └── watchlist_agent.py
```

## Workflow

1. Load holdings and watchlist from JSON
2. Run ticker analysis (technical, fundamental, sentiment)
3. Produce:
   - **Signal (market)**: BUY/HOLD/SELL
   - **Position Decision (holding)**: ADD/HOLD/TRIM/etc.
4. Evaluate watchlist actions
5. Compute allocation and rebalance drift
6. Generate recommendations (optional)
7. Apply guardrails (`strict`/`balanced`/`off`)
8. Build capital deployment plan (single ticker or basket)

## Setup

### 1) Clone and enter project

```bash
git clone https://github.com/lindanguyen886/portfolio-assistant-ai.git
cd portfolio-assistant-ai
```

### 2) Install dependencies

```bash
python3 -m pip install openai streamlit yfinance ta matplotlib pandas altair
```

### 3) Configure API key

Create `.env` in project root:

```env
OPENAI_API_KEY=your_real_openai_key
```

## Run

### CLI Agent

```bash
python3 main.py
```

### Streamlit UI

```bash
python3 -m streamlit run app.py
```

If port is busy:

```bash
python3 -m streamlit run app.py --server.port 8502
```

## Notes

- This tool is for educational/research purposes, not financial advice.
- Market-data calls may fail if network access is unavailable.
- Keep `.env` private and never commit secrets.

## Roadmap

- Trade journal and execution logging
- Backtesting module for decision rules
- Risk limits and max position sizing controls
- Automated report export (PDF/Markdown)

---

If this project helps, consider starring the repo:  
`https://github.com/lindanguyen886/portfolio-assistant-ai`

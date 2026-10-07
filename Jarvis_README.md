# JARVIS – AI Forex Trading Assistant v3.0 FINAL

Educational Python tool for Forex (and gold/silver) analysis with a full technical indicator suite, multi-timeframe bias, position sizing, CSV logging, and Telegram alerts.

> **⚠️ DISCLAIMER**  
> This is **NOT financial advice**.  
> Forex trading involves substantial risk of loss.  
> Past performance is not indicative of future results.  
> Use for educational and research purposes only.  
> Never risk money you cannot afford to lose.

---

## What’s in v3.0 FINAL

| Feature | Details |
|---------|---------|
| **Pairs** | 30+ (majors, yen/euro/pound crosses, gold, silver) |
| **Timeframes** | 15m primary + 1h higher-timeframe bias |
| **Trend** | EMA 9/21/50/200, SuperTrend, Ichimoku Cloud |
| **Momentum** | RSI, Stochastic, MACD, CCI, Williams %R |
| **Volatility** | Bollinger Bands, ATR |
| **Trend strength** | ADX + +DI/−DI |
| **Support/Resistance** | Classic Pivot Points (S1/R1/S2/R2) |
| **Sessions** | Asian / London / NY / Overlap detection |
| **Risk** | ATR-based SL (1.5×) & TP (3.0×), position size calculator |
| **Alerts** | Telegram for strong signals (confidence ≥ 65%) |
| **Log** | Every signal saved to `jarvis_signals_log.csv` |

---

## Install

```bash
pip install yfinance pandas numpy pandas-ta requests
```

---

## Telegram setup (optional)

1. Message **@BotFather** → `/newbot` → copy token  
2. Start a chat with your bot  
3. Open: `https://api.telegram.org/botYOUR_TOKEN/getUpdates`  
4. Copy your `chat.id`  
5. Either export:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_token"
   export TELEGRAM_CHAT_ID="your_chat_id"
   ```
   or paste them at the top of `Jarvis_Forex.py`.

---

## Run

```bash
python Jarvis_Forex.py
```

### Commands

| Command | Description |
|---------|-------------|
| `scan` | Analyze all pairs once |
| `live` | Continuous scan + Telegram |
| `pair EURUSD` | One pair (`GOLD` / `SILVER` also work) |
| `pairs` | List tracked pairs |
| `add USDSEK` | Add pair |
| `remove USDSEK` | Remove pair |
| `account 5000 1` | Set balance $5000, risk 1% |
| `test_telegram` | Test Telegram |
| `help` | Help |
| `quit` | Exit |

---

## Example signal output

```
============================================================
  PAIR: EURUSD   |   2026-10-07 00:45 UTC   |   Session: LONDON
  Price: 1.12562   |   HTF Bias: BULLISH
------------------------------------------------------------
  SIGNAL: BUY (LONG)   (Confidence: 84%)
  Score: 6.2   |   RSI: 28.3   |   ADX: 31.2
  Entry       : 1.12562
  Stop Loss   : 1.12310  (1.5× ATR)
  Take Profit : 1.13066  (3.0× ATR)
  Risk:Reward : 1 : 2.0
  Position    : ~4,000 units (risk $100.00)
------------------------------------------------------------
  Key reasons:
    • Strong bullish EMA stack
    • RSI oversold (28.3)
    • MACD bullish crossover
    • SuperTrend bullish
    • Price above Ichimoku cloud
    • HTF (1h) bias BULLISH
    • Strong trend (ADX=31.2)
============================================================
```

---

## Notes

- Data from Yahoo Finance (free). Rate limits possible.  
- Signals are technical only — not a guarantee of profit.  
- Always combine with news/economic calendar and strict risk management (≤ 1% risk per trade recommended).  
- This script is analysis-only. Live order execution requires a broker API.

Trade safely.  
— Jarvis

#!/usr/bin/env python3
"""
JARVIS - AI Forex Trading Assistant  v3.0  (Final)
==================================================
Educational / research tool only. NOT financial advice.
Past performance does not guarantee future results.
Trading Forex involves substantial risk of loss.
Always do your own research and never risk money you cannot afford to lose.
Use at your own risk. No warranty of any kind.
"""

import time
import os
import csv
from datetime import datetime, timezone
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
import requests

# ====================== CONFIG ======================
DEFAULT_PAIRS = [
    # --- Majors ---
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
    "USDCAD=X", "USDCHF=X", "NZDUSD=X",
    # --- Yen crosses ---
    "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "CADJPY=X",
    "CHFJPY=X", "NZDJPY=X",
    # --- Euro crosses ---
    "EURGBP=X", "EURAUD=X", "EURCAD=X", "EURCHF=X", "EURNZD=X",
    # --- Pound crosses ---
    "GBPAUD=X", "GBPCAD=X", "GBPCHF=X", "GBPNZD=X",
    # --- Other crosses ---
    "AUDCAD=X", "AUDCHF=X", "AUDNZD=X", "CADCHF=X",
    "NZDCAD=X", "NZDCHF=X",
    # --- Metals ---
    "GC=F",     # Gold
    "SI=F",     # Silver
]

INTERVAL = "15m"          # Primary timeframe
HTF_INTERVAL = "1h"       # Higher timeframe for trend bias
LOOKBACK = "7d"
HTF_LOOKBACK = "30d"
POLL_SECONDS = 90

# ---------- Indicator settings ----------
EMA_FAST, EMA_SLOW, EMA_TREND, EMA_LONG = 9, 21, 50, 200
RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT = 14, 30, 70
STOCH_K, STOCH_D, STOCH_SMOOTH = 14, 3, 3
STOCH_OVERSOLD, STOCH_OVERBOUGHT = 20, 80
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
BB_PERIOD, BB_STD = 20, 2.0
ATR_PERIOD = 14
ADX_PERIOD, ADX_STRONG = 14, 25
CCI_PERIOD, CCI_OVERSOLD, CCI_OVERBOUGHT = 20, -100, 100
WILLIAMS_PERIOD, WILLIAMS_OVERSOLD, WILLIAMS_OVERBOUGHT = 14, -80, -20
SUPERTREND_LENGTH, SUPERTREND_MULTIPLIER = 10, 3.0

# Risk management
SL_ATR_MULT = 1.5
TP_ATR_MULT = 3.0
DEFAULT_RISK_PCT = 1.0          # % of account risked per trade
DEFAULT_ACCOUNT = 10_000        # default account size for position sizing

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED   = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
MIN_CONFIDENCE_FOR_ALERT = 65

# Logging
LOG_FILE = Path("jarvis_signals_log.csv")
# ====================================================


class Jarvis:
    def __init__(self):
        self.pairs = DEFAULT_PAIRS.copy()
        self.last_alerts = {}
        self.account_balance = DEFAULT_ACCOUNT
        self.risk_pct = DEFAULT_RISK_PCT
        print(self._banner())
        print("Jarvis v3.0 FINAL — Full suite + MTF + Ichimoku + Pivots + Position sizing")
        if TELEGRAM_ENABLED:
            print("Telegram alerts: ENABLED")
            self.send_telegram("🤖 <b>Jarvis v3.0 FINAL</b> is online.")
        else:
            print("Telegram alerts: DISABLED (set TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID)")
        print(f"Account size for position calc: ${self.account_balance:,.0f}  |  Risk: {self.risk_pct}%")
        print("Type 'help' for commands.\n")

    def _banner(self):
        return r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
        Forex Trading Assistant v3.0 FINAL
  30+ pairs • Multi-TF • Ichimoku • Pivots • ADX
  EMA • RSI • Stoch • MACD • BB • ATR • SuperTrend
  CCI • Williams %R • Position Sizing • Telegram
        Educational use only — Not financial advice
"""

    # ------------------------------------------------------------------
    # Session detection
    # ------------------------------------------------------------------
    def current_session(self) -> str:
        hour = datetime.now(timezone.utc).hour
        if 0 <= hour < 7:
            return "ASIAN"
        elif 7 <= hour < 12:
            return "LONDON"
        elif 12 <= hour < 16:
            return "LONDON / NEW YORK OVERLAP (highest liquidity)"
        elif 16 <= hour < 21:
            return "NEW YORK"
        else:
            return "AFTER HOURS / THIN"

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------
    def send_telegram(self, message: str) -> bool:
        if not TELEGRAM_ENABLED:
            return False
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            return r.status_code == 200
        except Exception as e:
            print(f"  [!] Telegram error: {e}")
            return False

    def alert_signal(self, res: dict):
        if res["confidence"] < MIN_CONFIDENCE_FOR_ALERT:
            return
        if "NEUTRAL" in res["signal"] or "WAIT" in res["signal"]:
            return

        key = f"{res['symbol']}_{res['signal']}"
        now = time.time()
        if key in self.last_alerts and (now - self.last_alerts[key]) < 1800:
            return
        self.last_alerts[key] = now

        emoji = "🟢" if "BUY" in res["signal"] else "🔴"
        msg = (
            f"{emoji} <b>JARVIS v3 SIGNAL</b>\n\n"
            f"<b>Pair:</b> {res['symbol']}\n"
            f"<b>Signal:</b> {res['signal']}\n"
            f"<b>Confidence:</b> {res['confidence']}%\n"
            f"<b>Price:</b> {res['price']}\n"
            f"<b>RSI:</b> {res['rsi']}  |  <b>ADX:</b> {res.get('adx', 'n/a')}\n"
            f"<b>Session:</b> {res.get('session', 'n/a')}\n"
            f"<b>HTF Bias:</b> {res.get('htf_bias', 'n/a')}\n\n"
        )
        if res.get("sl") and res.get("tp"):
            risk = abs(res["price"] - res["sl"])
            reward = abs(res["tp"] - res["price"])
            rr = reward / risk if risk > 0 else 0
            msg += (
                f"<b>Entry:</b> {res['price']}\n"
                f"<b>Stop Loss:</b> {res['sl']}\n"
                f"<b>Take Profit:</b> {res['tp']}\n"
                f"<b>R:R</b> ≈ 1:{rr:.1f}\n"
            )
            if res.get("position_size"):
                msg += f"<b>Suggested size:</b> {res['position_size']}\n"
            msg += "\n"
        msg += "<b>Top reasons:</b>\n"
        for r in res["reasons"][:6]:
            msg += f"• {r}\n"
        msg += f"\n<i>{res['time']} UTC</i>\n⚠️ Educational only — Not financial advice"

        if self.send_telegram(msg):
            print(f"  📤 Telegram alert sent for {res['symbol']}")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def log_signal(self, res: dict):
        write_header = not LOG_FILE.exists()
        try:
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow([
                        "timestamp", "symbol", "signal", "confidence", "price",
                        "sl", "tp", "rsi", "adx", "htf_bias", "session", "score"
                    ])
                writer.writerow([
                    res.get("time"), res.get("symbol"), res.get("signal"),
                    res.get("confidence"), res.get("price"),
                    res.get("sl"), res.get("tp"), res.get("rsi"),
                    res.get("adx"), res.get("htf_bias"), res.get("session"),
                    res.get("score"),
                ])
        except Exception as e:
            print(f"  [!] Log write error: {e}")

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def fetch_data(self, symbol: str, interval: str = INTERVAL, period: str = LOOKBACK):
        try:
            df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
            if df.empty or len(df) < 50:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.rename(columns=str.title)
            if not all(c in df.columns for c in ["Open", "High", "Low", "Close"]):
                return None
            if "Volume" not in df.columns:
                df["Volume"] = 0
            return df.dropna()
        except Exception as e:
            print(f"  [!] Data error {symbol} ({interval}): {e}")
            return None

    def get_htf_bias(self, symbol: str) -> str:
        """Higher-timeframe trend bias using EMA 50 vs EMA 200 on 1h."""
        df = self.fetch_data(symbol, interval=HTF_INTERVAL, period=HTF_LOOKBACK)
        if df is None or len(df) < 60:
            return "UNKNOWN"
        close = df["Close"]
        ema50 = ta.ema(close, length=50).iloc[-1]
        ema200 = ta.ema(close, length=200).iloc[-1]
        price = close.iloc[-1]
        if pd.isna(ema50) or pd.isna(ema200):
            return "UNKNOWN"
        if price > ema50 > ema200:
            return "BULLISH"
        if price < ema50 < ema200:
            return "BEARISH"
        if price > ema200:
            return "MILD BULLISH"
        return "MILD BEARISH"

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close, high, low, volume = df["Close"], df["High"], df["Low"], df["Volume"]

        # Moving averages
        df["EMA_Fast"] = ta.ema(close, length=EMA_FAST)
        df["EMA_Slow"] = ta.ema(close, length=EMA_SLOW)
        df["EMA_Trend"] = ta.ema(close, length=EMA_TREND)
        df["EMA_Long"] = ta.ema(close, length=EMA_LONG)

        # Momentum
        df["RSI"] = ta.rsi(close, length=RSI_PERIOD)

        stoch = ta.stoch(high, low, close, k=STOCH_K, d=STOCH_D, smooth_k=STOCH_SMOOTH)
        if stoch is not None:
            df = pd.concat([df, stoch], axis=1)

        macd = ta.macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        if macd is not None:
            df = pd.concat([df, macd], axis=1)
            for c in list(df.columns):
                if c.startswith("MACD_") and "MACDh" not in c and "MACDs" not in c:
                    df.rename(columns={c: "MACD"}, inplace=True)
                elif "MACDh" in c:
                    df.rename(columns={c: "MACD_Hist"}, inplace=True)
                elif "MACDs" in c:
                    df.rename(columns={c: "MACD_Signal"}, inplace=True)

        df["CCI"] = ta.cci(high, low, close, length=CCI_PERIOD)
        df["WILLR"] = ta.willr(high, low, close, length=WILLIAMS_PERIOD)

        # Volatility
        bb = ta.bbands(close, length=BB_PERIOD, std=BB_STD)
        if bb is not None:
            df = pd.concat([df, bb], axis=1)
        df["ATR"] = ta.atr(high, low, close, length=ATR_PERIOD)

        # Trend strength
        adx = ta.adx(high, low, close, length=ADX_PERIOD)
        if adx is not None:
            df = pd.concat([df, adx], axis=1)
            for c in list(df.columns):
                if c.startswith("ADX_"):
                    df.rename(columns={c: "ADX"}, inplace=True)
                elif c.startswith("DMP_"):
                    df.rename(columns={c: "DI_Plus"}, inplace=True)
                elif c.startswith("DMN_"):
                    df.rename(columns={c: "DI_Minus"}, inplace=True)

        # SuperTrend
        st = ta.supertrend(high, low, close, length=SUPERTREND_LENGTH, multiplier=SUPERTREND_MULTIPLIER)
        if st is not None:
            df = pd.concat([df, st], axis=1)
            for c in list(df.columns):
                if c.startswith("SUPERTd"):
                    df.rename(columns={c: "SuperTrend_Dir"}, inplace=True)

        # Ichimoku Cloud
        try:
            ichi = ta.ichimoku(high, low, close)
            if ichi is not None:
                if isinstance(ichi, tuple):
                    ichi_df = ichi[0]
                else:
                    ichi_df = ichi
                if isinstance(ichi_df, pd.DataFrame):
                    df = pd.concat([df, ichi_df], axis=1)
        except Exception:
            pass

        # Classic Pivot Points
        df["Pivot"] = (high.shift(1) + low.shift(1) + close.shift(1)) / 3
        df["R1"] = 2 * df["Pivot"] - low.shift(1)
        df["S1"] = 2 * df["Pivot"] - high.shift(1)
        df["R2"] = df["Pivot"] + (high.shift(1) - low.shift(1))
        df["S2"] = df["Pivot"] - (high.shift(1) - low.shift(1))

        # Volume
        if volume.sum() > 0:
            df["OBV"] = ta.obv(close, volume)

        return df.dropna()

    # ------------------------------------------------------------------
    # Signal engine
    # ------------------------------------------------------------------
    def generate_signal(self, df: pd.DataFrame, htf_bias: str = "UNKNOWN") -> dict:
        if len(df) < 5:
            return {"signal": "NONE", "confidence": 0, "reasons": ["Insufficient data"]}

        last, prev = df.iloc[-1], df.iloc[-2]
        reasons = []
        score = 0.0

        # 1. EMA structure
        if last["EMA_Fast"] > last["EMA_Slow"] > last["EMA_Trend"]:
            score += 2.0
            reasons.append("Strong bullish EMA stack")
        elif last["EMA_Fast"] < last["EMA_Slow"] < last["EMA_Trend"]:
            score -= 2.0
            reasons.append("Strong bearish EMA stack")
        elif last["EMA_Fast"] > last["EMA_Slow"]:
            score += 1.0
            reasons.append("EMA Fast > Slow")
        else:
            score -= 1.0
            reasons.append("EMA Fast < Slow")

        if prev["EMA_Fast"] <= prev["EMA_Slow"] and last["EMA_Fast"] > last["EMA_Slow"]:
            score += 1.5
            reasons.append("Bullish EMA crossover")
        elif prev["EMA_Fast"] >= prev["EMA_Slow"] and last["EMA_Fast"] < last["EMA_Slow"]:
            score -= 1.5
            reasons.append("Bearish EMA crossover")

        if "EMA_Long" in df.columns and not pd.isna(last["EMA_Long"]):
            if last["Close"] > last["EMA_Long"]:
                score += 0.7
                reasons.append("Price above EMA 200")
            else:
                score -= 0.7
                reasons.append("Price below EMA 200")

        # 2. RSI
        rsi = float(last["RSI"])
        if rsi < RSI_OVERSOLD:
            score += 1.5
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > RSI_OVERBOUGHT:
            score -= 1.5
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi > 55:
            score += 0.4
        elif rsi < 45:
            score -= 0.4

        # 3. Stochastic
        stoch_k = [c for c in df.columns if c.startswith("STOCHk")]
        stoch_d = [c for c in df.columns if c.startswith("STOCHd")]
        if stoch_k and stoch_d:
            k, d = float(last[stoch_k[0]]), float(last[stoch_d[0]])
            prev_k, prev_d = float(prev[stoch_k[0]]), float(prev[stoch_d[0]])
            if k < STOCH_OVERSOLD and d < STOCH_OVERSOLD:
                score += 1.2
                reasons.append(f"Stochastic oversold (K={k:.1f})")
            elif k > STOCH_OVERBOUGHT and d > STOCH_OVERBOUGHT:
                score -= 1.2
                reasons.append(f"Stochastic overbought (K={k:.1f})")
            if prev_k <= prev_d and k > d and k < 50:
                score += 1.0
                reasons.append("Stoch bullish cross (lower half)")
            elif prev_k >= prev_d and k < d and k > 50:
                score -= 1.0
                reasons.append("Stoch bearish cross (upper half)")

        # 4. MACD
        if "MACD" in df.columns and "MACD_Signal" in df.columns:
            macd, sig = float(last["MACD"]), float(last["MACD_Signal"])
            prev_macd, prev_sig = float(prev["MACD"]), float(prev["MACD_Signal"])
            if macd > sig and prev_macd <= prev_sig:
                score += 1.5
                reasons.append("MACD bullish crossover")
            elif macd < sig and prev_macd >= prev_sig:
                score -= 1.5
                reasons.append("MACD bearish crossover")
            elif macd > sig:
                score += 0.5
            else:
                score -= 0.5
            if "MACD_Hist" in df.columns:
                hist, prev_hist = float(last["MACD_Hist"]), float(prev["MACD_Hist"])
                if hist > 0 and hist > prev_hist:
                    score += 0.4
                    reasons.append("MACD hist expanding (bull)")
                elif hist < 0 and hist < prev_hist:
                    score -= 0.4
                    reasons.append("MACD hist expanding (bear)")

        # 5. Bollinger
        bb_l = [c for c in df.columns if "BBL" in c.upper()]
        bb_u = [c for c in df.columns if "BBU" in c.upper()]
        if bb_l and bb_u:
            lower, upper, close = float(last[bb_l[0]]), float(last[bb_u[0]]), float(last["Close"])
            if close <= lower:
                score += 1.0
                reasons.append("At/below lower Bollinger")
            elif close >= upper:
                score -= 1.0
                reasons.append("At/above upper Bollinger")

        # 6. ADX
        adx_val = None
        if "ADX" in df.columns and not pd.isna(last["ADX"]):
            adx_val = float(last["ADX"])
            if adx_val >= ADX_STRONG:
                reasons.append(f"Strong trend (ADX={adx_val:.1f})")
                if "DI_Plus" in df.columns and "DI_Minus" in df.columns:
                    if last["DI_Plus"] > last["DI_Minus"]:
                        score += 0.8
                        reasons.append("+DI > -DI")
                    else:
                        score -= 0.8
                        reasons.append("-DI > +DI")
            else:
                reasons.append(f"Weak/choppy (ADX={adx_val:.1f})")

        # 7. CCI
        if "CCI" in df.columns and not pd.isna(last["CCI"]):
            cci = float(last["CCI"])
            if cci < CCI_OVERSOLD:
                score += 1.0
                reasons.append(f"CCI oversold ({cci:.0f})")
            elif cci > CCI_OVERBOUGHT:
                score -= 1.0
                reasons.append(f"CCI overbought ({cci:.0f})")

        # 8. Williams %R
        if "WILLR" in df.columns and not pd.isna(last["WILLR"]):
            willr = float(last["WILLR"])
            if willr < WILLIAMS_OVERSOLD:
                score += 0.8
                reasons.append(f"Williams %R oversold ({willr:.1f})")
            elif willr > WILLIAMS_OVERBOUGHT:
                score -= 0.8
                reasons.append(f"Williams %R overbought ({willr:.1f})")

        # 9. SuperTrend
        if "SuperTrend_Dir" in df.columns and not pd.isna(last["SuperTrend_Dir"]):
            if int(last["SuperTrend_Dir"]) == 1:
                score += 1.2
                reasons.append("SuperTrend bullish")
            else:
                score -= 1.2
                reasons.append("SuperTrend bearish")

        # 10. Ichimoku Cloud bias
        span_a = [c for c in df.columns if "ISA" in c.upper()]
        span_b = [c for c in df.columns if "ISB" in c.upper()]
        if span_a and span_b:
            sa, sb = float(last[span_a[0]]), float(last[span_b[0]])
            price = float(last["Close"])
            cloud_top = max(sa, sb)
            cloud_bot = min(sa, sb)
            if price > cloud_top:
                score += 1.0
                reasons.append("Price above Ichimoku cloud")
            elif price < cloud_bot:
                score -= 1.0
                reasons.append("Price below Ichimoku cloud")
            else:
                reasons.append("Price inside Ichimoku cloud (caution)")

        # 11. Pivot proximity
        if "Pivot" in df.columns and not pd.isna(last["Pivot"]):
            price = float(last["Close"])
            s1 = float(last["S1"]) if not pd.isna(last.get("S1", np.nan)) else None
            r1 = float(last["R1"]) if not pd.isna(last.get("R1", np.nan)) else None
            atr = float(last["ATR"]) if not pd.isna(last.get("ATR", np.nan)) else price * 0.001
            near = atr * 0.4
            if s1 and abs(price - s1) < near:
                score += 0.6
                reasons.append("Near Pivot S1 support")
            if r1 and abs(price - r1) < near:
                score -= 0.6
                reasons.append("Near Pivot R1 resistance")

        # 12. Higher-timeframe bias alignment
        if htf_bias == "BULLISH":
            score += 1.0
            reasons.append("HTF (1h) bias BULLISH")
        elif htf_bias == "BEARISH":
            score -= 1.0
            reasons.append("HTF (1h) bias BEARISH")
        elif htf_bias == "MILD BULLISH":
            score += 0.4
        elif htf_bias == "MILD BEARISH":
            score -= 0.4

        # ---------- Decision ----------
        if score >= 5.0:
            signal, confidence = "BUY (LONG)", min(96, int(55 + score * 4.5))
        elif score <= -5.0:
            signal, confidence = "SELL (SHORT)", min(96, int(55 + abs(score) * 4.5))
        elif score >= 2.8:
            signal, confidence = "WEAK BUY", min(78, int(45 + score * 4))
        elif score <= -2.8:
            signal, confidence = "WEAK SELL", min(78, int(45 + abs(score) * 4))
        else:
            signal, confidence = "NEUTRAL / WAIT", 30
            reasons.append("No clear confluence — stay flat")

        price = float(last["Close"])
        atr = float(last["ATR"]) if not pd.isna(last.get("ATR", np.nan)) else price * 0.001

        if "BUY" in signal:
            sl = price - (SL_ATR_MULT * atr)
            tp = price + (TP_ATR_MULT * atr)
            direction = "LONG"
        elif "SELL" in signal:
            sl = price + (SL_ATR_MULT * atr)
            tp = price - (TP_ATR_MULT * atr)
            direction = "SHORT"
        else:
            sl = tp = None
            direction = "NONE"

        # Position size
        position_size = None
        if sl and direction != "NONE":
            risk_amount = self.account_balance * (self.risk_pct / 100)
            stop_distance = abs(price - sl)
            if stop_distance > 0:
                units = risk_amount / stop_distance
                position_size = f"~{units:,.0f} units (risk ${risk_amount:,.2f})"

        return {
            "signal": signal,
            "direction": direction,
            "confidence": confidence,
            "score": round(score, 2),
            "price": round(price, 5),
            "atr": round(atr, 5),
            "sl": round(sl, 5) if sl else None,
            "tp": round(tp, 5) if tp else None,
            "rsi": round(rsi, 1),
            "adx": round(adx_val, 1) if adx_val is not None else None,
            "htf_bias": htf_bias,
            "session": self.current_session(),
            "position_size": position_size,
            "reasons": reasons,
            "time": last.name.strftime("%Y-%m-%d %H:%M") if hasattr(last.name, "strftime") else str(last.name),
        }

    # ------------------------------------------------------------------
    # Analysis helpers
    # ------------------------------------------------------------------
    def analyze_pair(self, symbol: str):
        df = self.fetch_data(symbol)
        if df is None:
            return None
        df = self.add_indicators(df)
        if df.empty or len(df) < 5:
            return None
        htf = self.get_htf_bias(symbol)
        result = self.generate_signal(df, htf_bias=htf)
        result["symbol"] = symbol.replace("=X", "").replace("=F", "")
        if result["symbol"] == "GC":
            result["symbol"] = "GOLD"
        elif result["symbol"] == "SI":
            result["symbol"] = "SILVER"
        return result

    def print_analysis(self, res: dict):
        print("=" * 64)
        print(f"  PAIR: {res['symbol']}   |   {res['time']} UTC   |   Session: {res.get('session', '')}")
        print(f"  Price: {res['price']}   |   HTF Bias: {res.get('htf_bias', 'n/a')}")
        print("-" * 64)
        print(f"  SIGNAL: {res['signal']}   (Confidence: {res['confidence']}%)")
        print(f"  Score: {res['score']}   |   RSI: {res['rsi']}", end="")
        if res.get("adx") is not None:
            print(f"   |   ADX: {res['adx']}")
        else:
            print()
        if res.get("sl") and res.get("tp"):
            risk = abs(res["price"] - res["sl"])
            reward = abs(res["tp"] - res["price"])
            rr = reward / risk if risk > 0 else 0
            print(f"  Entry       : {res['price']}")
            print(f"  Stop Loss   : {res['sl']}  ({SL_ATR_MULT}× ATR)")
            print(f"  Take Profit : {res['tp']}  ({TP_ATR_MULT}× ATR)")
            print(f"  Risk:Reward : 1 : {rr:.1f}")
            if res.get("position_size"):
                print(f"  Position    : {res['position_size']}")
        print("-" * 64)
        print("  Key reasons:")
        for r in res["reasons"][:9]:
            print(f"    • {r}")
        print("=" * 64)
        print()

    def scan_all(self, send_alerts: bool = True):
        print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC]  Session: {self.current_session()}")
        print("Scanning market...\n")
        results = []
        for pair in self.pairs:
            res = self.analyze_pair(pair)
            if res:
                results.append(res)
                self.print_analysis(res)
                self.log_signal(res)
                if send_alerts:
                    self.alert_signal(res)
            else:
                print(f"  [!] Could not analyze {pair}")
            time.sleep(0.5)

        actionable = [r for r in results if "BUY" in r["signal"] or "SELL" in r["signal"]]
        if actionable:
            print("\n>>> ACTIONABLE SIGNALS (sorted by confidence) <<<")
            for r in sorted(actionable, key=lambda x: -x["confidence"]):
                print(f"  {r['symbol']:8} {r['signal']:15} Conf:{r['confidence']:3}%  HTF:{r.get('htf_bias','?'):12} Price:{r['price']}")
        else:
            print("\n>>> No high-confidence signals right now. Stay patient. <<<")
        print()

    def live_mode(self):
        print(f"LIVE mode — refresh every {POLL_SECONDS}s. Ctrl+C to stop.\n")
        try:
            while True:
                self.scan_all(send_alerts=True)
                print(f"Next scan in {POLL_SECONDS}s...")
                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            print("\nLive mode stopped.")

    def single_pair(self, symbol: str):
        if not symbol.endswith("=X") and not symbol.endswith("=F"):
            up = symbol.upper()
            if up in ("GOLD", "XAUUSD", "XAU"):
                symbol = "GC=F"
            elif up in ("SILVER", "XAGUSD", "XAG"):
                symbol = "SI=F"
            else:
                symbol = up + "=X"
        res = self.analyze_pair(symbol)
        if res:
            self.print_analysis(res)
            self.log_signal(res)
            self.alert_signal(res)
        else:
            print(f"Could not fetch or analyze {symbol}")

    def set_account(self, balance: float, risk: float = None):
        self.account_balance = balance
        if risk is not None:
            self.risk_pct = risk
        print(f"Account set to ${self.account_balance:,.0f}  |  Risk per trade: {self.risk_pct}%")

    def help(self):
        print("""
Commands:
  scan                 Analyze all pairs once
  live                 Continuous scan + Telegram alerts
  pair EURUSD          Analyze one pair (also: GOLD, SILVER)
  pairs                List tracked pairs
  add USDSEK           Add a pair
  remove USDSEK        Remove a pair
  account 5000 1       Set account balance $5000 and risk 1%
  test_telegram        Send test message
  help                 This help
  quit / exit          Exit

Features in v3.0 FINAL:
  • 30+ pairs (majors, crosses, gold, silver)
  • Multi-timeframe bias (15m + 1h)
  • Ichimoku Cloud, Pivot Points, SuperTrend
  • EMA, RSI, Stochastic, MACD, Bollinger, ATR, ADX, CCI, Williams %R
  • Session awareness (Asian / London / NY)
  • Position size calculator
  • CSV signal log (jarvis_signals_log.csv)
  • Telegram alerts for strong signals
""")

    def run(self):
        while True:
            try:
                cmd = input("Jarvis> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nShutting down. Trade safely.")
                break
            if not cmd:
                continue
            low = cmd.lower()
            if low in ("quit", "exit", "q"):
                print("Shutting down. Trade safely.")
                break
            elif low == "help":
                self.help()
            elif low == "scan":
                self.scan_all()
            elif low == "live":
                self.live_mode()
            elif low == "pairs":
                names = [p.replace("=X", "").replace("=F", "") for p in self.pairs]
                print("Tracked:", ", ".join(names))
            elif low.startswith("pair "):
                self.single_pair(cmd.split(maxsplit=1)[1])
            elif low.startswith("add "):
                symbol = cmd.split(maxsplit=1)[1].upper()
                full = symbol if symbol.endswith(("=X", "=F")) else symbol + "=X"
                if full not in self.pairs:
                    self.pairs.append(full)
                    print(f"Added {symbol}")
                else:
                    print("Already tracked")
            elif low.startswith("remove "):
                symbol = cmd.split(maxsplit=1)[1].upper()
                full = symbol if symbol.endswith(("=X", "=F")) else symbol + "=X"
                if full in self.pairs:
                    self.pairs.remove(full)
                    print(f"Removed {symbol}")
                else:
                    print("Not in list")
            elif low.startswith("account "):
                parts = cmd.split()
                try:
                    bal = float(parts[1])
                    risk = float(parts[2]) if len(parts) > 2 else None
                    self.set_account(bal, risk)
                except (ValueError, IndexError):
                    print("Usage: account 10000 1")
            elif low == "test_telegram":
                if TELEGRAM_ENABLED:
                    ok = self.send_telegram("🤖 Jarvis v3 test — Telegram OK!")
                    print("Sent." if ok else "Failed.")
                else:
                    print("Telegram not configured.")
            else:
                print("Unknown command. Type 'help'.")


if __name__ == "__main__":
    print(__doc__)
    jarvis = Jarvis()
    jarvis.run()

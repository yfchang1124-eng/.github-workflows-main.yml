import yfinance as yf
import pandas as pd
import requests
import os
import datetime

# =========================
# 🔑 Telegram 設定
# =========================
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram_msg(message):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram 未設定")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

# =========================
# 📊 追蹤清單
# =========================
tickers = {
    "BENCHMARK": ["^SOX"], 
    "GIANTS": ["MU", "005930.KS", "000660.KS"],
    "TAIWAN": ["2408.TW", "2344.TW", "2337.TW"]
}

all_symbols = list(set(sum(tickers.values(), [])))

# =========================
# 📈 進階技術指標計算
# =========================
def analyze_advanced(price_df, symbol):
    s = price_df[symbol].dropna()
    if len(s) < 30: return None

    # --- 1. 布林通道 (BB) ---
    ma20 = s.rolling(20).mean()
    std20 = s.rolling(20).std()
    upper_band = ma20 + (std20 * 2)
    lower_band = ma20 - (std20 * 2)

    # --- 2. MACD ---
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    
    # --- 3. RSI ---
    delta = s.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + gain/loss))

    # 取最新值
    last_p = s.iloc[-1]
    last_macd = macd_line.iloc[-1]
    prev_macd = macd_line.iloc[-2]
    last_sig = signal_line.iloc[-1]
    prev_sig = signal_line.iloc[-2]

    # 訊號判斷
    bb_status = "🔴 超漲" if last_p > upper_band.iloc[-1] else "🟢 超跌" if last_p < lower_band.iloc[-1] else "⚪ 正常"
    
    macd_signal = "⚡ 金叉" if prev_macd < prev_sig and last_macd > last_sig else \
                  "💀 死叉" if prev_macd > prev_sig and last_macd < last_sig else "⚖️ 穩定"

    return {
        "p": last_p,
        "rsi": rsi.iloc[-1],
        "bb": bb_status,
        "macd": macd_signal,
        "mtd": (last_p / s.iloc[-20]) - 1,
        "trend": "📈 多頭" if last_p > ma20.iloc[-1] else "📉 修正"
    }

def fetch_data():
    df = yf.download(all_symbols, period="6mo", group_by="column", threads=False)
    if df.empty: return None
    return df["Adj Close"] if "Adj Close" in df.columns.get_level_values(0) else df["Close"]

def analyze():
    price_df = fetch_data()
    if price_df is None: return

    report = f"🤖 <b>Memory AI 終極監控</b>\n"
    report += f"📅 {datetime.date.today()}\n"
    report += "━━━━━━━━━━━━━━━━━━\n"

    # 分析各板塊
    for category, name in [("BENCHMARK", "🏛️ 基準 (費半)"), ("GIANTS", "🏭 國際巨頭"), ("TAIWAN", "🇹🇼 台股觀測")]:
        report += f"<b>{name}</b>\n"
        for s in tickers[category]:
            res = analyze_advanced(price_df, s)
            if not res: continue
            
            # 亮點整合
            indicators = []
            if res['macd'] != "⚖️ 穩定": indicators.append(res['macd'])
            if res['bb'] != "⚪ 正常": indicators.append(res['bb'])
            ind_str = f"({', '.join(indicators)})" if indicators else ""
            
            report += f"• {s}: {res['p']:.1f} | RSI:{res['rsi']:.0f} {ind_str}\n"
        report += "\n"

    # 🎯 AI 策略小結論
    sox = analyze_advanced(price_df, "^SOX")
    mu = analyze_advanced(price_df, "MU")
    
    report += "━━━━━━━━━━━━━━━━━━\n💡 <b>操作策略：</b>\n"
    if sox['macd'] == "⚡ 金叉" or mu['macd'] == "⚡ 金叉":
        report += "✨ 趨勢轉強，空手者可關注分批佈局。"
    elif sox['bb'] == "🔴 超漲" or mu['rsi'] > 75:
        report += "⚠️ 短線過熱，正乖離過大，不宜追高。"
    elif sox['trend'] == "📈 多頭" and mu['trend'] == "📈 多頭":
        report += "💪 記憶體族群強勢，續抱為主。"
    else:
        report += "💤 目前波動較小，等待明顯轉折訊號。"

    send_telegram_msg(report)

if __name__ == "__main__":
    analyze()

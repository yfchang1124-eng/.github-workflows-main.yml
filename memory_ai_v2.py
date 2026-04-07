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
# 📊 擴充追蹤清單 (加入費半 SOX)
# =========================
tickers = {
    "BENCHMARK": ["^SOX"], # 費城半導體指數
    "DRAM_PROXY": ["MU", "WDC"],
    "GIANTS": ["MU", "005930.KS", "000660.KS"],
    "TAIWAN": ["2408.TW", "2344.TW", "2337.TW"]
}

all_symbols = list(set(sum(tickers.values(), [])))

# =========================
# 📈 技術指標計算工具
# =========================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def fetch_data():
    # 抓取 3 個月的資料以利計算均線與 RSI
    df = yf.download(all_symbols, period="3mo", group_by="column", threads=False)
    if df.empty: return None
    price_df = df["Adj Close"] if "Adj Close" in df.columns.get_level_values(0) else df["Close"]
    volume_df = df["Volume"]
    return price_df.dropna(how="all"), volume_df

# =========================
# 🧠 進階分析邏輯
# =========================
def analyze_advanced(price_df, volume_df, symbol):
    s = price_df[symbol].dropna()
    v = volume_df[symbol].dropna()
    if len(s) < 20: return None

    last_price = s.iloc[-1]
    ma5 = s.rolling(5).mean().iloc[-1]
    ma20 = s.rolling(20).mean().iloc[-1]
    rsi = calculate_rsi(s).iloc[-1]
    
    # 乖離率 (與20日線距離)
    bias = ((last_price - ma20) / ma20) * 100
    
    # 量價偵測
    v_sma = v.rolling(5).mean().iloc[-1]
    v_ratio = v.iloc[-1] / v_sma
    
    # 趨勢判斷
    if last_price > ma5 > ma20:
        trend = "🔥 多頭排列"
    elif last_price < ma5 < ma20:
        trend = "❄️ 空頭排列"
    else:
        trend = "⚖️ 區間震盪"

    return {
        "price": last_price,
        "mtd": (last_price / s.iloc[-20]) - 1, # 近 20 日漲幅
        "rsi": rsi,
        "bias": bias,
        "v_ratio": v_ratio,
        "trend": trend
    }

def analyze():
    data = fetch_data()
    if not data: return
    price_df, volume_df = data
    
    # 1. 基準點：費半指數
    sox = analyze_advanced(price_df, volume_df, "^SOX")
    
    report = f"🚀 <b>記憶體進階監控報告</b>\n"
    report += f"📅 {datetime.date.today()}\n"
    report += "━━━━━━━━━━━━━━━━━━\n"
    
    if sox:
        report += f"🏛️ <b>費半指數 (^SOX)</b>\n趨勢: {sox['trend']}\nRSI: {sox['rsi']:.1f} | 20D漲跌: {sox['mtd']*100:+.1f}%\n\n"

    # 2. 核心巨頭
    report += "🏭 <b>記憶體三巨頭 (美/韓)</b>\n"
    for s in tickers["GIANTS"]:
        res = analyze_advanced(price_df, volume_df, s)
        if res:
            emoji = "🔴" if res['rsi'] > 70 else "🟢" if res['rsi'] < 30 else "⚪"
            report += f"{emoji} {s}: {res['price']:.1f} ({res['mtd']*100:+.1f}%) | RSI: {res['rsi']:.0f}\n"
    
    report += "\n"

    # 3. 台股深度分析
    report += "🇹🇼 <b>台股記憶體族群</b>\n"
    for s in tickers["TAIWAN"]:
        res = analyze_advanced(price_df, volume_df, s)
        if not res: continue
        
        # 深度點評
        comment = ""
        if res['v_ratio'] > 1.8: comment = " (⚠️ 爆量)"
        if res['rsi'] > 75: comment = " (❌ 過熱)"
        if res['rsi'] < 30: comment = " (✅ 超跌)"
        
        report += f"• {s}\n  狀態: {res['trend']}{comment}\n"
        report += f"  乖離: {res['bias']:+.1f}% | RSI: {res['rsi']:.1f}\n"

    report += "━━━━━━━━━━━━━━━━━━\n"
    
    # 4. 投資決策輔助
    score = 0
    if sox and sox['trend'] == "🔥 多頭排列": score += 2
    mu_res = analyze_advanced(price_df, volume_df, "MU")
    if mu_res and mu_res['rsi'] < 65: score += 1
    
    status = "🌟 強力看多" if score >= 3 else "🤔 觀望為宜" if score >= 1 else "⚠️ 減碼風險"
    report += f"💡 <b>綜合評估：{status}</b>"

    print(report)
    send_telegram_msg(report)

if __name__ == "__main__":
    analyze()

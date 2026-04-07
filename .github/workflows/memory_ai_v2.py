import yfinance as yf
import pandas as pd
import requests
import os
import datetime

# =========================
# 🔑 Telegram 設定（用 GitHub Secrets）
# =========================
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram_msg(message):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram 未設定")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

# =========================
# 📊 股票池（修正ETF問題）
# =========================
tickers = {
    "DRAM_PROXY": ["MU", "WDC"],  # 👉 取代假ETF
    "GIANTS": ["MU", "005930.KS", "000660.KS"],
    "TAIWAN": ["2408.TW", "2344.TW", "2337.TW"]
}

all_symbols = list(set(sum(tickers.values(), [])))

# =========================
# 📊 抓資料（穩定版）
# =========================
def fetch_data():
    df = yf.download(all_symbols, period="1mo", group_by="column", threads=False)

    if df.empty:
        return None

    if "Adj Close" in df.columns.get_level_values(0):
        price_df = df["Adj Close"]
    else:
        price_df = df["Close"]

    volume_df = df["Volume"]

    return price_df.dropna(how="all"), volume_df

# =========================
# 📈 基本分析
# =========================
def get_data_safe(price_df, symbol):
    if symbol not in price_df.columns:
        return None

    s = price_df[symbol].dropna()
    if len(s) < 5:
        return None

    first = s.iloc[0]
    last = s.iloc[-1]

    mtd = (last / first) - 1
    ma20 = s.rolling(20).mean().iloc[-1] if len(s) >= 20 else s.mean()
    trend = "📈 多頭" if last > ma20 else "📉 修正"

    return {
        "mtd": mtd,
        "last": last,
        "trend": trend
    }

# =========================
# 🔥 主力出貨偵測（關鍵）
# =========================
def detect_distribution(price_df, volume_df, symbol):
    try:
        p = price_df[symbol].dropna()
        v = volume_df[symbol].dropna()

        if len(p) < 5:
            return 0

        p5 = p.iloc[-5:]
        v5 = v.iloc[-5:]

        price_change = (p5.iloc[-1] - p5.iloc[0]) / p5.iloc[0]
        volume_ratio = v5.iloc[-1] / v5.mean()

        # 🔥 爆量不漲 = 出貨
        if volume_ratio > 1.5 and price_change <= 0:
            return -1

        # 🔥 量價齊揚 = 主升段
        if volume_ratio > 1.2 and price_change > 0:
            return 1

    except:
        return 0

    return 0

# =========================
# 💰 資金流 proxy（免費版）
# =========================
def flow_proxy(price_df, symbol):
    try:
        s = price_df[symbol].dropna()
        if len(s) < 5:
            return 0

        recent = s.iloc[-5:]
        up_days = sum(recent.diff() > 0)

        if up_days >= 4:
            return 1
        elif up_days <= 1:
            return -1

    except:
        return 0

    return 0

# =========================
# 🧠 主分析
# =========================
def analyze():
    data = fetch_data()
    if not data:
        send_telegram_msg("❌ 資料抓取失敗")
        return

    price_df, volume_df = data

    report = "🚀 <b>記憶體AI監控 V2</b>\n\n"
    score = 0

    # =========================
    # 🌍 全球 DRAM proxy
    # =========================
    dram_scores = []
    for s in tickers["DRAM_PROXY"]:
        d = get_data_safe(price_df, s)
        if d:
            dram_scores.append(d["mtd"])

    dram_avg = sum(dram_scores)/len(dram_scores) if dram_scores else 0

    report += f"🌍 DRAM Proxy 平均: {dram_avg*100:+.2f}%\n"

    if dram_avg > 0.05:
        score += 1

    # =========================
    # 🌍 三巨頭
    # =========================
    giants = []
    for s in tickers["GIANTS"]:
        d = get_data_safe(price_df, s)
        if d:
            giants.append(d["mtd"])

    giant_avg = sum(giants)/len(giants) if giants else 0
    report += f"🏭 三巨頭均值: {giant_avg*100:+.2f}%\n\n"

    if giant_avg > 0.05:
        score += 1

    # =========================
    # 🇹🇼 台股
    # =========================
    tw_report = ""
    tw_mtd_list = []

    for s in tickers["TAIWAN"]:
        d = get_data_safe(price_df, s)
        if not d:
            continue

        flow = flow_proxy(price_df, s)
        dist = detect_distribution(price_df, volume_df, s)

        tw_mtd_list.append(d["mtd"])

        tw_report += f"• {s} {d['mtd']*100:+.2f}% {d['trend']} "

        if dist == -1:
            tw_report += "⚠️出貨"
            score -= 2
        elif flow == 1:
            tw_report += "🔥強勢"
            score += 1

        tw_report += "\n"

    report += "🇹🇼 台股觀測：\n" + tw_report + "\n"

    # =========================
    # 🔥 強弱排序（很重要）
    # =========================
    ranking = []
    for s in all_symbols:
        d = get_data_safe(price_df, s)
        if d:
            ranking.append((s, d["mtd"]))

    ranking = sorted(ranking, key=lambda x: x[1], reverse=True)

    report += "🏆 強勢TOP3：\n"
    for r in ranking[:3]:
        report += f"{r[0]} {r[1]*100:+.2f}%\n"

    report += "\n"

    # =========================
    # 🎯 最終判斷
    # =========================
    if score >= 3:
        status = "🔥 <b>主升段</b>"
    elif score <= -2:
        status = "⚠️ <b>高檔出貨</b>"
    else:
        status = "⚖️ <b>震盪</b>"

    report += f"📊 總分: {score}\n狀態: {status}"

    print(report)
    send_telegram_msg(report)

# =========================
# 🚀 執行
# =========================
if __name__ == "__main__":
    analyze()

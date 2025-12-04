# estimate.py (GitHub Actions版・最新構成銘柄反映)

import yfinance as yf
import pandas as pd
import requests
import json
from io import StringIO
from datetime import datetime, timedelta
import traceback
import os

pd.set_option('display.float_format', '{:,.2f}'.format)

# ======================================
# 1. Daiwa CSV
# ======================================
def fetch_daiwa_csv_last_row(fund_code: str) -> pd.Series:
    url = f"https://www.daiwa-am.co.jp/funds/detail/csv_out.php?code={fund_code}&type=1"
    res = requests.get(url)
    df = pd.read_csv(StringIO(res.content.decode("shift_jis")))
    return df.iloc[-1]

# ======================================
# 2. 最新 Weights（みんかぶ構成比率を使用）
# ======================================
WEIGHTS = {
    "CRWD": 0.1110,   # クラウドストライク
    "NVDA": 0.1100,   # エヌビディア
    "AAPL": 0.1050,   # アップル
    "GOOGL": 0.1040,  # アルファベットA
    "AVGO": 0.1000,   # ブロードコム
    "MSFT": 0.0950,   # マイクロソフト
    "NOW": 0.0910,    # サービスナウ
    "AMZN": 0.0890,   # アマゾン
    "NFLX": 0.0820,   # ネットフリックス
    "META": 0.0790    # メタ
}

TICKERS = list(WEIGHTS.keys())

# ======================================
# 3. Market Data
# ======================================
def get_prices_and_fx():
    end = datetime.now()
    start = end - timedelta(days=7)

    data = yf.download(TICKERS + ["USDJPY=X"], start=start, end=end, auto_adjust=False)

    prices = data["Close"][TICKERS].ffill()
    fx = data["Close"]["USDJPY=X"].ffill()

    return prices, fx

# ======================================
# 4. Estimate Shares
# ======================================
def estimate_shares(previous_nav, previous_base_price, prev_prices, prev_fx):
    units = previous_nav / previous_base_price
    shares = {}

    for ticker, weight in WEIGHTS.items():
        usd_value = (previous_nav * weight) / prev_fx
        shares[ticker] = usd_value / prev_prices[ticker]

    return shares, units

# ======================================
# 5. NAV Estimation
# ======================================
def calculate_today_nav():
    last_row = fetch_daiwa_csv_last_row("3346")
    previous_base_price = float(last_row["基準価額"])
    previous_nav = float(last_row["純資産総額"])

    prices, fx = get_prices_and_fx()

    prev_prices = prices.iloc[-2]
    last_prices = prices.iloc[-1]

    prev_fx = float(fx.iloc[-2])
    last_fx = float(fx.iloc[-1])

    shares, units = estimate_shares(previous_nav, previous_base_price, prev_prices, prev_fx)

    total_usd = sum(shares[t] * last_prices[t] for t in TICKERS)
    total_jpy = total_usd * last_fx

    estimated_base_price = total_jpy / units

    msg = []
    msg.append("📈【FANG+ 推定基準価額（最新構成銘柄版）】")
    msg.append(f"前日基準価額: {previous_base_price:,.2f} 円")
    msg.append(f"推定基準価額: {estimated_base_price:,.2f} 円")
    diff = estimated_base_price - previous_base_price
    msg.append(f"前日比: {diff:,.2f} 円 ({(diff/previous_base_price)*100:.2f}%)")
    msg.append("")
    msg.append(f"USDJPY: {prev_fx:.2f} → {last_fx:.2f}")

    msg.append("\n保有株数推定：")
    for t in TICKERS:
        msg.append(f"{t}: {shares[t]:,.1f}株")

    return "\n".join(msg)

# ======================================
# 6. LINE Messaging API
# ======================================
def send_line_message(text: str):

    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_TO_USER_ID")

    if not token or not user_id:
        print("❌ LINE の環境変数が設定されていません")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}]
    }

    r = requests.post(url, headers=headers, data=json.dumps(body))
    print("LINE API レスポンス:", r.status_code, r.text)

# ======================================
# 7. Main
# ======================================
def main():
    try:
        msg = calculate_today_nav()
        print(msg)
        send_line_message(msg)

    except Exception as e:
        error_text = "⚠️ NAV推定でエラー\n\n" + traceback.format_exc()
        print(error_text)
        send_line_message(error_text)

if __name__ == "__main__":
    main()

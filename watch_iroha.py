import os, time, json, re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

URL  = os.getenv("TARGET_URL", "https://official-goods-store.jp/sumika/v2/product/detail/SMK272")
TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
STATE_FILE = ".sumika_state.json"
HEADERS = {
    # ブロック回避のため簡単なUAを付ける
    "User-Agent": "Mozilla/5.0 (compatible; StockWatch/1.0; +https://example.local)"
}

def fetch_html():
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

def is_sold_out(html: str) -> bool:
    """指定のクラスに限定してSOLD OUTを探索。fallbackで全体からも検出。"""
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find("div", class_="ogs-v2-text weight-bold color-danger align-center")
    txts = []
    if div:
        txts.append(div.get_text(strip=True))
    txts.append(soup.get_text(" ", strip=True))  # fallback
    for t in txts:
        if re.search(r"\bSOLD\s*OUT\b", t, flags=re.IGNORECASE):
            return True
    return False

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def line_broadcast(text: str):
    """友だち全員へ一斉送信。ユーザーID不要・Webhook不要の最小構成。"""
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [{"type": "text", "text": text}]
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    try:
        resp.raise_for_status()
    except Exception as e:
        # エラー内容はログに出すだけ（監視は続行）
        print("LINE send error:", resp.status_code, resp.text)
        raise

def check_once():
    if not TOKEN:
        raise SystemExit("ERROR: LINE_CHANNEL_ACCESS_TOKEN is not set.")
    state = load_state()
    last = state.get("sold_out")

    html = fetch_html()
    now_soldout = is_sold_out(html)

    if last is True and now_soldout is False:
        msg = f"在庫復活！\n{URL}"
        line_broadcast(msg)
        print("Notified:", msg)

    state["sold_out"] = now_soldout
    save_state(state)
    print("checked. sold_out=", now_soldout)

def main_loop():
    if not TOKEN:
        raise SystemExit("ERROR: LINE_CHANNEL_ACCESS_TOKEN is not set.")
    state = load_state()
    last = state.get("sold_out")
    while True:
        try:
            html = fetch_html()
            now_soldout = is_sold_out(html)
            if last is True and now_soldout is False:
                msg = f"在庫復活！\n{URL}"
                line_broadcast(msg)
                print("Notified:", msg)
            last = now_soldout
            state["sold_out"] = now_soldout
            save_state(state)
            print("checked. sold_out=", now_soldout)
        except Exception as e:
            print("check error:", e)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    run_once = os.getenv("RUN_ONCE", "").lower() in ("1", "true", "yes")
    if run_once:
        check_once()
    else:
        main_loop()

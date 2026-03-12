import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

SITES = [
    "https://app-marko.damaju.com.co",
    "https://damaju.com.co",
    "https://intercom.damaju.com.co/",
    "https://luma.damaju.com.co",
    "https://mando.damaju.com.co",
    "https://marko.damaju.com.co",
    "https://ops.damaju.com.co",
    "https://tracker.damaju.com.co",
]

TIMEOUT_SECONDS = 10
MAX_HISTORY = 288
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DamajuStatusMonitor/1.0)"}

STATUS_FILE = Path(__file__).parent / "status.json"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_status():
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"last_updated": now_iso(), "services": {}}


def save_status(data):
    STATUS_FILE.write_text(json.dumps(data, indent=2))


def service_name(url):
    host = url.replace("https://", "").replace("http://", "").rstrip("/")
    return host.split(".")[0].capitalize()


def check_site(url):
    ts = now_iso()
    try:
        start = time.monotonic()
        resp = requests.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=True, headers=HEADERS)
        elapsed_ms = round((time.monotonic() - start) * 1000)
        up = 200 <= resp.status_code < 300
        return {"up": up, "status_code": resp.status_code, "response_time": elapsed_ms, "timestamp": ts}
    except requests.exceptions.Timeout:
        return {"up": False, "status_code": 0, "response_time": TIMEOUT_SECONDS * 1000, "timestamp": ts, "error": "timeout"}
    except requests.exceptions.RequestException as exc:
        return {"up": False, "status_code": 0, "response_time": 0, "timestamp": ts, "error": str(exc)[:120]}


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except Exception as exc:
        print(f"Telegram error: {exc}")


def build_alert(url, result, went_down):
    icon = "🔴" if went_down else "🟢"
    label = service_name(url)
    status = "DOWN" if went_down else "BACK UP"
    code = result.get("status_code", 0)
    ms = result.get("response_time", 0)
    err = result.get("error", "")
    detail = f"HTTP {code} · {ms}ms" if not err else f"Error: {err}"
    return f"{icon} <b>Damaju Status Alert</b>\nService: <b>{label}</b>\nURL: {url}\nStatus: <b>{status}</b>\nDetail: {detail}\nTime: {result['timestamp']}"


def main():
    data = load_status()
    services = data.setdefault("services", {})
    for url in SITES:
        print(f"Checking {url}")
        result = check_site(url)
        print(f"  up={result['up']} code={result['status_code']} ms={result['response_time']}")
        entry = services.setdefault(url, {"current": None, "history": []})
        previous = entry.get("current")
        if previous is not None:
            if previous.get("up", True) and not result["up"]:
                send_telegram(build_alert(url, result, went_down=True))
            elif not previous.get("up", True) and result["up"]:
                send_telegram(build_alert(url, result, went_down=False))
        entry["current"] = result
        entry["history"].append(result)
        if len(entry["history"]) > MAX_HISTORY:
            entry["history"] = entry["history"][-MAX_HISTORY:]
    data["last_updated"] = now_iso()
    save_status(data)
    print(f"Done. Updated at {data['last_updated']}")


if __name__ == "__main__":
    main()

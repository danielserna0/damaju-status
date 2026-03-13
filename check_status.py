import json
import os
import time
from datetime import datetime, timezone, timedelta
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
MAX_HISTORY = 2016
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
    first_error = None
    
    for attempt in range(2):
        try:
            start = time.monotonic()
            resp = requests.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=True, headers=HEADERS)
            elapsed_ms = round((time.monotonic() - start) * 1000)
            up = resp.status_code < 500
            
            if attempt == 1 and first_error:
                print(f"  ✅ Recuperado en segundo intento después de: {first_error}")
            
            return {"up": up, "status_code": resp.status_code, "response_time": elapsed_ms, "timestamp": ts}
            
        except requests.exceptions.Timeout:
            first_error = first_error or f"timeout (intento {attempt + 1})"
            if attempt == 0:
                time.sleep(15)
            else:
                return {"up": False, "status_code": 0, "response_time": TIMEOUT_SECONDS * 1000, "timestamp": ts, "error": "timeout"}
                
        except requests.exceptions.RequestException as exc:
            first_error = first_error or f"{type(exc).__name__}: {str(exc)[:50]} (intento {attempt + 1})"
            if attempt == 0:
                time.sleep(15)
            else:
                return {"up": False, "status_code": 0, "response_time": 0, "timestamp": ts, "error": str(exc)[:120]}

def send_telegram_with_button(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [[
            {"text": "🔍 Revisar", "url": "https://status.damaju.com.co/"}
        ]]
    }
    
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": message, 
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }, timeout=10)
    except Exception as exc:
        print(f"Telegram error: {exc}")

def build_alert(down_sites, timestamp):
    if not down_sites:
        return None
    
    icon = "🔴"
    count = len(down_sites)
    
    # Formatear lista de sitios
    if count <= 3:
        sites_list = ", ".join([service_name(url).replace('.damaju.com.co', '').replace('.com.co', '') for url in down_sites])
    else:
        first_three = ", ".join([service_name(url).replace('.damaju.com.co', '').replace('.com.co', '') for url in down_sites[:3]])
        sites_list = f"{first_three} y {count - 3} más..."
    
    # Formatear fecha hora Colombia
    try:
        dt_colombia = datetime.fromisoformat(timestamp).astimezone(timezone(timedelta(hours=-5)))
        time_str = dt_colombia.strftime('%d/%m %H:%M')
    except:
        time_str = timestamp
    
    return f"{icon} Damaju Status\nCAÍDO: {sites_list}\n{time_str}"

def main():
    print(f"[{now_iso()}] 🚀 Iniciando monitoreo de {len(SITES)} servicios")
    data = load_status()
    services = data.setdefault("services", {})
    
    confirmed_down_sites = []

    for url in SITES:
        print(f"\n[{now_iso()}] 🔍 Revisando {url}")
        result = check_site(url)
        print(f"  📊 Estado: up={result['up']} code={result['status_code']} ms={result['response_time']}")

        entry = services.setdefault(url, {"current": None, "history": [], "pending_down": False})
        previous = entry.get("current")
        pending_down = entry.get("pending_down", False)

        print(f"  📋 Anterior: up={previous.get('up') if previous else 'None'} | pending_down={pending_down}")

        if previous is not None:
            if result["up"]:
                # Está arriba ahora
                if not previous.get("up", True):
                    # Estaba DOWN confirmado → registrar recuperación
                    downtime = datetime.fromisoformat(result['timestamp']) - datetime.fromisoformat(previous['timestamp'])
                    print(f"  ⏰ Downtime: {downtime.total_seconds():.1f}s")
                    print(f"  🟢 RECUPERADO (downtime: {downtime.total_seconds():.1f}s)")
                        
                elif pending_down:
                    # Estaba pending_down pero se recuperó → no alertar, solo limpiar
                    print(f"  ✅ Recuperado antes de confirmación, sin alerta")
                entry["pending_down"] = False
            else:
                # Está abajo ahora
                if pending_down:
                    # Ya falló el run anterior también → confirmar DOWN
                    print(f"  🔴 CONFIRMADO DOWN (2 ejecuciones consecutivas)")
                    confirmed_down_sites.append(url)
                    entry["pending_down"] = False
                elif previous.get("up", True):
                    # Primera vez que falla → marcar pending, NO alertar todavía
                    print(f"  ⚠️ Primer fallo → marcando pending_down, esperar siguiente ejecución")
                    entry["pending_down"] = True
                # Si previous ya era down y pending_down=False, ya se alertó antes, no hacer nada

        entry["current"] = result
        entry["history"].append(result)
        if len(entry["history"]) > MAX_HISTORY:
            entry["history"] = entry["history"][-MAX_HISTORY:]

    # Enviar alerta grupal si hay sitios confirmados caídos
    if confirmed_down_sites:
        alert_message = build_alert(confirmed_down_sites, now_iso())
        if alert_message:
            print(f"\n📢 ENVIANDO ALERTA GRUPAL: {len(confirmed_down_sites)} sitios caídos")
            send_telegram_with_button(alert_message)
    else:
        print(f"\n✅ Todos los servicios operativos, sin alertas")

    data["last_updated"] = now_iso()
    save_status(data)
    print(f"\n[{now_iso()}] ✅ Monitoreo completado. Actualizado: {data['last_updated']}")

if __name__ == "__main__":
    main()

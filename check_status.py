import json
import os
import time
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# Cargar configuración
CONFIG_FILE = Path(__file__).parent / "config.json"
try:
    with open(CONFIG_FILE) as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    print(f"⚠️ config.json no encontrado, usando valores por defecto")
    CONFIG = {
        "sites": [
            "https://app-marko.damaju.com.co",
            "https://damaju.com.co",
            "https://intercom.damaju.com.co/",
            "https://luma.damaju.com.co",
            "https://mando.damaju.com.co",
            "https://marko.damaju.com.co",
            "https://ops.damaju.com.co",
            "https://tracker.damaju.com.co",
        ],
        "timeout_seconds": 60,
        "max_history": 2016,
        "user_agent": "Mozilla/5.0 (compatible; DamajuStatusMonitor/1.0)",
        "dashboard_url": "https://status.damaju.com.co/"
    }

SITES = CONFIG["sites"]
TIMEOUT_SECONDS = CONFIG["timeout_seconds"]
MAX_HISTORY = CONFIG["max_history"]
HEADERS = {"User-Agent": CONFIG["user_agent"]}
STATUS_FILE = Path(__file__).parent / "status.json"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def load_status():
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text())
        except json.JSONDecodeError as e:
            print(f"⚠️ Error al cargar status.json: {e}")
            print(f"⚠️ Creando backup y reiniciando desde cero")
            try:
                backup_file = STATUS_FILE.parent / f"status.json.backup.{int(time.time())}"
                STATUS_FILE.rename(backup_file)
                print(f"✅ Backup guardado en: {backup_file}")
            except Exception as backup_error:
                print(f"❌ Error al crear backup: {backup_error}")
        except Exception as e:
            print(f"❌ Error inesperado al cargar status.json: {e}")
    return {"last_updated": now_iso(), "services": {}}

def save_status(data):
    try:
        # Validar que data es serializable
        json_str = json.dumps(data, indent=2)
        STATUS_FILE.write_text(json_str)
    except (TypeError, ValueError) as e:
        print(f"❌ Error al serializar datos: {e}")
        raise
    except IOError as e:
        print(f"❌ Error al escribir status.json: {e}")
        raise
    except Exception as e:
        print(f"❌ Error inesperado al guardar status.json: {e}")
        raise

def service_name(url):
    host = url.replace("https://", "").replace("http://", "").rstrip("/")
    return host.split(".")[0].capitalize()

def calculate_metrics(history):
    """Calcula métricas avanzadas de uptime"""
    if not history:
        return {
            "uptime_24h": None,
            "uptime_7d": None,
            "uptime_30d": None,
            "avg_response_time": None,
            "incidents_count": 0,
            "mttr": None
        }
    
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Filtrar por períodos
    last_24h = [h for h in history if h and datetime.fromisoformat(h['timestamp']) > day_ago]
    last_7d = [h for h in history if h and datetime.fromisoformat(h['timestamp']) > week_ago]
    last_30d = [h for h in history if h and datetime.fromisoformat(h['timestamp']) > month_ago]
    
    # Calcular uptime
    uptime_24h = (sum(1 for h in last_24h if h.get('up')) / len(last_24h) * 100) if last_24h else None
    uptime_7d = (sum(1 for h in last_7d if h.get('up')) / len(last_7d) * 100) if last_7d else None
    uptime_30d = (sum(1 for h in last_30d if h.get('up')) / len(last_30d) * 100) if last_30d else None
    
    # Response time promedio
    valid_times = [h['response_time'] for h in last_24h if h.get('up') and h.get('response_time', 0) > 0]
    avg_response = sum(valid_times) / len(valid_times) if valid_times else None
    
    # Contar incidentes (transiciones de up a down)
    incidents = 0
    for i in range(1, len(last_7d)):
        if last_7d[i-1].get('up') and not last_7d[i].get('up'):
            incidents += 1
    
    # MTTR (Mean Time To Recovery) - promedio de tiempo de recuperación
    recovery_times = []
    down_start = None
    for h in last_7d:
        if not h.get('up') and down_start is None:
            down_start = datetime.fromisoformat(h['timestamp'])
        elif h.get('up') and down_start is not None:
            recovery_time = (datetime.fromisoformat(h['timestamp']) - down_start).total_seconds()
            recovery_times.append(recovery_time)
            down_start = None
    
    mttr = sum(recovery_times) / len(recovery_times) if recovery_times else None
    
    return {
        "uptime_24h": round(uptime_24h, 2) if uptime_24h else None,
        "uptime_7d": round(uptime_7d, 2) if uptime_7d else None,
        "uptime_30d": round(uptime_30d, 2) if uptime_30d else None,
        "avg_response_time": round(avg_response) if avg_response else None,
        "incidents_count": incidents,
        "mttr": round(mttr) if mttr else None
    }

def check_site(url):
    ts = now_iso()

    for attempt in range(2):
        try:
            start = time.monotonic()
            resp = requests.get(url, timeout=30, allow_redirects=True, headers=HEADERS)
            elapsed_ms = round((time.monotonic() - start) * 1000)
            return {"up": True, "status_code": resp.status_code, "response_time": elapsed_ms, "timestamp": ts}

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == 0:
                # Reintentar una vez para DNS/conexión transitoria
                time.sleep(5)
                continue
            # Fallo en ambos intentos
            error_type = "timeout" if isinstance(exc, requests.exceptions.Timeout) else "connection_error"
            return {"up": False, "status_code": 0, "response_time": 30000, "timestamp": ts, "error": error_type}

        except requests.exceptions.RequestException as exc:
            # Para otros errores (HTTP errors, etc), no reintentar
            return {"up": False, "status_code": 0, "response_time": 0, "timestamp": ts, "error": str(exc)[:120]}

def send_telegram_with_button(message):
    print(f"  📱 Intentando enviar Telegram: {TELEGRAM_TOKEN[:10] if TELEGRAM_TOKEN else 'NONE'}...{TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else 'NONE'}")
    
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"  ❌ Telegram no configurado: TOKEN={'SET' if TELEGRAM_TOKEN else 'NOT SET'}, CHAT_ID={'SET' if TELEGRAM_CHAT_ID else 'NOT SET'}")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [[
            {"text": "🔍 Revisar", "url": CONFIG.get("dashboard_url", "https://status.damaju.com.co/")}
        ]]
    }
    
    try:
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": message, 
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }, timeout=10)
        
        if response.status_code == 200:
            print(f"  ✅ Telegram enviado exitosamente")
        else:
            print(f"  ❌ Error Telegram: HTTP {response.status_code} - {response.text[:100]}")
            
    except Exception as exc:
        print(f"  ❌ Telegram error: {exc}")

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

def build_recovery_alert(recovered_sites, timestamp):
    if not recovered_sites:
        return None
    
    icon = "🟢"
    count = len(recovered_sites)
    
    # Formatear lista de sitios
    if count <= 3:
        sites_list = ", ".join([service_name(url).replace('.damaju.com.co', '').replace('.com.co', '') for url in recovered_sites])
    else:
        first_three = ", ".join([service_name(url).replace('.damaju.com.co', '').replace('.com.co', '') for url in recovered_sites[:3]])
        sites_list = f"{first_three} y {count - 3} más..."
    
    # Formatear fecha hora Colombia
    try:
        dt_colombia = datetime.fromisoformat(timestamp).astimezone(timezone(timedelta(hours=-5)))
        time_str = dt_colombia.strftime('%d/%m %H:%M')
    except:
        time_str = timestamp
    
    return f"{icon} Damaju Status\nRECUPERADO: {sites_list}\n{time_str}"

def main():
    print(f"[{now_iso()}] 🚀 Iniciando monitoreo de {len(SITES)} servicios")
    data = load_status()
    services = data.setdefault("services", {})

    confirmed_down_sites = []
    recovered_sites = []

    for url in SITES:
        print(f"\n[{now_iso()}] 🔍 Revisando {url}")
        result = check_site(url)
        print(f"  📊 Estado: up={result['up']} code={result['status_code']} ms={result['response_time']}")

        entry = services.setdefault(url, {"current": None, "history": [], "alert_sent": False})
        previous = entry.get("current")
        alert_sent = entry.get("alert_sent", False)

        print(f"  📋 Anterior: up={previous.get('up') if previous else 'None'} | alert_sent={alert_sent}")

        if previous is not None:
            prev_up = previous.get("up", True)
            curr_up = result["up"]

            if curr_up and not prev_up:
                # Transición DOWN → UP: Solo alertar si ya se había alertado de caída
                if alert_sent:
                    downtime = datetime.fromisoformat(result['timestamp']) - datetime.fromisoformat(previous['timestamp'])
                    print(f"  ⏰ Downtime: {downtime.total_seconds():.1f}s")
                    print(f"  🟢 RECUPERADO (downtime: {downtime.total_seconds():.1f}s)")
                    recovered_sites.append(url)
                    entry["alert_sent"] = False
                else:
                    # Se recuperó pero nunca se alertó de caída → no alertar recuperación
                    print(f"  ✅ Recuperado, pero no se había enviado alerta de caída")
                    entry["alert_sent"] = False

            elif not curr_up and prev_up:
                # Transición UP → DOWN: Marcar para alertar en siguiente ciclo
                print(f"  ⚠️ Primer fallo detectado → esperando confirmación en siguiente ejecución")
                entry["alert_sent"] = False  # No alertar aún

            elif not curr_up and not prev_up and not alert_sent:
                # Confirmado: DOWN en dos ciclos consecutivos → ALERTA
                print(f"  🔴 CONFIRMADO DOWN (2 ciclos consecutivos sin recuperación)")
                confirmed_down_sites.append(url)
                entry["alert_sent"] = True

            elif curr_up and prev_up:
                # Todo normal, sigue UP
                entry["alert_sent"] = False

        entry["current"] = result
        entry["history"].append(result)
        if len(entry["history"]) > MAX_HISTORY:
            entry["history"] = entry["history"][-MAX_HISTORY:]

    # Enviar alerta grupal si hay sitios confirmados caídos
    if confirmed_down_sites:
        alert_message = build_alert(confirmed_down_sites, now_iso())
        if alert_message:
            print(f"\n📢 ENVIANDO ALERTA DE CAÍDA: {len(confirmed_down_sites)} sitios caídos")
            send_telegram_with_button(alert_message)
    
    # Enviar alerta grupal si hay sitios recuperados
    if recovered_sites:
        recovery_message = build_recovery_alert(recovered_sites, now_iso())
        if recovery_message:
            print(f"\n📢 ENVIANDO ALERTA DE RECUPERACIÓN: {len(recovered_sites)} sitios recuperados")
            send_telegram_with_button(recovery_message)
    
    if not confirmed_down_sites and not recovered_sites:
        print(f"\n✅ Todos los servicios operativos, sin cambios")

    data["last_updated"] = now_iso()
    
    # Health check: agregar métricas del monitor
    data["monitor_health"] = {
        "last_run": now_iso(),
        "services_checked": len(SITES),
        "alerts_sent": len(confirmed_down_sites) + len(recovered_sites),
        "execution_time": None  # Se calculará en versiones futuras
    }
    
    save_status(data)
    print(f"\n[{now_iso()}] ✅ Monitoreo completado. Actualizado: {data['last_updated']}")

if __name__ == "__main__":
    main()

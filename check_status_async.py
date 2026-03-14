"""
Versión experimental con concurrent checks usando asyncio
Para usar: python check_status_async.py
"""

import asyncio
import aiohttp
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Cargar configuración
CONFIG_FILE = Path(__file__).parent / "config.json"
try:
    with open(CONFIG_FILE) as f:
        CONFIG = json.load(f)
except FileNotFoundError:
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

async def check_site_async(session, url):
    """Check site asynchronously"""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    for attempt in range(2):
        try:
            start = time.monotonic()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)) as resp:
                elapsed_ms = round((time.monotonic() - start) * 1000)
                return {
                    "url": url,
                    "up": True,
                    "status_code": resp.status,
                    "response_time": elapsed_ms,
                    "timestamp": ts
                }
        except asyncio.TimeoutError:
            if attempt == 0:
                await asyncio.sleep(15)
            else:
                return {
                    "url": url,
                    "up": False,
                    "status_code": 0,
                    "response_time": TIMEOUT_SECONDS * 1000,
                    "timestamp": ts,
                    "error": "timeout"
                }
        except Exception as exc:
            if attempt == 0:
                await asyncio.sleep(15)
            else:
                return {
                    "url": url,
                    "up": False,
                    "status_code": 0,
                    "response_time": 0,
                    "timestamp": ts,
                    "error": str(exc)[:120]
                }

async def check_all_sites():
    """Check all sites concurrently"""
    print(f"🚀 Checking {len(SITES)} sites concurrently...")
    start_time = time.monotonic()
    
    async with aiohttp.ClientSession(headers={"User-Agent": CONFIG["user_agent"]}) as session:
        tasks = [check_site_async(session, url) for url in SITES]
        results = await asyncio.gather(*tasks)
    
    elapsed = time.monotonic() - start_time
    print(f"✅ All checks completed in {elapsed:.2f}s")
    
    return results

if __name__ == "__main__":
    results = asyncio.run(check_all_sites())
    
    for result in results:
        status = "✅ UP" if result['up'] else "❌ DOWN"
        print(f"{status} {result['url']} - {result['response_time']}ms")

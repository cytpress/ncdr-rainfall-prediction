import os
import json
import re
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks

load_dotenv()

NCDR_TOKEN = os.getenv("NCDR_API_TOKEN")
PRED_CHANNEL = os.getenv("PREDICTION_CHANNEL")
NCDR_URL = "https://dataapi2.ncdr.nat.gov.tw/NCDR/MaxDBZ?DataFormat=JSON"
RAIN_THRESHOLD = 15
RAIN_INTENSIFY_THRESHOLD = 5
NOMINATIM_USER_AGENT = (
    "RainfallBot (https://github.com/cytpress/ncdr-rainfall-prediction)"
)

app = FastAPI(title="NCDR Rainfall Prediction Bot")

def get_last_state():
    """Check the last message from PRED_CHANNEL to determine if we were in an alert state."""
    try:
        url = f"https://ntfy.sh/{PRED_CHANNEL}/json?poll=1&last=1"
        resp = requests.get(url, timeout=10).text.strip()
        if not resp:
            return False, 0.0
        for line in reversed(resp.split("\n")):
            data = json.loads(line)
            if data.get("event") == "message":
                title = data.get("title", "")
                is_alert = "ALERT" in title or "INTENSIFIED" in title
                msg = data.get("message", "")
                vals = re.findall(r":\s*([\d.]+)", msg)
                max_val = max([float(v) for v in vals]) if vals else 0.0
                return is_alert, max_val
    except Exception:
        pass
    return False, 0.0

def get_address(lat, lon):
    """Reverse geocode coordinates using Nominatim."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
        headers = {"User-Agent": NOMINATIM_USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=10).json()
        addr = resp.get("address", {})
        city = addr.get("city") or addr.get("county") or ""
        dist = (
            addr.get("suburb")
            or addr.get("district")
            or addr.get("township")
            or addr.get("town")
            or ""
        )
        road = addr.get("road") or ""
        full_addr = f"{city}{dist}{road}"
        return full_addr if full_addr else f"{lat}, {lon}"
    except Exception as e:
        print(f"Nominatim Error: {e}")
        return f"{lat}, {lon}"

def get_rain_report(lat, lon):
    """Fetch rainfall forecasts from NCDR."""
    try:
        lat, lon = float(lat), float(lon)
        headers = {"token": NCDR_TOKEN}
        resp = requests.get(NCDR_URL, headers=headers, timeout=30)
        grids = resp.json()

        data_list = []
        if isinstance(grids, list):
            data_list = grids
        elif isinstance(grids, dict):
            data_list = grids.get("Data") or grids.get("features") or grids.get("list") or []

        for g in data_list:
            if (
                abs(float(g["Lat"]) - lat) < 0.015
                and abs(float(g["Lon"]) - lon) < 0.015
            ):
                return g.get("T+1"), g.get("T+3"), g.get("T+6")
    except Exception as e:
        print(f"NCDR API Error: {e}")
    return None, None, None

def process_rainfall_check(lat, lon):
    """Core logic to check rain and send notification."""
    t10, t30, t60 = get_rain_report(lat, lon)
    if t10 is None:
        print(f"No weather data for {lat}, {lon}")
        return

    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    t10_tm = (now + timedelta(minutes=10)).strftime("%H:%M")
    t30_tm = (now + timedelta(minutes=30)).strftime("%H:%M")
    t60_tm = (now + timedelta(minutes=60)).strftime("%H:%M")

    def icon(v):
        if v >= 40: return "🟥"
        if v >= 30: return "🟧"
        if v >= RAIN_THRESHOLD: return "🟩"
        return "☀️"

    last_was_alert, last_max = get_last_state()
    curr_max = max(float(t10), float(t30), float(t60))
    is_raining = curr_max >= RAIN_THRESHOLD

    if is_raining:
        intensified = last_was_alert and (curr_max >= last_max + RAIN_INTENSIFY_THRESHOLD)
        if not last_was_alert or intensified:
            addr_str = get_address(lat, lon)
            title = "INTENSIFIED" if intensified else f"Rain Report (ALERT >= {RAIN_THRESHOLD} dBZ)"
            final_msg = (
                f"📍 {addr_str}\n"
                f"{icon(t10)} {t10_tm}: {round(float(t10), 2)}\n"
                f"{icon(t30)} {t30_tm}: {round(float(t30), 2)}\n"
                f"{icon(t60)} {t60_tm}: {round(float(t60), 2)}\n\n"
                f"(Data © OSM contributors)"
            )
            requests.post(
                f"https://ntfy.sh/{PRED_CHANNEL}",
                data=final_msg.encode("utf-8"),
                headers={"Title": title},
            )
    elif last_was_alert:
        addr_str = get_address(lat, lon)
        requests.post(
            f"https://ntfy.sh/{PRED_CHANNEL}",
            data=f"Rain has stopped at {addr_str}.\n(Data © OSM contributors)".encode("utf-8"),
            headers={"Title": f"Rain Report (CLEAR < {RAIN_THRESHOLD} dBZ)"},
        )

@app.get("/")
def health_check():
    return {"status": "ok", "bot": "RainfallBot"}

@app.post("/owntracks")
async def owntracks_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive location from OwnTracks and process in background."""
    try:
        data = await request.json()
        if data.get("_type") == "location":
            lat, lon = data.get("lat"), data.get("lon")
            print(f"Received location: {lat}, {lon}")
            background_tasks.add_task(process_rainfall_check, lat, lon)
            return {"status": "processing"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "ignored"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

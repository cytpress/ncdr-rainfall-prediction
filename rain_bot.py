import os
import json
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

NCDR_TOKEN = os.getenv("NCDR_API_TOKEN")
LOC_CHANNEL = os.getenv("LOCATION_CHANNEL")
PRED_CHANNEL = os.getenv("PREDICTION_CHANNEL")
NCDR_URL = "https://dataapi2.ncdr.nat.gov.tw/NCDR/MaxDBZ?DataFormat=JSON"


def get_location():
    """Fetch last OwnTracks coordinates from ntfy"""
    try:
        url = f"https://ntfy.sh/{LOC_CHANNEL}/json?poll=1&last=1"
        resp = requests.get(url, timeout=10).text.strip()
        for line in reversed(resp.split("\n")):
            data = json.loads(line)
            if data.get("event") == "message":
                msg_body = json.loads(data["message"])
                if msg_body.get("_type") == "location":
                    return msg_body["lat"], msg_body["lon"]
    except Exception as e:
        print(f"Failed to get location: {e}")
    return None, None


def get_rain_report(lat, lon):
    """從 NCDR 找最近的網格並提取 10, 30, 60 分鐘預測值"""
    try:
        lat, lon = float(lat), float(lon)
        headers = {"token": NCDR_TOKEN}
        resp = requests.get(NCDR_URL, headers=headers, timeout=30)
        grids = resp.json()

        if isinstance(grids, list):
            data_list = grids
        elif isinstance(grids, dict):
            data_list = grids.get("Data") or grids.get("features") or grids.get("list")
            if data_list is None:
                print(
                    f"API Error: Dict received but no data. Keys: {list(grids.keys())}"
                )
                return None, None, None
        else:
            print(f"API Error: Unknown type {type(grids)}")
            return None, None, None

        for g in data_list:
            if (
                abs(float(g["Lat"]) - lat) < 0.015
                and abs(float(g["Lon"]) - lon) < 0.015
            ):
                return g.get("T+1"), g.get("T+3"), g.get("T+6")
    except Exception as e:
        print(f"NCDR API Error: {e}")
        if "grids" in locals():
            print(f"Data type: {type(grids)}")
    return None, None, None


def main():
    lat, lon = get_location()
    if lat is None:
        print("No valid location detected.")
        return

    t10, t30, t60 = get_rain_report(lat, lon)
    if t10 is None:
        print("No weather data found at current location.")
        return

    def icon(v):
        if v >= 30:
            return "⛈️"
        if v >= 20:
            return "🌧️"
        if v >= 10:
            return "🌦️"
        return "☀️"

    threshold = float(os.getenv("RAIN_THRESHOLD", "15"))

    # Time calculation (Force UTC+8 for consistency)
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    t10_tm = (now + timedelta(minutes=10)).strftime("%H:%M")
    t30_tm = (now + timedelta(minutes=30)).strftime("%H:%M")
    t60_tm = (now + timedelta(minutes=60)).strftime("%H:%M")

    msg = (
        f"📍 Loc: {round(lat, 3)}, {round(lon, 3)}\n"
        f"{icon(t10)} {t10_tm}: {round(float(t10), 2)}\n"
        f"{icon(t30)} {t30_tm}: {round(float(t30), 2)}\n"
        f"{icon(t60)} {t60_tm}: {round(float(t60), 2)}"
    )

    # Simplified log message
    log_vals = f"[{t10}, {t30}, {t60}]"

    # Send if any prediction >= threshold
    if any(float(v) >= threshold for v in [t10, t30, t60]):
        print(f"Pred: {log_vals} -> Sending Notification.")
        requests.post(
            f"https://ntfy.sh/{PRED_CHANNEL}",
            data=msg.encode("utf-8"),
            headers={
                "Title": f"Rain Plan Report (ALERT >= {threshold})",
                "Tags": "umbrella,bar_chart",
            },
        )
    else:
        print(f"Pred: {log_vals} -> Skipping (Max < {threshold} dBZ).")


if __name__ == "__main__":
    main()

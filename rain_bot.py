import os
import json
import re
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

NCDR_TOKEN = os.getenv("NCDR_API_TOKEN")
LOC_CHANNEL = os.getenv("LOCATION_CHANNEL")
PRED_CHANNEL = os.getenv("PREDICTION_CHANNEL")
NCDR_URL = "https://dataapi2.ncdr.nat.gov.tw/NCDR/MaxDBZ?DataFormat=JSON"
RAIN_THRESHOLD = 15
RAIN_INTENSIFY_THRESHOLD = 5
NOMINATIM_USER_AGENT = (
    "RainfallBot (https://github.com/cytpress/ncdr-rainfall-prediction)"
)


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


def get_last_state():
    """Check the last message from PRED_CHANNEL to determine if we were in an alert state and what the max rain was."""
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
                # Extract numbers after ":" which represent rainfall values
                vals = re.findall(r":\s*([\d.]+)", msg)
                max_val = max([float(v) for v in vals]) if vals else 0.0
                return is_alert, max_val
    except Exception:
        pass
    return False, 0.0


def get_address(lat, lon):
    """Reverse geocode coordinates to a Taiwan address (City District Road) using Nominatim."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
        headers = {"User-Agent": NOMINATIM_USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=10).json()
        addr = resp.get("address", {})

        # Parse Taiwan address: City/County + District/Suburb + Road
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
    """Fetch rainfall forecasts (10, 30, 60 min) for the nearest grid from NCDR."""
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
        if v >= 40:
            return "🟥"
        if v >= 30:
            return "🟧"
        if v >= RAIN_THRESHOLD:
            return "🟩"
        return "☀️"

    # Time calculation (Force UTC+8 for consistency)
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    t10_tm = (now + timedelta(minutes=10)).strftime("%H:%M")
    t30_tm = (now + timedelta(minutes=30)).strftime("%H:%M")
    t60_tm = (now + timedelta(minutes=60)).strftime("%H:%M")

    # Simplified log message
    log_vals = f"[{t10}, {t30}, {t60}]"

    # Send if state changes
    last_was_alert, last_max = get_last_state()
    curr_max = max(float(t10), float(t30), float(t60))
    is_raining = curr_max >= RAIN_THRESHOLD

    if is_raining:
        # Trigger push if:
        # 1. Start raining (not last alert)
        # 2. Rain significantly intensified (curr_max >= last_max + threshold)
        intensified = last_was_alert and (curr_max >= last_max + RAIN_INTENSIFY_THRESHOLD)

        if not last_was_alert or intensified:
            addr_str = get_address(lat, lon)
            if not last_was_alert:
                print(f"Pred: {log_vals} -> Rain Started (Sending Alert).")
                title = f"Rain Report (ALERT >= {RAIN_THRESHOLD} dBZ)"
            else:
                print(
                    f"Pred: {log_vals} -> Rain Intensified (+{round(curr_max - last_max, 1)} dBZ). Sending alert."
                )
                title = "INTENSIFIED"

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
                headers={
                    "Title": title,
                },
            )
        else:
            print(
                f"Pred: {log_vals} -> Continuous Rain (Muted). Current: {curr_max}, Last: {last_max}"
            )
    elif last_was_alert:
        # Rain stopped: Send a clear notification to reset state
        addr_str = get_address(lat, lon)
        print(f"Pred: {log_vals} -> Rain Stopped (Sending Clear).")
        requests.post(
            f"https://ntfy.sh/{PRED_CHANNEL}",
            data=f"Rain has stopped at {addr_str}.\n(Data © OSM contributors)".encode(
                "utf-8"
            ),
            headers={
                "Title": f"Rain Report (CLEAR < {RAIN_THRESHOLD} dBZ)",
            },
        )
    else:
        print(f"Pred: {log_vals} -> Clear (Skipping).")


if __name__ == "__main__":
    main()

import os
import json
import requests
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Initialize environment
load_dotenv()
<<<<<<< HEAD

=======
>>>>>>> 7b7e2ceb90c0e75fa1fa1c8220e8da2b28fae2c5
NCDR_TOKEN = os.getenv("NCDR_API_TOKEN")
LOC_CHANNEL = os.getenv("LOCATION_CHANNEL")
PRED_CHANNEL = os.getenv("PREDICTION_CHANNEL")
NCDR_URL = "https://dataapi2.ncdr.nat.gov.tw/NCDR/MaxDBZ?DataFormat=JSON"

def get_location():
    """Retrieve last OwnTracks coordinates from ntfy"""
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
    """Find the nearest grid and extract 10, 30, 60 min forecasts from NCDR"""
    try:
        lat, lon = float(lat), float(lon)
        headers = {"token": NCDR_TOKEN}
        resp = requests.get(NCDR_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        grids = resp.json()

        if isinstance(grids, list):
            data_list, rec_dt = grids, None
        elif isinstance(grids, dict):
            data_list = grids.get("Data") or grids.get("features") or grids.get("list")
<<<<<<< HEAD
            if data_list is None:
                print(
                    f"API Error: Dict received but no data. Keys: {list(grids.keys())}"
                )
                return None, None, None
=======
            rec_dt = grids.get("RecDateTime")
            if not data_list: return None, None, None, None
>>>>>>> 7b7e2ceb90c0e75fa1fa1c8220e8da2b28fae2c5
        else:
            return None, None, None, None

        def dist_sq(g):
            try:
                return (float(g["Lat"]) - lat)**2 + (float(g["Lon"]) - lon)**2
            except:
                return float('inf')

        best = min(data_list, key=dist_sq, default=None)
        if best and dist_sq(best) < 0.0005: 
            return best.get("T+1"), best.get("T+3"), best.get("T+6"), rec_dt

<<<<<<< HEAD
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


=======
    except Exception as e:
        print(f"NCDR API Error: {e}")
    return None, None, None, None

def get_last_state():
    """Poll ntfy history to retrieve the last sent message state"""
    try:
        url = f"https://ntfy.sh/{PRED_CHANNEL}/json?poll=1&last=1"
        resp = requests.get(url, timeout=10).text.strip()
        if not resp: return 0, 0.0
        
        data = json.loads(resp.split("\n")[-1])
        if data.get("event") == "message":
            msg = data.get("message", "")
            last_time = data.get("time", 0)
            
            # Message format:
            # 📍 Loc: 24.983, 121.467
            # ☀️ 19:50: 0.0
            # ☀️ 20:10: 0.0
            # ...
            lines = msg.split("\n")
            forecast_vals = []
            for line in lines:
                if ":" in line and any(icon in line for icon in ["⛈️", "🌧️", "🌦️", "☀️"]):
                    try:
                        # Take the text after the last colon and convert to float
                        val = float(line.split(":")[-1].strip())
                        forecast_vals.append(val)
                    except:
                        continue
            
            return last_time, max(forecast_vals) if forecast_vals else 0.0
    except:
        pass
    return 0, 0.0

>>>>>>> 7b7e2ceb90c0e75fa1fa1c8220e8da2b28fae2c5
def main():
    # 1. Fetch current coordinates
    lat, lon = get_location()
    if lat is None:
        print("No valid location detected.")
        return

<<<<<<< HEAD
    t10, t30, t60 = get_rain_report(lat, lon)
    if t10 is None:
        print("No weather data found at current location.")
=======
    # 2. Fetch rainfall prediction data
    t1, t3, t6, rec_dt = get_rain_report(lat, lon)
    if t1 is None:
        print(f"No weather data found near ({lat}, {lon}).")
>>>>>>> 7b7e2ceb90c0e75fa1fa1c8220e8da2b28fae2c5
        return

    # 3. Data normalization and icon mapping
    try:
        vals = [max(0.0, float(v)) if v is not None else 0.0 for v in [t1, t3, t6]]
        t1_f, t3_f, t6_f = vals
        current_max = max(vals)
    except:
        return

    def icon(v):
        if v >= 30: return "⛈️"
        if v >= 20: return "🌧️"
        if v >= 10: return "🌦️"
        return "☀️"

<<<<<<< HEAD
=======
    # 4. Sync forecast timestamps with API RecDateTime (UTC to Local)
    tz8 = timezone(timedelta(hours=8))
    now = datetime.now(tz8)
    if rec_dt:
        try:
            raw = datetime.fromisoformat(rec_dt.replace("Z", "+00:00"))
            base = (raw.replace(tzinfo=timezone.utc) if raw.tzinfo is None else raw).astimezone(tz8)
        except:
            base = now
    else:
        base = now

    t10_tm = (base + timedelta(minutes=10)).strftime("%H:%M")
    t30_tm = (base + timedelta(minutes=30)).strftime("%H:%M")
    t60_tm = (base + timedelta(minutes=60)).strftime("%H:%M")

>>>>>>> 7b7e2ceb90c0e75fa1fa1c8220e8da2b28fae2c5
    threshold = float(os.getenv("RAIN_THRESHOLD", "15"))

    # 5. Cool-down Logic (State from ntfy)
    last_time, last_max = get_last_state()
    time_diff = now.timestamp() - last_time
    
    is_raining = current_max >= threshold
    was_raining = last_max >= threshold
    
    should_push = False
    if is_raining != was_raining:
        should_push = True # Rain started or stopped
    elif is_raining and (abs(current_max - last_max) >= 5 or time_diff >= 3600):
        should_push = True # Steady rain but changed significantly or 1 hour passed
    
    # 6. Silent window (06:00 ~ 24:00 only)
    is_awake_time = 6 <= now.hour < 24
    
    msg = (
        f"📍 Loc: {round(lat, 3)}, {round(lon, 3)}\n"
        f"{icon(t1_f)} {t10_tm}: {round(t1_f, 2)}\n"
        f"{icon(t3_f)} {t30_tm}: {round(t3_f, 2)}\n"
        f"{icon(t6_f)} {t60_tm}: {round(t6_f, 2)}"
    )

<<<<<<< HEAD
    # Simplified log message
    log_vals = f"[{t10}, {t30}, {t60}]"

    # Send if any prediction >= threshold
    if any(float(v) >= threshold for v in [t10, t30, t60]):
        print(f"Pred: {log_vals} -> Sending Notification.")
=======
    if should_push and is_awake_time:
>>>>>>> 7b7e2ceb90c0e75fa1fa1c8220e8da2b28fae2c5
        requests.post(
            f"https://ntfy.sh/{PRED_CHANNEL}",
            data=msg.encode("utf-8"),
            headers={
                "Title": f"Rain Plan Report (ALERT >= {threshold})",
                "Tags": "umbrella,bar_chart",
<<<<<<< HEAD
=======
                "Priority": "high" if any(v >= 35 for v in vals) else "default"
>>>>>>> 7b7e2ceb90c0e75fa1fa1c8220e8da2b28fae2c5
            },
        )
        print(f"Pushed to ntfy: {current_max} dBZ")
    else:
<<<<<<< HEAD
        print(f"Pred: {log_vals} -> Skipping (Max < {threshold} dBZ).")

=======
        print(f"Skipped push (Raining: {is_raining}, Awake: {is_awake_time}, TimeDiff: {int(time_diff)}s)")
>>>>>>> 7b7e2ceb90c0e75fa1fa1c8220e8da2b28fae2c5

if __name__ == "__main__":
    main()

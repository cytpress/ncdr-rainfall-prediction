import os
import json
import re
import math
from datetime import datetime, timedelta, timezone
from utils import get_full_rain_data, get_rain_at_point, get_address, calculate_distance, expand_google_maps_url, send_ntfy, get_pred_channel

RAIN_THRESHOLD = 15
RAIN_INTENSIFY_THRESHOLD = 5

def get_last_state():
    channel = get_pred_channel()
    try:
        url = f"https://ntfy.sh/{channel}/json?poll=1&last=1"
        import requests
        resp = requests.get(url, timeout=10).text.strip()
        if not resp: return False, 0.0
        for line in reversed(resp.split("\n")):
            data = json.loads(line)
            if data.get("event") == "message":
                title = data.get("title", "")
                is_alert = any(x in title for x in ["ALERT", "INTENSIFIED"])
                msg = data.get("message", "")
                vals = re.findall(r":\s*([\d.]+)", msg)
                max_val = max([float(v) for v in vals]) if vals else 0.0
                return is_alert, max_val
    except: pass
    return False, 0.0

def process_automatic_alert(lat, lon):
    rain_data = get_full_rain_data()
    t1, t3, t6 = get_rain_at_point(lat, lon, rain_data)
    if t1 is None: return

    curr_max = max(float(t1), float(t3), float(t6))
    last_was_alert, last_max = get_last_state()
    is_raining = curr_max >= RAIN_THRESHOLD

    if is_raining:
        intensified = last_was_alert and (curr_max >= last_max + RAIN_INTENSIFY_THRESHOLD)
        if not last_was_alert or intensified:
            addr = get_address(lat, lon)
            title = "INTENSIFIED" if intensified else "Rain Alert"
            msg = f"📍 {addr}\n強度：{curr_max} dBZ\nT+10: {t1}\nT+30: {t3}\nT+60: {t6}"
            print(f"[Auto] Alert sent for {addr} ({curr_max} dBZ)")
            send_ntfy(msg, title=title, priority="high")
    elif last_was_alert:
        addr = get_address(lat, lon)
        print(f"[Auto] Clear message sent for {addr}")
        send_ntfy(f"Rain has stopped at {addr}", title="CLEAR")

def process_manual_route_check(short_url, current_loc):
    dest_lat, dest_lon = expand_google_maps_url(short_url)
    if dest_lat is None:
        print(f"[Route] Error: Could not resolve destination for {short_url}")
        return "無法解析地圖網址，請確認分享內容。"

    orig_lat, orig_lon = current_loc["lat"], current_loc["lon"]
    dist_km = calculate_distance(orig_lat, orig_lon, dest_lat, dest_lon)
    num_steps = max(1, math.ceil(dist_km))
    
    rain_data = get_full_rain_data()
    rain_found, max_dbz, rain_points = False, 0.0, 0

    for i in range(num_steps + 1):
        ratio = i / num_steps
        c_lat = orig_lat + (dest_lat - orig_lat) * ratio
        c_lon = orig_lon + (dest_lon - orig_lon) * ratio
        t1, t3, t6 = get_rain_at_point(c_lat, c_lon, rain_data)
        if t1:
            dbz = max(float(t1), float(t3), float(t6))
            max_dbz = max(max_dbz, dbz)
            if dbz >= RAIN_THRESHOLD:
                rain_found, rain_points = True, rain_points + 1

    addr_dest = get_address(dest_lat, dest_lon)
    rain_percent = round((rain_points / (num_steps + 1)) * 100)
    
    if rain_found:
        msg = f"📍 目的地：{addr_dest}\n📏 距離：{round(dist_km, 1)}km\n⛈️ 下雨路段：{rain_percent}%\n🔥 最高強度：{max_dbz}dBZ\n⚠️ 建議攜帶雨具！"
    else:
        msg = f"📍 目的地：{addr_dest}\n📏 距離：{round(dist_km, 1)}km\n✅ 整段路徑採樣無降雨預報。"
    
    print(f"[Route] Check completed for {addr_dest}. Rain: {rain_found}")
    return msg

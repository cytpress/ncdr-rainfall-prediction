import os
import re
import math
import requests
import json

# Fetching at runtime instead of module level to be safe
def get_ncdr_token(): return os.getenv("NCDR_API_TOKEN")
def get_pred_channel(): return os.getenv("PREDICTION_CHANNEL")

NCDR_URL = "https://dataapi2.ncdr.nat.gov.tw/NCDR/MaxDBZ?DataFormat=JSON"
NOMINATIM_USER_AGENT = "RainfallBot (https://github.com/cytpress/ncdr-rainfall-prediction)"

def get_full_rain_data():
    token = get_ncdr_token()
    print(f"[Log] Fetching NCDR data with token: {token[:5]}***")
    try:
        headers = {"token": token}
        resp = requests.get(NCDR_URL, headers=headers, timeout=30)
        print(f"[Log] NCDR Response Status: {resp.status_code}")
        grids = resp.json()
        if isinstance(grids, list): return grids
        if isinstance(grids, dict): return grids.get("Data") or grids.get("features") or grids.get("list") or []
    except Exception as e:
        print(f"[Error] NCDR API Error: {e}")
    return []

def get_rain_at_point(lat, lon, rain_data):
    for g in rain_data:
        if abs(float(g["Lat"]) - lat) < 0.015 and abs(float(g["Lon"]) - lon) < 0.015:
            return g.get("T+1"), g.get("T+3"), g.get("T+6")
    return None, None, None

def get_address(lat, lon):
    print(f"[Log] Reverse geocoding for {lat}, {lon}")
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
        headers = {"User-Agent": NOMINATIM_USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=10).json()
        addr = resp.get("address", {})
        city = addr.get("city") or addr.get("county") or ""
        dist = addr.get("suburb") or addr.get("district") or addr.get("township") or addr.get("town") or ""
        road = addr.get("road") or ""
        full_addr = f"{city}{dist}{road}"
        return full_addr if full_addr else f"{lat}, {lon}"
    except Exception as e:
        print(f"[Error] Nominatim Error: {e}")
        return f"{lat}, {lon}"

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

from urllib.parse import unquote

def expand_google_maps_url(short_url):
    print(f"[Log] Original input: {short_url}")
    # Decode URL-encoded characters
    short_url = unquote(short_url).replace("\\/", "/")
    print(f"[Log] Decoded URL: {short_url}")
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(short_url, allow_redirects=True, timeout=10, headers=headers)
        long_url = resp.url
        print(f"[Log] Expanded URL: {long_url}")
        match = re.search(r'!3d([\d\.]+)!4d([\d\.]+)', long_url)
        if match: 
            print(f"[Log] Extracted Coordinates: {match.group(1)}, {match.group(2)}")
            return float(match.group(1)), float(match.group(2))
    except Exception as e:
        print(f"[Error] URL Expansion Error: {e}")
    return None, None

def send_ntfy(message, title=None, priority="default"):
    channel = get_pred_channel()
    print(f"[Log] Sending ntfy to channel: {channel}")
    try:
        headers = {"Priority": priority}
        if title: headers["Title"] = title.encode('utf-8').decode('latin-1')
        resp = requests.post(f"https://ntfy.sh/{channel}", data=message.encode("utf-8"), headers=headers, timeout=10)
        print(f"[Log] ntfy Response: {resp.status_code}")
    except Exception as e:
        print(f"[Error] ntfy Sending Failed: {e}")

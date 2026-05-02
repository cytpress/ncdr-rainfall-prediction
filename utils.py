import os
import re
import math
import requests
import json

NCDR_TOKEN = os.getenv("NCDR_API_TOKEN")
NCDR_URL = "https://dataapi2.ncdr.nat.gov.tw/NCDR/MaxDBZ?DataFormat=JSON"
NOMINATIM_USER_AGENT = "RainfallBot (https://github.com/cytpress/ncdr-rainfall-prediction)"

def get_full_rain_data():
    """Fetch all rainfall grids from NCDR."""
    try:
        headers = {"token": NCDR_TOKEN}
        resp = requests.get(NCDR_URL, headers=headers, timeout=30)
        grids = resp.json()
        if isinstance(grids, list): return grids
        if isinstance(grids, dict): return grids.get("Data") or grids.get("features") or grids.get("list") or []
    except Exception as e:
        print(f"NCDR API Error: {e}")
    return []

def get_rain_at_point(lat, lon, rain_data):
    """Lookup rain values for a point."""
    for g in rain_data:
        if abs(float(g["Lat"]) - lat) < 0.015 and abs(float(g["Lon"]) - lon) < 0.015:
            return g.get("T+1"), g.get("T+3"), g.get("T+6")
    return None, None, None

def get_address(lat, lon):
    """Reverse geocode coordinates."""
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
    except Exception: return f"{lat}, {lon}"

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def expand_google_maps_url(short_url):
    """Resolve short URL."""
    try:
        resp = requests.get(short_url, allow_redirects=True, timeout=10)
        long_url = resp.url
        match = re.search(r'!3d([\d\.]+)!4d([\d\.]+)', long_url)
        if match: return float(match.group(1)), float(match.group(2))
    except Exception: pass
    return None, None

def send_ntfy(channel, message, title=None, priority="default"):
    """Centralized ntfy sender."""
    try:
        headers = {"Priority": priority}
        if title: headers["Title"] = title.encode('utf-8').decode('latin-1')
        requests.post(f"https://ntfy.sh/{channel}", data=message.encode("utf-8"), headers=headers)
    except Exception as e:
        print(f"ntfy Error: {e}")

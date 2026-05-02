import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
from services import process_automatic_alert, process_manual_route_check

load_dotenv()

app = FastAPI(title="NCDR Rainfall Prediction Bot")

# State shared across endpoints
last_known_loc = {"lat": 25.033, "lon": 121.565}

@app.get("/")
def health_check():
    return {"status": "ok", "bot": "RainfallBot"}

@app.post("/owntracks")
async def owntracks_webhook(request: Request, background_tasks: BackgroundTasks):
    """Entry point for automatic location updates."""
    try:
        data = await request.json()
        if data.get("_type") == "location":
            lat, lon = data.get("lat"), data.get("lon")
            last_known_loc["lat"] = lat
            last_known_loc["lon"] = lon
            background_tasks.add_task(process_automatic_alert, lat, lon)
            return {"status": "processing_auto"}
    except: pass
    return {"status": "ignored"}

@app.post("/route-check")
async def route_check_webhook(request: Request, background_tasks: BackgroundTasks):
    """Entry point for manual route requests."""
    try:
        data = await request.json()
        url = data.get("url")
        if url:
            background_tasks.add_task(process_manual_route_check, url, last_known_loc)
            return {"status": "processing_route"}
    except: pass
    return {"status": "error"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

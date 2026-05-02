import { getFullRainData, getRainAtPoint, getAddress, calculateDistance, expandGoogleMapsUrl, sendNtfy } from "./utils";

const RAIN_THRESHOLD = 15;
const RAIN_INTENSIFY_THRESHOLD = 5;

async function getLastState(channel: string) {
  try {
    const url = `https://ntfy.sh/${channel}/json?poll=1&last=1`;
    const resp = await fetch(url);
    const text = await resp.text();
    if (!text) return { isAlert: false, maxVal: 0.0 };
    
    const lines = text.trim().split("\n");
    for (let i = lines.length - 1; i >= 0; i--) {
      const data = JSON.parse(lines[i]);
      if (data.event === "message") {
        const title = data.title || "";
        const isAlert = title.includes("ALERT") || title.includes("INTENSIFIED");
        const msg = data.message || "";
        const vals = (msg.match(/:\s*([\d.]+)/g) || []).map((v: string) => parseFloat(v.split(":")[1]));
        const maxVal = vals.length > 0 ? Math.max(...vals) : 0.0;
        return { isAlert, maxVal };
      }
    }
  } catch {}
  return { isAlert: false, maxVal: 0.0 };
}

export async function processAutomaticAlert(lat: number, lon: number, token: string, channel: string) {
  const rainData = await getFullRainData(token);
  const [t1, t3, t6] = getRainAtPoint(lat, lon, rainData);
  if (t1 === null) return;

  const currMax = Math.max(parseFloat(t1), parseFloat(t3 || "0"), parseFloat(t6 || "0"));
  const { isAlert: lastWasAlert, maxVal: lastMax } = await getLastState(channel);
  const isRaining = currMax >= RAIN_THRESHOLD;

  if (isRaining) {
    const intensified = lastWasAlert && (currMax >= lastMax + RAIN_INTENSIFY_THRESHOLD);
    if (!lastWasAlert || intensified) {
      const addr = await getAddress(lat, lon);
      const title = intensified ? "INTENSIFIED" : "Rain Alert";
      const msg = `📍 ${addr}\n強度：${currMax} dBZ\nT+10: ${t1}\nT+30: ${t3}\nT+60: ${t6}`;
      console.log(`[Auto] Alert sent for ${addr} (${currMax} dBZ)`);
      await sendNtfy(channel, msg, title, "high");
    }
  } else if (lastWasAlert) {
    const addr = await getAddress(lat, lon);
    console.log(`[Auto] Clear message sent for ${addr}`);
    await sendNtfy(channel, `Rain has stopped at ${addr}`, "CLEAR");
  }
}

export async function processManualRouteCheck(shortUrl: string, currentLoc: {lat: number, lon: number}, token: string, channel: string) {
  const [destLat, destLon] = await expandGoogleMapsUrl(shortUrl);
  if (destLat === null || destLon === null) {
    console.log(`[Route] Error: Could not resolve destination for ${shortUrl}`);
    return "無法解析地圖網址，請確認分享內容。";
  }

  const { lat: origLat, lon: origLon } = currentLoc;
  const distKm = calculateDistance(origLat, origLon, destLat, destLon);
  const numSteps = Math.max(1, Math.ceil(distKm));
  
  const rainData = await getFullRainData(token);
  let rainFound = false;
  let maxDbz = 0.0;
  let rainPoints = 0;

  for (let i = 0; i <= numSteps; i++) {
    const ratio = i / numSteps;
    const cLat = origLat + (destLat - origLat) * ratio;
    const cLon = origLon + (destLon - origLon) * ratio;
    const [t1, t3, t6] = getRainAtPoint(cLat, cLon, rainData);
    if (t1 !== null) {
      const dbz = Math.max(parseFloat(t1), parseFloat(t3 || "0"), parseFloat(t6 || "0"));
      maxDbz = Math.max(maxDbz, dbz);
      if (dbz >= RAIN_THRESHOLD) {
        rainFound = true;
        rainPoints++;
      }
    }
  }

  const addrDest = await getAddress(destLat, destLon);
  const rainPercent = Math.round((rainPoints / (numSteps + 1)) * 100);
  
  const msg = rainFound 
    ? `📍 目的地：${addrDest}\n📏 距離：${distKm.toFixed(1)}km\n⛈️ 下雨路段：${rainPercent}%\n🔥 最高強度：${maxDbz}dBZ\n⚠️ 建議攜帶雨具！`
    : `📍 目的地：${addrDest}\n📏 距離：${distKm.toFixed(1)}km\n✅ 整段路徑採樣無降雨預報。`;
  
  console.log(`[Route] Check completed for ${addrDest}. Rain: ${rainFound}`);
  return msg;
}

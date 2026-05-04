import { getFullRainData, getRainAtPoint, getAddress, calculateDistance, expandGoogleMapsUrl, sendNtfy } from "./utils";

const RAIN_THRESHOLD = 15;
const RAIN_INTENSIFY_THRESHOLD = 5;

export async function processPointCheck(lat: number, lon: number, token: string) {
  const rainData = await getFullRainData(token);
  const [t1, t3, t6] = getRainAtPoint(lat, lon, rainData);
  if (t1 === null) return "無法取得該位置的降雨資料。";

  const addr = await getAddress(lat, lon);
  const maxDbz = Math.max(parseFloat(t1), parseFloat(t3 || "0"), parseFloat(t6 || "0"));
  const rainIcon = maxDbz >= RAIN_THRESHOLD ? "⛈️" : "✅";
  
  return `📍 當前位置：${addr}\n${rainIcon} 降雨強度：${maxDbz} dBZ\n--- 預報 ---\nT+10m: ${t1}\nT+30m: ${t3}\nT+60m: ${t6}`;
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

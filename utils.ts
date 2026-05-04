export const NCDR_URL = "https://dataapi2.ncdr.nat.gov.tw/NCDR/MaxDBZ?DataFormat=JSON";
const NOMINATIM_USER_AGENT = "RainfallBot (https://github.com/cytpress/ncdr-rainfall-prediction)";

export async function getFullRainData(token: string) {
  try {
    const resp = await fetch(NCDR_URL, { headers: { token } });
    const grids = await resp.json() as any;
    if (Array.isArray(grids)) return grids;
    return grids?.Data || grids?.features || grids?.list || [];
  } catch (e) {
    console.error(`[Error] NCDR API Error: ${e}`);
    return [];
  }
}

export function getRainAtPoint(lat: number, lon: number, rainData: any[]) {
  for (const g of rainData) {
    if (Math.abs(parseFloat(g.Lat) - lat) < 0.015 && Math.abs(parseFloat(g.Lon) - lon) < 0.015) {
      return [g["T+1"], g["T+3"], g["T+6"]];
    }
  }
  return [null, null, null];
}

export async function getAddress(lat: number, lon: number) {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&addressdetails=1`;
    const resp = await fetch(url, { headers: { "User-Agent": NOMINATIM_USER_AGENT } });
    const data = await resp.json() as any;
    const addr = data.address || {};
    const city = addr.city || addr.county || "";
    const dist = addr.suburb || addr.district || addr.township || addr.town || "";
    const road = addr.road || "";
    const fullAddr = `${city}${dist}${road}`;
    return fullAddr || `${lat}, ${lon}`;
  } catch {
    return `${lat}, ${lon}`;
  }
}

export function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

const BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

export async function expandGoogleMapsUrl(shortUrl: string) {
  try {
    // Clean and decode URL
    let decodedUrl = decodeURIComponent(shortUrl);
    // Handle various escaping scenarios (like \/ or \\/)
    decodedUrl = decodedUrl.replace(/\\+\//g, "/");
    
    // Add protocol if missing (some clients might send //maps.app.goo.gl/...)
    if (decodedUrl.startsWith("//")) decodedUrl = "https:" + decodedUrl;

    const resp = await fetch(decodedUrl, { 
      redirect: 'follow',
      headers: { "User-Agent": BROWSER_USER_AGENT }
    });
    const longUrl = resp.url;
    
    // 1. Try standard !3d (lat) !4d (lon) - most common for places
    const coordsMatch = longUrl.match(/!3d([-?\d\.]+)!4d([-?\d\.]+)/);
    if (coordsMatch) return [parseFloat(coordsMatch[1]), parseFloat(coordsMatch[2])];
    
    // 2. Try !2d (lat) !1d (lon) - common in some direction URLs
    // Note: In Google Maps internal data, !1d is often Lon, !2d is Lat
    const dataMatch = longUrl.match(/!2d([-?\d\.]+)!1d([-?\d\.]+)/);
    if (dataMatch) {
      // In some contexts it's [Lat, Lon], in others [Lon, Lat]. 
      // For Taiwan, Lon is ~121, Lat is ~25.
      const val1 = parseFloat(dataMatch[1]);
      const val2 = parseFloat(dataMatch[2]);
      if (val1 < 90 && val1 > -90 && (val2 > 90 || val2 < -90)) return [val1, val2]; // val1 is lat
      return [val2, val1]; // assume val2 is lat
    }

    // 3. Try /dir/lat,lon/lat,lon/ format
    const dirMatch = longUrl.match(/\/dir\/[-?\d\.]+,[-?\d\.]+\/([-?\d\.]+),([-?\d\.]+)\//);
    if (dirMatch) return [parseFloat(dirMatch[1]), parseFloat(dirMatch[2])];

    // 4. Try @lat,lon viewport format (fallback)
    const viewportMatch = longUrl.match(/@([-?\d\.]+),([-?\d\.]+),/);
    if (viewportMatch) return [parseFloat(viewportMatch[1]), parseFloat(viewportMatch[2])];

  } catch (e) {
    console.error(`[Error] URL Expansion Error for ${shortUrl}: ${e}`);
  }
  return [null, null];
}

export async function sendNtfy(channel: string, message: string, title?: string, priority = "default") {
  try {
    const headers: any = { "Priority": priority };
    if (title) headers["Title"] = encodeURIComponent(title); // ntfy supports URL encoded titles
    await fetch(`https://ntfy.sh/${channel}`, {
      method: "POST",
      body: message,
      headers
    });
  } catch (e) {
    console.error(`[Error] ntfy Failed: ${e}`);
  }
}

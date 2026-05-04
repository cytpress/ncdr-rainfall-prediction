import { Hono } from 'hono';
import { processPointCheck, processManualRouteCheck } from './services';
import 'dotenv/config';

const app = new Hono();

const NCDR_TOKEN = process.env.NCDR_API_TOKEN || "";
const PRED_CHANNEL = process.env.PREDICTION_CHANNEL || "";

// State shared across endpoints
let lastKnownLoc = { lat: 25.033, lon: 121.565 };

app.get('/', (c) => {
  return c.json({ status: 'ok', bot: 'RainfallBot-TS', runtime: 'Bun + Hono' });
});

app.post('/check', async (c) => {
  try {
    const { lat, lon } = await c.req.json();
    if (lat && lon) {
      console.log(`[Log] Point check requested for: ${lat}, ${lon}`);
      lastKnownLoc = { lat: parseFloat(lat), lon: parseFloat(lon) };
      const resultMsg = await processPointCheck(lastKnownLoc.lat, lastKnownLoc.lon, NCDR_TOKEN);
      return c.text(resultMsg);
    }
  } catch (e) {
    return c.text(`Error: ${e}`);
  }
  return c.text('Invalid coordinates');
});

app.post('/route-check', async (c) => {
  try {
    const data = await c.req.json();
    const url = data.url;
    if (url) {
      console.log(`[Log] Route check requested for: ${url}`);
      const resultMsg = await processManualRouteCheck(url, lastKnownLoc, NCDR_TOKEN, PRED_CHANNEL);
      return c.text(resultMsg);
    }
  } catch (e) {
    return c.text(`Error: ${e}`);
  }
  return c.text('Ignored');
});

console.log(`🚀 RainfallBot-TS is running on http://0.0.0.0:8000`);

export default {
  port: 8000,
  fetch: app.fetch,
};

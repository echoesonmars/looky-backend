import express, { Request, Response } from "express";
import cors from "cors";
require("dotenv").config();

const app = express();
const PORT = process.env.PORT || 3001;
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL?.replace(/\/$/, "");

app.use(cors());
app.use(express.json());

app.get("/api/health", (_req: Request, res: Response) => {
  res.json({ status: "OK", service: "looky-node", message: "Looky Node API is running" });
});

app.get("/api/items", (_req: Request, res: Response) => {
  res.json({ items: [] });
});

/** Aggregated status: Node + optional FastAPI (PYTHON_SERVICE_URL). */
app.get("/api/services", async (_req: Request, res: Response) => {
  const payload: {
    node: { ok: boolean };
    python?: { ok: boolean; detail?: unknown };
  } = { node: { ok: true } };

  if (!PYTHON_SERVICE_URL) {
    res.json({ ...payload, python: { ok: false, detail: "PYTHON_SERVICE_URL not set" } });
    return;
  }

  try {
    const r = await fetch(`${PYTHON_SERVICE_URL}/api/health`);
    const body = (await r.json().catch(() => ({}))) as unknown;
    payload.python = { ok: r.ok, detail: body };
  } catch (e) {
    payload.python = { ok: false, detail: String(e) };
  }

  res.json(payload);
});

export default app;

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`[looky-node] http://localhost:${PORT}`);
  });
}

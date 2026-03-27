import express, { Request, Response } from "express";
import cors from "cors";
import { getPool } from "./db";
require("dotenv").config();

const app = express();
const PORT = process.env.PORT || 3001;
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL?.replace(/\/$/, "");

app.use(cors());
app.use(express.json());

app.get("/api/health", (_req: Request, res: Response) => {
  res.json({ status: "OK", service: "looky-node", message: "Looky Node API is running" });
});

app.get("/api/items", async (_req: Request, res: Response) => {
  const pool = getPool();
  if (!pool) {
    res.status(503).json({
      items: [],
      error: "DATABASE_URL is not configured",
    });
    return;
  }

  try {
    const result = await pool.query<{
      id: string;
      title: string;
      created_at: string;
    }>(
      `select id, title, created_at
       from public.items
       order by created_at desc
       limit 100`
    );
    res.json({ items: result.rows });
  } catch (e) {
    console.error("[looky-node] /api/items", e);
    res.status(500).json({
      items: [],
      error: "database_query_failed",
      message: e instanceof Error ? e.message : String(e),
    });
  }
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

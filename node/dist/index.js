"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const db_1 = require("./db");
require("dotenv").config();
const app = (0, express_1.default)();
const PORT = process.env.PORT || 3001;
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL?.replace(/\/$/, "");
app.use((0, cors_1.default)());
app.use(express_1.default.json());
app.get("/api/health", (_req, res) => {
    res.json({ status: "OK", service: "looky-node", message: "Looky Node API is running" });
});
app.get("/api/items", async (_req, res) => {
    const pool = (0, db_1.getPool)();
    if (!pool) {
        res.status(503).json({
            items: [],
            error: "DATABASE_URL is not configured",
        });
        return;
    }
    try {
        const result = await pool.query(`select id, title, created_at
       from public.items
       order by created_at desc
       limit 100`);
        res.json({ items: result.rows });
    }
    catch (e) {
        console.error("[looky-node] /api/items", e);
        res.status(500).json({
            items: [],
            error: "database_query_failed",
            message: e instanceof Error ? e.message : String(e),
        });
    }
});
/** Aggregated status: Node + optional FastAPI (PYTHON_SERVICE_URL). */
app.get("/api/services", async (_req, res) => {
    const payload = { node: { ok: true } };
    if (!PYTHON_SERVICE_URL) {
        res.json({ ...payload, python: { ok: false, detail: "PYTHON_SERVICE_URL not set" } });
        return;
    }
    try {
        const r = await fetch(`${PYTHON_SERVICE_URL}/api/health`);
        const body = (await r.json().catch(() => ({})));
        payload.python = { ok: r.ok, detail: body };
    }
    catch (e) {
        payload.python = { ok: false, detail: String(e) };
    }
    res.json(payload);
});
exports.default = app;
if (require.main === module) {
    app.listen(PORT, () => {
        console.log(`[looky-node] http://localhost:${PORT}`);
    });
}

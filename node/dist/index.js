"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
require("dotenv").config();
const app = (0, express_1.default)();
const PORT = process.env.PORT || 3001;
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL?.replace(/\/$/, "");
app.use((0, cors_1.default)());
app.use(express_1.default.json());
app.get("/api/health", (_req, res) => {
    res.json({ status: "OK", service: "looky-node", message: "Looky Node API is running" });
});
app.get("/api/items", (_req, res) => {
    res.json({ items: [] });
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

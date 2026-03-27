"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getPool = getPool;
const pg_1 = require("pg");
let pool = null;
function getPool() {
    const url = process.env.DATABASE_URL;
    if (!url)
        return null;
    if (!pool) {
        const useSsl = url.includes("supabase.co") || url.includes("sslmode=require");
        pool = new pg_1.Pool({
            connectionString: url,
            max: 10,
            ssl: useSsl ? { rejectUnauthorized: false } : undefined,
        });
    }
    return pool;
}

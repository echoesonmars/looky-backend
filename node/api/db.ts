import { Pool } from "pg";

let pool: Pool | null = null;

export function getPool(): Pool | null {
  const url = process.env.DATABASE_URL;
  if (!url) return null;

  if (!pool) {
    const useSsl =
      url.includes("supabase.co") || url.includes("sslmode=require");
    pool = new Pool({
      connectionString: url,
      max: 10,
      ssl: useSsl ? { rejectUnauthorized: false } : undefined,
    });
  }
  return pool;
}

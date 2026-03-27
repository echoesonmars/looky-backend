-- Run once in Supabase SQL Editor (or via psql against DATABASE_URL).
-- Table used by Looky Node GET /api/items and optional Next.js reads.

create table if not exists public.items (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  created_at timestamptz not null default now()
);

alter table public.items enable row level security;

-- Public read for anon (adjust for production)
create policy "items_select_public"
  on public.items
  for select
  to anon, authenticated
  using (true);

-- Optional seed (uncomment):
-- insert into public.items (title) values ('demo item');

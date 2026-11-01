-- LUMI · Personalidad Evolutiva v1
-- Ejecutar una única vez en Supabase SQL Editor antes de activar el módulo.
-- No altera CIC, memorias ni auditoría anteriores.

create table if not exists public.lumi_personalidad_decisiones (
    id uuid primary key default gen_random_uuid(),
    interaccion_id uuid not null unique,
    origen text not null,
    eleccion text not null,
    motivo text not null,
    alternativa text not null,
    estado text not null default 'pendiente'
        check (estado in ('pendiente', 'contrastada', 'descartada')),
    creado_en timestamptz not null default now()
);

create table if not exists public.lumi_personalidad_evidencias (
    id uuid primary key default gen_random_uuid(),
    clave_evento text not null unique,
    decision_id uuid references public.lumi_personalidad_decisiones(id)
        on delete set null,
    rasgo text not null,
    delta smallint not null check (delta between -20 and 20 and delta <> 0),
    contexto text not null,
    validador text not null,
    evidencia jsonb not null default '{}'::jsonb,
    creado_en timestamptz not null default now()
);

create index if not exists idx_lumi_personalidad_decisiones_fecha
    on public.lumi_personalidad_decisiones (creado_en desc);

create index if not exists idx_lumi_personalidad_evidencias_rasgo_fecha
    on public.lumi_personalidad_evidencias (rasgo, creado_en desc);

-- Solo el backend con la clave secreta puede operar estas tablas.
alter table public.lumi_personalidad_decisiones enable row level security;
alter table public.lumi_personalidad_evidencias enable row level security;

revoke all on public.lumi_personalidad_decisiones from public, anon, authenticated;
revoke all on public.lumi_personalidad_evidencias from public, anon, authenticated;
grant all on public.lumi_personalidad_decisiones to service_role;
grant all on public.lumi_personalidad_evidencias to service_role;

-- Una vista de lectura, agregada y sin datos privados, siempre con RLS invocador.
create or replace view public.lumi_personalidad_resumen
with (security_invoker = true)
as
select
    rasgo,
    greatest(0, least(100, coalesce(sum(delta), 0)))::integer as puntuacion,
    count(*) filter (where delta > 0)::integer as apoyos,
    count(distinct (creado_en at time zone 'UTC')::date)
        filter (where delta > 0)::integer as dias_con_evidencia
from public.lumi_personalidad_evidencias
group by rasgo;

revoke all on public.lumi_personalidad_resumen from public, anon, authenticated;
grant select on public.lumi_personalidad_resumen to service_role;

-- Comprobaciones sin escrituras extra: aquí deben existir 2 tablas y la vista.
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name like 'lumi_personalidad_%'
order by table_name;

select * from public.lumi_personalidad_resumen;

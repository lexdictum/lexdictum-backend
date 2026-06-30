-- Document chunks for Postgres full-text search (sparse leg of hybrid RAG)

create table public.document_chunks (
    id uuid primary key default gen_random_uuid(),
    case_id uuid not null references public.cases (id) on delete cascade,
    document_id uuid not null references public.documents (id) on delete cascade,
    chunk_index integer not null,
    text text not null,
    page integer,
    search_vector tsvector generated always as (
        to_tsvector('spanish', coalesce(text, ''))
    ) stored,
    created_at timestamptz not null default now(),
    unique (document_id, chunk_index)
);

create index document_chunks_case_id_idx on public.document_chunks (case_id);
create index document_chunks_document_id_idx on public.document_chunks (document_id);
create index document_chunks_search_vector_idx
    on public.document_chunks using gin (search_vector);

alter table public.document_chunks enable row level security;

create policy "Users can view chunks for own documents"
    on public.document_chunks for select
    using (
        exists (
            select 1 from public.documents d
            where d.id = document_id and d.user_id = auth.uid()
        )
    );

-- Service role (workers) bypasses RLS for insert/delete.

create or replace function public.search_case_chunks_fts(
    p_case_id uuid,
    p_query text,
    p_limit integer default 10
)
returns table (
    document_id uuid,
    chunk_index integer,
    text text,
    page integer,
    rank real
)
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if auth.uid() is not null then
        if not exists (
            select 1 from public.cases c
            where c.id = p_case_id and c.user_id = auth.uid()
        ) then
            return;
        end if;
    end if;

    return query
    select
        dc.document_id,
        dc.chunk_index,
        dc.text,
        dc.page,
        ts_rank_cd(
            dc.search_vector,
            websearch_to_tsquery('spanish', p_query)
        )::real as rank
    from public.document_chunks dc
    where dc.case_id = p_case_id
      and dc.search_vector @@ websearch_to_tsquery('spanish', p_query)
    order by rank desc
    limit p_limit;
end;
$$;

grant execute on function public.search_case_chunks_fts(uuid, text, integer)
    to authenticated, service_role;

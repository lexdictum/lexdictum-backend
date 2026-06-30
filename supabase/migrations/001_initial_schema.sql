-- LexDictum initial schema
-- Run via Supabase CLI: supabase db push

-- Profiles (extends auth.users)
create table public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    full_name text,
    firm_name text,
    bar_number text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Cases (expedientes)
create type public.case_status as enum ('open', 'in_progress', 'closed', 'archived');

create table public.cases (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    title text not null,
    description text,
    status public.case_status not null default 'open',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index cases_user_id_idx on public.cases (user_id);
create index cases_status_idx on public.cases (status);

-- Documents
create type public.document_status as enum ('pending', 'processing', 'ready', 'failed');

create table public.documents (
    id uuid primary key default gen_random_uuid(),
    case_id uuid not null references public.cases (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    filename text not null,
    storage_path text not null,
    mime_type text,
    status public.document_status not null default 'pending',
    chunk_count integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index documents_case_id_idx on public.documents (case_id);
create index documents_user_id_idx on public.documents (user_id);
create index documents_status_idx on public.documents (status);

-- Conversations
create table public.conversations (
    id uuid primary key default gen_random_uuid(),
    case_id uuid not null references public.cases (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    title text not null default 'Nueva conversación',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index conversations_case_id_idx on public.conversations (case_id);
create index conversations_user_id_idx on public.conversations (user_id);

-- Messages
create type public.message_role as enum ('user', 'assistant', 'system');

create table public.messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references public.conversations (id) on delete cascade,
    role public.message_role not null,
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index messages_conversation_id_idx on public.messages (conversation_id);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, full_name)
    values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', ''));
    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- Updated_at trigger
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger profiles_updated_at before update on public.profiles
    for each row execute function public.set_updated_at();
create trigger cases_updated_at before update on public.cases
    for each row execute function public.set_updated_at();
create trigger documents_updated_at before update on public.documents
    for each row execute function public.set_updated_at();
create trigger conversations_updated_at before update on public.conversations
    for each row execute function public.set_updated_at();

-- Row Level Security
alter table public.profiles enable row level security;
alter table public.cases enable row level security;
alter table public.documents enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;

-- Profiles policies
create policy "Users can view own profile"
    on public.profiles for select
    using (auth.uid() = id);

create policy "Users can update own profile"
    on public.profiles for update
    using (auth.uid() = id);

-- Cases policies
create policy "Users can view own cases"
    on public.cases for select
    using (auth.uid() = user_id);

create policy "Users can create own cases"
    on public.cases for insert
    with check (auth.uid() = user_id);

create policy "Users can update own cases"
    on public.cases for update
    using (auth.uid() = user_id);

create policy "Users can delete own cases"
    on public.cases for delete
    using (auth.uid() = user_id);

-- Documents policies
create policy "Users can view own documents"
    on public.documents for select
    using (auth.uid() = user_id);

create policy "Users can create own documents"
    on public.documents for insert
    with check (auth.uid() = user_id);

create policy "Users can update own documents"
    on public.documents for update
    using (auth.uid() = user_id);

create policy "Users can delete own documents"
    on public.documents for delete
    using (auth.uid() = user_id);

-- Conversations policies
create policy "Users can view own conversations"
    on public.conversations for select
    using (auth.uid() = user_id);

create policy "Users can create own conversations"
    on public.conversations for insert
    with check (auth.uid() = user_id);

create policy "Users can update own conversations"
    on public.conversations for update
    using (auth.uid() = user_id);

create policy "Users can delete own conversations"
    on public.conversations for delete
    using (auth.uid() = user_id);

-- Messages policies (via conversation ownership)
create policy "Users can view messages in own conversations"
    on public.messages for select
    using (
        exists (
            select 1 from public.conversations c
            where c.id = conversation_id and c.user_id = auth.uid()
        )
    );

create policy "Users can create messages in own conversations"
    on public.messages for insert
    with check (
        exists (
            select 1 from public.conversations c
            where c.id = conversation_id and c.user_id = auth.uid()
        )
    );

create policy "Users can update messages in own conversations"
    on public.messages for update
    using (
        exists (
            select 1 from public.conversations c
            where c.id = conversation_id and c.user_id = auth.uid()
        )
    );

create policy "Users can delete messages in own conversations"
    on public.messages for delete
    using (
        exists (
            select 1 from public.conversations c
            where c.id = conversation_id and c.user_id = auth.uid()
        )
    );

-- Storage bucket for documents (run in Supabase dashboard or via API)
-- insert into storage.buckets (id, name, public) values ('documents', 'documents', false);

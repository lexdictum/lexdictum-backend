-- Documents storage bucket with owner-scoped RLS policies
-- Run via Supabase CLI: supabase db push

insert into storage.buckets (id, name, public, file_size_limit)
values ('documents', 'documents', false, 52428800)
on conflict (id) do nothing;

create policy "Users can view own document files"
    on storage.objects for select
    using (
        bucket_id = 'documents'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

create policy "Users can upload own document files"
    on storage.objects for insert
    with check (
        bucket_id = 'documents'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

create policy "Users can update own document files"
    on storage.objects for update
    using (
        bucket_id = 'documents'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

create policy "Users can delete own document files"
    on storage.objects for delete
    using (
        bucket_id = 'documents'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

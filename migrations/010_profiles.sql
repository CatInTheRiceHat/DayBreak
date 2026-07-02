-- Migration 010 - Profiles (Supabase Auth-linked user profiles)
--
-- Real, per-user Chrysalis profiles, linked 1:1 to Supabase Auth users.
--
-- SECURITY / PRIVACY NOTES (Chrysalis is teen-centered — keep this minimal & safe):
--   * We NEVER store passwords, password hashes, or auth tokens here. Supabase
--     Auth (auth.users) owns all credentials. This table holds only profile/app
--     data that is safe to expose to other users.
--   * Email and phone are intentionally NOT columns in this table. They live in
--     auth.users and are revealed only to the owning user via their Auth session.
--     They are never published through this public profiles table.
--   * Row Level Security is enabled: a row is readable by others only when the
--     owner has NOT marked it private, and writable only by its owner.
--
-- Idempotent: safe to run repeatedly.

create extension if not exists pgcrypto;  -- gen_random_uuid(), if ever needed

-- ---------------------------------------------------------------------------
-- profiles table
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
    id                uuid primary key references auth.users (id) on delete cascade,
    username          text        not null,
    display_name      text,
    bio               text,
    avatar_url        text,
    -- optional / nullable app fields
    pronouns          text,
    location_label    text,        -- coarse, self-entered label only (e.g. "NYC"); never GPS
    website_url       text,
    intention         text,
    current_mode      text,
    is_private        boolean     not null default false,
    allow_messages    boolean     not null default true,
    profile_completed boolean     not null default false,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),

    -- username is stored lowercase and constrained to a safe handle shape.
    constraint profiles_username_format
        check (username = lower(username) and username ~ '^[a-z0-9_.]{3,30}$'),
    constraint profiles_display_name_len
        check (display_name is null or char_length(display_name) <= 50),
    constraint profiles_bio_len
        check (bio is null or char_length(bio) <= 280)
);

-- Case-insensitive unique username.
create unique index if not exists profiles_username_unique
    on public.profiles (lower(username));

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- Self-contained: create-or-reuse a safe, generic timestamp function. Using
-- CREATE OR REPLACE means this migration does not assume the function already
-- exists, and re-running it is harmless.
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
    before update on public.profiles
    for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;

-- SELECT: public profiles are world-readable; a private profile is visible only
-- to its owner.
drop policy if exists "Profiles are viewable when public or own" on public.profiles;
create policy "Profiles are viewable when public or own"
    on public.profiles for select
    using (is_private = false or auth.uid() = id);

-- INSERT: a user may create only their own profile row.
drop policy if exists "Users can insert their own profile" on public.profiles;
create policy "Users can insert their own profile"
    on public.profiles for insert
    with check (auth.uid() = id);

-- UPDATE: a user may update only their own row, and cannot reassign it to anyone
-- else (WITH CHECK also pins id = auth.uid()). This is what prevents editing
-- another user's profile.
drop policy if exists "Users can update their own profile" on public.profiles;
create policy "Users can update their own profile"
    on public.profiles for update
    using (auth.uid() = id)
    with check (auth.uid() = id);

-- No DELETE policy: profile rows are removed automatically by the
-- auth.users ON DELETE CASCADE when an account is deleted.

-- ---------------------------------------------------------------------------
-- Auto-create a profile row when a new auth user signs up.
-- SECURITY DEFINER so the trigger can insert into public.profiles regardless of
-- the (anonymous) caller's privileges.
--
-- USERNAME COLLISION SAFETY: the default handle is derived from the user id
-- ('user_' + 12 hex chars = ~48 bits), so a clash is astronomically unlikely —
-- BUT it is still *possible* (e.g. someone manually took that exact handle).
-- A plain `on conflict (id) do nothing` would NOT catch a username (lower(username))
-- collision; the resulting unique_violation would bubble up and abort the whole
-- signup transaction. To make signup bullet-proof we retry with a numeric suffix,
-- then fall back to a fully random handle. The loop also stays idempotent: if a
-- row for this id already exists (trigger re-fired), it simply exits.
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    base_name text := 'user_' || substr(replace(new.id::text, '-', ''), 1, 12);
    candidate text := base_name;
    suffix    int  := 0;
begin
    loop
        begin
            insert into public.profiles (id, username, display_name)
            values (
                new.id,
                candidate,
                nullif(new.raw_user_meta_data ->> 'display_name', '')
            );
            return new;  -- inserted cleanly
        exception
            when unique_violation then
                -- If this id already has a profile, we're done (idempotent).
                if exists (select 1 from public.profiles where id = new.id) then
                    return new;
                end if;
                -- Otherwise it was a username collision: try another handle.
                suffix := suffix + 1;
                if suffix <= 50 then
                    candidate := left(base_name, 24) || '_' || suffix::text;
                else
                    -- Extremely unlikely escape hatch: a fully random handle.
                    candidate := 'user_' || substr(md5(random()::text || clock_timestamp()::text), 1, 16);
                end if;
        end;
    end loop;
end;
$$;

drop trigger if exists trg_on_auth_user_created on auth.users;
create trigger trg_on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Avatar storage bucket + owner-only write policies.
-- Files live at avatars/{user_id}/avatar.<ext>. The bucket is public-read so
-- avatars can be shown anywhere, but only the owner may write/replace/delete
-- their own folder.
--
-- ⚠️ AVATAR PRIVACY (known v1/demo limitation — acceptable, documented):
-- Because this bucket is PUBLIC, an avatar's public URL stays reachable by anyone
-- who already has the link even if the user later marks their profile private or
-- the profile row is hidden by RLS. Making a profile private hides the profile
-- ROW/PAGE, NOT a previously-issued avatar image URL.
--   * This is acceptable for the demo: avatars are low-sensitivity and the path
--     is not enumerable without the row (which RLS protects).
--   * FUTURE PRIVACY HARDENING (do later, not now): switch private users' avatars
--     to a non-public bucket + short-lived signed URLs (createSignedUrl), and/or
--     rotate the avatar path when a profile is set to private so old links 404.
-- We intentionally keep public URLs for v1 to keep the demo simple and stable.
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do nothing;

-- READ: anyone can view avatar images.
drop policy if exists "Avatar images are publicly readable" on storage.objects;
create policy "Avatar images are publicly readable"
    on storage.objects for select
    using (bucket_id = 'avatars');

-- INSERT: only into your own {user_id}/ folder.
drop policy if exists "Users can upload their own avatar" on storage.objects;
create policy "Users can upload their own avatar"
    on storage.objects for insert
    with check (
        bucket_id = 'avatars'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

-- UPDATE: only your own files.
drop policy if exists "Users can update their own avatar" on storage.objects;
create policy "Users can update their own avatar"
    on storage.objects for update
    using (
        bucket_id = 'avatars'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

-- DELETE: only your own files (used when replacing an avatar).
drop policy if exists "Users can delete their own avatar" on storage.objects;
create policy "Users can delete their own avatar"
    on storage.objects for delete
    using (
        bucket_id = 'avatars'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

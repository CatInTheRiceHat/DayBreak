import { supabase } from './supabaseClient';

/**
 * Profile + avatar data access, straight to Supabase with the user's session.
 * Row Level Security (see migrations/010_profiles.sql) is what actually enforces
 * "only edit your own profile" — these helpers are the thin client surface.
 */

const AVATAR_BUCKET = 'avatars';
const MAX_AVATAR_BYTES = 5 * 1024 * 1024; // 5 MB
const ALLOWED_AVATAR_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];

// Fields a user is allowed to edit on their own profile. Deliberately excludes
// id/created_at/updated_at and anything credential-related (none exist here).
const EDITABLE_FIELDS = [
  'username', 'display_name', 'bio', 'avatar_url', 'pronouns', 'location_label',
  'website_url', 'intention', 'current_mode', 'is_private', 'allow_messages',
  'profile_completed',
];

function requireClient() {
  if (!supabase) throw new Error('Supabase is not configured.');
  return supabase;
}

export async function getMyProfile() {
  const sb = requireClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;
  const { data, error } = await sb
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .maybeSingle();
  if (error) throw error;
  return data;
}

export async function updateMyProfile(patch) {
  const sb = requireClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) throw new Error('You need to be signed in.');

  const clean = {};
  for (const key of EDITABLE_FIELDS) {
    if (key in patch) clean[key] = patch[key];
  }
  if (typeof clean.username === 'string') {
    clean.username = clean.username.trim().toLowerCase();
  }

  const { data, error } = await sb
    .from('profiles')
    .update(clean)
    .eq('id', user.id)
    .select()
    .maybeSingle();
  if (error) throw error;
  return data;
}

export async function getProfileByUsername(username) {
  const sb = requireClient();
  const { data, error } = await sb
    .from('profiles')
    .select('*')
    .eq('username', String(username || '').trim().toLowerCase())
    .maybeSingle();
  if (error) throw error;
  return data;
}

/** Local, pre-upload validation so we fail fast with a friendly message. */
export function validateAvatarFile(file) {
  if (!file) return 'Choose an image to upload.';
  if (!ALLOWED_AVATAR_TYPES.includes(file.type)) {
    return 'Please choose a PNG, JPG, WEBP, or GIF image.';
  }
  if (file.size > MAX_AVATAR_BYTES) return 'Image must be 5 MB or smaller.';
  return null;
}

/**
 * Upload (or replace) the signed-in user's avatar.
 * Stored at avatars/{user_id}/avatar.<ext>; old files in the folder are removed
 * first so we never accumulate stale images. Returns the public URL (also saved
 * onto profiles.avatar_url).
 */
export async function uploadAvatar(file) {
  const sb = requireClient();
  const validationError = validateAvatarFile(file);
  if (validationError) throw new Error(validationError);

  const { data: { user } } = await sb.auth.getUser();
  if (!user) throw new Error('You need to be signed in.');

  const ext = (file.name.split('.').pop() || 'png').toLowerCase().replace(/[^a-z0-9]/g, '') || 'png';

  // Replace cleanly: remove any existing files in the user's folder first.
  const { data: existing } = await sb.storage.from(AVATAR_BUCKET).list(user.id);
  if (existing && existing.length) {
    await sb.storage
      .from(AVATAR_BUCKET)
      .remove(existing.map((entry) => `${user.id}/${entry.name}`));
  }

  const path = `${user.id}/avatar.${ext}`;
  const { error: uploadError } = await sb.storage
    .from(AVATAR_BUCKET)
    .upload(path, file, { upsert: true, contentType: file.type });
  if (uploadError) throw uploadError;

  // NOTE (v1/demo privacy limitation): the `avatars` bucket is public, so this
  // URL stays reachable to anyone with the link even if the profile is later made
  // private. Making a profile private hides the row/page, not an already-issued
  // avatar URL. Future hardening: private bucket + signed URLs. See
  // migrations/010_profiles.sql for the full rationale.
  const { data: pub } = sb.storage.from(AVATAR_BUCKET).getPublicUrl(path);
  // Cache-bust so the freshly uploaded image shows immediately.
  const publicUrl = `${pub.publicUrl}?v=${Date.now()}`;
  await updateMyProfile({ avatar_url: publicUrl });
  return publicUrl;
}

import { createClient, SupabaseClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

/** True only when both Supabase env vars are present at build time. */
export const isSupabaseConfigured = Boolean(url && anonKey);

/**
 * Whether the app should force a login gate. Defaults to on when Supabase is
 * configured; set VITE_REQUIRE_AUTH=false for an open local-dev build.
 */
export const requireAuth =
  (import.meta.env.VITE_REQUIRE_AUTH ?? 'true').toString().toLowerCase() !== 'false';

// Created only when configured, so a local build without Supabase still runs.
export const supabase: SupabaseClient | null = isSupabaseConfigured
  ? createClient(url as string, anonKey as string, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true, // handles the emailed password-reset link
      },
    })
  : null;

/** Current access token for API calls, or null when signed out / not configured. */
export const getAccessToken = async (): Promise<string | null> => {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
};

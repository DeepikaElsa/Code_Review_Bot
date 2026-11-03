import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { isSupabaseConfigured, requireAuth, supabase } from '../lib/supabase';

interface AuthResult {
  ok: boolean;
  message?: string;
}

interface AuthContextType {
  configured: boolean;
  requireAuth: boolean;
  loading: boolean;
  session: Session | null;
  user: User | null;
  /** True while the user arrived via a password-reset email link. */
  recoveryMode: boolean;
  signIn: (email: string, password: string) => Promise<AuthResult>;
  signUp: (email: string, password: string) => Promise<AuthResult>;
  signOut: () => Promise<void>;
  sendPasswordReset: (email: string) => Promise<AuthResult>;
  updatePassword: (password: string) => Promise<AuthResult>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};

const message = (error: unknown) =>
  error instanceof Error ? error.message : 'Something went wrong. Please try again.';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [recoveryMode, setRecoveryMode] = useState(false);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((event, next) => {
      setSession(next);
      if (event === 'PASSWORD_RECOVERY') setRecoveryMode(true);
      if (event === 'SIGNED_OUT') setRecoveryMode(false);
    });

    return () => sub.subscription.unsubscribe();
  }, []);

  const signIn = useCallback(async (email: string, password: string): Promise<AuthResult> => {
    if (!supabase) return { ok: false, message: 'Auth is not configured.' };
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return error ? { ok: false, message: error.message } : { ok: true };
  }, []);

  const signUp = useCallback(async (email: string, password: string): Promise<AuthResult> => {
    if (!supabase) return { ok: false, message: 'Auth is not configured.' };
    try {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: window.location.origin },
      });
      if (error) return { ok: false, message: error.message };
      // With email confirmations on, there is no session until they confirm.
      if (!data.session) {
        return { ok: true, message: 'Check your email to confirm your account.' };
      }
      return { ok: true };
    } catch (error) {
      return { ok: false, message: message(error) };
    }
  }, []);

  const signOut = useCallback(async () => {
    await supabase?.auth.signOut();
  }, []);

  const sendPasswordReset = useCallback(async (email: string): Promise<AuthResult> => {
    if (!supabase) return { ok: false, message: 'Auth is not configured.' };
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin,
    });
    return error
      ? { ok: false, message: error.message }
      : { ok: true, message: 'If that email is registered, a reset link is on its way.' };
  }, []);

  const updatePassword = useCallback(async (password: string): Promise<AuthResult> => {
    if (!supabase) return { ok: false, message: 'Auth is not configured.' };
    const { error } = await supabase.auth.updateUser({ password });
    if (error) return { ok: false, message: error.message };
    setRecoveryMode(false);
    return { ok: true, message: 'Password updated.' };
  }, []);

  return (
    <AuthContext.Provider
      value={{
        configured: isSupabaseConfigured,
        requireAuth,
        loading,
        session,
        user: session?.user ?? null,
        recoveryMode,
        signIn,
        signUp,
        signOut,
        sendPasswordReset,
        updatePassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

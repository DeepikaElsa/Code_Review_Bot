import React from 'react';
import { AlertCircle, Code2, Loader2, Lock, Mail } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

type Mode = 'signin' | 'signup' | 'forgot' | 'reset';

const field =
  'w-full bg-ink-850 text-fg text-sm rounded-lg pl-10 pr-3 py-2.5 border border-white/10 ' +
  'placeholder:text-fg-muted focus:ring-2 focus:ring-sky/40 focus:border-sky/40 focus:outline-none';

const AuthScreen: React.FC = () => {
  const {
    configured,
    recoveryMode,
    signIn,
    signUp,
    sendPasswordReset,
    updatePassword,
  } = useAuth();

  const [mode, setMode] = React.useState<Mode>('signin');
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [confirm, setConfirm] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');

  const active: Mode = recoveryMode ? 'reset' : mode;

  const reset = (next: Mode) => {
    setMode(next);
    setError('');
    setNotice('');
    setPassword('');
    setConfirm('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setNotice('');

    if (active === 'signup' || active === 'reset') {
      if (password.length < 8) {
        setError('Password must be at least 8 characters.');
        return;
      }
      if (password !== confirm) {
        setError('Passwords do not match.');
        return;
      }
    }

    setBusy(true);
    try {
      if (active === 'signin') {
        const res = await signIn(email, password);
        if (!res.ok) setError(res.message ?? 'Could not sign in.');
      } else if (active === 'signup') {
        const res = await signUp(email, password);
        if (!res.ok) setError(res.message ?? 'Could not sign up.');
        else if (res.message) setNotice(res.message);
      } else if (active === 'forgot') {
        const res = await sendPasswordReset(email);
        if (!res.ok) setError(res.message ?? 'Could not send reset email.');
        else setNotice(res.message ?? 'Reset link sent.');
      } else if (active === 'reset') {
        const res = await updatePassword(password);
        if (!res.ok) setError(res.message ?? 'Could not update password.');
        else setNotice('Password updated. You are signed in.');
      }
    } finally {
      setBusy(false);
    }
  };

  const titles: Record<Mode, string> = {
    signin: 'Sign in',
    signup: 'Create your account',
    forgot: 'Reset your password',
    reset: 'Choose a new password',
  };

  const cta: Record<Mode, string> = {
    signin: 'Sign in',
    signup: 'Sign up',
    forgot: 'Send reset link',
    reset: 'Update password',
  };

  const showEmail = active === 'signin' || active === 'signup' || active === 'forgot';
  const showPassword = active === 'signin' || active === 'signup' || active === 'reset';
  const showConfirm = active === 'signup' || active === 'reset';

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-950 px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-2 mb-6">
          <div className="w-10 h-10 rounded-xl bg-sand/20 flex items-center justify-center">
            <Code2 size={22} className="text-sand" />
          </div>
          <span className="text-xl font-semibold text-fg">CodeBot</span>
        </div>

        <div className="bg-ink-900 border border-white/5 rounded-2xl p-6 shadow-xl">
          <h1 className="text-lg font-semibold text-fg mb-1">{titles[active]}</h1>
          <p className="text-sm text-fg-muted mb-5">
            {active === 'signin' && 'Welcome back.'}
            {active === 'signup' && 'Write, review, and verify code across Python, C, and Java.'}
            {active === 'forgot' && 'We will email you a secure link to set a new password.'}
            {active === 'reset' && 'Enter a new password for your account.'}
          </p>

          {!configured && (
            <div className="mb-4 flex items-start gap-2 text-xs text-sand bg-sand/10 border border-sand/30 rounded-lg p-3">
              <AlertCircle size={16} className="mt-0.5 flex-none" />
              <span>
                Auth is not configured. Set <code>VITE_SUPABASE_URL</code> and{' '}
                <code>VITE_SUPABASE_ANON_KEY</code>, then rebuild.
              </span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            {showEmail && (
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-3 text-fg-muted" />
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className={field}
                />
              </div>
            )}

            {showPassword && (
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-3 text-fg-muted" />
                <input
                  type="password"
                  autoComplete={active === 'signin' ? 'current-password' : 'new-password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={active === 'signin' ? 'Password' : 'New password (min 8 chars)'}
                  className={field}
                />
              </div>
            )}

            {showConfirm && (
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-3 text-fg-muted" />
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Confirm password"
                  className={field}
                />
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 text-xs text-danger bg-danger/10 border border-danger/30 rounded-lg p-2.5">
                <AlertCircle size={14} className="mt-0.5 flex-none" />
                <span>{error}</span>
              </div>
            )}
            {notice && (
              <div className="text-xs text-sky bg-sky/10 border border-sky/30 rounded-lg p-2.5">
                {notice}
              </div>
            )}

            <button
              type="submit"
              disabled={busy || !configured}
              className={`w-full py-2.5 rounded-lg font-medium flex items-center justify-center gap-2 transition-all ${
                busy || !configured
                  ? 'bg-ink-800 text-fg-muted cursor-not-allowed'
                  : 'bg-sand text-ink-950 hover:bg-sand-dark'
              }`}
            >
              {busy && <Loader2 size={16} className="animate-spin" />}
              {cta[active]}
            </button>
          </form>

          {active !== 'reset' && (
            <div className="mt-4 text-sm text-fg-muted space-y-2">
              {active === 'signin' && (
                <>
                  <button onClick={() => reset('forgot')} className="text-sky hover:underline">
                    Forgot password?
                  </button>
                  <p>
                    No account?{' '}
                    <button onClick={() => reset('signup')} className="text-sky hover:underline">
                      Create one
                    </button>
                  </p>
                </>
              )}
              {active === 'signup' && (
                <p>
                  Already have an account?{' '}
                  <button onClick={() => reset('signin')} className="text-sky hover:underline">
                    Sign in
                  </button>
                </p>
              )}
              {active === 'forgot' && (
                <button onClick={() => reset('signin')} className="text-sky hover:underline">
                  Back to sign in
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AuthScreen;

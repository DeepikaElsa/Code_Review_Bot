import { Loader2 } from 'lucide-react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import AuthScreen from './components/auth/AuthScreen';
import MainLayout from './components/MainLayout';

const Gate = () => {
  const { loading, session, recoveryMode, requireAuth, configured } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-ink-950">
        <Loader2 size={28} className="text-sky animate-spin" />
      </div>
    );
  }

  // Arrived from a password-reset email: force the new-password form.
  if (recoveryMode) return <AuthScreen />;

  // Gate only when auth is actually set up. Without Supabase configured there
  // is nothing to authenticate against, so local dev opens straight to the app.
  if (requireAuth && configured && !session) return <AuthScreen />;

  return <MainLayout />;
};

function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}

export default App;

import React from 'react';
import { Code2, LogOut } from 'lucide-react';
import { useReviewContext } from '../contexts/ReviewContext';
import { useAuth } from '../contexts/AuthContext';

const Header: React.FC = () => {
  const { health } = useReviewContext();
  const { user, signOut } = useAuth();

  const online = health?.status === 'ok';
  const statusText = !health
    ? 'Backend offline'
    : online
    ? `Ollama connected · ${health.installedModels.length} models`
    : `Ollama unreachable at ${health.ollamaHost}`;

  const missing = health?.missingModels ?? [];

  return (
    <header className="flex-none h-14 bg-ink-900 border-b border-white/5 flex items-center px-4 gap-3">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-sand/20 flex items-center justify-center">
          <Code2 size={18} className="text-sand" />
        </div>
        <h1 className="text-base font-semibold text-fg">CodeBot</h1>
        <span className="text-xs text-fg-muted hidden sm:inline">Write · Review · Verify</span>
      </div>

      <div className="ml-auto flex items-center gap-4">
        {missing.length > 0 && (
          <span
            className="text-xs text-sand hidden md:inline"
            title={`Run: ollama pull ${missing.join(' && ollama pull ')}`}
          >
            Pull needed: {missing.join(', ')}
          </span>
        )}
        <span className="flex items-center gap-2 text-xs text-fg-muted" title={statusText}>
          <span className={`w-2 h-2 rounded-full ${online ? 'bg-sky' : 'bg-danger'}`} />
          <span className="hidden sm:inline">{statusText}</span>
        </span>

        {user && (
          <div className="flex items-center gap-2 pl-3 border-l border-white/5">
            {user.email && (
              <span className="text-xs text-fg-soft hidden sm:inline max-w-[180px] truncate">
                {user.email}
              </span>
            )}
            <button
              onClick={signOut}
              title="Sign out"
              className="flex items-center gap-1 text-xs text-fg-muted hover:text-fg px-2 py-1 rounded-md hover:bg-ink-800 transition-colors"
            >
              <LogOut size={14} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;

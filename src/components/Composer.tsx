import React from 'react';
import { Send, Square } from 'lucide-react';
import { useReviewContext } from '../contexts/ReviewContext';
import { Language, ReviewMode, isSpecMode } from '../types';

const PLACEHOLDERS: Record<Language, string> = {
  [Language.PYTHON]: 'Paste Python code…',
  [Language.C]: 'Paste C code…',
  [Language.JAVA]: 'Paste Java code…',
};

const MODE_HINT: Record<ReviewMode, string> = {
  [ReviewMode.GENERATE]: 'Describe what to build',
  [ReviewMode.COMPLETE]: 'Paste code with stubs to finish',
  [ReviewMode.TRANSLATE]: 'Paste code to translate',
  [ReviewMode.TESTS]: 'Paste code to test',
  [ReviewMode.EXPLAIN]: 'Paste code to explain',
  [ReviewMode.CORRECT]: 'Paste buggy code to fix',
  [ReviewMode.COMPLEXITY]: 'Paste code to analyze',
  [ReviewMode.DUPLICATION]: 'Paste code to scan',
};

const LANGUAGE_LABELS: Record<Language, string> = {
  [Language.PYTHON]: 'Python',
  [Language.C]: 'C',
  [Language.JAVA]: 'Java',
};

const Composer: React.FC = () => {
  const {
    code,
    setCode,
    spec,
    setSpec,
    mode,
    language,
    targetLanguage,
    submitReview,
    cancelReview,
    isLoading,
  } = useReviewContext();

  const specMode = isSpecMode(mode);
  const value = specMode ? spec : code;
  const setValue = specMode ? setSpec : setCode;
  const canSubmit = value.trim().length > 0;

  const contextLabel =
    mode === ReviewMode.TRANSLATE
      ? `${LANGUAGE_LABELS[language]} → ${LANGUAGE_LABELS[targetLanguage]}`
      : LANGUAGE_LABELS[language];

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter inserts a newline.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (canSubmit && !isLoading) submitReview();
    }
  };

  return (
    <div className="flex-none border-t border-white/5 bg-ink-900 px-6 py-4">
      <div className="flex items-center gap-2 mb-2 text-xs text-fg-muted">
        <span className="px-2 py-0.5 rounded bg-ink-800 text-sky">{MODE_HINT[mode]}</span>
        <span className="px-2 py-0.5 rounded bg-ink-800 text-sand">{contextLabel}</span>
        <span className="ml-auto text-fg-muted/70">Enter to send · Shift+Enter for newline</span>
      </div>

      <div className="flex items-end gap-3">
        <div className="flex-1 rounded-2xl bg-ink-850 border border-white/5 focus-within:border-sky/40 transition-colors overflow-hidden">
          <textarea
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={3}
            spellCheck="false"
            placeholder={specMode ? 'e.g. A binary search tree with insert, delete, and in-order traversal.' : PLACEHOLDERS[language]}
            className={`block w-full resize-none bg-transparent text-fg px-4 py-3 border-0 focus:outline-none text-sm max-h-52 ${
              specMode ? '' : 'font-mono'
            }`}
          />
        </div>

        {isLoading ? (
          <button
            onClick={cancelReview}
            className="h-12 w-12 rounded-2xl bg-ink-800 text-fg-soft hover:text-fg hover:bg-ink-700 transition-all flex items-center justify-center flex-none"
            title="Stop generating"
          >
            <Square size={18} />
          </button>
        ) : (
          <button
            onClick={submitReview}
            disabled={!canSubmit}
            className={`h-12 w-12 rounded-2xl flex items-center justify-center flex-none transition-all ${
              canSubmit
                ? 'bg-sand text-ink-950 hover:bg-sand-dark'
                : 'bg-ink-800 text-fg-muted cursor-not-allowed'
            }`}
            title="Send"
          >
            <Send size={18} />
          </button>
        )}
      </div>
    </div>
  );
};

export default Composer;

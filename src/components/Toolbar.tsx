import React from 'react';
import { ArrowRight, Cloud, Cpu, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useReviewContext } from '../contexts/ReviewContext';
import { Language, ReviewMode } from '../types';

const FALLBACK_LANGUAGES = [
  { id: Language.PYTHON, label: 'Python' },
  { id: Language.C, label: 'C' },
  { id: Language.JAVA, label: 'Java' },
];

const selectClasses =
  'w-full bg-ink-850 text-fg text-sm rounded-lg px-3 py-2 border border-white/5 ' +
  'focus:ring-2 focus:ring-sky/40 focus:outline-none';

/** Language + model controls for the right-hand panel. */
const Toolbar: React.FC = () => {
  const {
    language,
    setLanguage,
    targetLanguage,
    setTargetLanguage,
    languages,
    mode,
    models,
    modelKey,
    setModelKey,
    health,
  } = useReviewContext();

  const options = languages.length
    ? languages.map((item) => ({ id: item.id, label: item.label }))
    : FALLBACK_LANGUAGES;

  const isTranslate = mode === ReviewMode.TRANSLATE;
  const outputLanguage = isTranslate ? targetLanguage : language;
  const verifier = health?.toolchains?.[outputLanguage];
  const activeModel = models.find((item) => item.key === modelKey);

  return (
    <div className="space-y-4">
      <div>
        <p className="text-[11px] uppercase tracking-wide text-fg-muted mb-2">
          {isTranslate ? 'Translate' : 'Language'}
        </p>
        <select
          value={language}
          onChange={(event) => setLanguage(event.target.value as Language)}
          className={selectClasses}
        >
          {options.map((item) => (
            <option key={item.id} value={item.id}>
              {isTranslate ? `From ${item.label}` : item.label}
            </option>
          ))}
        </select>

        {isTranslate && (
          <div className="mt-2 flex items-center gap-2">
            <ArrowRight size={16} className="text-sand flex-none" />
            <select
              value={targetLanguage}
              onChange={(event) => setTargetLanguage(event.target.value as Language)}
              className={selectClasses}
            >
              {options
                .filter((item) => item.id !== language)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    To {item.label}
                  </option>
                ))}
            </select>
          </div>
        )}

        {verifier && (
          <div
            className={`mt-2 flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg ${
              verifier.available ? 'text-sky bg-sky/10' : 'text-sand bg-sand/10'
            }`}
            title={
              verifier.available
                ? `Generated code is compile-checked with ${verifier.compiler}.`
                : `${verifier.compiler} is not installed, so output cannot be compile-checked.`
            }
          >
            {verifier.available ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
            {verifier.available
              ? `Verified with ${verifier.compiler}`
              : `${verifier.compiler} not installed`}
          </div>
        )}
      </div>

      {models.length > 0 && (
        <div>
          <p className="text-[11px] uppercase tracking-wide text-fg-muted mb-2">Model</p>
          <div className="flex items-center gap-2">
            {activeModel?.cloud ? (
              <Cloud size={16} className="text-sand flex-none" />
            ) : (
              <Cpu size={16} className="text-sky flex-none" />
            )}
            <select
              value={modelKey}
              onChange={(event) => setModelKey(event.target.value)}
              className={selectClasses}
              title={activeModel?.description}
            >
              {models.map((item) => (
                <option key={item.key} value={item.key} disabled={!item.available}>
                  {item.label}
                  {item.available ? '' : ' — not installed'}
                </option>
              ))}
            </select>
          </div>
          {activeModel?.description && (
            <p className="text-xs text-fg-muted mt-1.5">{activeModel.description}</p>
          )}
          {activeModel?.cloud && (
            <p className="text-xs text-sand mt-1">Code leaves this machine.</p>
          )}
        </div>
      )}
    </div>
  );
};

export default Toolbar;

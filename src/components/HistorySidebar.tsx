import React from 'react';
import {
  AlignJustify,
  BarChart2,
  Clock,
  Copy,
  FileCheck,
  FlaskConical,
  History,
  Languages,
  ShieldCheck,
  Sparkles,
  Wand2,
  XCircle,
} from 'lucide-react';
import { useReviewContext } from '../contexts/ReviewContext';
import { CodeReview, Language, ReviewMode } from '../types';

const MODE_ICONS: Record<ReviewMode, React.ReactNode> = {
  [ReviewMode.EXPLAIN]: <AlignJustify size={13} />,
  [ReviewMode.CORRECT]: <FileCheck size={13} />,
  [ReviewMode.COMPLEXITY]: <BarChart2 size={13} />,
  [ReviewMode.DUPLICATION]: <Copy size={13} />,
  [ReviewMode.GENERATE]: <Sparkles size={13} />,
  [ReviewMode.COMPLETE]: <Wand2 size={13} />,
  [ReviewMode.TRANSLATE]: <Languages size={13} />,
  [ReviewMode.TESTS]: <FlaskConical size={13} />,
};

const LANGUAGE_LABELS: Record<Language, string> = {
  [Language.PYTHON]: 'Python',
  [Language.C]: 'C',
  [Language.JAVA]: 'Java',
};

const formatTime = (date: Date) =>
  new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: 'numeric',
    hour12: true,
  }).format(date instanceof Date ? date : new Date(date));

const HistorySidebar: React.FC = () => {
  const { history, restoreFromHistory } = useReviewContext();

  const languageLabel = (review: CodeReview) =>
    review.mode === ReviewMode.TRANSLATE && review.targetLanguage
      ? `${LANGUAGE_LABELS[review.language]} → ${LANGUAGE_LABELS[review.targetLanguage]}`
      : LANGUAGE_LABELS[review.language];

  const preview = (review: CodeReview) =>
    (review.mode === ReviewMode.GENERATE ? review.spec : review.code) || review.result;

  return (
    <div className="h-full flex flex-col bg-ink-900">
      <div className="flex items-center gap-2 px-4 h-14 border-b border-white/5 flex-none">
        <History size={16} className="text-sky" />
        <h2 className="text-sm font-semibold text-fg">History</h2>
        {history.length > 0 && (
          <span className="ml-auto text-xs text-fg-muted bg-ink-800 rounded-full px-2 py-0.5">
            {history.length}
          </span>
        )}
      </div>

      {history.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
          <Clock className="text-fg-muted mb-2" size={22} />
          <p className="text-fg-muted text-sm">Your runs will appear here</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto scroll-slim p-3 space-y-2">
          {history.map((review) => (
            <button
              key={review.id}
              type="button"
              onClick={() => restoreFromHistory(review)}
              className="w-full text-left rounded-lg p-3 bg-ink-850 border border-transparent
                         hover:border-sky/30 hover:bg-ink-800 transition-colors"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-sand/15 text-sand flex-none">
                  {MODE_ICONS[review.mode]}
                  <span className="capitalize">{review.mode}</span>
                </span>
                <span className="flex items-center gap-1 text-xs text-fg-muted flex-none">
                  {review.verification?.status === 'passed' && (
                    <ShieldCheck size={12} className="text-sky" />
                  )}
                  {review.verification?.status === 'failed' && (
                    <XCircle size={12} className="text-danger" />
                  )}
                  {formatTime(review.timestamp)}
                </span>
              </div>
              <p className="text-[11px] text-fg-muted mb-1">{languageLabel(review)}</p>
              <p className="text-xs text-fg-soft font-mono truncate">
                {preview(review).slice(0, 90)}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default HistorySidebar;

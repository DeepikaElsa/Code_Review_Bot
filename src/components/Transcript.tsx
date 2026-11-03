import React from 'react';
import { Bot, MessageSquareCode, User, XCircle } from 'lucide-react';
import { useReviewContext } from '../contexts/ReviewContext';
import { CodeReview, Language, ReviewMode, isSpecMode } from '../types';
import ResultView from './ResultView';

const LANGUAGE_LABELS: Record<Language, string> = {
  [Language.PYTHON]: 'Python',
  [Language.C]: 'C',
  [Language.JAVA]: 'Java',
};

const MODE_LABELS: Record<ReviewMode, string> = {
  [ReviewMode.EXPLAIN]: 'Explain',
  [ReviewMode.CORRECT]: 'Correct',
  [ReviewMode.COMPLEXITY]: 'Complexity',
  [ReviewMode.DUPLICATION]: 'Duplication',
  [ReviewMode.GENERATE]: 'Generate',
  [ReviewMode.COMPLETE]: 'Complete',
  [ReviewMode.TRANSLATE]: 'Translate',
  [ReviewMode.TESTS]: 'Tests',
};

const langLabel = (mode: ReviewMode, language: Language, target?: Language) =>
  mode === ReviewMode.TRANSLATE && target
    ? `${LANGUAGE_LABELS[language]} → ${LANGUAGE_LABELS[target]}`
    : LANGUAGE_LABELS[language];

const MetaChip: React.FC<{ text: string }> = ({ text }) => (
  <span className="text-[11px] uppercase tracking-wide text-fg-muted">{text}</span>
);

const UserBubble: React.FC<{
  content: string;
  mode: ReviewMode;
  language: Language;
  target?: Language;
}> = ({ content, mode, language, target }) => (
  <div className="flex justify-end gap-3">
    <div className="max-w-[80%] min-w-0">
      <div className="flex items-center justify-end gap-2 mb-1">
        <MetaChip text={`${MODE_LABELS[mode]} · ${langLabel(mode, language, target)}`} />
      </div>
      <div className="bg-ink-700 text-fg rounded-2xl rounded-tr-sm px-4 py-3">
        <pre className="text-sm font-mono whitespace-pre-wrap break-words max-h-60 overflow-y-auto scroll-slim">
          {content.trim()}
        </pre>
      </div>
    </div>
    <div className="w-8 h-8 rounded-full bg-ink-700 flex items-center justify-center flex-none mt-6">
      <User size={16} className="text-sky" />
    </div>
  </div>
);

const AssistantShell: React.FC<{ children: React.ReactNode; meta?: string }> = ({
  children,
  meta,
}) => (
  <div className="flex justify-start gap-3">
    <div className="w-8 h-8 rounded-full bg-sand/20 flex items-center justify-center flex-none mt-6">
      <Bot size={16} className="text-sand" />
    </div>
    <div className="max-w-[85%] min-w-0">
      {meta && (
        <div className="mb-1">
          <MetaChip text={meta} />
        </div>
      )}
      <div className="bg-ink-850 rounded-2xl rounded-tl-sm px-4 py-3">{children}</div>
    </div>
  </div>
);

const HistoryExchange: React.FC<{ review: CodeReview }> = ({ review }) => {
  const userContent =
    (review.mode === ReviewMode.GENERATE ? review.spec : review.code) || review.result;

  return (
    <>
      <UserBubble
        content={userContent}
        mode={review.mode}
        language={review.language}
        target={review.targetLanguage}
      />
      <AssistantShell meta={review.model ? `Model: ${review.model}` : undefined}>
        <ResultView
          mode={review.mode}
          language={review.language}
          targetLanguage={review.targetLanguage}
          result={review.result}
          verification={review.verification}
          attempts={review.attempts}
        />
      </AssistantShell>
    </>
  );
};

const Transcript: React.FC = () => {
  const {
    history,
    isLoading,
    streamingText,
    stage,
    attempts,
    error,
    code,
    spec,
    mode,
    language,
    targetLanguage,
  } = useReviewContext();

  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [history.length, streamingText, isLoading, error]);

  // Newest at the bottom, like a chat.
  const ordered = React.useMemo(() => [...history].reverse(), [history]);

  const isEmpty = ordered.length === 0 && !isLoading && !error;

  if (isEmpty) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
        <div className="w-14 h-14 rounded-2xl bg-ink-800 flex items-center justify-center mb-4">
          <MessageSquareCode size={26} className="text-sky" />
        </div>
        <h2 className="text-lg font-semibold text-fg">Write or review code</h2>
        <p className="text-sm text-fg-muted mt-2 max-w-sm">
          Pick a mode and language on the right, type below, and press send. Generated
          code is compiled and auto-repaired before you see it.
        </p>
      </div>
    );
  }

  const pendingUserContent = isSpecMode(mode) ? spec : code;

  return (
    <div className="flex-1 overflow-y-auto scroll-slim px-6 py-6 space-y-6">
      {ordered.map((review) => (
        <HistoryExchange key={review.id} review={review} />
      ))}

      {isLoading && (
        <>
          {pendingUserContent.trim() && (
            <UserBubble
              content={pendingUserContent}
              mode={mode}
              language={language}
              target={targetLanguage}
            />
          )}
          <AssistantShell
            meta={attempts > 1 ? `Repair pass ${attempts}` : stage || 'Working'}
          >
            {streamingText ? (
              <pre className="text-sm text-fg-soft font-mono whitespace-pre-wrap break-words">
                {streamingText}
                <span className="inline-block w-2 h-4 bg-sky/70 align-middle animate-pulse ml-0.5" />
              </pre>
            ) : (
              <div className="flex items-center gap-2 text-fg-muted text-sm">
                <div className="w-4 h-4 border-t-2 border-r-2 border-sky rounded-full animate-spin" />
                {stage === 'connecting' ? 'Connecting to the model…' : 'Thinking…'}
              </div>
            )}
          </AssistantShell>
        </>
      )}

      {error && (
        <AssistantShell meta="Error">
          <div className="flex items-start gap-2 text-danger">
            <XCircle size={18} className="mt-0.5 flex-none" />
            <div>
              <p className="font-semibold">Request failed</p>
              <p className="text-sm text-fg-soft mt-1">{error}</p>
            </div>
          </div>
        </AssistantShell>
      )}

      <div ref={bottomRef} />
    </div>
  );
};

export default Transcript;

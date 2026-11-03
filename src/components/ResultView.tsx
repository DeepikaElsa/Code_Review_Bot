import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  AlertTriangle,
  Check,
  CircleSlash,
  Copy,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import {
  Language,
  ReviewMode,
  VerificationResult,
  isCodeOutputMode,
} from '../types';

const HIGHLIGHTER: Record<Language, string> = {
  [Language.PYTHON]: 'python',
  [Language.C]: 'c',
  [Language.JAVA]: 'java',
};

const VerificationBadge: React.FC<{
  verification: VerificationResult;
  attempts: number;
}> = ({ verification, attempts }) => {
  const [expanded, setExpanded] = React.useState(false);

  const styles: Record<
    string,
    { className: string; icon: React.ReactNode; label: string }
  > = {
    passed: {
      className: 'text-sky bg-sky/10 border-sky/30',
      icon: <ShieldCheck size={14} />,
      label: 'Compiles',
    },
    failed: {
      className: 'text-danger bg-danger/10 border-danger/30',
      icon: <XCircle size={14} />,
      label: 'Does not compile',
    },
    unavailable: {
      className: 'text-sand bg-sand/10 border-sand/30',
      icon: <AlertTriangle size={14} />,
      label: 'Not verified',
    },
    skipped: {
      className: 'text-rose bg-rose/10 border-rose/30',
      icon: <CircleSlash size={14} />,
      label: 'Verification skipped',
    },
    error: {
      className: 'text-sand bg-sand/10 border-sand/30',
      icon: <AlertTriangle size={14} />,
      label: 'Verifier error',
    },
  };

  const style = styles[verification.status] ?? styles.skipped;
  const hasOutput = Boolean(verification.output);

  return (
    <div className="mb-3">
      <button
        type="button"
        onClick={() => hasOutput && setExpanded((value) => !value)}
        className={`w-full text-left flex items-center gap-2 text-xs px-3 py-2 rounded-lg border ${style.className} ${
          hasOutput ? 'cursor-pointer' : 'cursor-default'
        }`}
      >
        {style.icon}
        <span className="font-semibold">{style.label}</span>
        <span className="opacity-80 truncate">— {verification.detail}</span>
        {attempts > 1 && (
          <span className="ml-auto opacity-80 flex-none">
            {attempts} passes · auto-repaired
          </span>
        )}
      </button>

      {expanded && hasOutput && (
        <pre className="mt-2 p-3 rounded-lg bg-ink-950 text-xs text-fg-soft overflow-x-auto whitespace-pre-wrap scroll-slim">
          {verification.output}
        </pre>
      )}
    </div>
  );
};

interface ResultViewProps {
  mode: ReviewMode;
  language: Language;
  targetLanguage?: Language;
  result: string;
  verification: VerificationResult | null;
  attempts: number;
}

const ResultView: React.FC<ResultViewProps> = ({
  mode,
  language,
  targetLanguage,
  result,
  verification,
  attempts,
}) => {
  const [copied, setCopied] = React.useState(false);

  const outputLanguage = mode === ReviewMode.TRANSLATE ? targetLanguage ?? language : language;
  const highlighter = HIGHLIGHTER[outputLanguage] ?? 'text';

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderCode = () => {
    const match = result.match(/```[a-z+#-]*\n([\s\S]*?)```/i);
    const code = match ? match[1].trim() : result;

    return (
      <div className="relative">
        <button
          onClick={() => handleCopy(code)}
          className="absolute top-2 right-2 z-10 p-2 rounded-md bg-ink-700/60 hover:bg-ink-600 transition-all"
          title="Copy code"
        >
          {copied ? (
            <Check size={16} className="text-sky" />
          ) : (
            <Copy size={16} className="text-fg-soft" />
          )}
        </button>
        <div className="overflow-hidden rounded-lg">
          <SyntaxHighlighter
            language={highlighter}
            style={vscDarkPlus}
            showLineNumbers
            wrapLines
            customStyle={{ margin: 0, borderRadius: '8px', background: '#06172c' }}
          >
            {code}
          </SyntaxHighlighter>
        </div>
      </div>
    );
  };

  const renderBullets = () => (
    <div className="text-fg-soft">
      {result
        .split('\n')
        .filter((line) => line.trim())
        .map((line, index) => (
          <div key={index} className="py-1">
            {line.startsWith('-') ? (
              <div className="flex">
                <span className="text-sky mr-2">→</span>
                <span>{line.slice(1)}</span>
              </div>
            ) : (
              line
            )}
          </div>
        ))}
    </div>
  );

  const renderSections = () => {
    const formatted = result.replace(/\*\s/g, '→ ').replace(/\*/g, '');
    return (
      <div className="text-fg-soft space-y-3">
        {formatted.split('\n\n').map((section, index) => (
          <div key={index} className="bg-ink-950/60 rounded-lg p-3">
            {section.split('\n').map((line, lineIndex) => (
              <div key={lineIndex} className="py-0.5">
                {line.startsWith('→') ? (
                  <div className="flex text-sky">
                    <span className="mr-2">→</span>
                    <span>{line.slice(2)}</span>
                  </div>
                ) : (
                  <div className={line.startsWith('#') ? 'text-base font-semibold text-fg mb-1' : ''}>
                    {line.startsWith('#') ? line.replace(/^#+\s*/, '') : line}
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  };

  const renderBody = () => {
    if (isCodeOutputMode(mode)) return renderCode();
    if (mode === ReviewMode.EXPLAIN) return renderBullets();
    if (mode === ReviewMode.COMPLEXITY || mode === ReviewMode.DUPLICATION) {
      return renderSections();
    }
    return <div className="text-fg-soft whitespace-pre-wrap">{result}</div>;
  };

  return (
    <div>
      {verification && <VerificationBadge verification={verification} attempts={attempts} />}
      {renderBody()}
    </div>
  );
};

export default ResultView;

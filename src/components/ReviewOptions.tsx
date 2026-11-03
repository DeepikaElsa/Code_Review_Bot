import React from 'react';
import {
  AlignJustify,
  BarChart2,
  Copy,
  FileCheck,
  FlaskConical,
  Languages,
  Sparkles,
  Wand2,
} from 'lucide-react';
import { useReviewContext } from '../contexts/ReviewContext';
import { ReviewMode } from '../types';

interface ModeOption {
  label: string;
  value: ReviewMode;
  icon: React.ReactNode;
}

const WRITE_OPTIONS: ModeOption[] = [
  { label: 'Generate', value: ReviewMode.GENERATE, icon: <Sparkles size={16} /> },
  { label: 'Complete', value: ReviewMode.COMPLETE, icon: <Wand2 size={16} /> },
  { label: 'Translate', value: ReviewMode.TRANSLATE, icon: <Languages size={16} /> },
  { label: 'Tests', value: ReviewMode.TESTS, icon: <FlaskConical size={16} /> },
];

const REVIEW_OPTIONS: ModeOption[] = [
  { label: 'Explain', value: ReviewMode.EXPLAIN, icon: <AlignJustify size={16} /> },
  { label: 'Correct', value: ReviewMode.CORRECT, icon: <FileCheck size={16} /> },
  { label: 'Complexity', value: ReviewMode.COMPLEXITY, icon: <BarChart2 size={16} /> },
  { label: 'Duplication', value: ReviewMode.DUPLICATION, icon: <Copy size={16} /> },
];

const ReviewOptions: React.FC = () => {
  const { mode, setMode } = useReviewContext();

  const renderGrid = (options: ModeOption[]) => (
    <div className="grid grid-cols-2 gap-2">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => setMode(option.value)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
            mode === option.value
              ? 'bg-sand text-ink-950 font-medium'
              : 'bg-ink-850 text-fg-soft hover:bg-ink-800'
          }`}
        >
          {option.icon}
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  );

  return (
    <div className="space-y-4">
      <div>
        <p className="text-[11px] uppercase tracking-wide text-fg-muted mb-2">Write</p>
        {renderGrid(WRITE_OPTIONS)}
      </div>
      <div>
        <p className="text-[11px] uppercase tracking-wide text-fg-muted mb-2">Review</p>
        {renderGrid(REVIEW_OPTIONS)}
      </div>
    </div>
  );
};

export default ReviewOptions;

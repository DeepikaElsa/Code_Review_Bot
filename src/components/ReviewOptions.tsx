import React from 'react';
import { useReviewContext } from '../contexts/ReviewContext';
import { ReviewMode } from '../types';
import { FileCheck, AlignJustify, BarChart2, Copy } from 'lucide-react';

const ReviewOptions: React.FC = () => {
  const { mode, setMode } = useReviewContext();

  const options = [
    {
      label: 'Explain',
      value: ReviewMode.EXPLAIN,
      icon: <AlignJustify size={18} />,
      description: 'Get a detailed explanation in bullet points'
    },
    {
      label: 'Correct',
      value: ReviewMode.CORRECT,
      icon: <FileCheck size={18} />,
      description: 'Get corrected code with improvements'
    },
    {
      label: 'Complexity',
      value: ReviewMode.COMPLEXITY,
      icon: <BarChart2 size={18} />,
      description: 'Analyze code complexity metrics'
    },
    {
      label: 'Duplication',
      value: ReviewMode.DUPLICATION,
      icon: <Copy size={18} />,
      description: 'Detect duplicate code patterns'
    }
  ];

  return (
    <div className="flex-none mb-4">
      <div className="flex gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            onClick={() => setMode(option.value)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-all ${
              mode === option.value
                ? 'bg-[#1ABC9C] text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {option.icon}
            <span>{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default ReviewOptions;
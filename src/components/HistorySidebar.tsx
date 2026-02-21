import React from 'react';
import { useReviewContext } from '../contexts/ReviewContext';
import { ReviewMode } from '../types';
import { Clock, FileCheck, AlignJustify, BarChart2, Copy } from 'lucide-react';

const HistorySidebar: React.FC = () => {
  const { history } = useReviewContext();

  const getModeIcon = (mode: ReviewMode) => {
    switch (mode) {
      case ReviewMode.EXPLAIN:
        return <AlignJustify size={14} />;
      case ReviewMode.CORRECT:
        return <FileCheck size={14} />;
      case ReviewMode.COMPLEXITY:
        return <BarChart2 size={14} />;
      case ReviewMode.DUPLICATION:
        return <Copy size={14} />;
    }
  };

  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: 'numeric',
      hour12: true
    }).format(date);
  };

  if (history.length === 0) {
    return (
      <div className="h-full p-4 bg-[#454545]">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">History</h2>
        <div className="flex flex-col items-center justify-center h-40 text-center">
          <Clock className="text-gray-400 mb-2" size={24} />
          <p className="text-gray-400 text-sm">
            Your review history will appear here
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full p-4 overflow-y-auto bg-[#454545]">
      <h2 className="text-lg font-semibold text-gray-200 mb-4">History</h2>
      <div className="space-y-3">
        {history.map((review) => (
          <div
            key={review.id}
            className="border border-gray-700 rounded-md p-3 hover:border-[#1ABC9C] transition-colors cursor-pointer bg-[#2D2E26]"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center text-sm">
                <span className={`
                  inline-flex items-center px-2 py-1 rounded text-xs mr-2
                  bg-[#1ABC9C] text-gray-800
                `}>
                  {getModeIcon(review.mode)}
                  <span className="ml-1 capitalize">{review.mode}</span>
                </span>
                <span className="text-gray-400 flex items-center">
                  <Clock size={12} className="mr-1" />
                  {formatTime(review.timestamp)}
                </span>
              </div>
            </div>
            <div className="text-xs bg-[#2D2E26] rounded p-2 font-mono whitespace-nowrap overflow-hidden text-ellipsis text-gray-300">
              {review.code.slice(0, 120)}
              {review.code.length > 120 && '...'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default HistorySidebar;
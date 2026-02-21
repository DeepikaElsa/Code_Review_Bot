import React from 'react';
import { useReviewContext } from '../contexts/ReviewContext';

const CodeEditor: React.FC = () => {
  const { code, setCode, submitReview, isLoading } = useReviewContext();

  return (
    <div className="flex flex-col space-y-4">
      <div className="relative rounded-md shadow-sm bg-[#2D2E26] overflow-hidden">
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="block w-full resize-none bg-transparent text-gray-200 px-4 py-3 border-0 focus:ring-2 focus:ring-[#1ABC9C] focus:outline-none font-mono text-sm h-[200px]"
          placeholder="Enter code for review..."
          spellCheck="false"
        />
        {!code && (
          <div className="absolute inset-0 pointer-events-none p-4 text-gray-500 font-mono flex items-center justify-center text-center">
            <span>// Paste your code here to get started</span>
          </div>
        )}
      </div>
      <button
        onClick={submitReview}
        disabled={isLoading}
        className={`w-full py-2.5 px-4 rounded-md text-white font-medium shadow transition-all ${
          isLoading
            ? 'bg-[#1ABC9C] opacity-70 cursor-not-allowed'
            : 'bg-[#1ABC9C] hover:bg-[#16A085]'
        }`}
      >
        {isLoading ? (
          <div className="flex items-center justify-center">
            <div className="w-5 h-5 border-t-2 border-r-2 border-white rounded-full animate-spin mr-2"></div>
            Processing...
          </div>
        ) : (
          'Review Code'
        )}
      </button>
    </div>
  );
};

export default CodeEditor;
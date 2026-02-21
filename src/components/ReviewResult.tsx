import React from 'react';
import { useReviewContext } from '../contexts/ReviewContext';
import { ReviewMode } from '../types';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check } from 'lucide-react';

const ReviewResult: React.FC = () => {
  const { mode, result, isLoading } = useReviewContext();
  const [copied, setCopied] = React.useState(false);

  if (!result && !isLoading) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-40 bg-[#2D2E26] rounded-lg">
        <div className="w-10 h-10 border-t-2 border-r-2 border-[#1ABC9C] rounded-full animate-spin mb-4"></div>
        <p className="text-gray-300">Analyzing your code...</p>
      </div>
    );
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderContent = () => {
    switch (mode) {
      case ReviewMode.EXPLAIN:
        return (
          <div className="p-4 text-gray-200">
            {result.split('\n').filter(line => line.trim()).map((line, index) => (
              <div key={index} className="py-1">
                {line.startsWith('-') ? (
                  <div className="flex">
                    <span className="text-[#1ABC9C] mr-2">→</span>
                    <span>{line.slice(1)}</span>
                  </div>
                ) : (
                  line
                )}
              </div>
            ))}
          </div>
        );
        
      case ReviewMode.CORRECT:
        const codeMatch = result.match(/```[a-z]*\n([\s\S]*?)```/);
        const code = codeMatch ? codeMatch[1].trim() : result;
        
        return (
          <div className="relative">
            <button
              onClick={() => handleCopy(code)}
              className="absolute top-2 right-2 p-2 rounded-md bg-[#1ABC9C] bg-opacity-20 hover:bg-opacity-30 transition-all"
              title="Copy code"
            >
              {copied ? <Check size={16} className="text-[#1ABC9C]" /> : <Copy size={16} className="text-[#1ABC9C]" />}
            </button>
            <div className="overflow-hidden rounded-md">
              <SyntaxHighlighter
                language="python"
                style={vscDarkPlus}
                showLineNumbers
                wrapLines
                customStyle={{ margin: 0, borderRadius: '6px', background: '#2D2E26' }}
              >
                {code}
              </SyntaxHighlighter>
            </div>
          </div>
        );

      case ReviewMode.COMPLEXITY:
      case ReviewMode.DUPLICATION:
        const formattedResult = result.replace(/\*\s/g, '→ ').replace(/\*/g, '');
        return (
          <div className="p-4 text-gray-200 space-y-4">
            {formattedResult.split('\n\n').map((section, index) => (
              <div key={index} className="bg-[#2D2E26] rounded-lg p-4">
                {section.split('\n').map((line, lineIndex) => (
                  <div key={lineIndex} className="py-1">
                    {line.startsWith('→') ? (
                      <div className="flex text-[#1ABC9C]">
                        <span className="mr-2">→</span>
                        <span>{line.slice(2)}</span>
                      </div>
                    ) : (
                      <div className={line.startsWith('#') ? 'text-lg font-semibold mb-2' : ''}>
                        {line.startsWith('#') ? line.slice(2) : line}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        );
        
      default:
        return <div className="p-4 text-gray-200">{result}</div>;
    }
  };

  return (
    <div className="bg-[#2D2E26] rounded-lg overflow-hidden">
      {renderContent()}
    </div>
  );
};

export default ReviewResult;
import React, { createContext, useContext, useState } from 'react';
import { CodeReview, ReviewContextType, ReviewMode } from '../types';
import { v4 as uuidv4 } from 'uuid';

const ReviewContext = createContext<ReviewContextType | undefined>(undefined);

export const useReviewContext = () => {
  const context = useContext(ReviewContext);
  if (!context) {
    throw new Error('useReviewContext must be used within a ReviewProvider');
  }
  return context;
};

export const ReviewProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [code, setCode] = useState<string>('');
  const [mode, setMode] = useState<ReviewMode>(ReviewMode.EXPLAIN);
  const [result, setResult] = useState<string>('');
  const [history, setHistory] = useState<CodeReview[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const addToHistory = (review: CodeReview) => {
    setHistory((prev) => [review, ...prev]);
  };

  const submitReview = async () => {
    if (!code.trim()) return;
    
    setIsLoading(true);
    
    try {
      const response = await fetch('http://localhost:5000/api/review', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        mode: 'cors',
        credentials: 'same-origin',
        body: JSON.stringify({
          code,
          mode: mode.toLowerCase(),
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      let formattedResult = data.result;

      // Format the result based on the mode
      if (mode === ReviewMode.EXPLAIN) {
        // Convert text into bullet points if not already
        formattedResult = formattedResult
          .split('\n')
          .filter(line => line.trim())
          .map(line => line.startsWith('-') ? line : `- ${line}`)
          .join('\n');
      } else if (mode === ReviewMode.CORRECT) {
        // Wrap code in markdown code block if not already
        if (!formattedResult.includes('```')) {
          formattedResult = '```python\n' + formattedResult + '\n```';
        }
      } else if (mode === ReviewMode.FLOWCHART) {
        // Ensure proper mermaid flowchart format
        if (!formattedResult.includes('graph')) {
          formattedResult = 'graph TD\n' + formattedResult;
        }
      }
      
      setResult(formattedResult);
      
      const review: CodeReview = {
        id: uuidv4(),
        code,
        mode,
        result: formattedResult,
        timestamp: new Date(),
      };
      
      addToHistory(review);
    } catch (error) {
      console.error('Error submitting review:', error);
      setResult('An error occurred while processing your code. Please try again. ' + (error instanceof Error ? error.message : ''));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ReviewContext.Provider
      value={{
        code,
        setCode,
        mode,
        setMode,
        result,
        setResult,
        history,
        addToHistory,
        isLoading,
        setIsLoading,
        submitReview,
      }}
    >
      {children}
    </ReviewContext.Provider>
  );
};
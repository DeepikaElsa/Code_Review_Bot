export interface CodeReview {
  id: string;
  code: string;
  mode: ReviewMode;
  result: string;
  timestamp: Date;
}

export enum ReviewMode {
  EXPLAIN = 'explain',
  CORRECT = 'correct',
  COMPLEXITY = 'complexity',
  DUPLICATION = 'duplication'
}

export interface ReviewContextType {
  code: string;
  setCode: (code: string) => void;
  mode: ReviewMode;
  setMode: (mode: ReviewMode) => void;
  result: string;
  setResult: (result: string) => void;
  history: CodeReview[];
  addToHistory: (review: CodeReview) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  submitReview: () => void;
}
export enum Language {
  PYTHON = 'python',
  C = 'c',
  JAVA = 'java',
}

export interface LanguageInfo {
  id: Language;
  label: string;
  extension: string;
  highlighter: string;
  verifierAvailable: boolean;
  compiler: string | null;
}

export enum ReviewMode {
  // Review modes: analyse code that already exists.
  EXPLAIN = 'explain',
  CORRECT = 'correct',
  COMPLEXITY = 'complexity',
  DUPLICATION = 'duplication',
  // Writing modes: produce new code.
  GENERATE = 'generate',
  COMPLETE = 'complete',
  TRANSLATE = 'translate',
  TESTS = 'tests',
}

/** Modes whose output is a source file rather than prose. */
export const CODE_OUTPUT_MODES: ReviewMode[] = [
  ReviewMode.CORRECT,
  ReviewMode.GENERATE,
  ReviewMode.COMPLETE,
  ReviewMode.TRANSLATE,
  ReviewMode.TESTS,
];

/** Modes driven by a written specification instead of pasted code. */
export const SPEC_MODES: ReviewMode[] = [ReviewMode.GENERATE];

export const isCodeOutputMode = (mode: ReviewMode) => CODE_OUTPUT_MODES.includes(mode);
export const isSpecMode = (mode: ReviewMode) => SPEC_MODES.includes(mode);

export type VerificationStatus =
  | 'passed'
  | 'failed'
  | 'unavailable'
  | 'skipped'
  | 'error';

export interface VerificationResult {
  ok: boolean;
  status: VerificationStatus;
  tool: string | null;
  output: string;
  detail: string;
}

export interface ModelOption {
  key: string;
  label: string;
  description: string;
  cloud: boolean;
  id: string;
  available: boolean;
  default: boolean;
}

export interface HealthInfo {
  status: string;
  ollamaHost: string;
  installedModels: string[];
  missingModels: string[];
  cloudEnabled: boolean;
  cloudKeyPresent: boolean;
  verifyEnabled: boolean;
  toolchains: Record<string, { label: string; compiler: string; available: boolean }>;
}

export interface CodeReview {
  id: string;
  code: string;
  spec: string;
  mode: ReviewMode;
  language: Language;
  targetLanguage?: Language;
  model?: string;
  result: string;
  verification: VerificationResult | null;
  attempts: number;
  timestamp: Date;
}

/** Events streamed by POST /api/generate as newline-delimited JSON. */
export type StreamEvent =
  | { type: 'status'; stage: string }
  | { type: 'token'; text: string }
  | { type: 'verify'; attempt: number } & Partial<VerificationResult>
  | { type: 'repair'; attempt: number; reason: string }
  | { type: 'error'; message: string }
  | {
      type: 'done';
      result: string;
      code: string;
      language: Language;
      mode: ReviewMode;
      model: string;
      attempts: number;
      verification: VerificationResult | null;
    };

export interface ReviewContextType {
  code: string;
  setCode: (code: string) => void;
  spec: string;
  setSpec: (spec: string) => void;
  mode: ReviewMode;
  setMode: (mode: ReviewMode) => void;
  language: Language;
  setLanguage: (language: Language) => void;
  targetLanguage: Language;
  setTargetLanguage: (language: Language) => void;
  modelKey: string;
  setModelKey: (key: string) => void;
  models: ModelOption[];
  languages: LanguageInfo[];
  health: HealthInfo | null;
  result: string;
  setResult: (result: string) => void;
  streamingText: string;
  stage: string;
  verification: VerificationResult | null;
  attempts: number;
  error: string;
  history: CodeReview[];
  addToHistory: (review: CodeReview) => void;
  restoreFromHistory: (review: CodeReview) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  submitReview: () => void;
  cancelReview: () => void;
}

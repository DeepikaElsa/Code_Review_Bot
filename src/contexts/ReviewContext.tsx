import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import {
  CodeReview,
  HealthInfo,
  Language,
  LanguageInfo,
  ModelOption,
  ReviewContextType,
  ReviewMode,
  StreamEvent,
  VerificationResult,
  isCodeOutputMode,
  isSpecMode,
} from '../types';
import { getAccessToken } from '../lib/supabase';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:5000';

const ReviewContext = createContext<ReviewContextType | undefined>(undefined);

export const useReviewContext = () => {
  const context = useContext(ReviewContext);
  if (!context) {
    throw new Error('useReviewContext must be used within a ReviewProvider');
  }
  return context;
};

export const ReviewProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [code, setCode] = useState('');
  const [spec, setSpec] = useState('');
  const [mode, setMode] = useState<ReviewMode>(ReviewMode.EXPLAIN);
  const [language, setLanguage] = useState<Language>(Language.PYTHON);
  const [targetLanguage, setTargetLanguage] = useState<Language>(Language.JAVA);
  const [modelKey, setModelKey] = useState('quality');
  const [models, setModels] = useState<ModelOption[]>([]);
  const [languages, setLanguages] = useState<LanguageInfo[]>([]);
  const [health, setHealth] = useState<HealthInfo | null>(null);

  const [result, setResult] = useState('');
  const [streamingText, setStreamingText] = useState('');
  const [stage, setStage] = useState('');
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<CodeReview[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  // Discover what the backend can do: which models are pulled, which
  // compilers are installed, whether cloud is enabled.
  useEffect(() => {
    const load = async () => {
      try {
        const [healthRes, modelsRes, langsRes] = await Promise.all([
          fetch(`${API_BASE}/api/health`),
          fetch(`${API_BASE}/api/models`),
          fetch(`${API_BASE}/api/languages`),
        ]);
        if (healthRes.ok) setHealth(await healthRes.json());
        if (modelsRes.ok) {
          const list: ModelOption[] = await modelsRes.json();
          setModels(list);
          const preferred =
            list.find((m) => m.default && m.available) ??
            list.find((m) => m.available) ??
            list.find((m) => m.default);
          if (preferred) setModelKey(preferred.key);
        }
        if (langsRes.ok) setLanguages(await langsRes.json());
      } catch {
        // Backend down: the Header status dot reports it, and submitting
        // will surface the real error.
        setHealth(null);
      }
    };
    load();
  }, []);

  const addToHistory = useCallback((review: CodeReview) => {
    setHistory((prev) => [review, ...prev].slice(0, 50));
  }, []);

  const restoreFromHistory = useCallback((review: CodeReview) => {
    setCode(review.code);
    setSpec(review.spec);
    setMode(review.mode);
    setLanguage(review.language);
    if (review.targetLanguage) setTargetLanguage(review.targetLanguage);
    setResult(review.result);
    setVerification(review.verification);
    setAttempts(review.attempts);
    setStreamingText('');
    setError('');
  }, []);

  const cancelReview = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsLoading(false);
    setStage('');
  }, []);

  const submitReview = useCallback(async () => {
    if (isSpecMode(mode) ? !spec.trim() : !code.trim()) return;

    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError('');
    setResult('');
    setStreamingText('');
    setVerification(null);
    setAttempts(0);
    setStage('connecting');

    // For translate, the backend's `language` is the target and the editor's
    // language is the source.
    const outputLanguage = mode === ReviewMode.TRANSLATE ? targetLanguage : language;

    try {
      // Attach the Supabase access token so the backend can authorize the call
      // and enable compile verification for signed-in users.
      const token = await getAccessToken();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = `Bearer ${token}`;

      const response = await fetch(`${API_BASE}/api/generate`, {
        method: 'POST',
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          code,
          spec,
          mode,
          language: outputLanguage,
          sourceLanguage: mode === ReviewMode.TRANSLATE ? language : undefined,
          model: modelKey,
        }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || `Request failed with status ${response.status}`);
      }
      if (!response.body) {
        throw new Error('Streaming is not supported by this browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamed = '';
      let finished = false;

      // Newline-delimited JSON: one event per line, last line may be partial.
      while (!finished) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.trim()) continue;

          let event: StreamEvent;
          try {
            event = JSON.parse(line) as StreamEvent;
          } catch {
            continue;
          }

          if (event.type === 'status') {
            setStage(event.stage);
          } else if (event.type === 'token') {
            streamed += event.text;
            setStreamingText(streamed);
          } else if (event.type === 'repair') {
            // A repair pass restarts the file, so clear the streamed draft.
            setAttempts(event.attempt);
            streamed = '';
            setStreamingText('');
          } else if (event.type === 'verify') {
            setVerification({
              ok: event.ok ?? false,
              status: event.status ?? 'skipped',
              tool: event.tool ?? null,
              output: event.output ?? '',
              detail: event.detail ?? '',
            });
          } else if (event.type === 'error') {
            throw new Error(event.message);
          } else if (event.type === 'done') {
            setResult(event.result);
            setVerification(event.verification);
            setAttempts(event.attempts);
            setStreamingText('');
            setStage('');
            finished = true;

            addToHistory({
              id: uuidv4(),
              code,
              spec,
              mode,
              language,
              targetLanguage: mode === ReviewMode.TRANSLATE ? targetLanguage : undefined,
              model: event.model,
              result: event.result,
              verification: event.verification,
              attempts: event.attempts,
              timestamp: new Date(),
            });
          }
        }
      }

      // Stream ended without a 'done' event: keep whatever arrived.
      if (!finished && streamed) {
        setResult(isCodeOutputMode(mode) ? streamed : streamed.trim());
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.');
    } finally {
      abortRef.current = null;
      setIsLoading(false);
      setStage('');
    }
  }, [addToHistory, code, language, mode, modelKey, spec, targetLanguage]);

  return (
    <ReviewContext.Provider
      value={{
        code,
        setCode,
        spec,
        setSpec,
        mode,
        setMode,
        language,
        setLanguage,
        targetLanguage,
        setTargetLanguage,
        modelKey,
        setModelKey,
        models,
        languages,
        health,
        result,
        setResult,
        streamingText,
        stage,
        verification,
        attempts,
        error,
        history,
        addToHistory,
        restoreFromHistory,
        isLoading,
        setIsLoading,
        submitReview,
        cancelReview,
      }}
    >
      {children}
    </ReviewContext.Provider>
  );
};

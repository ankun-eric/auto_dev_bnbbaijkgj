'use client';

/**
 * [BUG-HSC-FIX-V2 2026-05-21] B-3 通用 ErrorBoundary
 *
 * 捕获子组件运行时异常 → 渲染友好兜底页，避免 Next.js 全局
 * "Application error: a client-side exception has occurred" 白屏。
 *
 * 用法：
 *   <ErrorBoundary fallback={<FriendlyErrorPage onRetry={load} onBack={() => router.back()} />}>
 *     {/* 任意子组件 *\/}
 *   </ErrorBoundary>
 */

import React from 'react';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode | ((err: Error) => React.ReactNode);
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    try {
      // 控制台输出（避免静默吞错）
      // eslint-disable-next-line no-console
      console.error('[ErrorBoundary] caught:', error, info?.componentStack);
    } catch {
      /* noop */
    }
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      const { fallback } = this.props;
      if (typeof fallback === 'function') {
        return fallback(this.state.error || new Error('Unknown error'));
      }
      if (fallback) return fallback as React.ReactNode;
      return (
        <div
          style={{
            minHeight: '60vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
            color: '#64748B',
            background: '#F5F7FB',
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 12 }}>⚠️</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#0F172A', marginBottom: 6 }}>
            页面遇到点小问题
          </div>
          <div style={{ fontSize: 13, marginBottom: 16 }}>请尝试刷新页面或稍后再试</div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              type="button"
              onClick={() => {
                this.reset();
                if (typeof window !== 'undefined') window.location.reload();
              }}
              style={{
                padding: '8px 20px',
                background: '#0EA5E9',
                color: '#FFF',
                border: 'none',
                borderRadius: 8,
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              刷新
            </button>
            <button
              type="button"
              onClick={() => {
                if (typeof window !== 'undefined') window.history.back();
              }}
              style={{
                padding: '8px 20px',
                background: '#FFF',
                color: '#0F172A',
                border: '1px solid #E2E8F0',
                borderRadius: 8,
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              返回
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;

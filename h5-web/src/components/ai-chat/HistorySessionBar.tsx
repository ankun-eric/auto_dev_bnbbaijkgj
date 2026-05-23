'use client';
import React from 'react';

interface HistorySessionBarProps {
  visible: boolean;
  sessionSummary?: string;
  onBackToCurrent: () => void;
  onDismiss: () => void;
}

export default function HistorySessionBar({ visible, sessionSummary, onBackToCurrent, onDismiss }: HistorySessionBarProps) {
  if (!visible) return null;

  return (
    <>
      {/* Top bar */}
      <div style={{
        width: '100%', height: 40,
        background: '#E0F2FE',
        display: 'flex', alignItems: 'center',
        padding: '0 12px', gap: 8,
      }}>
        <span style={{ fontSize: 16, flexShrink: 0 }}>🕐</span>
        <span style={{
          flex: 1, fontSize: 13, color: '#0284C7',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {sessionSummary || '正在查看历史会话'}
        </span>
        <button
          onClick={onDismiss}
          style={{
            background: 'none', border: 'none', padding: 4,
            fontSize: 14, color: '#0284C7', cursor: 'pointer', flexShrink: 0,
          }}
        >✕</button>
      </div>

      {/* Floating back-to-current button */}
      <button
        onClick={onBackToCurrent}
        style={{
          position: 'fixed', right: 16, bottom: 100, zIndex: 900,
          padding: '8px 16px', borderRadius: 24, border: 'none',
          background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
          color: '#FFFFFF', fontSize: 13, fontWeight: 500,
          boxShadow: '0 4px 12px rgba(2,132,199,0.3)',
          cursor: 'pointer', whiteSpace: 'nowrap',
        }}
      >
        回到当前
      </button>
    </>
  );
}

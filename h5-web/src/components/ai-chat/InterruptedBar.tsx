'use client';
import React from 'react';

interface InterruptedBarProps {
  onContinue: () => void;
  onRegenerate: () => void;
}

export default function InterruptedBar({ onContinue, onRegenerate }: InterruptedBarProps) {
  return (
    <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Warning bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: '#FEF3C7', borderRadius: 8, padding: '10px 12px',
      }}>
        <span style={{ fontSize: 16, color: '#F59E0B', flexShrink: 0 }}>⚠️</span>
        <span style={{ fontSize: 13, color: '#92400E' }}>回答已中断</span>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 12 }}>
        <button
          onClick={onContinue}
          style={{
            flex: 1, height: 36, padding: '0 20px', borderRadius: 20,
            background: '#FFFFFF', border: '1px solid #BAE6FD',
            color: '#0284C7', fontSize: 14, fontWeight: 500, cursor: 'pointer',
          }}
        >
          继续生成
        </button>
        <button
          onClick={onRegenerate}
          style={{
            flex: 1, height: 36, padding: '0 20px', borderRadius: 20,
            background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
            border: 'none', color: '#FFFFFF',
            fontSize: 14, fontWeight: 500, cursor: 'pointer',
          }}
        >
          重新回答
        </button>
      </div>
    </div>
  );
}

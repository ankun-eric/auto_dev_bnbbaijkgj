'use client';
import React, { useEffect, useState } from 'react';

interface VoiceInputPanelProps {
  visible: boolean;
  transcript?: string;
  onCancel: () => void;
  onSend: (text: string) => void;
}

const WAVE_BAR_COUNT = 5;

const keyframesId = 'voice-panel-pulse';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(keyframesId)) return;
  const style = document.createElement('style');
  style.id = keyframesId;
  style.textContent = `
    @keyframes voicePulse {
      0%, 100% { transform: scaleY(0.3); }
      50% { transform: scaleY(1); }
    }
    @keyframes voicePanelSlideIn {
      from { transform: translateY(100%); }
      to { transform: translateY(0); }
    }
    @keyframes voicePanelFadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
  `;
  document.head.appendChild(style);
}

export default function VoiceInputPanel({ visible, transcript, onCancel, onSend }: VoiceInputPanelProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    ensureKeyframes();
  }, []);

  useEffect(() => {
    if (visible) setMounted(true);
  }, [visible]);

  const handleAnimationEnd = () => {
    if (!visible) setMounted(false);
  };

  if (!mounted && !visible) return null;

  return (
    <div
      onClick={onCancel}
      onAnimationEnd={handleAnimationEnd}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.4)',
        animation: visible ? 'voicePanelFadeIn 300ms ease-out' : undefined,
        opacity: visible ? 1 : 0,
        transition: 'opacity 300ms ease-out',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: 320,
          background: '#FFFFFF',
          borderRadius: '24px 24px 0 0',
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          padding: '32px 24px 24px',
          animation: visible ? 'voicePanelSlideIn 300ms ease-out' : undefined,
          transform: visible ? 'translateY(0)' : 'translateY(100%)',
          transition: 'transform 300ms ease-out',
        }}
      >
        {/* Wave bars */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, height: 60, marginBottom: 24 }}>
          {Array.from({ length: WAVE_BAR_COUNT }).map((_, i) => (
            <div
              key={i}
              style={{
                width: 4, height: 40, borderRadius: 2,
                background: '#38BDF8',
                animation: `voicePulse 1.2s ease-in-out ${i * 0.15}s infinite`,
                transformOrigin: 'center',
              }}
            />
          ))}
        </div>

        {/* Hint */}
        <div style={{ fontSize: 13, color: '#9CA3AF', marginBottom: 16 }}>正在聆听...</div>

        {/* Live transcript */}
        <div style={{
          flex: 1, width: '100%', overflowY: 'auto',
          fontSize: 15, color: '#1F2937', lineHeight: 1.6,
          textAlign: 'center', padding: '0 8px',
          minHeight: 0,
        }}>
          {transcript || ''}
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 16, width: '100%', marginTop: 20 }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1, height: 44, borderRadius: 24, border: 'none',
              background: '#F1F5F9', color: '#64748B',
              fontSize: 15, fontWeight: 500, cursor: 'pointer',
            }}
          >
            取消
          </button>
          <button
            onClick={() => onSend(transcript || '')}
            style={{
              flex: 1, height: 44, borderRadius: 24, border: 'none',
              background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
              color: '#FFFFFF',
              fontSize: 15, fontWeight: 500, cursor: 'pointer',
            }}
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}

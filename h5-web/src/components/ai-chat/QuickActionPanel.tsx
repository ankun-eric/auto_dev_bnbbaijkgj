'use client';
import React, { useEffect, useState } from 'react';

interface QuickActionPanelProps {
  visible: boolean;
  onClose: () => void;
  onAction: (action: string) => void;
}

const ACTIONS = [
  { icon: '📷', label: '拍照', key: 'camera' },
  { icon: '🖼', label: '相册', key: 'album' },
  { icon: '📋', label: '上传报告', key: 'upload_report' },
  { icon: '🎤', label: '语音', key: 'voice' },
  { icon: '📂', label: '健康档案', key: 'health_record' },
  { icon: '👨‍👩‍👦', label: '切家人', key: 'switch_family' },
  { icon: '🗑', label: '清空', key: 'clear' },
  { icon: '⚙', label: '更多', key: 'more' },
];

const keyframesId = 'quick-action-panel-kf';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(keyframesId)) return;
  const style = document.createElement('style');
  style.id = keyframesId;
  style.textContent = `
    @keyframes qapSlideIn {
      from { transform: translateY(100%); }
      to { transform: translateY(0); }
    }
    @keyframes qapFadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
  `;
  document.head.appendChild(style);
}

export default function QuickActionPanel({ visible, onClose, onAction }: QuickActionPanelProps) {
  const [mounted, setMounted] = useState(false);
  const [pressedKey, setPressedKey] = useState<string | null>(null);

  useEffect(() => { ensureKeyframes(); }, []);

  useEffect(() => {
    if (visible) setMounted(true);
  }, [visible]);

  const handleAnimationEnd = () => {
    if (!visible) setMounted(false);
  };

  if (!mounted && !visible) return null;

  return (
    <div
      onClick={onClose}
      onAnimationEnd={handleAnimationEnd}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.4)',
        animation: visible ? 'qapFadeIn 300ms ease-out' : undefined,
        opacity: visible ? 1 : 0,
        transition: 'opacity 300ms ease-out',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: '#FFFFFF',
          borderRadius: '24px 24px 0 0',
          padding: '24px 16px',
          animation: visible ? 'qapSlideIn 300ms ease-out' : undefined,
          transform: visible ? 'translateY(0)' : 'translateY(100%)',
          transition: 'transform 300ms ease-out',
        }}
      >
        {/* Handle bar */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
          <div style={{ width: 36, height: 4, borderRadius: 2, background: '#E2E8F0' }} />
        </div>

        {/* Grid */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16,
        }}>
          {ACTIONS.map((item) => (
            <button
              key={item.key}
              onClick={() => onAction(item.key)}
              onTouchStart={() => setPressedKey(item.key)}
              onTouchEnd={() => setPressedKey(null)}
              onMouseDown={() => setPressedKey(item.key)}
              onMouseUp={() => setPressedKey(null)}
              onMouseLeave={() => setPressedKey(null)}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                transition: 'background 200ms ease',
              }}
            >
              <div style={{
                width: 48, height: 48, borderRadius: 24,
                background: pressedKey === item.key ? '#E0F2FE' : '#F0F9FF',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 22, color: '#0284C7',
                transition: 'background 200ms ease',
              }}>
                {item.icon}
              </div>
              <span style={{ fontSize: 12, color: '#64748B', lineHeight: 1.2 }}>{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

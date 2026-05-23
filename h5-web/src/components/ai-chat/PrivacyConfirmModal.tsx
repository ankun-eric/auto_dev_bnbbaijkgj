'use client';
import React, { useEffect, useState } from 'react';

interface PrivacyConfirmModalProps {
  visible: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const PRIVACY_ITEMS = [
  '对话数据加密存储',
  '健康数据脱敏处理',
  '数据保留180天后自动清除',
  '不与第三方共享',
];

const keyframesId = 'privacy-modal-kf';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(keyframesId)) return;
  const style = document.createElement('style');
  style.id = keyframesId;
  style.textContent = `
    @keyframes privacyFadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes privacyScaleIn {
      from { opacity: 0; transform: translate(-50%, -50%) scale(0.9); }
      to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
    }
  `;
  document.head.appendChild(style);
}

export default function PrivacyConfirmModal({ visible, onConfirm, onCancel }: PrivacyConfirmModalProps) {
  const [mounted, setMounted] = useState(false);

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
      onClick={onCancel}
      onAnimationEnd={handleAnimationEnd}
      style={{
        position: 'fixed', inset: 0, zIndex: 1100,
        background: 'rgba(0,0,0,0.5)',
        animation: visible ? 'privacyFadeIn 250ms ease-out' : undefined,
        opacity: visible ? 1 : 0,
        transition: 'opacity 250ms ease-out',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 'calc(100vw - 48px)', maxWidth: 360,
          borderRadius: 20, background: '#FFFFFF',
          padding: '32px 24px',
          animation: visible ? 'privacyScaleIn 250ms ease-out' : undefined,
        }}
      >
        {/* Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
          <div style={{
            width: 64, height: 64, borderRadius: 32,
            background: '#F0F9FF',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28, color: '#0284C7',
          }}>
            🔒
          </div>
        </div>

        {/* Title */}
        <div style={{
          fontSize: 18, fontWeight: 700, color: '#1F2937',
          textAlign: 'center', marginBottom: 20,
        }}>
          数据隐私说明
        </div>

        {/* Data list */}
        <div style={{ marginBottom: 24 }}>
          {PRIVACY_ITEMS.map((item, idx) => (
            <div key={idx} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              height: 40,
            }}>
              <span style={{ fontSize: 16, color: '#0284C7', flexShrink: 0 }}>✅</span>
              <span style={{ fontSize: 14, color: '#374151' }}>{item}</span>
            </div>
          ))}
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1, height: 48, borderRadius: 12, border: 'none',
              background: '#F1F5F9', color: '#64748B',
              fontSize: 15, fontWeight: 500, cursor: 'pointer',
            }}
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            style={{
              flex: 1, height: 48, borderRadius: 12, border: 'none',
              background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
              color: '#FFFFFF',
              fontSize: 15, fontWeight: 500, cursor: 'pointer',
            }}
          >
            同意并继续
          </button>
        </div>
      </div>
    </div>
  );
}

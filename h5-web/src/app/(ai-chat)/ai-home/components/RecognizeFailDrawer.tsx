'use client';

/**
 * [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.1.3-3.1.4 2026-05-18] 识药失败抽屉
 *
 * 失败抽屉两个步骤（同抽屉左右滑动切换）：
 *   step 1: 「再试一次 / 手动录入 / 取消」 三选一
 *   step 2: 手动录入表单（复用 MedicationFormPanel mode=drawer）
 *           左上角「← 返回」按钮可平滑滑回 step 1
 *           右上角「✕」关闭整个抽屉
 *
 * 支持点击遮罩关闭。
 */
import React, { useState } from 'react';
import MedicationFormPanel from '@/components/medication/MedicationFormPanel';

export interface RecognizeFailDrawerProps {
  open: boolean;
  onClose: () => void;
  /** 「再试一次」点击 → 通常会关闭本抽屉并打开 RetakePhotoDrawer */
  onRetry: () => void;
  /** 当前 AI 对话页选中咨询人 family_member.id；本人态传 null/0 */
  familyMemberId?: number | null;
  /** 手动录入保存成功回调（newId） */
  onSaved?: (newId: number | null) => void;
}

export default function RecognizeFailDrawer({
  open,
  onClose,
  onRetry,
  familyMemberId,
  onSaved,
}: RecognizeFailDrawerProps) {
  const [step, setStep] = useState<1 | 2>(1);

  if (!open) return null;

  const handleClose = () => {
    setStep(1); // 关闭时重置
    onClose();
  };

  return (
    <div
      data-testid="recognize-fail-drawer"
      onClick={handleClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          width: '100%',
          maxWidth: 600,
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* 顶部条 */}
        <div
          style={{
            padding: '14px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid #F0F0F0',
            flexShrink: 0,
          }}
        >
          {step === 2 ? (
            <button
              type="button"
              data-testid="fail-back-btn"
              onClick={() => setStep(1)}
              style={{ border: 'none', background: 'transparent', fontSize: 18, color: '#374151', cursor: 'pointer' }}
              aria-label="back"
            >
              ‹ 返回
            </button>
          ) : (
            <div style={{ width: 60 }} />
          )}
          <div style={{ fontSize: 16, fontWeight: 600, color: '#111827' }}>
            {step === 1 ? '未识别到药品' : '手动录入用药'}
          </div>
          <button
            type="button"
            data-testid="fail-close-btn"
            onClick={handleClose}
            style={{ border: 'none', background: 'transparent', fontSize: 22, color: '#6B7280', cursor: 'pointer', width: 60, textAlign: 'right' }}
            aria-label="close"
          >
            ✕
          </button>
        </div>

        {/* 内容滑动区：用横向 flex + transform 模拟左右滑动切换 */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          <div
            style={{
              display: 'flex',
              width: '200%',
              height: '100%',
              transform: step === 1 ? 'translateX(0)' : 'translateX(-50%)',
              transition: 'transform 280ms cubic-bezier(0.4,0,0.2,1)',
            }}
          >
            {/* Step 1：失败提示 + 三按钮 */}
            <div style={{ width: '50%', height: '100%', padding: '24px 20px', boxSizing: 'border-box', overflowY: 'auto' }}>
              <div style={{ textAlign: 'center', fontSize: 36, marginBottom: 12 }}>📷</div>
              <div style={{ textAlign: 'center', fontSize: 15, color: '#374151', marginBottom: 6, fontWeight: 500 }}>
                未能识别出药品信息
              </div>
              <div style={{ textAlign: 'center', fontSize: 13, color: '#6B7280', marginBottom: 24, lineHeight: 1.6 }}>
                建议：用更清晰角度重新拍摄药盒；
                <br />
                或直接手动录入用药信息。
              </div>
              <button
                type="button"
                data-testid="fail-retry-btn"
                onClick={() => {
                  setStep(1);
                  onRetry();
                }}
                style={primaryBtn}
              >
                再试一次
              </button>
              <button
                type="button"
                data-testid="fail-manual-btn"
                onClick={() => setStep(2)}
                style={{ ...outlineBtn, marginTop: 10 }}
              >
                手动录入
              </button>
              <button
                type="button"
                data-testid="fail-cancel-btn"
                onClick={handleClose}
                style={{ ...textBtn, marginTop: 10 }}
              >
                取消
              </button>
            </div>

            {/* Step 2：手动录入表单 */}
            <div style={{ width: '50%', height: '100%', overflowY: 'auto' }}>
              {step === 2 && (
                <MedicationFormPanel
                  mode="drawer"
                  familyMemberId={familyMemberId ?? null}
                  hideDelete
                  onSaved={(id) => {
                    onSaved?.(id);
                    handleClose();
                  }}
                  onCancel={() => setStep(1)}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const primaryBtn: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '12px 0',
  background: '#0EA5E9',
  color: '#fff',
  border: 'none',
  borderRadius: 24,
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
};

const outlineBtn: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '12px 0',
  background: '#fff',
  color: '#0EA5E9',
  border: '1px solid #0EA5E9',
  borderRadius: 24,
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
};

const textBtn: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '10px 0',
  background: 'transparent',
  color: '#6B7280',
  border: 'none',
  fontSize: 14,
  cursor: 'pointer',
};

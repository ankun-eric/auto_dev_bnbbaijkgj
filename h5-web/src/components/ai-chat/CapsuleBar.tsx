/**
 * [AICHAT-OPTIM-FIX-V1 F-05 2026-05-14] AI 对话详情页胶囊条
 *
 * 位置：紧贴输入框上沿（输入框上 0px 间距，向上延伸一行）
 * 数据源：GET /api/function-buttons?is_enabled=true（统一来源 chat_function_buttons）
 * 行为：
 *   - 横向单排可滑动（overflow-x: auto）
 *   - 键盘弹起时整体隐藏（hideOnKeyboard 控制）
 *   - 点击胶囊 → 由父组件传入 onCapsuleClick 回调处理
 *   - 数据为空 / 接口异常 → 整体不渲染
 *
 * 视觉规格：
 *   - 整体高度 36px、胶囊高度 28px、圆角 14px（全圆角）
 *   - 胶囊背景浅灰、内边距 4×12px
 *   - Emoji 16px、按钮名 13px、间距 4px
 *   - 胶囊间距 8px、首尾距屏幕 12px
 */
'use client';

import React, { useEffect, useRef } from 'react';
import { aiHomeFnTrack } from '@/lib/analytics';

export interface CapsuleButton {
  id: number | string;
  name: string;
  /** Emoji 字符（来自 chat_function_buttons.icon 字段） */
  icon?: string;
  button_type: string;
}

export interface CapsuleBarProps {
  buttons: CapsuleButton[];
  /** 是否隐藏（键盘弹起时由外部传 true） */
  hidden?: boolean;
  onCapsuleClick: (btn: CapsuleButton) => void;
}

export default function CapsuleBar({ buttons, hidden, onCapsuleClick }: CapsuleBarProps) {
  const exposedRef = useRef(false);

  // 首次有按钮渲染时打曝光埋点（仅一次）
  useEffect(() => {
    if (!exposedRef.current && buttons.length > 0 && !hidden) {
      exposedRef.current = true;
      try {
        aiHomeFnTrack.capsuleExposure(buttons.map((b) => b.id));
      } catch {}
    }
  }, [buttons, hidden]);

  if (!buttons || buttons.length === 0) {
    // 降级：接口异常或返回空数组 → 整个胶囊条不渲染
    return null;
  }

  return (
    <div
      data-testid="ai-chat-capsule-bar"
      data-capsule-count={buttons.length}
      style={{
        display: hidden ? 'none' : 'block',
        background: '#FFFFFF',
        borderTop: '1px solid #E2E8F0',
        padding: '4px 0',
      }}
    >
      <div
        className="ai-chat-capsule-bar-scroll"
        style={{
          display: 'flex',
          gap: 8,
          overflowX: 'auto',
          WebkitOverflowScrolling: 'touch',
          padding: '0 12px',
          scrollbarWidth: 'none' as any,
          msOverflowStyle: 'none' as any,
          height: 36,
          alignItems: 'center',
        }}
      >
        {buttons.map((btn) => (
          <button
            key={btn.id}
            data-testid="ai-chat-capsule-item"
            data-button-id={btn.id}
            data-button-type={btn.button_type}
            onClick={() => {
              try {
                aiHomeFnTrack.capsuleClick(btn.id, btn.name, btn.button_type);
              } catch {}
              onCapsuleClick(btn);
            }}
            style={{
              flexShrink: 0,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              height: 28,
              padding: '4px 12px',
              background: '#FFFFFF',
              border: '1px solid #E2E8F0',
              color: '#374151',
              borderRadius: 12,
              fontSize: 13,
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              lineHeight: 1,
            }}
          >
            <span style={{ fontSize: 16, lineHeight: 1, color: '#0284C7' }}>{btn.icon || '📌'}</span>
            <span>{btn.name}</span>
          </button>
        ))}
      </div>
      <style jsx>{`
        .ai-chat-capsule-bar-scroll::-webkit-scrollbar { display: none; }
      `}</style>
    </div>
  );
}

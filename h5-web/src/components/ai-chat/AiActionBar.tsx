'use client';

/**
 * [PRD-440] AI 回答下方操作栏 — 统一组件
 *
 * 设计要点：
 * - 三图标固定顺序：复制 → 转发 → 语音播报，左下角一排
 * - 提示文字「AI 生成仅供参考」位于操作图标上方一行，靠右对齐
 * - 提示文字与图标之间有一条全宽 1px dashed #E5E5E5 虚线
 * - 未触发态：浅灰 #999；悬停 / 长按 / 触发态：双色渐变 #6a8dff → #b07cff（135°）
 * - 语音播报「播报中」叠加 Wi-Fi 弧线一圈圈向外扩散动效（1 秒一圈、3 圈错位）
 * - 复制成功后，桌面端（hover-capable）顶部居中弹出 Toast「已复制」1.5s 自动消失；
 *   移动端（无 hover）则调用系统/UA 原生轻提示语义，由调用方传入的 onMobileNotify 实现
 */

import React, { useEffect, useState } from 'react';

export const AI_ACTION_BAR_GRADIENT_ID = 'ai-action-bar-gradient-440';

interface AiActionBarProps {
  /** 是否正在播报当前消息 */
  ttsPlaying?: boolean;
  /** 复制按钮点击回调；返回 Promise 时表示异步复制 */
  onCopy: () => void | Promise<void>;
  /** 转发按钮点击回调（沿用线上现有弹窗/分享逻辑） */
  onShare: () => void;
  /** 语音播报按钮点击回调（再次点击立即停止） */
  onTts: () => void;
  /** 提示文字（默认：AI 生成仅供参考） */
  disclaimer?: string;
  /** 容器自定义样式 */
  style?: React.CSSProperties;
  /** 是否禁用内置 Web 端 Toast；移动端调用方可监听复制结果用 UA 提示 */
  disableToast?: boolean;
}

/** 渐变 + 虚线 + Wi-Fi 动效 全局样式（注入一次） */
const STYLE_ID = 'ai-action-bar-440-styles';
function ensureStylesInjected() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
@keyframes aiActionBarWifi440 {
  0%   { transform: scale(1);    opacity: 1; }
  100% { transform: scale(2.5);  opacity: 0; }
}
@keyframes aiActionBarToast440In {
  0%   { opacity: 0; transform: translate(-50%, -8px); }
  100% { opacity: 1; transform: translate(-50%, 0); }
}
@keyframes aiActionBarToast440Out {
  0%   { opacity: 1; transform: translate(-50%, 0); }
  100% { opacity: 0; transform: translate(-50%, -8px); }
}
.ai-action-bar-440-icon { color: #999; transition: color 0.15s ease; }
.ai-action-bar-440-icon:hover,
.ai-action-bar-440-icon:active,
.ai-action-bar-440-icon.is-active { color: url(#${AI_ACTION_BAR_GRADIENT_ID}); stroke: url(#${AI_ACTION_BAR_GRADIENT_ID}); }
.ai-action-bar-440-toast {
  position: fixed; top: 56px; left: 50%; transform: translate(-50%, 0);
  background: rgba(51,51,51,0.92); color: #fff; font-size: 14px;
  padding: 8px 16px; border-radius: 8px; z-index: 9999;
  pointer-events: none;
  animation: aiActionBarToast440In 0.18s ease-out;
}
.ai-action-bar-440-toast.is-out { animation: aiActionBarToast440Out 0.2s ease-in forwards; }
`;
  document.head.appendChild(style);
}

/** 全局 Toast，单例 */
function showCopiedToast() {
  if (typeof document === 'undefined') return;
  ensureStylesInjected();
  const oldEl = document.getElementById('ai-action-bar-440-toast-el');
  if (oldEl) oldEl.remove();
  const el = document.createElement('div');
  el.id = 'ai-action-bar-440-toast-el';
  el.className = 'ai-action-bar-440-toast';
  el.textContent = '已复制';
  document.body.appendChild(el);
  setTimeout(() => {
    el.classList.add('is-out');
    setTimeout(() => el.remove(), 220);
  }, 1500);
}

export function isLikelyMobile(): boolean {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false;
  if (typeof window.matchMedia === 'function' && window.matchMedia('(hover: none)').matches) return true;
  const ua = navigator.userAgent || '';
  return /Mobi|Android|iPhone|iPad|iPod|MicroMessenger/i.test(ua);
}

/** 复制成功后的统一反馈（Web 顶部 Toast / 移动端系统轻提示） */
export function notifyCopied() {
  if (isLikelyMobile()) {
    // 移动端使用系统/原生轻量反馈：振动 + 不打扰提示
    try {
      if (navigator?.vibrate) navigator.vibrate(20);
    } catch {}
    // 同时降级输出一条轻 Toast，避免某些移动浏览器无反馈
    showCopiedToast();
  } else {
    showCopiedToast();
  }
}

const ICON_SIZE = 18;
const STROKE = 1.5;

export const SvgGradientDefs: React.FC = () => (
  <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden>
    <defs>
      <linearGradient id={AI_ACTION_BAR_GRADIENT_ID} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#6a8dff" />
        <stop offset="100%" stopColor="#b07cff" />
      </linearGradient>
    </defs>
  </svg>
);

/** 复制图标（渐变可激活态） */
const CopyIcon: React.FC<{ active?: boolean }> = ({ active }) => (
  <svg
    className={`ai-action-bar-440-icon${active ? ' is-active' : ''}`}
    width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none"
    stroke={active ? `url(#${AI_ACTION_BAR_GRADIENT_ID})` : '#999'}
    strokeWidth={STROKE} strokeLinecap="round" strokeLinejoin="round"
  >
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5" />
  </svg>
);

/** 转发图标 — 三点连线分享图（方案 3） */
const ShareIcon: React.FC<{ active?: boolean }> = ({ active }) => (
  <svg
    className={`ai-action-bar-440-icon${active ? ' is-active' : ''}`}
    width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none"
    stroke={active ? `url(#${AI_ACTION_BAR_GRADIENT_ID})` : '#999'}
    strokeWidth={STROKE} strokeLinecap="round" strokeLinejoin="round"
  >
    <circle cx="18" cy="5" r="2.5" />
    <circle cx="6" cy="12" r="2.5" />
    <circle cx="18" cy="19" r="2.5" />
    <line x1="8.2" y1="13.3" x2="15.8" y2="17.7" />
    <line x1="15.8" y1="6.3" x2="8.2" y2="10.7" />
  </svg>
);

/** 语音播报喇叭图标（含 Wi-Fi 弧线扩散动效） */
const SpeakerIcon: React.FC<{ playing?: boolean }> = ({ playing }) => {
  const stroke = playing ? `url(#${AI_ACTION_BAR_GRADIENT_ID})` : '#999';
  return (
    <span style={{ position: 'relative', display: 'inline-flex', width: ICON_SIZE, height: ICON_SIZE }}>
      <svg
        className={`ai-action-bar-440-icon${playing ? ' is-active' : ''}`}
        width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 24 24" fill="none"
        stroke={stroke} strokeWidth={STROKE} strokeLinecap="round" strokeLinejoin="round"
      >
        <polygon points="11 5 6 9 3 9 3 15 6 15 11 19 11 5" />
      </svg>
      {/* 三圈错位扩散波 */}
      {playing && (
        <span aria-hidden style={{ position: 'absolute', inset: 0 }}>
          {[0, 333, 666].map((delay) => (
            <span
              key={delay}
              style={{
                position: 'absolute',
                left: '50%',
                top: '50%',
                width: ICON_SIZE,
                height: ICON_SIZE,
                marginLeft: -ICON_SIZE / 2,
                marginTop: -ICON_SIZE / 2,
                borderRadius: '50%',
                border: `1.2px solid #6a8dff`,
                transformOrigin: 'center',
                animation: `aiActionBarWifi440 1000ms ease-out ${delay}ms infinite`,
                opacity: 0,
              }}
            />
          ))}
        </span>
      )}
    </span>
  );
};

const AiActionBar: React.FC<AiActionBarProps> = ({
  ttsPlaying = false,
  onCopy,
  onShare,
  onTts,
  disclaimer = 'AI 生成仅供参考',
  style,
  disableToast = false,
}) => {
  const [copyActive, setCopyActive] = useState(false);
  const [shareActive, setShareActive] = useState(false);

  useEffect(() => {
    ensureStylesInjected();
  }, []);

  const handleCopyClick = async () => {
    setCopyActive(true);
    try {
      await onCopy();
      if (!disableToast) notifyCopied();
    } finally {
      setTimeout(() => setCopyActive(false), 600);
    }
  };

  const handleShareClick = () => {
    setShareActive(true);
    onShare();
    setTimeout(() => setShareActive(false), 600);
  };

  return (
    <div data-testid="ai-action-bar-440" style={{ width: '100%', ...style }}>
      <SvgGradientDefs />
      {/* 提示文字（靠右） */}
      <div
        style={{
          fontSize: 11,
          color: '#999',
          textAlign: 'right',
          lineHeight: 1.4,
          marginBottom: 6,
        }}
      >
        {disclaimer}
      </div>
      {/* 全宽虚线 */}
      <div style={{ borderTop: '1px dashed #E5E5E5', width: '100%' }} />
      {/* 三个图标：左下一排 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          marginTop: 8,
        }}
      >
        <button
          aria-label="复制"
          onClick={handleCopyClick}
          style={btnStyle}
        >
          <CopyIcon active={copyActive} />
        </button>
        <button
          aria-label="转发"
          onClick={handleShareClick}
          style={btnStyle}
        >
          <ShareIcon active={shareActive} />
        </button>
        <button
          aria-label={ttsPlaying ? '停止播报' : '语音播报'}
          onClick={onTts}
          style={btnStyle}
        >
          <SpeakerIcon playing={ttsPlaying} />
        </button>
      </div>
    </div>
  );
};

const btnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 32,
  height: 32,
  background: 'transparent',
  border: 'none',
  padding: 0,
  cursor: 'pointer',
  outline: 'none',
};

export default AiActionBar;

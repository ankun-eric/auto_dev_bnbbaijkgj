'use client';

/**
 * [PRD-449] AiAvatar 公共组件
 *
 * 统一处理 AI 头像「取后台 → 兜底 → 占位」三段逻辑，
 * 欢迎区大头像（A 位）和 AI 消息小头像（B 位）共用。
 *
 * 渲染规则（PRD §3.2）：
 *   - 初始 / loading / error / src 为空 → 显示默认图
 *   - loaded → 平滑切换到后台图（CSS opacity 过渡 200ms，无白屏 / 无闪烁）
 *
 * 兜底场景（PRD §三 R5）：
 *   ① 接口请求失败    → 父组件传 src=undefined → 走默认图分支
 *   ② 后台字段为空    → src='' / null / undefined → 走默认图分支
 *   ③ 图片加载失败    → onError → 切到默认图
 *   ④ src 为 emoji（非 URL，如 🌿） → 不渲染 <img>，按 emoji 渲染
 */

import { useEffect, useState } from 'react';

const DEFAULT_AVATAR_URL =
  (process.env.NEXT_PUBLIC_BASE_PATH || '') + '/images/default-ai-avatar.png';

export interface AiAvatarProps {
  /** 后台头像 URL（可为空 / undefined / 相对路径 / 绝对 URL / emoji） */
  src?: string | null;
  /** 头像尺寸（px），同时作为 width 和 height */
  size: number;
  /** 形状：圆形（默认）/ 方形 */
  shape?: 'circle' | 'square';
  /** 自定义 className */
  className?: string;
  /** 自定义 style（会覆盖宽高，慎用） */
  style?: React.CSSProperties;
  /** 无障碍 alt 文本 */
  alt?: string;
  /** 自定义 testId */
  testId?: string;
}

/** 判断字符串是否是 URL（http(s):// 开头或 / 开头的相对路径） */
function isUrl(s: string): boolean {
  if (!s) return false;
  return /^https?:\/\//i.test(s) || s.startsWith('/');
}

/** 判断是否是 emoji（简单启发式：非 URL 且长度较短） */
function isEmoji(s: string): boolean {
  if (!s) return false;
  if (isUrl(s)) return false;
  // 2~4 个字符且非英文字母数字 → 视为 emoji
  return s.length <= 4;
}

/** 路径标准化：相对路径补 basePath；http(s) 直接返回；空返回空 */
function normalizeUrl(s: string | null | undefined): string {
  if (!s) return '';
  const v = s.trim();
  if (!v) return '';
  if (/^https?:\/\//i.test(v)) return v;
  if (v.startsWith('/')) {
    const bp = process.env.NEXT_PUBLIC_BASE_PATH || '';
    if (bp && !v.startsWith(bp)) {
      return bp + v;
    }
    return v;
  }
  return v;
}

export default function AiAvatar({
  src,
  size,
  shape = 'circle',
  className = '',
  style,
  alt = 'AI 头像',
  testId = 'ai-avatar',
}: AiAvatarProps) {
  const radius = shape === 'circle' ? '50%' : 8;

  // 处理后的实际 URL（仅当是 URL 类型时）
  const normalizedSrc = src && isUrl(String(src)) ? normalizeUrl(String(src)) : '';
  // 是否 emoji 类型
  const emojiSrc = src && !isUrl(String(src)) && isEmoji(String(src)) ? String(src) : '';

  // 加载状态：'idle' | 'loading' | 'loaded' | 'error'
  const [status, setStatus] = useState<'idle' | 'loading' | 'loaded' | 'error'>(
    normalizedSrc ? 'loading' : 'idle',
  );

  useEffect(() => {
    // src 变化时重置状态
    if (normalizedSrc) {
      setStatus('loading');
    } else {
      setStatus('idle');
    }
  }, [normalizedSrc]);

  // 是否需要展示后台图片：仅当有 URL 且未失败时
  const showBackendImg = !!normalizedSrc && status !== 'error';
  // 是否展示 emoji（兼容旧数据：avatar.type='emoji' 也透传到 src）
  const showEmoji = !normalizedSrc && !!emojiSrc;
  // 默认图：未加载完成 / 失败 / 无 src 且非 emoji 时显示
  const showDefault = !showEmoji && (status !== 'loaded' || !showBackendImg);

  const baseStyle: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: radius,
    display: 'inline-block',
    position: 'relative',
    overflow: 'hidden',
    flexShrink: 0,
    ...style,
  };

  // emoji 分支：直接渲染 emoji 字符（兼容旧 avatar.type='emoji' 数据）
  if (showEmoji) {
    return (
      <span
        className={className}
        style={{
          ...baseStyle,
          background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
          color: '#fff',
          fontSize: Math.round(size * 0.55),
          lineHeight: `${size}px`,
          textAlign: 'center',
        }}
        data-testid={testId}
        aria-label={alt}
      >
        {emojiSrc}
      </span>
    );
  }

  return (
    <span
      className={className}
      style={baseStyle}
      data-testid={testId}
      aria-label={alt}
    >
      {/* 默认图（占位 + 兜底）—— 始终渲染在底层，loading/error/empty 时可见，loaded 时被后台图覆盖 */}
      {showDefault && (
        <img
          src={DEFAULT_AVATAR_URL}
          alt={alt}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            borderRadius: radius,
            display: 'block',
          }}
          data-testid={`${testId}-default`}
        />
      )}

      {/* 后台头像 —— 仅在有有效 URL 时渲染，加载完成前 opacity:0；加载完成后 opacity:1 平滑过渡（200ms） */}
      {showBackendImg && (
        <img
          src={normalizedSrc}
          alt={alt}
          onLoad={() => setStatus('loaded')}
          onError={() => setStatus('error')}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            borderRadius: radius,
            display: 'block',
            opacity: status === 'loaded' ? 1 : 0,
            transition: 'opacity 200ms ease-out',
          }}
          data-testid={`${testId}-backend`}
        />
      )}
    </span>
  );
}

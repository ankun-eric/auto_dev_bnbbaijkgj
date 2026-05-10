'use client';

/**
 * [PRD-448 v1.1] 咨询人胶囊：左侧线性小人头像 / 人物剪影图标
 * 颜色 #8C8C8C，默认尺寸 16 × 16（v1.1 由 12 → 16）
 *
 * 注：viewBox 仍为 0 0 12 12，依赖 SVG 自动等比缩放到 width/height，
 * 因此可任意尺寸渲染，且笔触保持视觉一致。
 */
export default function PersonIcon({ size = 16, color = '#8C8C8C' }: { size?: number; color?: string }) {
  return (
    <svg
      data-testid="advisor-capsule-icon"
      width={size}
      height={size}
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{ flexShrink: 0, display: 'block' }}
    >
      {/* 头部 */}
      <circle cx="6" cy="3.5" r="2" stroke={color} strokeWidth="1" fill="none" />
      {/* 肩膀/身体（剪影底部弧形） */}
      <path
        d="M2 10.5 C2 7.8, 4 6.5, 6 6.5 C8 6.5, 10 7.8, 10 10.5"
        stroke={color}
        strokeWidth="1"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

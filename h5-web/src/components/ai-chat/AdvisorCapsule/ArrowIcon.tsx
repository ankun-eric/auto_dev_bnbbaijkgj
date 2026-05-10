'use client';

/**
 * [PRD-448 v1.1 2026-05-10] 咨询人胶囊：右侧折叠/展开箭头（SVG）
 *
 * 取代 v1.0 的 Unicode 字符 ⌄ / ⌃，原因：字符在不同字体下视觉重心不一致，
 * 导致折叠态偏下；改 SVG 后通过 viewBox + transform 严格保证位置不变。
 *
 * 折叠态：直接渲染（朝下 ⌄ 形态）
 * 展开态：仅对同一个 SVG 节点应用 transform: rotate(180deg)，让箭头朝上（⌃ 形态）
 * 折叠/展开态箭头位置完全不动，仅方向反转。
 */

export interface ArrowIconProps {
  size?: number;
  color?: string;
  expanded?: boolean;
  testId?: string;
}

export default function ArrowIcon({
  size = 16,
  color = '#8C8C8C',
  expanded = false,
  testId,
}: ArrowIconProps) {
  return (
    <svg
      data-testid={testId}
      data-expanded={expanded ? '1' : '0'}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{
        flexShrink: 0,
        display: 'block',
        transition: 'transform 0.2s ease',
        transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
        transformOrigin: '50% 50%',
      }}
    >
      <path
        d="M4 6L8 10L12 6"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

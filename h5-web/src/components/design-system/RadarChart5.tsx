'use client';
import React from 'react';

export interface RadarChart5Data {
  label: string;
  /** 0~100 */
  value: number;
}

export interface RadarChart5Props {
  data: RadarChart5Data[];
  size?: number;
  /** 0~100，雷达图最大值 */
  max?: number;
  className?: string;
  testId?: string;
}

/**
 * 5 维雷达图（屏 ⑱ 健康档案）。
 * 数据驱动 + 纯 SVG 渲染；性能上限 30fps（由父组件节流）。
 * 颜色来自语义层 token：填充 --color-radar-fill, 描边 --color-radar-stroke。
 */
export const RadarChart5: React.FC<RadarChart5Props> = ({
  data,
  size = 200,
  max = 100,
  className = '',
  testId = 'bh-radar-chart',
}) => {
  const safeData = (data || []).slice(0, 5);
  while (safeData.length < 5) safeData.push({ label: '', value: 0 });

  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 24;
  const angleStep = (Math.PI * 2) / 5;
  const startAngle = -Math.PI / 2;

  const pointAt = (i: number, ratio: number) => {
    const a = startAngle + angleStep * i;
    return [cx + Math.cos(a) * radius * ratio, cy + Math.sin(a) * radius * ratio] as const;
  };

  const dataPoints = safeData.map((d, i) => pointAt(i, Math.min(1, d.value / max)));
  const dataPath = dataPoints.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ') + ' Z';

  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  return (
    <svg
      className={`bh-radar-chart ${className}`}
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      data-testid={testId}
    >
      {/* 网格 */}
      {gridLevels.map((lv, gi) => {
        const pts = Array.from({ length: 5 }, (_, i) => pointAt(i, lv));
        const d = pts.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(' ') + ' Z';
        return (
          <path
            key={gi}
            d={d}
            fill="none"
            stroke="var(--color-neutral-200)"
            strokeWidth={1}
          />
        );
      })}
      {/* 5 条轴线 */}
      {Array.from({ length: 5 }, (_, i) => {
        const [x, y] = pointAt(i, 1);
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={x}
            y2={y}
            stroke="var(--color-neutral-200)"
            strokeWidth={1}
          />
        );
      })}
      {/* 数据多边形（填充与描边均走 token） */}
      <path
        d={dataPath}
        fill="var(--color-radar-fill)"
        stroke="var(--color-radar-stroke)"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {/* 5 个数据点 */}
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={3} fill="var(--color-radar-stroke)" />
      ))}
      {/* 5 个标签 */}
      {safeData.map((d, i) => {
        const [x, y] = pointAt(i, 1.18);
        return (
          <text
            key={i}
            x={x}
            y={y}
            fontSize={12}
            fill="var(--color-text-base)"
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {d.label}
          </text>
        );
      })}
    </svg>
  );
};

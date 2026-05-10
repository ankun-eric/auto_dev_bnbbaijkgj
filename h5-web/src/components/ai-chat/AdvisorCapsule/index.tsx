'use client';

/**
 * [PRD-448 v1.1 2026-05-10] 咨询人胶囊（AdvisorCapsule）
 *
 * 统一替换 AI 详情页 / AI 首页 中"XXX 的档案"提示行为浅灰圆角胶囊。
 *
 * v1.1 关键变更（相对 v1.0）：
 * - 文字字号：12px → 14px，行高 18px → 20px
 * - 左侧小人图标：12 × 12 → 16 × 16
 * - 右侧箭头：Unicode 字符 ⌄/⌃ → SVG 图标（16 × 16，仅 transform 翻转方向）
 * - 内边距：上下 4 / 左右 10 → 上下 6 / 左右 12
 * - 圆角：8px → 10px
 * - 图标-文字间距：6px → 8px
 * - 三元素（小人/文字/箭头）通过 flex align-items: center 严格垂直居中
 * - 加载中/空 → 整条胶囊不渲染（不再显示"加载中…"或"我的档案"占位）
 * - 新增 isSelf prop：本人时上层应传 memberName="本人"，组件内部不做隐式判断
 *
 * 文案规范：上层直接传入「本次回答结合 {memberName} 的档案」中的 memberName。
 * - 本人：上层传 "本人"
 * - 妈妈/宝宝/张三：上层传该成员的真实 name
 * - 未选定 / 加载中 / name 为空：上层不应使用本组件（或按规则不渲染）
 *
 * 渲染规则：本组件本身在 memberName 为空字符串时直接返回 null（兜底保护，
 * 配合 PRD §3.3 "整条胶囊不渲染"）。
 */

import React, { useCallback, useState } from 'react';
import PersonIcon from './PersonIcon';
import ArrowIcon from './ArrowIcon';

export interface AdvisorCapsuleProps {
  /** 家庭成员名字。本人需上层传入 "本人" 二字，避免显示真实姓名/账号昵称 */
  memberName: string;
  /** [v1.1 新增] 是否本人，决定 memberName 取值与可能的样式微调；组件不做隐式判断逻辑 */
  isSelf?: boolean;
  /** 默认是否展开，默认 false */
  defaultExpanded?: boolean;
  /** 受控展开状态（可选） */
  expanded?: boolean;
  /** 展开/折叠状态切换回调 */
  onToggle?: (expanded: boolean) => void;
  /** 展开态显示的内容（slot），由调用方传入 */
  expandedContent?: React.ReactNode;
  /** 自定义类名 */
  className?: string;
  /** 自定义外层包裹样式（一般不需要传） */
  style?: React.CSSProperties;
  /** 自定义 data-testid，默认 advisor-capsule */
  testId?: string;
}

export default function AdvisorCapsule({
  memberName,
  isSelf,
  defaultExpanded = false,
  expanded,
  onToggle,
  expandedContent,
  className,
  style,
  testId = 'advisor-capsule',
}: AdvisorCapsuleProps) {
  const [internalExpanded, setInternalExpanded] = useState<boolean>(defaultExpanded);

  const isControlled = typeof expanded === 'boolean';
  const isExpanded = isControlled ? (expanded as boolean) : internalExpanded;

  const handleToggle = useCallback(() => {
    const next = !isExpanded;
    if (!isControlled) {
      setInternalExpanded(next);
    }
    onToggle?.(next);
  }, [isExpanded, isControlled, onToggle]);

  // [PRD-448 v1.1 §3.3] 加载中 / 空 → 整条胶囊不渲染
  // 上层传入 memberName 为空字符串/null/undefined 时，直接返回 null，避免出现"半成品胶囊"
  const safeName = (memberName ?? '').toString().trim();
  if (!safeName) {
    return null;
  }

  // [PRD-448 v1.1 §4.1] 文案模板：本次回答结合 {memberName} 的档案
  // 与 memberName 直接拼接（不加书名号、引号），各保留一个半角空格
  const labelText = `本次回答结合 ${safeName} 的档案`;

  return (
    <div
      data-testid={`${testId}-wrapper`}
      data-is-self={isSelf ? '1' : '0'}
      className={className}
      style={{ width: '100%', ...style }}
    >
      <div
        data-testid={testId}
        data-expanded={isExpanded ? '1' : '0'}
        role="button"
        tabIndex={0}
        onClick={handleToggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleToggle();
          }
        }}
        style={{
          display: 'flex',
          alignItems: 'center', // 三元素垂直居中（小人/文字/箭头对齐到同一中线）
          justifyContent: 'flex-start',
          gap: 8, // [v1.1] 小人图标与文字之间的间距，与 14px 字号配平
          width: '100%',
          background: '#F5F5F5',
          borderRadius: 10, // [v1.1] 8px → 10px
          padding: '6px 12px', // [v1.1] 4px/10px → 6px/12px
          fontSize: 14, // [v1.1] 12px → 14px
          lineHeight: '20px', // [v1.1] 18px → 20px
          color: '#8C8C8C',
          cursor: 'pointer',
          userSelect: 'none',
          boxSizing: 'border-box',
        }}
      >
        <PersonIcon size={16} color="#8C8C8C" /> {/* [v1.1] 12 → 16 */}
        <span
          data-testid={`${testId}-label`}
          style={{
            flex: '1 1 auto', // 文字占满中间，把箭头顶到最右
            fontSize: 14,
            lineHeight: '20px',
            color: '#8C8C8C',
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            textOverflow: 'ellipsis',
          }}
        >
          {labelText}
        </span>
        {/* [v1.1] 右侧箭头：SVG 16x16，仅 transform 翻转方向，位置完全不变 */}
        <ArrowIcon
          size={16}
          color="#8C8C8C"
          expanded={isExpanded}
          testId={`${testId}-arrow`}
        />
      </div>
      {isExpanded && expandedContent ? (
        <div
          data-testid={`${testId}-expanded`}
          style={{ marginTop: 8 }}
          onClick={(e) => e.stopPropagation()}
        >
          {expandedContent}
        </div>
      ) : null}
    </div>
  );
}

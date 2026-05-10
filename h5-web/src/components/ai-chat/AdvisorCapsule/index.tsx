'use client';

/**
 * [PRD-448 2026-05-10] 咨询人胶囊（AdvisorCapsule）
 *
 * 统一替换 AI 详情页 / AI 首页 中"XXX 的档案"提示行为浅灰圆角胶囊：
 * - 浅灰背景 #F5F5F5、圆角 8px、内边距 4px / 10px
 * - 左侧 12x12 线性小人头像（#8C8C8C）
 * - 文案"XXX 的档案"，字号 12px，颜色 #8C8C8C
 * - 右侧折叠箭头：折叠 ⌄、展开 ⌃
 * - 整条点击切换折叠/展开
 * - 展开内容由调用方通过 expandedContent slot 传入
 *
 * 注意：胶囊本身要嵌入在 AI 回答气泡内部第一行（气泡上下/左右内边距由调用方控制）。
 */

import React, { useCallback, useState } from 'react';
import PersonIcon from './PersonIcon';

export interface AdvisorCapsuleProps {
  /** 家庭成员名字，例如 "妈妈" / "宝宝" / "张三"；为空时按兜底策略显示 */
  memberName?: string | null | undefined;
  /** 加载中状态：显示"加载中…"占位 */
  loading?: boolean;
  /** 默认是否展开，默认 false */
  defaultExpanded?: boolean;
  /** 受控展开状态（可选） */
  expanded?: boolean;
  /** 展开/折叠状态切换回调 */
  onToggle?: (expanded: boolean) => void;
  /** 展开态显示的内容（slot），由调用方传入：
   *  - AI 详情页：档案信息卡
   *  - AI 首页：7 项档案字段
   */
  expandedContent?: React.ReactNode;
  /** 自定义类名 */
  className?: string;
  /** 自定义外层包裹样式（一般不需要传） */
  style?: React.CSSProperties;
  /** 自定义 data-testid，默认 advisor-capsule */
  testId?: string;
}

const FALLBACK_NAME = '我';

export default function AdvisorCapsule({
  memberName,
  loading,
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

  // 文案兜底：成员名空 → "我的档案"；loading → "加载中…"
  const safeName = (memberName ?? '').toString().trim();
  let labelText: string;
  if (loading) {
    labelText = '加载中…';
  } else if (safeName) {
    labelText = `${safeName} 的档案`;
  } else {
    labelText = `${FALLBACK_NAME}的档案`;
  }

  return (
    <div
      data-testid={`${testId}-wrapper`}
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
          alignItems: 'center',
          width: '100%',
          background: '#F5F5F5',
          borderRadius: 8,
          padding: '4px 10px',
          cursor: 'pointer',
          userSelect: 'none',
          boxSizing: 'border-box',
        }}
      >
        <PersonIcon size={12} color="#8C8C8C" />
        <span
          data-testid={`${testId}-label`}
          style={{
            marginLeft: 6,
            flex: 1,
            fontSize: 12,
            lineHeight: '18px',
            color: '#8C8C8C',
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            textOverflow: 'ellipsis',
          }}
        >
          {labelText}
        </span>
        <span
          data-testid={`${testId}-arrow`}
          aria-hidden="true"
          style={{
            marginLeft: 8,
            color: '#8C8C8C',
            fontSize: 12,
            lineHeight: '12px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 12,
            height: 12,
            flexShrink: 0,
          }}
        >
          {isExpanded ? '⌃' : '⌄'}
        </span>
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

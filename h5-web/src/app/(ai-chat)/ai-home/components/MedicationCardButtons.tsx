'use client';

/**
 * [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] 识药结果卡片底部 4 按钮（2x2 网格）
 *
 * 按 PRD 规格实现：
 *   - 布局：2 行 2 列，1 行 2 按钮
 *   - 排列：上行 [💊 加入用药计划] [📅 查看用药计划]
 *           下行 [⏰ 今日用药]      [📸 重新拍照]
 *   - 胶囊样式：圆角 999px、高度 36、横向 padding 12、emoji 与文字间距 6
 *   - 字号 14px（窄屏自动缩小为 12px）
 *   - 默认背景：rgba(124,58,237,0.08)，文字色 #7C3AED
 *   - 红点：仅「今日用药」按钮，hasTodayMedication=true 时显示
 *   - 置灰规则：
 *       · recognitionFailed=true → 「加入用药计划」置灰
 *       · hasTodayMedication=false → 「今日用药」置灰
 *       · alreadyJoined=true → 「加入用药计划」变为「✓ 已加入」灰态
 *   - 置灰按钮点击完全无响应
 */

import React from 'react';

export interface MedicationCardButtonsProps {
  /** 识药是否失败（用于判定「加入用药计划」是否置灰） */
  recognitionFailed: boolean;
  /** 当前咨询人「今天是否有用药计划」 */
  hasTodayMedication: boolean;
  /** 是否已加入用药计划（来自 drugAddedMap） */
  alreadyJoined: boolean;
  /** 首屏数据未拉到（loading 中），用于防止红点闪烁 */
  loadingTodayMedication?: boolean;
  onJoin: () => void;
  onView: () => void;
  onToday: () => void;
  onRetake: () => void;
}

interface BtnDef {
  key: 'join' | 'view' | 'today' | 'retake';
  icon: string;
  label: string;
}

// PRD 1.2：三端字符锁死
const BTNS: BtnDef[] = [
  { key: 'join', icon: '\u{1F48A}', label: '加入用药计划' }, // 💊
  { key: 'view', icon: '\u{1F4C5}', label: '查看用药计划' }, // 📅
  { key: 'today', icon: '\u23F0', label: '今日用药' }, // ⏰
  { key: 'retake', icon: '\u{1F4F8}', label: '重新拍照' }, // 📸
];

export default function MedicationCardButtons(props: MedicationCardButtonsProps) {
  const {
    recognitionFailed,
    hasTodayMedication,
    alreadyJoined,
    loadingTodayMedication = false,
    onJoin,
    onView,
    onToday,
    onRetake,
  } = props;

  const isDisabled = (key: BtnDef['key']): boolean => {
    if (key === 'join') return recognitionFailed;
    if (key === 'today') return !hasTodayMedication;
    return false;
  };

  // 红点仅「今日用药」+「有计划」时显示；loading 阶段不显示，防闪烁
  const showRedDot = (key: BtnDef['key']): boolean =>
    key === 'today' && hasTodayMedication && !loadingTodayMedication;

  const handlers: Record<BtnDef['key'], () => void> = {
    join: onJoin,
    view: onView,
    today: onToday,
    retake: onRetake,
  };

  return (
    <div
      data-testid="medication-card-buttons"
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        columnGap: 8,
        rowGap: 8,
        width: '100%',
      }}
    >
      {BTNS.map((b) => {
        const disabled = isDisabled(b.key);
        const isJoinDone = b.key === 'join' && alreadyJoined && !recognitionFailed;
        const label = isJoinDone ? '✓ 已加入' : b.label;
        const reddot = showRedDot(b.key);

        return (
          <button
            key={b.key}
            type="button"
            data-testid={`med-btn-${b.key}`}
            disabled={disabled || isJoinDone}
            onClick={() => {
              if (disabled) return;
              handlers[b.key]();
            }}
            className="aihome-med-btn"
            style={{
              position: 'relative',
              height: 36,
              borderRadius: 999,
              padding: '0 12px',
              border: 'none',
              cursor: disabled || isJoinDone ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              background: disabled
                ? 'rgba(0,0,0,0.05)'
                : isJoinDone
                ? 'rgba(0,0,0,0.05)'
                : 'rgba(124, 58, 237, 0.08)',
              color: disabled || isJoinDone ? '#9CA3AF' : '#7C3AED',
              fontSize: 14,
              fontWeight: 500,
              lineHeight: 1,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              transition: 'transform 0.08s ease-out',
            }}
          >
            <span
              data-testid={`med-btn-${b.key}-emoji`}
              style={{
                fontSize: 15,
                lineHeight: 1,
                opacity: disabled ? 0.6 : 1,
                filter: disabled ? 'grayscale(1)' : 'none',
                flexShrink: 0,
              }}
            >
              {b.icon}
            </span>
            <span
              data-testid={`med-btn-${b.key}-label`}
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                minWidth: 0,
              }}
            >
              {label}
            </span>
            {reddot && (
              <span
                data-testid={`med-btn-${b.key}-reddot`}
                aria-label="今日有用药计划"
                style={{
                  position: 'absolute',
                  top: -2,
                  right: -2,
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#FF3B30',
                  boxShadow: '0 0 0 1.5px #fff',
                  pointerEvents: 'none',
                }}
              />
            )}
          </button>
        );
      })}
      {/* 窄屏（<=360px）字号回退到 12px */}
      <style>{`
        @media (max-width: 360px) {
          [data-testid="medication-card-buttons"] .aihome-med-btn {
            font-size: 12px !important;
          }
          [data-testid="medication-card-buttons"] .aihome-med-btn span[data-testid$="-emoji"] {
            font-size: 13px !important;
          }
        }
        [data-testid="medication-card-buttons"] .aihome-med-btn:not(:disabled):active {
          transform: scale(0.96);
        }
      `}</style>
    </div>
  );
}

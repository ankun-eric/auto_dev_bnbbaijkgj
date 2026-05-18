'use client';

/**
 * [PRD-FAMILY-MEMBER-V2 2026-05-18] 家庭成员字徽（圆形主色底 + 白色文字）
 *
 * 全局统一字徽：取关系字（爸/妈/夫/妻/...），按辈分分色。
 * 本人字徽内容为「我」，主色渐变背景。
 * 老数据兜底：姓名首字 + 灰蓝 + 待补充角标。
 */

import { BADGE_TONE_COLOR, getMemberBadge } from '@/lib/family-relation';

interface Props {
  /** 关系名（"本人" / 15 种预置 / "其他" / 老数据为空） */
  relationName?: string | null;
  /** 老数据兜底用：姓名 */
  name?: string | null;
  /** "其他"关系时用户填写的具体关系名 */
  customRelation?: string | null;
  /** 是否本人卡片 */
  isSelf?: boolean;
  /** 尺寸 */
  size?: number;
  /** 字号 */
  fontSize?: number;
  /** 是否显示「待补充」黄色角标（老数据缺关系字段时） */
  showPlaceholderTag?: boolean;
}

export default function MemberBadge({
  relationName,
  name,
  customRelation,
  isSelf,
  size = 42,
  fontSize,
  showPlaceholderTag = true,
}: Props) {
  const effectiveRelation = isSelf ? '本人' : relationName;
  const badge = getMemberBadge(effectiveRelation, name, customRelation);
  const tone = badge.tone;
  const color = BADGE_TONE_COLOR[tone === 'self' ? 'self' : tone];
  const fs = fontSize ?? Math.round(size * 0.4);
  const isTwoChar = badge.text.length >= 2;
  return (
    <div
      style={{
        position: 'relative',
        width: size,
        height: size,
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          background: color.bg,
          color: color.fg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: isTwoChar ? Math.round(fs * 0.75) : fs,
          fontWeight: 700,
          letterSpacing: isTwoChar ? -1 : 0,
        }}
      >
        {badge.text}
      </div>
      {badge.placeholder && showPlaceholderTag && (
        <div
          style={{
            position: 'absolute',
            right: -2,
            top: -4,
            background: '#FEF3C7',
            color: '#D97706',
            fontSize: 9,
            padding: '1px 4px',
            borderRadius: 6,
            fontWeight: 600,
            lineHeight: 1,
            border: '1px solid #FCD34D',
          }}
        >
          待补充
        </div>
      )}
    </div>
  );
}

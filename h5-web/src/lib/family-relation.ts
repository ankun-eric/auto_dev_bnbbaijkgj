/**
 * [PRD-FAMILY-MEMBER-V2 2026-05-18] 家庭成员模块共用工具
 *
 * - 15 种预置关系 +「其他」
 * - 性别智能锁定
 * - 出生年智能默认值
 * - 关系唯一性
 * - 关系合理性硬校验
 * - 字徽（取字 + 分色）
 * - 年龄计算
 */

export type RelationCategory = 'parent' | 'grand' | 'spouse' | 'sibling' | 'child' | 'other';

export interface RelationDef {
  /** 关系名（中文 key） */
  name: string;
  /** 强制性别：M=男、F=女、null=用户选（仅"其他"） */
  gender: 'M' | 'F' | null;
  /** 是否唯一（每个用户只能有 1 个） */
  unique: boolean;
  /** 字徽（圆形头像内文字） */
  badge: string;
  /** 字徽底色分类 */
  badgeTone: 'self' | 'elder' | 'peer' | 'younger' | 'other';
  /** 出生年偏移量：本人年份 + offset（正=更老）；其他=同岁 */
  birthYearOffset: number | 'same';
  /** 合理性硬校验类型：'elder'=必须比本人老（出生年 > 本人）  'younger'=必须比本人小（出生年 < 本人）  null=不校验 */
  ageRule: 'elder' | 'younger' | null;
  category: RelationCategory;
}

/**
 * 15 种预置关系 + 「其他」
 * 顺序：爸爸、妈妈、老公、老婆、儿子、女儿、哥哥、姐姐、弟弟、妹妹、爷爷、奶奶、外公、外婆、其他
 */
export const RELATION_DEFS: RelationDef[] = [
  { name: '爸爸', gender: 'M', unique: true,  badge: '爸',   badgeTone: 'elder',   birthYearOffset: 25,    ageRule: 'elder',   category: 'parent' },
  { name: '妈妈', gender: 'F', unique: true,  badge: '妈',   badgeTone: 'elder',   birthYearOffset: 25,    ageRule: 'elder',   category: 'parent' },
  { name: '老公', gender: 'M', unique: true,  badge: '夫',   badgeTone: 'peer',    birthYearOffset: -2,    ageRule: null,      category: 'spouse' },
  { name: '老婆', gender: 'F', unique: true,  badge: '妻',   badgeTone: 'peer',    birthYearOffset: 2,     ageRule: null,      category: 'spouse' },
  { name: '儿子', gender: 'M', unique: false, badge: '儿',   badgeTone: 'younger', birthYearOffset: -25,   ageRule: 'younger', category: 'child' },
  { name: '女儿', gender: 'F', unique: false, badge: '女',   badgeTone: 'younger', birthYearOffset: -25,   ageRule: 'younger', category: 'child' },
  { name: '哥哥', gender: 'M', unique: false, badge: '哥',   badgeTone: 'peer',    birthYearOffset: 3,     ageRule: null,      category: 'sibling' },
  { name: '姐姐', gender: 'F', unique: false, badge: '姐',   badgeTone: 'peer',    birthYearOffset: 3,     ageRule: null,      category: 'sibling' },
  { name: '弟弟', gender: 'M', unique: false, badge: '弟',   badgeTone: 'peer',    birthYearOffset: -3,    ageRule: null,      category: 'sibling' },
  { name: '妹妹', gender: 'F', unique: false, badge: '妹',   badgeTone: 'peer',    birthYearOffset: -3,    ageRule: null,      category: 'sibling' },
  { name: '爷爷', gender: 'M', unique: true,  badge: '爷',   badgeTone: 'elder',   birthYearOffset: 50,    ageRule: 'elder',   category: 'grand' },
  { name: '奶奶', gender: 'F', unique: true,  badge: '奶',   badgeTone: 'elder',   birthYearOffset: 50,    ageRule: 'elder',   category: 'grand' },
  { name: '外公', gender: 'M', unique: true,  badge: '外公', badgeTone: 'elder',   birthYearOffset: 50,    ageRule: 'elder',   category: 'grand' },
  { name: '外婆', gender: 'F', unique: true,  badge: '外婆', badgeTone: 'elder',   birthYearOffset: 50,    ageRule: 'elder',   category: 'grand' },
  { name: '其他', gender: null,unique: false, badge: '',    badgeTone: 'other',   birthYearOffset: 'same',ageRule: null,      category: 'other' },
];

/** 字徽底色 → 颜色 */
export const BADGE_TONE_COLOR: Record<RelationDef['badgeTone'], { bg: string; fg: string }> = {
  self:    { bg: 'linear-gradient(135deg, #38BDF8, #0284C7)', fg: '#fff' },
  elder:   { bg: '#0284C7', fg: '#fff' },
  peer:    { bg: '#0EA5E9', fg: '#fff' },
  younger: { bg: '#06B6D4', fg: '#fff' },
  other:   { bg: '#64748B', fg: '#fff' },
};

/** 主题色 */
export const FAM_THEME = {
  primary: '#0EA5E9',
  primaryDark: '#0284C7',
  primaryLight: '#38BDF8',
  pillBg: '#F0F9FF',
  pillBgActive: '#E0F2FE',
  pillBorderActive: '#0EA5E9',
  pillBgDisabled: '#F1F5F9',
  textPrimary: '#0F172A',
  textSecondary: '#334155',
  textHint: '#94A3B8',
  textError: '#DC2626',
  errorBorder: '#EF4444',
  warnBg: '#FEF3C7',
  warnFg: '#D97706',
  cardBg: '#FFFFFF',
  pageBg: '#F0F9FF',
  divider: '#E2E8F0',
};

/** 常见慢性病（10 个） */
export const CHRONIC_DISEASE_OPTIONS = [
  '高血压', '糖尿病', '高血脂', '冠心病', '脑卒中',
  '慢阻肺', '哮喘', '慢性肾病', '甲状腺', '痛风',
];

export function findRelationDef(name?: string | null): RelationDef | null {
  if (!name) return null;
  return RELATION_DEFS.find((r) => r.name === name) || null;
}

/**
 * 计算出生年默认值
 * @param selfBirthYear 本人出生年
 * @param relationName 关系名
 * @returns YYYY-01-01 格式字符串
 */
export function computeDefaultBirthday(selfBirthYear: number, relationName: string): string {
  const def = findRelationDef(relationName);
  if (!def) return `${selfBirthYear}-01-01`;
  const currentYear = new Date().getFullYear();
  let year: number;
  if (def.birthYearOffset === 'same') {
    year = selfBirthYear;
  } else {
    year = selfBirthYear + def.birthYearOffset;
  }
  // 儿子/女儿：必须 > 0（即出生年要 ≤ 当前年）
  if (def.ageRule === 'younger' && year >= currentYear) {
    year = currentYear - 1;
  }
  // 校验合理范围
  if (year < 1900) year = 1900;
  if (year > currentYear) year = currentYear;
  return `${year}-01-01`;
}

/**
 * 计算周岁（按今天）
 */
export function calcAge(birthday?: string | null): number | null {
  if (!birthday) return null;
  const m = String(birthday).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const by = parseInt(m[1], 10);
  const bm = parseInt(m[2], 10);
  const bd = parseInt(m[3], 10);
  if (!by) return null;
  const today = new Date();
  let age = today.getFullYear() - by;
  const tm = today.getMonth() + 1;
  const td = today.getDate();
  if (tm < bm || (tm === bm && td < bd)) age -= 1;
  return age >= 0 ? age : null;
}

/**
 * 关系合理性校验
 * @returns 合法返回 true；不合法返回 false
 */
export function validateRelationAge(
  relationName: string,
  memberBirthday: string,
  selfBirthday: string,
): boolean {
  const def = findRelationDef(relationName);
  if (!def || !def.ageRule) return true;
  const memberAge = calcAge(memberBirthday);
  const selfAge = calcAge(selfBirthday);
  if (memberAge == null || selfAge == null) return true;
  if (def.ageRule === 'elder') {
    // 长辈：成员年龄必须 > 本人；如果 memberAge <= selfAge，则非法
    return memberAge > selfAge;
  }
  if (def.ageRule === 'younger') {
    // 晚辈：成员年龄必须 < 本人；如果 memberAge >= selfAge，则非法
    return memberAge < selfAge;
  }
  return true;
}

/**
 * 字徽内容
 * @param relationName 关系名（"本人" / 15 种预置 / "其他"）
 * @param fallbackName 当无关系字段时的姓名首字兜底
 * @param customRelation "其他"关系时用户填写的具体关系名
 */
export function getMemberBadge(
  relationName: string | null | undefined,
  fallbackName: string | null | undefined,
  customRelation?: string | null,
): { text: string; tone: RelationDef['badgeTone'] | 'self'; placeholder: boolean } {
  if (relationName === '本人' || relationName === 'self') {
    return { text: '我', tone: 'self', placeholder: false };
  }
  const def = findRelationDef(relationName);
  if (def) {
    if (def.name === '其他') {
      const txt = (customRelation || '').trim().charAt(0) || '他';
      return { text: txt, tone: 'other', placeholder: false };
    }
    return { text: def.badge, tone: def.badgeTone, placeholder: false };
  }
  // 兜底：姓名首字
  const txt = (fallbackName || '').trim().charAt(0) || '?';
  return { text: txt, tone: 'other', placeholder: true };
}

/**
 * 输入：本人健康档案（含 birthday）；返回 birthYear，若缺失返回 null
 */
export function extractSelfBirthYear(selfProfile: { birthday?: string | null } | null | undefined): number | null {
  const b = selfProfile?.birthday;
  if (!b) return null;
  const m = String(b).match(/^(\d{4})/);
  if (!m) return null;
  const y = parseInt(m[1], 10);
  if (!y || y < 1900) return null;
  return y;
}

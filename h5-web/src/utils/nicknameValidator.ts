/**
 * [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29] 守护人体系 v1.3.2 补丁
 * 三端共用的姓名校验工具：场景 1 NewFamilyMemberModal + i-guard InviteGuardianDrawer + /family-invite。
 *
 * 校验规则（D5：三端字符级一致）：
 *  - trim 后非空
 *  - 长度 1–20 字符（含中英文 / emoji）
 *  - 不允许纯特殊字符（"!!!"、"???"、"---"、"。。。"、"###" 等）
 *  - 允许 emoji 与昵称符号（如 "张妈妈❤"、"小李叔叔😊"）
 */

export interface NicknameValidateResult {
  ok: boolean;
  msg: string;
}

const MAX_NICKNAME_LENGTH = 20;
const MIN_NICKNAME_LENGTH = 1;

// 标点 / 符号集合（中文与英文常用纯符号）
// 注意：不能拦截 emoji（按 PRD 决策 D5 允许）。emoji 主要分布在 \u{1F300}-\u{1FAFF} 等高位 Unicode，
// 这里仅匹配"文字字符（CJK / 拉丁 / 数字）"的反集中"非文字非 emoji"部分，
// 实现方式：检查 trim 后是否至少包含一个"字符类"（文字 / 数字 / emoji）。
const HAS_LETTER_DIGIT_OR_EMOJI = /[\p{L}\p{N}\p{Extended_Pictographic}]/u;

export function validateNickname(value: string): NicknameValidateResult {
  if (value == null) {
    return { ok: false, msg: '请填写姓名' };
  }
  const trimmed = String(value).trim();
  if (!trimmed) {
    return { ok: false, msg: '请填写姓名' };
  }
  // 用户可见长度（按字符数算，不区分 surrogate pair）
  // 这里用 Array.from 兼容 emoji（避免一个 emoji 算两位长度）
  const len = Array.from(trimmed).length;
  if (len < MIN_NICKNAME_LENGTH) {
    return { ok: false, msg: '请填写姓名' };
  }
  if (len > MAX_NICKNAME_LENGTH) {
    return { ok: false, msg: `姓名长度需在 ${MIN_NICKNAME_LENGTH}–${MAX_NICKNAME_LENGTH} 之间` };
  }
  // 纯特殊字符拦截：trim 后必须至少有一个文字 / 数字 / emoji
  if (!HAS_LETTER_DIGIT_OR_EMOJI.test(trimmed)) {
    return { ok: false, msg: '姓名不能为纯符号' };
  }
  return { ok: true, msg: '' };
}

/**
 * 关系字段校验（trim + 1~10 长度）。仅用于场景 2 邀请页统一兜底。
 */
export function validateRelation(value: string): NicknameValidateResult {
  if (value == null) {
    return { ok: false, msg: '请填写关系（如：父亲、母亲）' };
  }
  const trimmed = String(value).trim();
  if (!trimmed) {
    return { ok: false, msg: '请填写关系（如：父亲、母亲）' };
  }
  const len = Array.from(trimmed).length;
  if (len < 1 || len > 10) {
    return { ok: false, msg: '关系长度需在 1–10 之间' };
  }
  return { ok: true, msg: '' };
}

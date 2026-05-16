/**
 * [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 通用展示格式化工具
 *
 * 用于统一处理后端原始字段在前端的展示文案。
 * 注意：写入侧（提交给后端）依然使用后端 schema 定义的原始值，
 *      仅在展示侧通过本工具映射为中文文案，避免数据库与 API schema 改动。
 */

export const GENDER_MAP: Record<string, string> = {
  male: '男',
  female: '女',
  m: '男',
  f: '女',
  '男': '男',
  '女': '女',
  unknown: '未设置',
  other: '其他',
  '其他': '其他',
  '': '未设置',
};

/**
 * 把后端原始性别字段映射为中文展示文案。
 * 兼容 male/female/m/f/中文男女/unknown/空字符串/undefined。
 */
export function formatGender(g?: string | null): string {
  if (g === undefined || g === null) return '未设置';
  const key = String(g).trim().toLowerCase();
  if (key in GENDER_MAP) return GENDER_MAP[key];
  // 已是中文男/女的原值（GENDER_MAP key 是 lowercase，中文不会被 lowercase 改变）
  const raw = String(g).trim();
  if (raw in GENDER_MAP) return GENDER_MAP[raw];
  return raw || '未设置';
}

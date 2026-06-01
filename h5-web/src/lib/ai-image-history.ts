/**
 * [BUG_FIX_AI_HOME_IMAGE_HISTORY_RESTORE_V1 2026-06-01]
 * AI 首页「上传图片对话切走再切回变文字」优化 —— 纯函数解析工具。
 *
 * 背景：
 *   用户用「报告解读 / 拍照识药」等入口上传图片发起对话时，真正存进后端的是一段
 *   「[用户上传的图片 N 张] + URL 列表 + 用户说明文字」的纯文本。切回历史时若不还原，
 *   就只会显示成一长串纯文字。本模块提供从这段纯文本中还原图片 URL + 说明文字的能力，
 *   供 ai-home 页面历史加载时统一调用（报告解读 / 拍照识药 / 其他上传入口共用）。
 *
 * 设计为纯函数 + 无副作用，便于独立单元测试。
 */

/** 图片裸链接：png/jpg/jpeg/gif/webp，可带查询串 */
export const IMG_URL_RE =
  /(https?:\/\/[^\s)\]\"']+?\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s)\]\"']*)?)/gi;
/** Markdown 图片语法 ![alt](url) */
export const MD_IMG_RE = /!\[[^\]]*\]\(([^)]+)\)/g;

/** 「[用户上传的图片 N 张]」占位 */
const IMG_PLACEHOLDER_RE = /\[用户上传的图片\s*\d*\s*张?\]/g;
/** 「[用户上传的文件 N 个]」占位 */
const FILE_PLACEHOLDER_RE = /\[用户上传的文件\s*\d*\s*个?\]/g;
/** 行首序号前缀，如「1. 」「2. 」 */
const NUMBERED_LINE_RE = /^\s*\d+\.\s*/;

/**
 * 从文本里抽离图片 URL（Markdown 形态 + 裸链接），
 * 返回剔除图片占位后的纯文本 + 去重后的图片 URL 数组。
 */
export function extractImagesFromContent(
  raw: string,
): { text: string; images: string[] } {
  if (!raw) return { text: raw, images: [] };
  const images: string[] = [];
  let text = raw.replace(MD_IMG_RE, (_, url) => {
    if (url) images.push(String(url).trim());
    return '';
  });
  text = text.replace(IMG_URL_RE, (url) => {
    images.push(url);
    return '';
  });
  text = text.replace(/\n{3,}/g, '\n\n').trim();
  const dedup = Array.from(new Set(images.filter(Boolean)));
  return { text, images: dedup };
}

/**
 * 历史消息「识别还原」：把存成纯文字的
 * 「[用户上传的图片 N 张] + URL 列表 + 用户说明」还原为
 * { images: 图片 URL 数组, caption: 去除占位/序号/裸 URL 后的真实说明文字 }。
 *
 * - 必须含「[用户上传的图片」占位且能抽到 ≥1 个图片 URL，才认定为图片消息；否则返回 null。
 * - 新老数据通用，报告解读 / 拍照识药 / 其他上传入口共用。
 */
export function restoreImageMessageFromContent(
  raw: string,
): { images: string[]; caption: string } | null {
  if (!raw) return null;
  if (!/\[用户上传的图片/.test(raw)) return null;
  const { text, images } = extractImagesFromContent(raw);
  if (images.length === 0) return null;
  let caption = text
    .replace(IMG_PLACEHOLDER_RE, '')
    .replace(FILE_PLACEHOLDER_RE, '');
  caption = caption
    .split('\n')
    .map((line) => line.replace(NUMBERED_LINE_RE, '').trim())
    .filter((line) => line.length > 0)
    .join('\n')
    .trim();
  return { images, caption };
}

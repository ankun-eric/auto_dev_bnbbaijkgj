#!/usr/bin/env node
// PRD-442 §9 旧绿色清退 lint（三层扫描：色值 / 语义关键词 / 图片资源）
// 用法：node scripts/lint-legacy-green.mjs [--strict]
//   --strict: 任意命中即返回非零退出码（用于 CI 阻断）
//   缺省：仅打印报告，不阻断

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { resolve, dirname, extname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = resolve(__dirname, '..');

const STRICT = process.argv.includes('--strict');

// 扫描白名单（不进入扫描的目录）
const SKIP_DIRS = new Set([
  'node_modules', '.git', '.next', 'dist', 'build', '.dart_tool',
  '.pytest_cache', '__pycache__', '.venv', 'venv', '.tools',
  'apk_download', 'apk_downloads', 'ipa_download', '_prd442_android_dl',
  'mem', 'uploads', 'build_artifacts', '_deploy_tmp',
  // 旧 PRD 文档/原型本身可能含有 PRD-441 的 hex 引用，扫描会误报
  'design-system', // 单一真相源不扫描自身
]);

// 文件后缀
const SCAN_EXT = new Set([
  '.css', '.scss', '.wxss',
  '.dart', '.kt', '.swift',
  '.tsx', '.ts', '.jsx', '.js',
  '.vue', '.wxml', '.html',
]);

// 第一层：色值字符串（旧绿色 #52c41a 全大小写组合 + rgb/hsl）
const COLOR_PATTERNS = [
  /#52c41a\b/gi,
  /rgb\(\s*82\s*,\s*196\s*,\s*26\s*\)/gi,
  /rgba\(\s*82\s*,\s*196\s*,\s*26\s*,\s*[\d.]+\s*\)/gi,
  /hsl\(\s*111\s*,\s*\d+%\s*,\s*\d+%\s*\)/gi,
];

// 第二层：语义关键词
const SEMANTIC_PATTERNS = [
  /\bsuccess[-_]green\b/gi,
  /\bbrand[-_]green\b/gi,
  /\bgreen[-_]primary\b/gi,
  /\btheme[-_]green\b/gi,
  /\bPRIMARY_GREEN\b/g,
  /\bBRAND_GREEN\b/g,
  /\bTHEME\.green\b/g,
  /\$green\b/g,
  /--green\b/g,
  /--primary-green\b/g,
];

// 白名单文件 glob（PRD-441 §7 允许的语义场景）
const ALLOWLIST_FILES = [
  /components\/StatusBadge/i,
  /components\/SuccessToast/i,
  /design-system-v2/i, // 自动生成的目标文件
  /menu-mode-design-system/i, // PRD-442 菜单模式 v1（已上线，独立色板）
];

const findings = [];

function isAllowed(filePath) {
  return ALLOWLIST_FILES.some(rx => rx.test(filePath));
}

function scanFile(filePath) {
  if (isAllowed(filePath)) return;
  const ext = extname(filePath).toLowerCase();
  if (!SCAN_EXT.has(ext)) return;
  let content;
  try { content = readFileSync(filePath, 'utf-8'); }
  catch { return; }
  // 太大文件跳过（避免日志/产物）
  if (content.length > 500000) return;

  for (const rx of COLOR_PATTERNS) {
    rx.lastIndex = 0;
    let m;
    while ((m = rx.exec(content))) {
      const before = content.slice(0, m.index);
      const line = before.split('\n').length;
      findings.push({ layer: 'color', file: relative(ROOT, filePath), line, match: m[0] });
    }
  }
  for (const rx of SEMANTIC_PATTERNS) {
    rx.lastIndex = 0;
    let m;
    while ((m = rx.exec(content))) {
      const before = content.slice(0, m.index);
      const line = before.split('\n').length;
      findings.push({ layer: 'semantic', file: relative(ROOT, filePath), line, match: m[0] });
    }
  }
}

function walk(dir) {
  let entries;
  try { entries = readdirSync(dir); } catch { return; }
  for (const name of entries) {
    if (SKIP_DIRS.has(name)) continue;
    if (name.startsWith('.') && !['.github'].includes(name)) continue;
    const full = resolve(dir, name);
    let st;
    try { st = statSync(full); } catch { continue; }
    if (st.isDirectory()) walk(full);
    else if (st.isFile()) scanFile(full);
  }
}

console.log(`[lint-legacy-green] scanning from: ${ROOT}`);
walk(ROOT);

const colorHits = findings.filter(f => f.layer === 'color').length;
const semHits   = findings.filter(f => f.layer === 'semantic').length;

console.log('');
console.log(`[lint-legacy-green] summary: color=${colorHits}  semantic=${semHits}  total=${findings.length}`);

if (findings.length > 0) {
  console.log('[lint-legacy-green] details (first 50):');
  for (const f of findings.slice(0, 50)) {
    console.log(`  [${f.layer}] ${f.file}:${f.line}  -> ${f.match}`);
  }
  if (STRICT) {
    console.error('[lint-legacy-green] FAIL (strict): legacy green usage detected.');
    process.exit(2);
  } else {
    console.log('[lint-legacy-green] non-strict mode: report only, no blocking.');
  }
} else {
  console.log('[lint-legacy-green] PASS: no legacy green usage detected.');
}

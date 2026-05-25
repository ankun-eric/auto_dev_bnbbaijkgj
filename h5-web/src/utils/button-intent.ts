/**
 * [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
 * 统一按钮意图解析（H5 前端版）。
 *
 * 后台「功能按钮管理」配置体系已升级为 3 层
 * (`button_type` + `ai_function_type` + `capture_purpose`)。
 * 本工具把任意一种合法配置统一翻译成「专用引擎 intent」：
 *
 * - `'report_interpret'` → 后端 ReportInterpretEngine
 * - `'drug_identify'`    → 后端 DrugIdentifyEngine
 * - `null`               → 通用 LLM
 *
 * ⚠️ 与后端 `backend/app/services/button_intent_resolver.py` 及小程序
 * `miniprogram/utils/buttonIntent.js` 的逻辑必须保持 100% 一致。
 * 三端任一修改时必须同步修改另外两端。
 */

export type ResolvedIntent = 'report_interpret' | 'drug_identify' | null;

export interface ButtonIntentInput {
  intent?: string | null;
  button_type?: string | null;
  ai_function_type?: string | null;
  capture_purpose?: string | null;
}

const REPORT_INTERPRET: ResolvedIntent = 'report_interpret';
const DRUG_IDENTIFY: ResolvedIntent = 'drug_identify';

const REPORT_TOP_TYPES = new Set<string>(['report_interpret', 'report_understand']);
const DRUG_TOP_TYPES = new Set<string>([
  'photo_recognize_drug',
  'drug_identify',
  'medication_recognize',
]);

const REPORT_AI_FN_LEGACY = new Set<string>(['report_interpret', 'report_understand']);
const DRUG_AI_FN_LEGACY = new Set<string>([
  'medicine_recognize',
  'photo_recognize_drug',
  'drug_identify',
]);

const CAPTURE_REPORT = 'interpret_report';
const CAPTURE_DRUG = 'identify_medicine';
const CAPTURE_UPLOAD = 'upload';

const norm = (v: string | null | undefined): string => (v || '').toString().trim().toLowerCase();

/**
 * 按优先级 P1→P5 解析按钮意图。命中即返回，不再继续判定。
 * - P1 显式 intent
 * - P2 老顶层 button_type
 * - P3 ai_function + 老子类型兼容
 * - P4 ai_function + image_capture + capture_purpose
 * - P5 兜底：null（通用 LLM）
 */
export function resolveButtonIntent(input: ButtonIntentInput): ResolvedIntent {
  const i = norm(input.intent);
  const bt = norm(input.button_type);
  const aft = norm(input.ai_function_type);
  const cp = norm(input.capture_purpose);

  // P1
  if (i === REPORT_INTERPRET) return REPORT_INTERPRET;
  if (i === DRUG_IDENTIFY) return DRUG_IDENTIFY;

  // P2
  if (REPORT_TOP_TYPES.has(bt)) return REPORT_INTERPRET;
  if (DRUG_TOP_TYPES.has(bt)) return DRUG_IDENTIFY;

  // P3 / P4
  if (bt === 'ai_function') {
    if (REPORT_AI_FN_LEGACY.has(aft)) return REPORT_INTERPRET;
    if (DRUG_AI_FN_LEGACY.has(aft)) return DRUG_IDENTIFY;

    if (aft === 'image_capture') {
      if (cp === CAPTURE_REPORT) return REPORT_INTERPRET;
      if (cp === CAPTURE_DRUG) return DRUG_IDENTIFY;
      if (cp === CAPTURE_UPLOAD) return null;
      return null;
    }
  }

  // P5
  return null;
}

/**
 * 推导上传后兜底用户气泡文案，与 resolveButtonIntent 共享同一套判定逻辑，
 * 避免「intent 走识药、文案显示通用」的不一致。
 */
export function resolveUploadFallbackPromptByIntent(
  input: ButtonIntentInput,
  kind: 'image' | 'file',
): string {
  if (kind === 'file') return '我上传了一份文件，请你帮我看看';
  const resolved = resolveButtonIntent(input);
  if (resolved === REPORT_INTERPRET) return '我上传了一份体检报告，请帮我解读';
  if (resolved === DRUG_IDENTIFY) return '我上传了一张药品图片，请帮我识别';
  return '我上传了一张图片，请你帮我看看';
}

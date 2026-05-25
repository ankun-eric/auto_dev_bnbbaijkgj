/**
 * [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
 * 统一按钮意图解析（微信小程序版）。
 *
 * 后台「功能按钮管理」配置体系已升级为 3 层
 * (button_type + ai_function_type + capture_purpose)。
 * 本工具把任意一种合法配置统一翻译成「专用引擎 intent」：
 *
 * - 'report_interpret' → 后端 ReportInterpretEngine
 * - 'drug_identify'    → 后端 DrugIdentifyEngine
 * - null               → 通用 LLM
 *
 * ⚠️ 与后端 backend/app/services/button_intent_resolver.py 及
 * H5 h5-web/src/utils/button-intent.ts 的逻辑必须保持 100% 一致。
 * 三端任一修改时必须同步修改另外两端。
 */

var REPORT_INTERPRET = 'report_interpret';
var DRUG_IDENTIFY = 'drug_identify';

var REPORT_TOP_TYPES = { report_interpret: 1, report_understand: 1 };
var DRUG_TOP_TYPES = {
  photo_recognize_drug: 1,
  drug_identify: 1,
  medication_recognize: 1,
};

var REPORT_AI_FN_LEGACY = { report_interpret: 1, report_understand: 1 };
var DRUG_AI_FN_LEGACY = {
  medicine_recognize: 1,
  photo_recognize_drug: 1,
  drug_identify: 1,
};

var CAPTURE_REPORT = 'interpret_report';
var CAPTURE_DRUG = 'identify_medicine';
var CAPTURE_UPLOAD = 'upload';

function norm(v) {
  if (v === null || v === undefined) return '';
  return String(v).trim().toLowerCase();
}

/**
 * 按优先级 P1→P5 解析按钮意图。命中即返回，不再继续判定。
 * @param {Object} input
 * @param {string|null} [input.intent]
 * @param {string|null} [input.button_type]
 * @param {string|null} [input.ai_function_type]
 * @param {string|null} [input.capture_purpose]
 * @returns {string|null} 'report_interpret' / 'drug_identify' / null
 */
function resolveButtonIntent(input) {
  input = input || {};
  var i = norm(input.intent);
  var bt = norm(input.button_type);
  var aft = norm(input.ai_function_type);
  var cp = norm(input.capture_purpose);

  // P1：显式 intent
  if (i === REPORT_INTERPRET) return REPORT_INTERPRET;
  if (i === DRUG_IDENTIFY) return DRUG_IDENTIFY;

  // P2：老顶层 button_type
  if (REPORT_TOP_TYPES[bt]) return REPORT_INTERPRET;
  if (DRUG_TOP_TYPES[bt]) return DRUG_IDENTIFY;

  // P3 / P4：ai_function 新顶层
  if (bt === 'ai_function') {
    if (REPORT_AI_FN_LEGACY[aft]) return REPORT_INTERPRET;
    if (DRUG_AI_FN_LEGACY[aft]) return DRUG_IDENTIFY;

    if (aft === 'image_capture') {
      if (cp === CAPTURE_REPORT) return REPORT_INTERPRET;
      if (cp === CAPTURE_DRUG) return DRUG_IDENTIFY;
      if (cp === CAPTURE_UPLOAD) return null;
      return null;
    }
  }

  // P5：兜底
  return null;
}

module.exports = {
  resolveButtonIntent: resolveButtonIntent,
  REPORT_INTERPRET: REPORT_INTERPRET,
  DRUG_IDENTIFY: DRUG_IDENTIFY,
};

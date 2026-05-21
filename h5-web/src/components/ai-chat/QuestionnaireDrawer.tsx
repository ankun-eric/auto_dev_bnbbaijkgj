'use client';

/**
 * [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 通用问卷抽屉
 *
 * 替代老 HealthSelfCheckDrawer，支持三种展示形态：
 * - DRAWER_SCROLL：抽屉-一屏多题（默认）
 * - DRAWER_STEPPED：抽屉-一题一屏
 * - INLINE_CHAT：对话内插入（不在本组件渲染，由对话页直接插入气泡处理）
 *
 * 支持的题型：single_choice / multi_choice / text
 * 支持的能力：题目联动（display_condition_json）、选项过滤（option_filter_json）、
 * 视觉布局 layout_hint=icon_grid / tag_grid / tag_list / text
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

export type DisplayForm = 'DRAWER_SCROLL' | 'DRAWER_STEPPED' | 'INLINE_CHAT';

export interface QnQuestionOption {
  label: string;
  value: string;
  icon?: string;
  score?: number;
  tags?: string[];
}

export interface QnQuestion {
  id: number;
  sort_order: number;
  question_type: 'single_choice' | 'multi_choice' | 'text';
  title: string;
  subtitle?: string | null;
  required?: boolean;
  options?: QnQuestionOption[];
  dimension?: string | null;
  display_condition_json?: any;
  option_filter_json?: any;
  layout_hint?: string;
}

export interface QnTemplate {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  intro_text?: string | null;
  estimated_minutes?: number;
  allow_back?: boolean;
  result_summary_template?: string | null;
  source?: string | null;
  ai_prompt_template?: string | null;
  ai_opening?: string | null;
}

export interface QnSubmitAnswerItem {
  question_id: number;
  value: any;
}

interface Props {
  open: boolean;
  onClose: () => void;
  template: QnTemplate | null;
  questions: QnQuestion[];
  displayForm: DisplayForm;
  /** 提交回调：用户在抽屉中点完所有题目并点提交后触发 */
  onSubmit: (answers: QnSubmitAnswerItem[]) => void | Promise<void>;
  /**
   * [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 自动下一步
   * 仅在 displayForm=DRAWER_STEPPED 时生效；
   * 选中单选题选项后立即跳下一题（无 delay），最后一题不自动提交。
   * 多选/文本题仍显示「下一题/提交」按钮。
   */
  autoNextEnabled?: boolean;
  /**
   * [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] DRAWER_SCROLL 形态下每页显示的题数（>=1）
   * 默认 999（一屏全部题目），>1 时按分页方式渲染（PRD：每页一组、底部下一页按钮）。
   */
  questionsPerPage?: number;
}

/** 判断题目"显示条件"是否满足 */
function isQuestionVisible(
  q: QnQuestion,
  answersByQid: Record<number, any>,
  questionsByDim: Record<string, QnQuestion>,
): boolean {
  const cond = q.display_condition_json;
  if (!cond || typeof cond !== 'object') return true;
  const deps: any[] = Array.isArray(cond.deps) ? cond.deps : [];
  if (deps.length === 0) return true;
  const logic = (cond.logic || 'and').toLowerCase();
  const results = deps.map((d: any) => {
    let depQid: number | undefined = d.question_id;
    if (!depQid && d.question_dimension) {
      const found = questionsByDim[d.question_dimension];
      depQid = found?.id;
    }
    if (!depQid) return true;
    const v = answersByQid[depQid];
    const op = (d.operator || 'in').toLowerCase();
    if (op === 'not_empty') {
      if (Array.isArray(v)) return v.length > 0;
      return v !== undefined && v !== null && v !== '';
    }
    const expected: any[] = Array.isArray(d.values) ? d.values : [];
    const arr: any[] = Array.isArray(v) ? v : v !== undefined && v !== null ? [v] : [];
    if (op === 'in') return arr.some((x) => expected.includes(x));
    if (op === 'not_in') return arr.every((x) => !expected.includes(x));
    if (op === 'eq') return arr[0] === expected[0];
    return true;
  });
  return logic === 'or' ? results.some(Boolean) : results.every(Boolean);
}

/** 计算题目的"实际可见选项"（应用 option_filter_json） */
function visibleOptions(
  q: QnQuestion,
  answersByQid: Record<number, any>,
  questionsByDim: Record<string, QnQuestion>,
): QnQuestionOption[] {
  const opts = q.options || [];
  const filt = q.option_filter_json;
  if (!filt || typeof filt !== 'object') return opts;
  const deps: any[] = Array.isArray(filt.deps) ? filt.deps : [];
  if (deps.length === 0) return opts;
  // 收集所有依赖题答案
  const triggerValues: string[] = [];
  for (const d of deps) {
    let depQid: number | undefined = d.question_id;
    if (!depQid && d.question_dimension) {
      const found = questionsByDim[d.question_dimension];
      depQid = found?.id;
    }
    if (!depQid) continue;
    const v = answersByQid[depQid];
    if (Array.isArray(v)) {
      for (const x of v) if (typeof x === 'string') triggerValues.push(x);
    } else if (typeof v === 'string') {
      triggerValues.push(v);
    }
  }
  const filterMap: Record<string, string[]> = filt.filter_map || {};
  if (Object.keys(filterMap).length === 0) return opts;
  if (triggerValues.length === 0) {
    // 无依赖答案：默认显示空集（PRD 中症状题在未选部位时不展示），但若 default='all' 则显示全部
    if (filt.default === 'all') return opts;
    return [];
  }
  const allow = new Set<string>();
  for (const tv of triggerValues) {
    const sub = filterMap[tv];
    if (Array.isArray(sub)) sub.forEach((s) => allow.add(s));
  }
  if (allow.size === 0) return [];
  return opts.filter((o) => allow.has(o.label) || allow.has(o.value));
}

function QuestionRenderer({
  q,
  value,
  options,
  onChange,
  disabled,
}: {
  q: QnQuestion;
  value: any;
  options: QnQuestionOption[];
  onChange: (v: any) => void;
  disabled?: boolean;
}) {
  const layout = q.layout_hint || 'tag_grid';

  if (q.question_type === 'text') {
    // [BUG-HSC-FIX-V2 2026-05-21] B-1：subtitle 只在题目上方作"小提示文案"展示，
    // textarea 的 placeholder 改用独立字段 (q as any).placeholder；缺省时用固定文案，
    // 避免 subtitle 同一段文字在"上方小标题"+"输入框 placeholder"重复出现。
    const phText =
      ((q as any).placeholder as string | undefined) ||
      '请输入您想补充的内容（选填）';
    return (
      <textarea
        value={(value as string) || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={phText}
        maxLength={200}
        rows={3}
        disabled={disabled}
        style={{
          width: '100%',
          border: '1px solid #e5e7eb',
          borderRadius: 8,
          padding: 10,
          fontSize: 14,
          resize: 'vertical',
        }}
      />
    );
  }

  const isMulti = q.question_type === 'multi_choice';
  const selectedArr: string[] = useMemo(
    () => (Array.isArray(value) ? value : value ? [value] : []),
    [value],
  );
  const toggle = (v: string) => {
    if (disabled) return;
    if (isMulti) {
      const next = selectedArr.includes(v)
        ? selectedArr.filter((x) => x !== v)
        : [...selectedArr, v];
      onChange(next);
    } else {
      onChange(v);
    }
  };

  if (layout === 'icon_grid') {
    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 8,
        }}
      >
        {options.map((opt) => {
          const selected = selectedArr.includes(opt.value);
          return (
            <button
              type="button"
              key={opt.value}
              onClick={() => toggle(opt.value)}
              style={{
                background: selected ? '#E6FAF7' : '#fff',
                border: selected ? '1.5px solid #2BB6A8' : '1px solid #e5e7eb',
                color: selected ? '#1F8E81' : '#333',
                borderRadius: 10,
                padding: '10px 4px',
                fontSize: 12,
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span style={{ fontSize: 22 }}>{opt.icon || '•'}</span>
              <span>{opt.label}</span>
            </button>
          );
        })}
      </div>
    );
  }

  // tag_grid / tag_list 共用
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {options.length === 0 ? (
        <div style={{ color: '#999', fontSize: 13 }}>请先完成上一题</div>
      ) : (
        options.map((opt) => {
          const selected = selectedArr.includes(opt.value);
          return (
            <button
              type="button"
              key={opt.value}
              onClick={() => toggle(opt.value)}
              style={{
                background: selected ? '#2BB6A8' : '#F2F4F7',
                color: selected ? '#fff' : '#333',
                border: selected ? '1px solid #2BB6A8' : '1px solid transparent',
                borderRadius: 16,
                padding: '6px 14px',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              {opt.label}
            </button>
          );
        })
      )}
    </div>
  );
}

export default function QuestionnaireDrawer({
  open,
  onClose,
  template,
  questions,
  displayForm,
  onSubmit,
  autoNextEnabled = false,
  questionsPerPage = 999,
}: Props) {
  const [answers, setAnswers] = useState<Record<number, any>>({});
  const [stepIdx, setStepIdx] = useState(0);
  // [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] DRAWER_SCROLL 分页模式下的当前页索引
  const [pageIdx, setPageIdx] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setAnswers({});
      setStepIdx(0);
      setPageIdx(0);
    }
  }, [open, template?.id]);

  const questionsByDim = useMemo(() => {
    const m: Record<string, QnQuestion> = {};
    for (const q of questions) {
      if (q.dimension) m[q.dimension] = q;
    }
    return m;
  }, [questions]);

  // 计算"当前可见题目列表"
  const visibleQuestions = useMemo(
    () => questions.filter((q) => isQuestionVisible(q, answers, questionsByDim)),
    [questions, answers, questionsByDim],
  );

  // 当依赖题答案变化时，自动清空被联动过滤掉的当前题答案（PRD E3）
  useEffect(() => {
    let changed = false;
    const next = { ...answers };
    for (const q of questions) {
      const v = next[q.id];
      if (v === undefined || v === null || (Array.isArray(v) && v.length === 0)) continue;
      const allowed = visibleOptions(q, next, questionsByDim);
      const allowSet = new Set(allowed.map((o) => o.value));
      if (Array.isArray(v)) {
        const filtered = v.filter((x) => allowSet.has(x));
        if (filtered.length !== v.length) {
          next[q.id] = filtered;
          changed = true;
        }
      } else if (typeof v === 'string' && allowSet.size > 0 && !allowSet.has(v)) {
        delete next[q.id];
        changed = true;
      }
    }
    if (changed) setAnswers(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(answers), questions]);

  const canSubmit = useMemo(() => {
    for (const q of visibleQuestions) {
      if (!q.required) continue;
      const v = answers[q.id];
      if (v === undefined || v === null) return false;
      if (Array.isArray(v) && v.length === 0) return false;
      if (typeof v === 'string' && !v.trim()) return false;
    }
    return visibleQuestions.length > 0;
  }, [visibleQuestions, answers]);

  const doSubmit = useCallback(async () => {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    try {
      const items: QnSubmitAnswerItem[] = visibleQuestions
        .filter((q) => {
          const v = answers[q.id];
          return v !== undefined && v !== null && !(Array.isArray(v) && v.length === 0);
        })
        .map((q) => ({ question_id: q.id, value: answers[q.id] }));
      await onSubmit(items);
    } finally {
      setSubmitting(false);
    }
  }, [answers, visibleQuestions, canSubmit, submitting, onSubmit]);

  if (!open || !template) return null;

  // 公共抽屉壳
  const drawerStyle: React.CSSProperties = {
    position: 'fixed',
    left: 0,
    right: 0,
    bottom: 0,
    background: '#fff',
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    boxShadow: '0 -6px 30px rgba(0,0,0,0.18)',
    maxHeight: '82vh',
    display: 'flex',
    flexDirection: 'column',
    zIndex: 1000,
    animation: 'qn-drawer-slide-up .22s ease-out',
  };
  const maskStyle: React.CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.32)',
    zIndex: 999,
  };

  const renderHeader = () => (
    <div
      style={{
        padding: '14px 16px 8px',
        borderBottom: '1px solid #F0F0F0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <div>
        <div style={{ fontSize: 16, fontWeight: 600, color: '#111' }}>
          {template.name}
        </div>
        {template.intro_text && (
          <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
            {template.intro_text}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="关闭"
        style={{
          width: 30,
          height: 30,
          border: 'none',
          borderRadius: 15,
          background: '#F5F5F5',
          fontSize: 16,
          cursor: 'pointer',
        }}
      >
        ×
      </button>
    </div>
  );

  if (displayForm === 'DRAWER_STEPPED') {
    const safeIdx = Math.min(stepIdx, Math.max(0, visibleQuestions.length - 1));
    const q = visibleQuestions[safeIdx];
    const opts = q ? visibleOptions(q, answers, questionsByDim) : [];
    const isLast = safeIdx === visibleQuestions.length - 1;
    // [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 单选题选中后自动跳下一题
    //   - 多选题/文本题：保留「下一步」按钮（混合模式）
    //   - 最后一题：不自动提交，停留显示「提交」按钮
    const handleSteppedChange = (v: any) => {
      if (!q) return;
      setAnswers((p) => ({ ...p, [q.id]: v }));
      if (autoNextEnabled && q.question_type === 'single_choice' && !isLast) {
        // [PRD-HSC-OPTIM-V3 2026-05-21] 排查日志，便于线上确认自动跳题是否触发
        if (typeof console !== 'undefined') {
          // eslint-disable-next-line no-console
          console.debug('[qn-drawer] autoNext fired', { idx: safeIdx, q_id: q.id });
        }
        // 用 setTimeout 触发下一帧，让 UI 先体现"选中态"再翻页
        setTimeout(() => {
          setStepIdx((i) => Math.min(i + 1, visibleQuestions.length - 1));
        }, 0);
      }
    };
    return (
      <>
        <div style={maskStyle} onClick={onClose} data-testid="qn-drawer-mask" />
        <div style={drawerStyle} data-testid="qn-drawer-stepped">
          {renderHeader()}
          <div style={{ padding: 16, flex: 1, overflowY: 'auto' }}>
            {q ? (
              <>
                <div style={{ fontSize: 14, color: '#999', marginBottom: 4 }}>
                  第 {safeIdx + 1} / {visibleQuestions.length} 题
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
                  {q.title}
                  {q.required ? <span style={{ color: '#E74C3C' }}> *</span> : null}
                </div>
                {q.subtitle && (
                  <div style={{ fontSize: 12, color: '#888', marginBottom: 10 }}>
                    {q.subtitle}
                  </div>
                )}
                <QuestionRenderer
                  q={q}
                  options={opts}
                  value={answers[q.id]}
                  onChange={handleSteppedChange}
                />
              </>
            ) : (
              <div style={{ color: '#999' }}>暂无可见题目</div>
            )}
          </div>
          <div
            style={{
              padding: 12,
              borderTop: '1px solid #F0F0F0',
              display: 'flex',
              gap: 8,
            }}
          >
            <button
              type="button"
              disabled={safeIdx === 0 || !template.allow_back}
              onClick={() => setStepIdx((i) => Math.max(0, i - 1))}
              style={{
                flex: 1,
                background: '#F5F5F5',
                border: 'none',
                borderRadius: 22,
                padding: 12,
                fontSize: 14,
                color: '#666',
                cursor: 'pointer',
              }}
            >
              上一题
            </button>
            <button
              type="button"
              disabled={!q || (q.required && !canAnswerForQuestion(q, answers))}
              onClick={() => {
                if (isLast) doSubmit();
                else setStepIdx((i) => i + 1);
              }}
              data-testid="qn-stepped-next-btn"
              style={{
                flex: 2,
                background: '#2BB6A8',
                border: 'none',
                borderRadius: 22,
                padding: 12,
                fontSize: 14,
                color: '#fff',
                cursor: 'pointer',
                opacity: !q || (q.required && !canAnswerForQuestion(q, answers)) ? 0.5 : 1,
              }}
            >
              {isLast ? (submitting ? '提交中…' : '提交') : '下一题'}
            </button>
          </div>
        </div>
      </>
    );
  }

  // 默认 DRAWER_SCROLL
  // [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 分页模式：questionsPerPage > 0 且 < 题目数时启用分页
  const qpp = Math.max(1, Math.min(999, questionsPerPage || 999));
  const totalPages = Math.max(1, Math.ceil(visibleQuestions.length / qpp));
  const safePage = Math.min(pageIdx, totalPages - 1);
  const pageQuestions =
    qpp >= visibleQuestions.length
      ? visibleQuestions
      : visibleQuestions.slice(safePage * qpp, (safePage + 1) * qpp);
  const isLastPage = safePage >= totalPages - 1;
  // 当前页题目是否全部已答（必填校验）
  const currentPageFilled = pageQuestions.every((q) => {
    if (!q.required) return true;
    const v = answers[q.id];
    if (v === undefined || v === null) return false;
    if (Array.isArray(v) && v.length === 0) return false;
    if (typeof v === 'string' && !v.trim()) return false;
    return true;
  });
  return (
    <>
      <div style={maskStyle} onClick={onClose} data-testid="qn-drawer-mask" />
      <div style={drawerStyle} data-testid="qn-drawer-scroll">
        {renderHeader()}
        <div style={{ padding: 16, flex: 1, overflowY: 'auto' }}>
          {totalPages > 1 && (
            <div
              style={{ fontSize: 12, color: '#999', marginBottom: 8 }}
              data-testid="qn-scroll-page-info"
            >
              第 {safePage + 1} / {totalPages} 页（共 {visibleQuestions.length} 题）
            </div>
          )}
          {pageQuestions.map((q, idx) => {
            const opts = visibleOptions(q, answers, questionsByDim);
            const globalIdx = safePage * qpp + idx;
            return (
              <div key={q.id} style={{ marginBottom: 18 }}>
                <div style={{ fontSize: 14, color: '#999', marginBottom: 4 }}>
                  Q{globalIdx + 1}
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
                  {q.title}
                  {q.required ? <span style={{ color: '#E74C3C' }}> *</span> : null}
                </div>
                {q.subtitle && (
                  <div style={{ fontSize: 12, color: '#888', marginBottom: 10 }}>
                    {q.subtitle}
                  </div>
                )}
                <QuestionRenderer
                  q={q}
                  options={opts}
                  value={answers[q.id]}
                  onChange={(v) => setAnswers((p) => ({ ...p, [q.id]: v }))}
                />
              </div>
            );
          })}
        </div>
        <div style={{ padding: 12, borderTop: '1px solid #F0F0F0', display: 'flex', gap: 8 }}>
          {totalPages > 1 && safePage > 0 && (
            <button
              type="button"
              onClick={() => setPageIdx((i) => Math.max(0, i - 1))}
              data-testid="qn-scroll-prev-page-btn"
              style={{
                flex: 1,
                background: '#F5F5F5',
                border: 'none',
                borderRadius: 22,
                padding: 12,
                fontSize: 14,
                color: '#666',
                cursor: 'pointer',
              }}
            >
              上一页
            </button>
          )}
          {!isLastPage ? (
            <button
              type="button"
              disabled={!currentPageFilled}
              onClick={() => setPageIdx((i) => Math.min(totalPages - 1, i + 1))}
              data-testid="qn-scroll-next-page-btn"
              style={{
                flex: 2,
                background: currentPageFilled ? '#2BB6A8' : '#CFCFCF',
                border: 'none',
                borderRadius: 22,
                padding: 12,
                fontSize: 15,
                color: '#fff',
                cursor: currentPageFilled ? 'pointer' : 'not-allowed',
              }}
            >
              下一页
            </button>
          ) : (
            <button
              type="button"
              disabled={!canSubmit || submitting}
              onClick={doSubmit}
              data-testid="qn-scroll-submit-btn"
              style={{
                flex: 2,
                background: canSubmit ? '#2BB6A8' : '#CFCFCF',
                border: 'none',
                borderRadius: 22,
                padding: 12,
                fontSize: 15,
                color: '#fff',
                cursor: canSubmit ? 'pointer' : 'not-allowed',
              }}
            >
              {submitting ? '提交中…' : '提交'}
            </button>
          )}
        </div>
      </div>
      <style jsx>{`
        @keyframes qn-drawer-slide-up {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
    </>
  );
}

function canAnswerForQuestion(q: QnQuestion, answers: Record<number, any>): boolean {
  const v = answers[q.id];
  if (v === undefined || v === null) return false;
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'string') return v.trim().length > 0;
  return true;
}

'use client';

/**
 * [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2] 识药结果卡片 V4
 *
 * 相对 V3 的改动（依据本次 PRD）：
 * - 内容结构改为 4 大模块（自上而下）：
 *   ① 药品基础信息（A）：通用名 / 商品名 / 规格 / 剂型 / 厂家 / 批准文号
 *   ② 用法用量（B）：成人 / 儿童 用法用量、服药时机
 *   ③ 安全提示（C）：禁忌 / 不良反应 / 相互作用 / 特殊人群
 *   ④ 个性化风险提示（D）：风险等级标签 + 一句话结论 + 详细原因
 * - 操作按钮区固定在卡片最底部，内容超长时内容可滚动，按钮不被挤出
 * - 主按钮"加入用药计划"在 added=true 时变灰显示「已加入用药计划」，不可重复点击
 * - 历史 V3 的"识别成功徽章 / 红色横幅"逻辑保留兼容（向后兼容）
 *
 * 合规口径（沿用 V3）：
 * - 按字段是否有值动态渲染，未识别字段整行不渲染
 * - 严禁"未在权威库"等技术词
 * - 未命中库时不渲染"用药提醒"高风险红框（避免编造禁忌）
 */
import React from 'react';
import MedicationCardButtons from './MedicationCardButtons';

export type DrugCardFields = {
  library_id?: number | null;
  drug_name?: string | null;
  generic_name?: string | null;
  brand_name?: string | null;
  spec?: string | null;
  dosage_form?: string | null;
  manufacturer?: string | null;
  approval_no?: string | null;
  category?: string | null;
  rx_type?: string | null;
  disease_tags?: string[] | null;
  indications?: string | null;
  // 用法用量
  usage?: string | null;
  usage_adult?: string | null;
  usage_children?: string | null;
  timing?: string | null;
  // 安全提示
  contraindications?: string | null;
  adverse_reactions?: string | null;
  interactions?: string | null;
  special_population?: string | null;
};

export type ConflictInfo = {
  type: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  block_add: boolean;
  matched_key?: string;
};

/** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] 个性化风险结论（来自 engine.meta.personalized_risk） */
export type PersonalizedRisk = {
  level: 'safe' | 'caution' | 'danger';
  label: string; // 例如 "⚠️ 不建议服用"
  conclusion: string;
  reasons?: string[];
};

export interface DrugIdentifyCardProps {
  card: DrugCardFields;
  libraryMatched: boolean;
  conflicts?: ConflictInfo[];
  /** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2] 个性化风险结论 */
  personalizedRisk?: PersonalizedRisk | null;
  /** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2] 当前选中咨询人姓名 */
  memberName?: string | null;
  /** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-3] 是否已加入用药计划 */
  added?: boolean;
  onAddPlan?: () => void;
  onViewDetail?: () => void;
  onRetake?: () => void;
  onViewAllPlans?: () => void;
  /** [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F9/F10/F11 2026-05-18]
   * 用药提醒按钮：点击事件 + 红点 + 置灰态
   * - onReminder：点击「用药提醒」按钮的回调（弹出与顶部铃铛 100% 等价的打卡抽屉）
   * - reminderRedDot：右上角是否显示红点（按咨询人维度）
   * - reminderDisabled：咨询人无任何用药计划时按钮置灰
   */
  onReminder?: () => void;
  reminderRedDot?: boolean;
  reminderDisabled?: boolean;
  /** [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] 识药结果（是否失败） —— 用于「加入用药计划」按钮置灰判定 */
  recognitionFailed?: boolean;
  /** [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] 当前咨询人今天是否有用药计划 */
  hasTodayMedication?: boolean;
  /** [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] 今日用药数据是否仍在加载（防止红点闪烁） */
  loadingTodayMedication?: boolean;
  /** [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F1~F4 2026-05-18]
   * 分阶段流式可见性：在卡片"基础信息卡 / 用法用量卡 / 安全提示卡 / 个性化风险卡"上做整卡淡入。
   * 未传入时默认全部可见（向后兼容）。
   */
  visibleSections?: {
    basic?: boolean;
    usage?: boolean;
    safety?: boolean;
    risk?: boolean;
  };
  /** 标记某区块加载失败（前端按 8s 超时判定），失败的区块改为"加载失败"占位卡 + 重试按钮 */
  failedSections?: {
    basic?: boolean;
    usage?: boolean;
    safety?: boolean;
    risk?: boolean;
  };
  /** 整次识药重试（点击失败占位卡的「点击重试」按钮触发） */
  onRetryAll?: () => void;
}

const row = (label: string, value: any) => {
  if (value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) {
    return null;
  }
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 6, lineHeight: 1.7 }}>
      <span style={{ color: '#888', fontSize: 16, minWidth: 64, flexShrink: 0 }}>{label}</span>
      <span style={{ color: '#333', fontSize: 16, wordBreak: 'break-word' }}>
        {Array.isArray(value) ? value.join('、') : String(value)}
      </span>
    </div>
  );
};

const riskColor = (level: PersonalizedRisk['level']) => {
  if (level === 'danger') return { bg: '#FEF2F2', border: '#FCA5A5', text: '#B91C1C', tag: '#DC2626' };
  if (level === 'caution') return { bg: '#FFFBEB', border: '#FCD34D', text: '#92400E', tag: '#D97706' };
  return { bg: '#F0FDF4', border: '#86EFAC', text: '#166534', tag: '#16A34A' };
};

export default function DrugIdentifyCard(props: DrugIdentifyCardProps) {
  const {
    card,
    libraryMatched,
    conflicts = [],
    personalizedRisk,
    memberName,
    added = false,
    onAddPlan,
    onViewDetail,
    onRetake,
    onViewAllPlans,
    onReminder,
    recognitionFailed = false,
    hasTodayMedication = false,
    loadingTodayMedication = false,
    visibleSections,
    failedSections,
    onRetryAll,
  } = props;

  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F1~F3]
  // 默认全部可见（向后兼容），传入 visibleSections 时按其控制
  const showBasic = visibleSections?.basic !== false;
  const showUsage = visibleSections?.usage !== false;
  const showSafety = visibleSections?.safety !== false;
  const showRisk = visibleSections?.risk !== false;

  const failBasic = !!failedSections?.basic;
  const failUsage = !!failedSections?.usage;
  const failSafety = !!failedSections?.safety;
  const failRisk = !!failedSections?.risk;

  const blockAdd = conflicts.some((c) => c.block_add) || personalizedRisk?.level === 'danger';
  const highConflict = conflicts.find((c) => c.severity === 'high');

  return (
    <div
      data-testid="drug-identify-card"
      style={{
        background: '#fff',
        borderRadius: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        margin: '8px 0',
        maxWidth: 520,
        display: 'flex',
        flexDirection: 'column',
        // [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2] 卡片整体最高 70vh，
        // 内容区可滚，按钮区固定在卡片最底部，永远不被挤出
        maxHeight: '70vh',
      }}
    >
      {/* —— 内容滚动区 —— */}
      <div
        data-testid="drug-card-scroll"
        style={{
          overflowY: 'auto',
          padding: '16px 16px 0 16px',
          flex: '1 1 auto',
          minHeight: 0,
        }}
      >
        {/* 顶部识别成功徽章 */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <span
            style={{
              background: '#52C41A',
              color: '#fff',
              fontSize: 14,
              padding: '4px 10px',
              borderRadius: 999,
              fontWeight: 600,
            }}
          >
            ✓ 识别成功
          </span>
          {memberName ? (
            <span style={{ marginLeft: 8, fontSize: 13, color: '#666' }}>
              · 已结合「{memberName}」档案
            </span>
          ) : null}
        </div>

        {/* 高危冲突横幅（V3 兼容） */}
        {highConflict && (
          <div
            style={{
              background: '#DC2626',
              color: '#fff',
              padding: '10px 12px',
              borderRadius: 8,
              fontSize: 16,
              fontWeight: 600,
              marginBottom: 12,
              lineHeight: 1.7,
            }}
            data-testid="conflict-banner"
          >
            ⚠ {highConflict.title}
          </div>
        )}

        {/* 药品名 */}
        {card.drug_name && (
          <div style={{ fontSize: 22, fontWeight: 700, color: '#111', marginBottom: 10, lineHeight: 1.5 }}>
            {card.drug_name}
          </div>
        )}

        {/* ① 药品基础信息（整卡淡入；失败时占位） */}
        {failBasic ? (
          <FailedSectionPlaceholder title="① 药品基础信息" onRetry={onRetryAll} testid="drug-card-section-basic-failed" />
        ) : showBasic ? (
          <div
            data-testid="drug-card-section-basic"
            className="aihome-drug-section-fadein"
            style={{ marginTop: 4, marginBottom: 12 }}
          >
            <div style={{ fontSize: 14, color: '#1677FF', fontWeight: 600, marginBottom: 6 }}>① 药品基础信息</div>
            {row('通用名', card.generic_name)}
            {row('商品名', card.brand_name)}
            {row('规格', card.spec)}
            {row('剂型', card.dosage_form)}
            {row('厂家', card.manufacturer)}
            {row('批准文号', card.approval_no)}
            {row('分类', card.category)}
            {row('类型', card.rx_type)}
          </div>
        ) : null}

        {/* ② 用法用量 —— 仅在命中库或字段有值时渲染（合规） */}
        {failUsage ? (
          <FailedSectionPlaceholder title="② 用法用量" onRetry={onRetryAll} testid="drug-card-section-usage-failed" />
        ) : showUsage && libraryMatched && (card.usage || card.usage_adult || card.usage_children || card.timing) ? (
          <div
            data-testid="drug-card-section-usage"
            className="aihome-drug-section-fadein"
            style={{ padding: 12, background: '#F0F9FF', borderRadius: 8, marginBottom: 12 }}
          >
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: '#0369A1' }}>
              ② 用法用量
            </div>
            {row('成人用法', card.usage_adult || card.usage)}
            {row('儿童用法', card.usage_children)}
            {row('服药时机', card.timing)}
          </div>
        ) : null}

        {/* ③ 安全提示 —— 仅在命中库时才渲染（避免编造禁忌） */}
        {failSafety ? (
          <FailedSectionPlaceholder title="③ 安全提示" onRetry={onRetryAll} testid="drug-card-section-safety-failed" />
        ) : showSafety && libraryMatched && (card.contraindications || card.adverse_reactions || card.interactions || card.special_population) ? (
          <div
            data-testid="drug-card-section-safety"
            className="aihome-drug-section-fadein"
            style={{
              padding: 12,
              background: '#FEF2F2',
              borderRadius: 8,
              border: '1px solid #FCA5A5',
              marginBottom: 12,
            }}
          >
            <div
              style={{
                display: 'inline-block',
                background: '#DC2626',
                color: '#fff',
                fontSize: 14,
                padding: '2px 8px',
                borderRadius: 4,
                marginBottom: 6,
                fontWeight: 600,
              }}
            >
              ③ 安全提示
            </div>
            {row('禁忌人群', card.contraindications)}
            {row('不良反应', card.adverse_reactions)}
            {row('相互作用', card.interactions)}
            {row('特殊人群', card.special_population)}
          </div>
        ) : null}

        {/* ④ 个性化风险提示（基于当前选中成员档案） */}
        {failRisk ? (
          <FailedSectionPlaceholder title="④ 个性化风险" onRetry={onRetryAll} testid="drug-card-section-risk-failed" />
        ) : showRisk && personalizedRisk ? (
          <div
            data-testid="drug-card-section-personalized"
            className="aihome-drug-section-fadein"
            style={{
              padding: 12,
              background: riskColor(personalizedRisk.level).bg,
              borderRadius: 8,
              border: `1px solid ${riskColor(personalizedRisk.level).border}`,
              marginBottom: 16,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span
                style={{
                  background: riskColor(personalizedRisk.level).tag,
                  color: '#fff',
                  fontSize: 13,
                  padding: '2px 8px',
                  borderRadius: 999,
                  fontWeight: 600,
                }}
              >
                {personalizedRisk.label}
              </span>
              <span style={{ fontSize: 13, color: '#666' }}>④ 个性化风险提示</span>
            </div>
            <div style={{ fontSize: 16, color: riskColor(personalizedRisk.level).text, fontWeight: 600, lineHeight: 1.7 }}>
              {personalizedRisk.conclusion}
            </div>
            {personalizedRisk.reasons && personalizedRisk.reasons.length > 0 && (
              <ul style={{ margin: '6px 0 0 0', paddingLeft: 18, fontSize: 14, color: '#555', lineHeight: 1.7 }}>
                {personalizedRisk.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        ) : null}

        {/* 卡片整卡淡入动画 keyframes（200~300ms） */}
        <style>{`
          @keyframes aihomeDrugSectionFadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
          }
          .aihome-drug-section-fadein {
            animation: aihomeDrugSectionFadeIn 260ms ease-out;
          }
        `}</style>
      </div>

      {/* —— ⑤ 操作按钮区（固定底部，2x2 胶囊布局） ——
       * [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19]
       *   上行：[💊 加入用药计划] [📅 查看用药计划]
       *   下行：[⏰ 今日用药]      [📸 重新拍照]
       *   - 胶囊样式 + emoji；红点仅「今日用药」
       *   - 置灰：识药失败→加入计划灰；今天无计划→今日用药灰
       */}
      <div
        data-testid="drug-card-actions"
        style={{
          padding: 12,
          borderTop: '1px solid #F0F0F0',
          background: '#fff',
          borderBottomLeftRadius: 12,
          borderBottomRightRadius: 12,
          flexShrink: 0,
        }}
      >
        <MedicationCardButtons
          recognitionFailed={recognitionFailed || blockAdd}
          hasTodayMedication={hasTodayMedication}
          loadingTodayMedication={loadingTodayMedication}
          alreadyJoined={added}
          onJoin={() => {
            if (onAddPlan) onAddPlan();
          }}
          onView={() => {
            if (onViewDetail) onViewDetail();
          }}
          onToday={() => {
            if (onReminder) onReminder();
          }}
          onRetake={() => {
            if (onRetake) onRetake();
          }}
        />
      </div>
    </div>
  );
}

/** [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F5] 单区块加载失败占位卡 + 整次重试 */
function FailedSectionPlaceholder(props: { title: string; onRetry?: () => void; testid?: string }) {
  const { title, onRetry, testid } = props;
  return (
    <div
      data-testid={testid}
      style={{
        padding: '14px 12px',
        background: '#FFF7ED',
        borderRadius: 8,
        border: '1px dashed #FDBA74',
        marginBottom: 12,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#9A3412' }}>
        <span style={{ fontSize: 16 }}>⚠</span>
        <span style={{ fontSize: 13 }}>{title}：该部分内容加载失败</span>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          style={{
            padding: '4px 12px',
            borderRadius: 6,
            border: '1px solid #FB923C',
            background: '#fff',
            color: '#EA580C',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          点击重试
        </button>
      )}
    </div>
  );
}

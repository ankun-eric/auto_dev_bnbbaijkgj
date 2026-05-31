'use client';

/**
 * [PRD-INVITE-FAMILY-CARD-V1 2026-05-30] 邀请家人入口卡片
 * [PRD-INVITE-FAMILY-CARD-V1.1 2026-05-30] 位置调整补丁：双点投放 + 主标题单行 + 健康档案位
 *
 * 来源 PRD：
 *   - v1.0《邀请家人入口卡片优化 PRD》（会员中心位）
 *   - v1.1《邀请家人入口卡片 · v1.1 位置调整补丁 PRD（FINAL）》（健康档案位）
 *
 * 设计：在会员中心页 + 健康档案-档案管理列表页两处放置同一张视觉强化的渐变大卡片，
 * 让用户在一张卡片上完成「看懂套餐 → 看清额度 → 点击邀请/新建档案」闭环。
 *
 * 数据来源（零新增后端字段）：
 * - planName : 来自 /api/member/center -> current.plan_name
 * - quotaMax : 来自 /api/family/member/quota -> quota_max（v1.1 已切换为含本人）
 * - quotaUsed: 来自 /api/family/member/quota -> quota_used（v1.1 含本人，包含本人卡）
 *
 * 状态：
 * - S1 正常态：quotaUsed < quotaMax 且非不限档
 * - S2 达上限态：quotaUsed >= quotaMax 且为有限档（quotaMax !== -1 && quotaMax < 9999）
 * - 不限档（quotaMax === -1 或 quotaMax >= 9999）永远展示为 S1
 *
 * 双位置差异（v1.1 §2.3）：
 * - 视觉完全一致（同一套组件 + 同一份样式）
 * - 仅主按钮下游动作不同：cardLocation='member_center' → 邀请流程（onInvite）；
 *   cardLocation='profile_list_top' → 拉起"新增家人档案"抽屉（onInvite 注入新建抽屉触发函数）
 * - 埋点字段 card_location + target_action 由 props 注入，区分两处曝光与点击
 */
import { useEffect, useRef, useState } from 'react';

// ─── 视觉规范（PRD §3.2）───
export const INVITE_CARD_GRADIENT = 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)';
export const INVITE_CARD_PRIMARY = '#0284C7';
export const INVITE_CARD_SHADOW = '0 6px 16px rgba(14, 165, 233, 0.18)';
export const INVITE_CARD_WARN_YELLOW = '#FBBF24';

// ─── 纯函数：状态判定（导出供测试用）───

export type InviteCardState = 'normal' | 'full';

/** 判断是否不限档 */
export function isUnlimitedQuota(quotaMax: number | null | undefined): boolean {
  if (quotaMax === null || quotaMax === undefined) return false;
  return quotaMax === -1 || quotaMax >= 9999;
}

/** 判断是否达上限态（仅有限档生效） */
export function isFullState(
  quotaUsed: number | null | undefined,
  quotaMax: number | null | undefined,
): boolean {
  if (isUnlimitedQuota(quotaMax)) return false;
  if (quotaUsed === null || quotaUsed === undefined) return false;
  if (quotaMax === null || quotaMax === undefined) return false;
  return quotaUsed >= quotaMax;
}

/** 计算卡片状态 */
export function computeCardState(
  quotaUsed: number | null | undefined,
  quotaMax: number | null | undefined,
): InviteCardState {
  return isFullState(quotaUsed, quotaMax) ? 'full' : 'normal';
}

/** 渲染权益短语
 *
 * [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #3]
 * 历史："不限家人数" / "可管理 N 位家人"
 * 现状：主标题（会员级别行）在档案列表/会员中心两处均会被容器宽度截断（如"普通会员 · 可管理 10..."），
 *       且"可管理 X 人"已在顶部卡片"已管理 X/Y"中清晰呈现，重复信息。
 * 修复：直接返回空串，从而让 formatTitleLine 仅展示套餐名（"普通会员"），杜绝截断与冗余。
 * 兼容：保留函数与导出签名不变，便于既有测试 / 业务代码无感升级。
 */
export function formatBenefitPhrase(_quotaMax: number | null | undefined): string {
  return '';
}

/** 渲染套餐名+权益短语主标题
 *
 * [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #3]
 * 当权益短语为空（默认情况）时，主标题仅显示套餐名，不再拼接" · 可管理 N 位家人"。
 */
export function formatTitleLine(planName: string | null | undefined, quotaMax: number | null | undefined): string {
  const name = (planName && planName.trim()) || '会员套餐';
  const phrase = formatBenefitPhrase(quotaMax);
  return phrase ? `${name} · ${phrase}` : name;
}

/** 渲染用量行 */
export function formatQuotaLine(
  quotaUsed: number | null | undefined,
  quotaMax: number | null | undefined,
): string {
  if (isUnlimitedQuota(quotaMax)) {
    const used = (typeof quotaUsed === 'number' && quotaUsed >= 0) ? quotaUsed : 0;
    return `已管理 ${used} 人 · 不限上限`;
  }
  if (quotaMax === null || quotaMax === undefined) {
    return '';
  }
  const used = (typeof quotaUsed === 'number' && quotaUsed >= 0) ? quotaUsed : 0;
  return `已管理 ${used} / 上限 ${quotaMax}`;
}

// ─── 埋点（沿用 navigator.sendBeacon，与项目其他卡片保持一致）───

function reportEvent(eventName: string, payload: Record<string, any>) {
  try {
    const body = JSON.stringify({
      event: eventName,
      ts: Date.now(),
      page: typeof window !== 'undefined' ? window.location.pathname : '',
      ...payload,
    });
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon('/api/_frontend_log', blob);
    }
  } catch {
    /* ignore */
  }
}

// ─── 组件 props ───

/**
 * [PRD-INVITE-FAMILY-CARD-V1.1 §2 §6] 卡片承载位置
 * - 'member_center'：会员中心位（v1.0），主按钮 → 邀请流程页
 * - 'profile_list_top'：健康档案-档案管理列表页顶部（v1.1 新增），主按钮 → 新增家人档案抽屉
 */
export type InviteCardLocation = 'member_center' | 'profile_list_top';

/**
 * [PRD-INVITE-FAMILY-CARD-V1.1 §6.2] 主按钮下游动作埋点取值
 * - 'invite_flow'：跳邀请流程页（会员中心位默认）
 * - 'create_profile'：拉起新增家人档案抽屉（健康档案位默认）
 */
export type InviteCardTargetAction = 'invite_flow' | 'create_profile';

export interface InviteFamilyCardProps {
  /** 套餐名（来自 /api/member/center -> current.plan_name） */
  planName: string | null | undefined;
  /** 上限 Y（含本人，来自 /api/family/member/quota -> quota_max；-1 / >=9999 视为不限） */
  quotaMax: number | null | undefined;
  /** 已管理 X（含本人，来自 /api/family/member/quota -> quota_used） */
  quotaUsed: number | null | undefined;
  /** 点击主按钮"邀请家人"时回调（沿用既有邀请流程 / 或拉起新增家人档案抽屉） */
  onInvite: () => void;
  /** 点击"升级套餐"链接时回调（跳转既有套餐购买页） */
  onUpgrade: () => void;
  /**
   * [PRD-INVITE-FAMILY-CARD-V1.1 §6.1] 卡片位置标识（埋点 card_location）
   * 默认 'member_center'（兼容 v1.0 调用方）
   */
  cardLocation?: InviteCardLocation;
  /**
   * [PRD-INVITE-FAMILY-CARD-V1.1 §6.1] 主按钮下游动作标识（埋点 target_action）
   * 默认根据 cardLocation 推断：member_center → invite_flow；profile_list_top → create_profile
   */
  targetAction?: InviteCardTargetAction;
  /** 调试 / 测试用 */
  className?: string;
}

// ─── 家人手拉手剪影 SVG（半透明白色矢量，32×32 PRD §3.2.4）───

function FamilyHandsIcon() {
  return (
    <svg
      width={32}
      height={32}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      style={{ flexShrink: 0, opacity: 0.9 }}
      data-testid="invite-card-icon"
    >
      <g fill="rgba(255,255,255,0.95)">
        {/* 大人头 */}
        <circle cx="8" cy="9" r="3" />
        {/* 小孩头 */}
        <circle cx="16" cy="11" r="2.4" />
        {/* 另一个家人 */}
        <circle cx="24" cy="9" r="3" />
        {/* 身体 + 牵手轮廓（圆角矩形拼接） */}
        <path d="M3.5 22c0-2.5 2-4.5 4.5-4.5s4.5 2 4.5 4.5v3.5h-9V22z" />
        <path d="M12.6 23c0-1.9 1.5-3.4 3.4-3.4s3.4 1.5 3.4 3.4v2.5h-6.8V23z" />
        <path d="M19.5 22c0-2.5 2-4.5 4.5-4.5s4.5 2 4.5 4.5v3.5h-9V22z" />
      </g>
    </svg>
  );
}

// ─── 组件主体 ───

export default function InviteFamilyCard(props: InviteFamilyCardProps) {
  const {
    planName,
    quotaMax,
    quotaUsed,
    onInvite,
    onUpgrade,
    className,
    cardLocation = 'member_center',
    targetAction,
  } = props;
  const state = computeCardState(quotaUsed, quotaMax);
  const isFull = state === 'full';
  const cardRef = useRef<HTMLDivElement | null>(null);
  const exposed = useRef(false);

  // [PRD-INVITE-FAMILY-CARD-V1.1 §6.3] target_action 默认值由 cardLocation 推断
  const effectiveTargetAction: InviteCardTargetAction =
    targetAction ?? (cardLocation === 'profile_list_top' ? 'create_profile' : 'invite_flow');

  // [PRD-INVITE-FAMILY-CARD-V1.1 §4.1] 主标题单行响应式字号
  // 主流屏（>=390px）→ 16pt；窄屏（<=375px）→ 15pt 兜底；保持 white-space:nowrap + ellipsis
  const [titleFontSize, setTitleFontSize] = useState<number>(16);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const compute = () => {
      const w = window.innerWidth || 390;
      setTitleFontSize(w <= 375 ? 15 : 16);
    };
    compute();
    window.addEventListener('resize', compute);
    return () => window.removeEventListener('resize', compute);
  }, []);

  // 曝光埋点（首次进入视口）
  useEffect(() => {
    const fireExposure = () => {
      reportEvent('invite_card_exposure', {
        card_location: cardLocation,
        plan_name: planName || '',
        quota_used: quotaUsed ?? null,
        quota_max: quotaMax ?? null,
        is_full: isFull,
      });
      if (isFull) {
        reportEvent('invite_card_full_state_view', {
          card_location: cardLocation,
          plan_name: planName || '',
          quota_max: quotaMax ?? null,
        });
      }
    };
    if (!cardRef.current || typeof IntersectionObserver === 'undefined') {
      // 兜底：直接上报曝光
      if (!exposed.current) {
        exposed.current = true;
        fireExposure();
      }
      return;
    }
    const node = cardRef.current;
    const ob = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting && !exposed.current) {
            exposed.current = true;
            fireExposure();
          }
        }
      },
      { threshold: 0.3 },
    );
    ob.observe(node);
    return () => ob.disconnect();
  }, [planName, quotaUsed, quotaMax, isFull, cardLocation]);

  const handleMainBtn = () => {
    if (isFull) return; // 禁用态：沉默无反应（PRD v1.0 §2.3 F2 / v1.1 §3.2 BR-14）
    reportEvent('invite_card_main_btn_click', {
      card_location: cardLocation,
      target_action: effectiveTargetAction,
      plan_name: planName || '',
      quota_used: quotaUsed ?? null,
      quota_max: quotaMax ?? null,
    });
    onInvite();
  };

  const handleUpgradeLink = (e: React.MouseEvent) => {
    e.stopPropagation();
    reportEvent('invite_card_upgrade_link_click', {
      card_location: cardLocation,
      plan_name: planName || '',
      quota_used: quotaUsed ?? null,
      quota_max: quotaMax ?? null,
    });
    onUpgrade();
  };

  return (
    <div
      ref={cardRef}
      data-testid="invite-family-card"
      data-card-location={cardLocation}
      data-state={state}
      className={className}
      style={{
        margin: '12px 16px 0',
        background: INVITE_CARD_GRADIENT,
        borderRadius: 14,
        padding: '16px',
        boxShadow: INVITE_CARD_SHADOW,
        color: '#fff',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <FamilyHandsIcon />
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* [PRD-INVITE-FAMILY-CARD-V1.1 §4.1] 主标题：套餐名 + 权益短语，强制单行 */}
          <div
            data-testid="invite-card-title"
            data-font-size={titleFontSize}
            title={formatTitleLine(planName, quotaMax)}
            style={{
              fontSize: titleFontSize,
              fontWeight: 600,
              color: '#fff',
              lineHeight: '22px',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {formatTitleLine(planName, quotaMax)}
          </div>

          {/* 用量行 */}
          <div
            data-testid="invite-card-quota"
            style={{
              fontSize: 14,
              color: 'rgba(255,255,255,0.85)',
              marginTop: 4,
              lineHeight: '20px',
            }}
          >
            {formatQuotaLine(quotaUsed, quotaMax)}
          </div>

          {/* 警示行（仅达上限态） */}
          {isFull && (
            <div
              data-testid="invite-card-warn"
              style={{
                fontSize: 13,
                color: 'rgba(255,236,179,0.95)',
                marginTop: 6,
                lineHeight: '20px',
                fontWeight: 500,
              }}
            >
              <span aria-hidden style={{ color: INVITE_CARD_WARN_YELLOW, marginRight: 4 }}>⚠</span>
              已达上限，请
              <span
                role="button"
                tabIndex={0}
                data-testid="invite-card-upgrade-link"
                onClick={handleUpgradeLink}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleUpgradeLink(e as any); }}
                style={{
                  color: '#fff',
                  textDecoration: 'underline',
                  marginLeft: 2,
                  cursor: 'pointer',
                }}
              >升级套餐</span>
            </div>
          )}

          {/* 辅助说明位 */}
          <div
            data-testid="invite-card-subtitle"
            style={{
              fontSize: 12,
              color: 'rgba(255,255,255,0.65)',
              marginTop: 8,
              lineHeight: '16px',
            }}
          >
            邀请家庭成员，共享健康守护
          </div>
        </div>

        {/* 邀请大按钮 */}
        <button
          type="button"
          data-testid="invite-card-main-btn"
          disabled={isFull}
          onClick={handleMainBtn}
          aria-disabled={isFull}
          style={{
            alignSelf: 'flex-end',
            minWidth: 96,
            height: 40,
            padding: '0 18px',
            borderRadius: 20,
            border: 'none',
            background: isFull ? 'rgba(255,255,255,0.5)' : '#fff',
            color: isFull ? 'rgba(2,132,199,0.5)' : INVITE_CARD_PRIMARY,
            fontSize: 14,
            fontWeight: 600,
            cursor: isFull ? 'not-allowed' : 'pointer',
            transition: 'opacity 100ms linear',
            flexShrink: 0,
            whiteSpace: 'nowrap',
          }}
        >
          邀请家庭成员
        </button>
      </div>
    </div>
  );
}

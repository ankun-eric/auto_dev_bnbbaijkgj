'use client';

/**
 * [PRD-MEMBER-PURPLE-THEME-V1 2026-05-30] 会员中心『付费态蓝紫主题』
 *
 * 在 v2.0 蓝紫主调基础上做全面深化：
 * - 顶部 Banner：付费态使用 PRD §F2 三段渐变 + 光斑 + 几何装饰；未付费态浅灰
 * - 新增「本月配额」卡（F3），从 /api/member/quota-usage 取已用值，total 来自 /api/member/center
 * - 等级徽章按 PRD §5.5 配色：尊享=金 / 健康=紫 / 普通=灰
 * - 即将到期（30 天内）橙黄状态条；已过期 主题降级为浅灰 + 红色状态条
 * - CTA 文案按 PRD §F5：
 *     · 普通用户 → 立即开通会员
 *     · 健康会员 → 升级到尊享会员
 *     · 尊享会员 → 续费 1 年
 *     · 已过期    → 立即续费，恢复权益
 *
 * 接口：
 * - /api/member/center 一次性聚合（已存在）
 * - /api/member/quota-usage 本月使用量（本次新增轻量只读接口）
 * - /api/family/member/quota 家庭守护配额（已存在）
 */
import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';
import GreenNavBar from '@/components/GreenNavBar';
import BenefitsCompareTable from './components/BenefitsCompareTable';
import InviteFamilyCard from './components/InviteFamilyCard';
import MonthlyQuotaCard from './components/MonthlyQuotaCard';
import {
  PURPLE_THEME,
  computeThemeState,
  computeLevelKey,
  getBadgePalette,
  getCtaText,
  isPurpleThemeEnabled,
  normalizeLevelLabel,
  type ThemeState,
} from './theme-purple';

interface BenefitsCard {
  key: string;
  label: string;
  value: number | null;
  unit: string;
}

interface PlanBrief {
  id: number;
  name: string;
  description: string | null;
  price_month: number | null;
  price_year: number | null;
  max_managed: number;
  ai_outbound_call_count: number;
  emergency_ai_call_count: number;
  max_managed_by: number;
  is_recommended: boolean;
  sort_order: number;
}

interface CenterCurrent {
  level: 'free' | 'paid';
  plan_id: number | null;
  plan_name: string;
  expire_date: string;
  expire_at: string | null;
  max_managed: number;
  ai_outbound_call_count: number;
  emergency_ai_call_count: number;
  max_managed_by: number;
  days_left: number | null;
  expiring_soon: boolean;
}

interface FreeQuota {
  max_managed: number;
  ai_outbound_call_count: number;
  emergency_ai_call_count: number;
}

interface CenterData {
  current: CenterCurrent;
  plans: PlanBrief[];
  current_plan_rank: number | null;
  ranks: Record<string, number>;
  benefits_cards: BenefitsCard[];
  free_quota?: FreeQuota;
}

interface QuotaUsageResp {
  ai_outbound_call_used: number;
  emergency_ai_call_used: number;
  max_managed_used: number;
  period_month: string;
}

interface FamilyQuotaResp {
  quota_used: number;
  quota_max: number;
  quota_remaining?: number;
}

function fmtVal(v: number | null): string {
  if (v === null) return '--';
  if (v === -1 || v >= 9999) return '不限';
  return String(v);
}

export default function MemberCenterPage() {
  const router = useRouter();
  const [data, setData] = useState<CenterData | null>(null);
  const [usage, setUsage] = useState<QuotaUsageResp | null>(null);
  const [familyQuota, setFamilyQuota] = useState<FamilyQuotaResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/api/member/center');
        setData((res as any).data || res);
      } catch (e: any) {
        console.error(e);
        showToast('加载会员中心失败', 'fail');
      } finally {
        setLoading(false);
      }
    })();
    (async () => {
      try {
        const r: any = await api.get('/api/member/quota-usage');
        const payload = r?.data || r;
        if (payload && typeof payload.ai_outbound_call_used === 'number') {
          setUsage(payload as QuotaUsageResp);
        }
      } catch {
        /* 静默兜底 */
      }
    })();
    (async () => {
      try {
        const r: any = await api.get('/api/family/member/quota');
        const payload = r?.data || r;
        if (payload && typeof payload.quota_max === 'number') {
          setFamilyQuota(payload as FamilyQuotaResp);
        }
      } catch {
        /* 静默兜底 */
      }
    })();
  }, []);

  // ─── 主题与等级判定 ───
  const themeState: ThemeState = useMemo(() => {
    if (!data) return 'unpaid';
    return computeThemeState({
      level: data.current.level,
      expireAt: data.current.expire_at,
      daysLeft: data.current.days_left,
      expiringSoon: data.current.expiring_soon,
    });
  }, [data]);

  const levelKey = useMemo(
    () => computeLevelKey(data?.current.plan_name || null, data?.current.level || 'free'),
    [data]
  );
  const purple = isPurpleThemeEnabled(themeState);
  const PAGE_BG = purple ? '#FFFFFF' : PURPLE_THEME.UNPAID_BG;

  const handleBuy = async (plan: PlanBrief, period: 'month' | 'year') => {
    if (busy) return;
    setBusy(true);
    try {
      const createRes: any = await api.post('/api/member/order', {
        plan_id: plan.id,
        period,
      });
      const order = createRes.data || createRes;
      await api.post(`/api/member/order/${order.order_id}/pay`, { simulate: true });
      showToast('开通成功', 'success');
      const res = await api.get('/api/member/center');
      setData((res as any).data || res);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '开通失败', 'fail');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div style={{ background: PURPLE_THEME.UNPAID_BG, minHeight: '100vh' }}>
        <GreenNavBar>会员中心</GreenNavBar>
        <div style={{ textAlign: 'center', padding: 40, color: PURPLE_THEME.TEXT_MUTED }}>加载中…</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ background: PURPLE_THEME.UNPAID_BG, minHeight: '100vh' }}>
        <GreenNavBar>会员中心</GreenNavBar>
        <div style={{ textAlign: 'center', padding: 40, color: PURPLE_THEME.TEXT_MUTED }}>加载失败，请稍后重试</div>
      </div>
    );
  }

  const { current, plans, current_plan_rank, ranks, benefits_cards, free_quota } = data;
  const isPaid = current.level === 'paid';

  // ─── Banner 样式 ───
  const bannerBgStyle: React.CSSProperties = purple
    ? {
        background: PURPLE_THEME.BANNER_GRADIENT,
        color: '#fff',
        boxShadow: '0 8px 24px rgba(91,108,255,0.25)',
      }
    : {
        background: PURPLE_THEME.UNPAID_BG,
        color: PURPLE_THEME.TEXT_DARK,
        border: `1px solid ${PURPLE_THEME.BORDER_LIGHT}`,
      };

  const badge = getBadgePalette(levelKey);

  // 状态条
  const showExpiringBar = themeState === 'paid_expiring' && current.days_left !== null;
  const showExpiredBar = themeState === 'expired';

  // CTA
  const ctaText = getCtaText({ themeState, levelKey });

  return (
    <div
      data-testid="member-center-root"
      data-theme-state={themeState}
      data-level-key={levelKey}
      style={{ background: PAGE_BG, minHeight: '100vh', paddingBottom: 96 }}
    >
      <GreenNavBar>会员中心</GreenNavBar>

      {/* 1. 顶部 Banner（F2） */}
      <div
        data-testid="mc-user-card"
        style={{
          margin: '12px 16px 0',
          borderRadius: 20,
          padding: '20px 18px 24px',
          position: 'relative',
          overflow: 'hidden',
          ...bannerBgStyle,
        }}
      >
        {/* 装饰：径向白光 + 几何点阵（仅付费态） */}
        {purple && (
          <>
            <div
              aria-hidden
              style={{
                position: 'absolute',
                top: -40,
                right: -40,
                width: 160,
                height: 160,
                background: 'radial-gradient(circle, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0) 70%)',
                pointerEvents: 'none',
              }}
            />
            <div
              aria-hidden
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: 60,
                background:
                  'radial-gradient(circle at 20% 80%, rgba(255,255,255,0.08) 1px, transparent 1px), radial-gradient(circle at 60% 30%, rgba(255,255,255,0.06) 1px, transparent 1px)',
                backgroundSize: '24px 24px',
                pointerEvents: 'none',
              }}
            />
          </>
        )}

        {/* 即将到期 状态条（付费态） */}
        {showExpiringBar && (
          <div
            data-testid="mc-expire-warn"
            style={{
              position: 'relative',
              zIndex: 1,
              background: PURPLE_THEME.WARN_ORANGE,
              color: '#fff',
              padding: '8px 12px',
              borderRadius: 8,
              fontSize: 13,
              marginBottom: 14,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontWeight: 600,
            }}
          >
            <span style={{ fontSize: 16 }}>⚠️</span>
            <span>您的会员将于 {current.days_left} 天后到期</span>
            <span style={{ marginLeft: 'auto', fontSize: 12, opacity: 0.95, textDecoration: 'underline' }}>立即续费 →</span>
          </div>
        )}

        {/* 已过期 状态条 */}
        {showExpiredBar && (
          <div
            data-testid="mc-expired-bar"
            style={{
              position: 'relative',
              zIndex: 1,
              background: PURPLE_THEME.ERR_RED,
              color: '#fff',
              padding: '8px 12px',
              borderRadius: 8,
              fontSize: 13,
              marginBottom: 14,
              fontWeight: 600,
            }}
          >
            您的会员已于 {current.days_left !== null ? Math.abs(current.days_left) : 0} 天前到期
          </div>
        )}

        <div style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 60,
              height: 60,
              borderRadius: '50%',
              background: purple ? 'rgba(255,255,255,0.2)' : '#FFFFFF',
              border: `2px solid ${purple ? '#FFFFFF' : PURPLE_THEME.BORDER_LIGHT}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 28,
              flexShrink: 0,
            }}
          >
            👤
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 18, fontWeight: 700 }} data-testid="mc-user-nick">
              {(current as any).nickname || '尊贵会员'}
            </div>
            <div
              data-testid="mc-level-tag"
              data-level-key={levelKey}
              style={{
                display: 'inline-block',
                background: badge.bg,
                color: badge.text,
                fontSize: 12,
                fontWeight: 700,
                padding: '3px 10px',
                borderRadius: 12,
                marginTop: 6,
                border: `1px solid ${badge.border}`,
              }}
            >
              {normalizeLevelLabel(current.plan_name, current.level)}
            </div>
            <div
              style={{
                fontSize: 13,
                marginTop: 8,
                opacity: purple ? 0.9 : 1,
                color: purple ? '#fff' : PURPLE_THEME.TEXT_MUTED,
              }}
              data-testid="mc-expire"
            >
              {isPaid ? `有效期至 ${current.expire_date}` : '开通会员，享 AI 外呼/紧急呼叫等权益'}
            </div>
          </div>
        </div>
      </div>

      {/* 2. 邀请家人入口（保留） */}
      <InviteFamilyCard
        planName={current.plan_name}
        quotaMax={(familyQuota && typeof familyQuota.quota_max === 'number') ? familyQuota.quota_max : current.max_managed}
        quotaUsed={(familyQuota && typeof familyQuota.quota_used === 'number') ? familyQuota.quota_used : 0}
        cardLocation='member_center'
        onInvite={() => router.push('/health-profile/my-guardians/invite')}
        onUpgrade={() => {
          if (typeof window !== 'undefined') {
            const el = document.querySelector('[data-mc-upgrade-section="1"]');
            if (el && (el as HTMLElement).scrollIntoView) {
              (el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'start' });
              return;
            }
          }
          showToast('请在下方"升级享更多权益"区选择套餐', 'warning');
        }}
      />

      {/* 3. 本月配额卡（F3） */}
      <MonthlyQuotaCard
        themeState={themeState}
        aiOutbound={{
          used: usage?.ai_outbound_call_used ?? 0,
          total: current.ai_outbound_call_count,
        }}
        emergencyAi={{
          used: usage?.emergency_ai_call_used ?? 0,
          total: current.emergency_ai_call_count,
        }}
        manageMember={{
          // [PRD-MEMBER-COUNT-CONSISTENCY-V1 2026-05-31] 修复"两数字对不上"Bug：
          // 优先使用 familyQuota.quota_used（含本人，与蓝卡口径一致，权威值），
          // 不再 -1 剔除本人；usage 接口在后端已统一为相同口径，仅作兜底。
          used: (familyQuota && typeof familyQuota.quota_used === 'number')
            ? familyQuota.quota_used
            : (usage?.max_managed_used ?? 0),
          total: current.max_managed,
        }}
      />

      {/* 4. 我的会员权益（4 格） */}
      <div
        style={{
          margin: '12px 16px 0',
          background: '#fff',
          borderRadius: 16,
          padding: '18px 16px',
          border: `1px solid ${PURPLE_THEME.BORDER_LIGHT}`,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: PURPLE_THEME.TEXT_DARK }}>我的会员权益</div>
          <div
            style={{ fontSize: 12, color: PURPLE_THEME.PRIMARY, cursor: 'pointer' }}
            onClick={() => showToast('更多权益开发中，敬请期待', 'info')}
            data-testid="mc-benefits-more"
          >
            查看全部 ›
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          {benefits_cards.map((b) => {
            const placeholder = b.key === 'placeholder';
            let displayValue: string = fmtVal(b.value);
            if (b.key === 'max_managed' && typeof b.value === 'number') {
              if (b.value === -1 || b.value >= 9999) displayValue = '不限';
              else displayValue = String(b.value);
            }
            return (
              <div
                key={b.key}
                data-testid={`mc-benefit-${b.key}`}
                style={{
                  background: placeholder ? 'transparent' : 'rgba(91,108,255,0.06)',
                  border: placeholder ? `1.5px dashed ${PURPLE_THEME.PRIMARY}` : 'none',
                  borderRadius: 14,
                  padding: '14px 10px',
                  textAlign: 'center',
                }}
              >
                <div
                  style={{
                    fontSize: placeholder ? 18 : 22,
                    fontWeight: 700,
                    color: placeholder ? PURPLE_THEME.PRIMARY : PURPLE_THEME.PRIMARY_DARK_TEXT,
                  }}
                >
                  {placeholder ? '✨ 敬请期待' : displayValue}
                </div>
                <div style={{ fontSize: 12, color: PURPLE_THEME.TEXT_MUTED, marginTop: 4 }}>
                  {b.label}
                  {!placeholder && b.unit ? `（${b.unit}）` : ''}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. 升级享更多权益 */}
      {plans.length > 0 && (
        <div style={{ margin: '20px 16px 0' }} data-mc-upgrade-section="1">
          <div style={{ fontSize: 16, fontWeight: 700, color: PURPLE_THEME.TEXT_DARK, marginBottom: 10, padding: '0 4px' }}>
            升级享更多权益
          </div>
          {plans.map((p) => {
            const rank = ranks[String(p.id)];
            const isCurrent = isPaid && current.plan_id === p.id;
            const canUpgrade = isPaid && current_plan_rank !== null && rank > current_plan_rank;
            const hidden = isPaid && current_plan_rank !== null && rank < current_plan_rank;
            if (hidden) return null;
            return (
              <div
                key={p.id}
                data-testid={`mc-plan-${p.id}`}
                style={{
                  background: '#fff',
                  borderRadius: 16,
                  padding: 16,
                  marginBottom: 12,
                  position: 'relative',
                  border: p.is_recommended ? `1.5px solid ${PURPLE_THEME.PRIMARY}` : `1px solid ${PURPLE_THEME.BORDER_LIGHT}`,
                  boxShadow: p.is_recommended ? '0 6px 18px rgba(91,108,255,0.15)' : 'none',
                }}
              >
                {p.is_recommended && (
                  <div
                    style={{
                      position: 'absolute',
                      top: -8,
                      right: 16,
                      background: PURPLE_THEME.CTA_GRADIENT,
                      color: '#fff',
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '2px 10px',
                      borderRadius: 10,
                    }}
                  >
                    ✦ 推荐
                  </div>
                )}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: 17, fontWeight: 700, color: PURPLE_THEME.TEXT_DARK }}>{p.name}</div>
                    <div style={{ fontSize: 12, color: PURPLE_THEME.TEXT_MUTED, marginTop: 4 }}>
                      家庭成员 {p.max_managed === -1 || p.max_managed >= 9999 ? '不限' : `${p.max_managed} 人`} · AI 外呼 {fmtVal(p.ai_outbound_call_count)} 次 · 紧急呼叫 {fmtVal(p.emergency_ai_call_count)} 次
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                  {p.price_month !== null && (
                    <button
                      data-testid={`mc-buy-month-${p.id}`}
                      disabled={busy || isCurrent}
                      onClick={() => handleBuy(p, 'month')}
                      style={{
                        flex: 1,
                        padding: '10px 0',
                        borderRadius: 22,
                        border: `1.5px solid ${PURPLE_THEME.PRIMARY}`,
                        background: '#fff',
                        color: PURPLE_THEME.PRIMARY,
                        fontSize: 14,
                        fontWeight: 600,
                        cursor: busy || isCurrent ? 'not-allowed' : 'pointer',
                        opacity: busy || isCurrent ? 0.6 : 1,
                      }}
                    >
                      {isCurrent ? '当前套餐' : canUpgrade ? `升级月卡 ¥${p.price_month}` : `月卡 ¥${p.price_month}`}
                    </button>
                  )}
                  {p.price_year !== null && (
                    <button
                      data-testid={`mc-buy-year-${p.id}`}
                      disabled={busy || isCurrent}
                      onClick={() => handleBuy(p, 'year')}
                      style={{
                        flex: 1,
                        padding: '10px 0',
                        borderRadius: 22,
                        border: 'none',
                        background: PURPLE_THEME.CTA_GRADIENT,
                        color: '#fff',
                        fontSize: 14,
                        fontWeight: 700,
                        cursor: busy || isCurrent ? 'not-allowed' : 'pointer',
                        opacity: busy || isCurrent ? 0.6 : 1,
                        boxShadow: '0 4px 16px rgba(91,108,255,0.35)',
                      }}
                    >
                      {isCurrent ? '已开通' : canUpgrade ? `升级年卡 ¥${p.price_year}` : `年卡 ¥${p.price_year}`}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 6. 三档对比表（F4） */}
      <BenefitsCompareTable
        current={current as any}
        plans={plans as any}
        ranks={ranks as any}
        freeQuota={free_quota}
      />

      {/* 7. 底部入口区 */}
      <div
        style={{
          margin: '16px 16px 0',
          background: '#fff',
          borderRadius: 16,
          padding: '4px 0',
          border: `1px solid ${PURPLE_THEME.BORDER_LIGHT}`,
        }}
      >
        {[
          { label: '我的订单', icon: '📦', tab: '/unified-orders', testid: 'mc-orders' },
          { label: '我的优惠券', icon: '🎫', tab: '/my-coupons', testid: 'mc-coupons' },
          { label: '常见问题', icon: '❓', tab: '#faq', testid: 'mc-faq' },
        ].map((item, idx, arr) => (
          <div
            key={item.label}
            data-testid={item.testid}
            onClick={() => {
              if (item.tab.startsWith('#')) {
                showToast('暂未开放', 'info');
              } else {
                router.push(item.tab);
              }
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 16px',
              borderBottom: idx < arr.length - 1 ? '1px solid #f0f0f0' : 'none',
              cursor: 'pointer',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>{item.icon}</span>
              <span style={{ fontSize: 14, color: PURPLE_THEME.TEXT_DARK }}>{item.label}</span>
            </div>
            <span style={{ color: PURPLE_THEME.TEXT_MUTED, fontSize: 14 }}>›</span>
          </div>
        ))}
      </div>

      <div style={{ textAlign: 'center', marginTop: 18, fontSize: 11, color: PURPLE_THEME.TEXT_MUTED, padding: '0 24px' }}>
        开通即同意《会员服务协议》《自动续费协议》
      </div>

      {/* 8. 底部吸底 CTA（F5） */}
      <div
        data-testid="mc-bottom-cta"
        style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          padding: '12px 16px calc(12px + env(safe-area-inset-bottom, 0px))',
          background: 'rgba(255,255,255,0.96)',
          backdropFilter: 'saturate(180%) blur(12px)',
          borderTop: `1px solid ${PURPLE_THEME.BORDER_LIGHT}`,
          zIndex: 50,
        }}
      >
        <button
          onClick={() => {
            if (typeof window !== 'undefined') {
              const el = document.querySelector('[data-mc-upgrade-section="1"]');
              if (el && (el as HTMLElement).scrollIntoView) {
                (el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'start' });
                return;
              }
            }
          }}
          style={{
            width: '100%',
            height: 48,
            border: 'none',
            borderRadius: 24,
            background: PURPLE_THEME.CTA_GRADIENT,
            color: '#fff',
            fontSize: 16,
            fontWeight: 700,
            cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(91,108,255,0.35)',
          }}
          data-testid="mc-bottom-cta-btn"
        >
          {ctaText}
        </button>
      </div>
    </div>
  );
}

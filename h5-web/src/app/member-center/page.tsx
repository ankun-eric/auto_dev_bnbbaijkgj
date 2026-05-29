'use client';

/**
 * [会员中心优化 PRD v2.0 2026-05-26] 会员中心新版
 *
 * 设计规范：方案一 蓝紫主调 + 金色点缀
 *
 * 页面结构（自上而下）：
 * 1. 顶部导航栏（返回 / 标题"会员中心" / 更多按钮）
 * 2. 用户信息卡（蓝紫渐变，金色皇冠 + 等级胶囊 + 有效期）
 * 3. 我的会员权益（4 格：守护人 / AI 外呼 / 紧急 AI 呼叫 / 占位卡）
 * 4. 升级享更多权益（动态拉取启用中套餐 + 推荐角标 + 月/年价按钮）
 * 5. 底部入口区（我的订单 / 我的优惠券 / 常见问题）
 * 6. 协议提示
 *
 * 接口：/api/member/center 一次性聚合 + /api/member/order + /api/member/order/{id}/pay
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';
import GreenNavBar from '@/components/GreenNavBar';
// [Bug 修复 v1.0 §3.2 2026-05-26] 新增「权益对比」表
import BenefitsCompareTable from './components/BenefitsCompareTable';

// ─── 视觉色：蓝紫主调 + 金色点缀 ───
const PRIMARY = '#5B7CFA';          // 蓝紫主色
const PRIMARY_DARK = '#3E5BD9';     // 蓝紫深
const PRIMARY_BG = '#EEF2FF';       // 蓝紫底
const GOLD = '#E5A23B';             // 金色（皇冠 + 等级胶囊）
const GOLD_LIGHT = '#F4D793';       // 浅金（渐变）
const GOLD_BG = 'rgba(229, 162, 59, 0.12)';
const PAGE_BG = '#F5F4FB';          // 蓝紫浅底
const DANGER = '#FF4D4F';
const TEXT_DARK = '#1a1a1a';
const TEXT_MUTED = '#8C8C8C';

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

// [优化 v1.0 2026-05-27] free_quota 字段：来自管理后台「免费会员额度配置」（free_member_quota 表），
// 与当前登录用户档位无关，全用户相同。供权益对比表「免费会员」列消费。
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

function fmtVal(v: number | null): string {
  if (v === null) return '--';
  if (v === -1) return '不限';
  return String(v);
}

export default function MemberCenterPage() {
  const router = useRouter();
  const [data, setData] = useState<CenterData | null>(null);
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
  }, []);

  const handleBuy = async (plan: PlanBrief, period: 'month' | 'year') => {
    if (busy) return;
    setBusy(true);
    try {
      const createRes: any = await api.post('/api/member/order', {
        plan_id: plan.id,
        period,
      });
      const order = createRes.data || createRes;
      // 模拟支付
      await api.post(`/api/member/order/${order.order_id}/pay`, { simulate: true });
      showToast('开通成功', 'success');
      // 重新拉取
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
      <div style={{ background: PAGE_BG, minHeight: '100vh' }}>
        <GreenNavBar>会员中心</GreenNavBar>
        <div style={{ textAlign: 'center', padding: 40, color: TEXT_MUTED }}>加载中…</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ background: PAGE_BG, minHeight: '100vh' }}>
        <GreenNavBar>会员中心</GreenNavBar>
        <div style={{ textAlign: 'center', padding: 40, color: TEXT_MUTED }}>加载失败，请稍后重试</div>
      </div>
    );
  }

  const { current, plans, current_plan_rank, ranks, benefits_cards, free_quota } = data;
  const isPaid = current.level === 'paid';

  return (
    <div style={{ background: PAGE_BG, minHeight: '100vh', paddingBottom: 32 }}>
      <GreenNavBar>会员中心</GreenNavBar>

      {/* 1. 用户信息卡（蓝紫渐变 + 金色点缀） */}
      <div
        data-testid="mc-user-card"
        style={{
          margin: '12px 16px 0',
          background: `linear-gradient(135deg, ${PRIMARY} 0%, ${PRIMARY_DARK} 100%)`,
          borderRadius: 20,
          padding: '20px 18px 24px',
          color: '#fff',
          boxShadow: '0 8px 24px rgba(91, 124, 250, 0.25)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* 到期红色横幅 */}
        {isPaid && current.expiring_soon && current.days_left !== null && (
          <div
            style={{
              background: DANGER,
              color: '#fff',
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: 12,
              marginBottom: 12,
              textAlign: 'center',
            }}
            data-testid="mc-expire-warn"
          >
            ⚠️ 您的会员将于 {current.days_left} 天后到期，立即续费
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* 头像占位 + 金色皇冠 */}
          <div
            style={{
              width: 60,
              height: 60,
              borderRadius: '50%',
              background: 'rgba(255,255,255,0.2)',
              border: `2px solid ${isPaid ? GOLD : '#fff'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 28,
              position: 'relative',
            }}
          >
            👤
            <span
              style={{
                position: 'absolute',
                top: -8,
                right: -4,
                fontSize: 20,
                filter: isPaid ? 'none' : 'grayscale(0.5)',
              }}
            >
              👑
            </span>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 17, fontWeight: 700 }}>{(current as any).nickname || '尊贵会员'}</div>
            {/* 等级胶囊（金色） */}
            <div
              style={{
                display: 'inline-block',
                background: `linear-gradient(90deg, ${GOLD} 0%, ${GOLD_LIGHT} 100%)`,
                color: '#5C3B00',
                fontSize: 12,
                fontWeight: 700,
                padding: '3px 10px',
                borderRadius: 12,
                marginTop: 6,
              }}
              data-testid="mc-level-tag"
            >
              {current.plan_name}
            </div>
            <div style={{ fontSize: 12, marginTop: 8, opacity: 0.85 }} data-testid="mc-expire">
              有效期：{current.expire_date}
            </div>
          </div>
        </div>
      </div>

      {/* 2. 我的会员权益（4 格） */}
      <div
        style={{
          margin: '-24px 16px 0',
          background: '#fff',
          borderRadius: 20,
          padding: '18px 16px',
          boxShadow: '0 4px 16px rgba(91, 124, 250, 0.10)',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: TEXT_DARK }}>我的会员权益</div>
          <div
            style={{ fontSize: 12, color: PRIMARY, cursor: 'pointer' }}
            onClick={() => showToast('更多权益开发中，敬请期待', 'info')}
            data-testid="mc-benefits-more"
          >
            查看全部 ›
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          {benefits_cards.map((b) => {
            const placeholder = b.key === 'placeholder';
            // [PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] max_managed 资产/配额展示：
            //   后端 value = 旧 max_managed（仅家人/守护对象计数，不含本人）；前端 +1 含本人
            //   -1（不限）展示「不限」
            let displayValue: any = fmtVal(b.value);
            if (b.key === 'max_managed' && typeof b.value === 'number') {
              if (b.value === -1 || b.value >= 9999) displayValue = '不限';
              else displayValue = String(b.value + 1);
            }
            return (
              <div
                key={b.key}
                data-testid={`mc-benefit-${b.key}`}
                style={{
                  background: placeholder ? 'transparent' : PRIMARY_BG,
                  border: placeholder ? `1.5px dashed ${PRIMARY}` : 'none',
                  borderRadius: 14,
                  padding: '14px 10px',
                  textAlign: 'center',
                }}
              >
                <div
                  style={{
                    fontSize: placeholder ? 18 : 22,
                    fontWeight: 700,
                    color: placeholder ? PRIMARY : PRIMARY_DARK,
                  }}
                >
                  {placeholder ? '✨ 敬请期待' : displayValue}
                </div>
                <div style={{ fontSize: 12, color: TEXT_MUTED, marginTop: 4 }}>
                  {b.label}
                  {!placeholder && b.unit ? `（${b.unit}）` : ''}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. 升级享更多权益 */}
      {plans.length > 0 && (
        <div style={{ margin: '20px 16px 0' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: TEXT_DARK, marginBottom: 10, padding: '0 4px' }}>
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
                  borderRadius: 18,
                  padding: 16,
                  marginBottom: 12,
                  position: 'relative',
                  boxShadow: '0 4px 12px rgba(91, 124, 250, 0.08)',
                  border: p.is_recommended ? `1.5px solid ${GOLD}` : `1px solid ${PRIMARY_BG}`,
                }}
              >
                {p.is_recommended && (
                  <div
                    style={{
                      position: 'absolute',
                      top: -8,
                      right: 16,
                      background: `linear-gradient(90deg, ${GOLD} 0%, ${GOLD_LIGHT} 100%)`,
                      color: '#5C3B00',
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '2px 10px',
                      borderRadius: 10,
                    }}
                  >
                    👑 推荐
                  </div>
                )}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_DARK }}>{p.name}</div>
                    <div style={{ fontSize: 12, color: TEXT_MUTED, marginTop: 4 }}>
                      {/* [PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 资产/配额语境：
                          「守护 X 人」→「可管理健康档案 X 份（含本人）」
                          max_managed 字段保留，仅显示 +1 含本人；-1（不限）显示「不限」 */}
                      可管理健康档案 {p.max_managed === -1 ? '不限' : `${p.max_managed + 1} 份（含本人）`} · AI 外呼 {fmtVal(p.ai_outbound_call_count)} 次 · 紧急呼叫 {fmtVal(p.emergency_ai_call_count)} 次
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
                        border: `1.5px solid ${PRIMARY}`,
                        background: '#fff',
                        color: PRIMARY,
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
                        background: p.is_recommended
                          ? `linear-gradient(90deg, ${GOLD} 0%, ${GOLD_LIGHT} 100%)`
                          : `linear-gradient(90deg, ${PRIMARY} 0%, ${PRIMARY_DARK} 100%)`,
                        color: p.is_recommended ? '#5C3B00' : '#fff',
                        fontSize: 14,
                        fontWeight: 700,
                        cursor: busy || isCurrent ? 'not-allowed' : 'pointer',
                        opacity: busy || isCurrent ? 0.6 : 1,
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

      {/* [Bug 修复 v1.0 §3.2 2026-05-26] [优化 v1.0 2026-05-27] 4. 权益对比表
          freeQuota 来自后端 free_quota 字段（管理后台「免费会员额度配置」），
          与当前用户档位无关，付费用户也能看到正确的「免费会员」列数值。 */}
      <BenefitsCompareTable
        current={current as any}
        plans={plans as any}
        ranks={ranks as any}
        freeQuota={free_quota}
      />

      {/* 5. 底部入口区 */}
      <div style={{ margin: '16px 16px 0', background: '#fff', borderRadius: 18, padding: '4px 0', boxShadow: '0 4px 12px rgba(91, 124, 250, 0.06)' }}>
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
              <span style={{ fontSize: 14, color: TEXT_DARK }}>{item.label}</span>
            </div>
            <span style={{ color: TEXT_MUTED, fontSize: 14 }}>›</span>
          </div>
        ))}
      </div>

      {/* 6. 协议提示 */}
      <div style={{ textAlign: 'center', marginTop: 24, fontSize: 11, color: TEXT_MUTED, padding: '0 24px' }}>
        开通即同意《会员服务协议》《自动续费协议》
      </div>
    </div>
  );
}

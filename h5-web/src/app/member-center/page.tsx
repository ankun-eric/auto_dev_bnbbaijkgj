'use client';

/**
 * [守护人体系 PRD v1.2 §13] 会员中心
 * - 我的当前等级
 * - 会员权益对比表（3 项核心权益）
 * - 本月配额（极简数据仪表风：3 个环形进度条）
 * - 升级套餐选购卡
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Empty, Tag } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';
import GreenNavBar from '@/components/GreenNavBar';

interface Plan {
  id: number;
  plan_code: string;
  name: string;
  price_monthly: number;
  price_yearly?: number;
  ai_remind_quota: number;
  emergency_ai_call_count: number;
  max_managed: number;
  discount_rate: number;
  point_multiplier: number;
  is_active: boolean;
  sort_order: number;
}

interface QuotaSummary {
  plan_name: string;
  is_paid_member: boolean;
  ai_remind: { total: number; used: number; remaining: number; unlimited: boolean; ratio: number };
  emergency_ai_call: { total: number; used: number; remaining: number; unlimited: boolean; ratio: number };
  max_managed: { total: number; used: number; remaining: number; unlimited: boolean; ratio: number };
}

interface MeMembership {
  is_paid_member: boolean;
  plan_name?: string;
  expire_at?: string;
}

const PRIMARY = '#1890FF';
const PRIMARY_DARK = '#096DD9';
const PRIMARY_BG = '#E6F7FF';
const PAGE_BG = '#F0F8FF';
const WARN = '#FAAD14';
const DANGER = '#FF4D4F';
const SUCCESS = '#52C41A';

function fmtVal(v: number) {
  if (v === -1) return '不限';
  return String(v);
}

function Ring({ ratio, color, label, value }: { ratio: number; color: string; label: string; value: string }) {
  const size = 90;
  const stroke = 8;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  const dash = Math.max(0, Math.min(1, ratio)) * circ;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={size} height={size}>
        <circle cx={cx} cy={cy} r={r} stroke='#f0f0f0' strokeWidth={stroke} fill='none' />
        <circle cx={cx} cy={cy} r={r} stroke={color} strokeWidth={stroke} fill='none'
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap='round'
          transform={`rotate(-90 ${cx} ${cy})`}
        />
        <text x={cx} y={cy + 5} textAnchor='middle' fontSize='14' fontWeight='700' fill='#1a1a1a'>{value}</text>
      </svg>
      <div style={{ marginTop: 4, fontSize: 12, color: '#8C8C8C' }}>{label}</div>
    </div>
  );
}

export default function MemberCenterPage() {
  const router = useRouter();
  const [me, setMe] = useState<MeMembership | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [summary, setSummary] = useState<QuotaSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [meR, plansR, sumR] = await Promise.all([
          api.get('/api/membership/me'),
          api.get('/api/membership/plans'),
          api.get('/api/guardian/v12/managed-quota-summary'),
        ]);
        setMe((meR as any).data || meR);
        setPlans(((plansR as any).data || plansR) || []);
        setSummary((sumR as any).data || sumR);
      } catch (e: any) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleBuy = async (p: Plan, cycle: 'monthly' | 'yearly') => {
    try {
      await api.post('/api/membership/subscribe', { plan_id: p.id, billing_cycle: cycle });
      showToast('开通成功（模拟支付）', 'success');
      // 重载
      window.location.reload();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '开通失败', 'fail');
    }
  };

  if (loading) {
    return (
      <div style={{ background: PAGE_BG, minHeight: '100vh' }}>
        <GreenNavBar>会员中心</GreenNavBar>
        <div style={{ textAlign: 'center', padding: 40 }}>加载中…</div>
      </div>
    );
  }

  return (
    <div style={{ background: PAGE_BG, minHeight: '100vh', paddingBottom: 32 }}>
      <GreenNavBar>会员中心</GreenNavBar>

      {/* 1. 我的当前等级卡片（Hero） */}
      <div style={{
        background: `linear-gradient(135deg, ${PRIMARY} 0%, ${PRIMARY_DARK} 100%)`,
        margin: 16, borderRadius: 20, padding: 20, color: '#fff',
        boxShadow: '0 8px 24px rgba(24, 144, 255, 0.25)',
      }}>
        <div style={{ fontSize: 14, opacity: 0.9 }}>当前等级</div>
        <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>
          {me?.plan_name || (me?.is_paid_member ? '付费会员' : '普通会员')}
        </div>
        {me?.expire_at && (
          <div style={{ fontSize: 12, marginTop: 8, opacity: 0.85 }}>
            有效期至 {new Date(me.expire_at).toLocaleDateString()}
          </div>
        )}
        {!me?.is_paid_member && (
          <div style={{ fontSize: 12, marginTop: 8, opacity: 0.85 }}>
            升级会员可获得更多 AI 外呼额度与守护他人上限
          </div>
        )}
      </div>

      {/* 2. 本月配额（极简数据仪表风） */}
      {summary && (
        <div style={{
          margin: 16, background: '#fff', borderRadius: 20, padding: '20px 16px',
          boxShadow: '0 4px 16px rgba(24, 144, 255, 0.08)',
        }}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, color: '#1a1a1a' }}>本月配额</div>
          <div style={{ display: 'flex', justifyContent: 'space-around' }}>
            <Ring
              ratio={summary.ai_remind.unlimited ? 0 : summary.ai_remind.ratio}
              color={PRIMARY}
              label='AI 外呼提醒'
              value={summary.ai_remind.unlimited ? '∞' : `${summary.ai_remind.remaining}/${summary.ai_remind.total}`}
            />
            <Ring
              ratio={summary.emergency_ai_call.unlimited ? 0 : summary.emergency_ai_call.ratio}
              color={summary.emergency_ai_call.remaining <= 2 && !summary.emergency_ai_call.unlimited ? WARN : PRIMARY}
              label='紧急 AI 呼叫'
              value={summary.emergency_ai_call.unlimited ? '∞' : `${summary.emergency_ai_call.remaining}/${summary.emergency_ai_call.total}`}
            />
            <Ring
              ratio={summary.max_managed.unlimited ? 0 : summary.max_managed.ratio}
              color={PRIMARY_DARK}
              label='守护他人'
              value={summary.max_managed.unlimited ? '∞' : `${summary.max_managed.used}/${summary.max_managed.total}`}
            />
          </div>
          <div style={{ marginTop: 16, fontSize: 12, color: '#8C8C8C', textAlign: 'center' }}>
            每月 1 号自动重置 · 单项可加购
          </div>
        </div>
      )}

      {/* 3. 会员权益对比表 */}
      {plans.length > 0 && (
        <div style={{
          margin: 16, background: '#fff', borderRadius: 20, padding: 16,
          boxShadow: '0 4px 16px rgba(24, 144, 255, 0.08)',
        }}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>会员权益对比</div>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: PRIMARY_BG }}>
                <th style={{ padding: 8, textAlign: 'left', color: PRIMARY_DARK }}>权益项</th>
                <th style={{ padding: 8, color: '#8C8C8C' }}>普通会员</th>
                {plans.slice(0, 3).map(p => (
                  <th key={p.id} style={{ padding: 8, color: PRIMARY_DARK }}>{p.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ padding: 8, color: '#1a1a1a' }}>AI 外呼提醒</td>
                <td style={{ padding: 8, textAlign: 'center', color: '#8C8C8C' }}>—</td>
                {plans.slice(0, 3).map(p => (
                  <td key={p.id} style={{ padding: 8, textAlign: 'center', color: '#1a1a1a' }}>{fmtVal(p.ai_remind_quota)}</td>
                ))}
              </tr>
              <tr style={{ background: '#fafafa' }}>
                <td style={{ padding: 8, color: '#1a1a1a' }}>紧急 AI 呼叫</td>
                <td style={{ padding: 8, textAlign: 'center', color: '#8C8C8C' }}>—</td>
                {plans.slice(0, 3).map(p => (
                  <td key={p.id} style={{ padding: 8, textAlign: 'center', color: '#1a1a1a' }}>{fmtVal(p.emergency_ai_call_count)}</td>
                ))}
              </tr>
              <tr>
                <td style={{ padding: 8, color: '#1a1a1a' }}>守护他人上限</td>
                <td style={{ padding: 8, textAlign: 'center', color: '#8C8C8C' }}>—</td>
                {plans.slice(0, 3).map(p => (
                  <td key={p.id} style={{ padding: 8, textAlign: 'center', color: '#1a1a1a' }}>{fmtVal(p.max_managed)}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* 4. 升级套餐选购卡 */}
      {plans.length > 0 ? (
        <div style={{ padding: '0 16px' }}>
          {plans.map(p => (
            <div key={p.id} style={{
              background: '#fff', borderRadius: 20, padding: 16, marginBottom: 12,
              boxShadow: '0 4px 16px rgba(24, 144, 255, 0.08)',
              border: `1px solid ${PRIMARY_BG}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: 17, fontWeight: 700, color: '#1a1a1a' }}>{p.name}</div>
                  <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>
                    AI 外呼 {fmtVal(p.ai_remind_quota)} · 紧急呼叫 {fmtVal(p.emergency_ai_call_count)} · 守护 {fmtVal(p.max_managed)} 人
                  </div>
                </div>
                <Tag color='primary' fill='solid' style={{ background: PRIMARY }}>付费</Tag>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <Button size='small' fill='outline' style={{ flex: 1, borderRadius: 22, borderColor: PRIMARY, color: PRIMARY }}
                  onClick={() => handleBuy(p, 'monthly')}>
                  月付 ¥{p.price_monthly}
                </Button>
                {p.price_yearly && (
                  <Button size='small' fill='solid' style={{ flex: 1, borderRadius: 22, background: PRIMARY }}
                    onClick={() => handleBuy(p, 'yearly')}>
                    年付 ¥{p.price_yearly}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ padding: 24, textAlign: 'center', color: '#8C8C8C' }}>
          暂无可购买的套餐，请联系客服
        </div>
      )}
    </div>
  );
}

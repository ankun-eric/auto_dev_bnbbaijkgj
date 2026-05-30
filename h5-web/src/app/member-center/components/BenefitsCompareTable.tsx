'use client';

/**
 * [Bug 修复 v1.0 §3.2 2026-05-26] 权益对比模块
 *
 * 设计要点：
 * - 位置：套餐区下方、底部入口区上方
 * - 行 = 3 项（守护人 / AI 外呼 / 紧急 AI 呼叫），与「我的会员权益」3 实卡同源
 * - 列 = 免费会员 + 后台启用付费套餐（按 plan_rank 升序，年价优先）
 * - 列头颜色按档位自动渐变：紫（免费）→ 橙黄 → 橙红 → 深红
 *
 * [优化 v1.0 2026-05-27] 「免费会员」列数值现在通过 props.freeQuota 传入，
 * 直接来自管理后台「免费会员额度配置」（free_member_quota 表），
 * 与当前登录用户档位无关，付费用户也能看到正确的免费会员额度。
 * - 「-1」展示为「不限」
 * - 推荐角标不在对比表内出现（仅套餐卡片显示）
 * - 窄屏整张表 overflow-x:auto 横向滚动
 */
import React, { useMemo } from 'react';

interface PlanBrief {
  id: number;
  name: string;
  max_managed: number;
  ai_outbound_call_count: number;
  emergency_ai_call_count: number;
  price_month: number | null;
  price_year: number | null;
}

interface CenterCurrent {
  level: 'free' | 'paid';
  plan_id: number | null;
  max_managed: number;
  ai_outbound_call_count: number;
  emergency_ai_call_count: number;
}

// [优化 v1.0 2026-05-27] free_quota 永远是「免费会员额度配置」表中的全局额度（全用户相同），
// 不随登录用户档位变化。current 是当前登录用户档位额度（付费用户为其套餐额度，免费用户与 freeQuota 相同）。
interface FreeQuota {
  max_managed: number;
  ai_outbound_call_count: number;
  emergency_ai_call_count: number;
}

interface Props {
  current: CenterCurrent;
  plans: PlanBrief[];
  ranks: Record<string, number>;
  freeQuota?: FreeQuota;
}

const PRIMARY = '#5B6CFF';
const PRIMARY_DARK = '#3D4CCC';
const PRIMARY_BG_LIGHT = 'rgba(91,108,255,0.08)';
const TEXT_DARK = '#1F2937';
const TEXT_MUTED = '#6B7280';
const TEXT_GRAY = '#374151';
const BORDER_LIGHT = '#E5E7F0';

// 付费列颜色梯度：[PRD-MEMBER-PURPLE-THEME-V1 2026-05-30] 改为蓝紫调梯度
// 浅紫 → 主蓝紫 → 深蓝紫，与系统主色保持一致，废弃旧的橙红渐变
const PAID_GRADIENT = ['#8B6CFF', '#6C7BFF', '#5B6CFF', '#3D4CCC', '#2E3DBF'];

function fmtVal(v: number | null | undefined): string {
  if (v === null || v === undefined) return '--';
  if (v === -1) return '不限';
  return String(v);
}

// [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30 C2/C5]
// 口径统一：max_managed 即"家庭守护成员总人数"（已含本人，数据库迁移后），前端零加工原样展示
// -1 或 >=9999 展示「不限」；不写"含本人/不含本人"
function fmtArchiveVal(v: number | null | undefined): string {
  if (v === null || v === undefined) return '--';
  if (v === -1 || (typeof v === 'number' && v >= 9999)) return '不限';
  return `${v} 人`;
}

export default function BenefitsCompareTable({ current, plans, ranks, freeQuota }: Props) {
  // [优化 v1.0 2026-05-27] 「免费会员」列必须来自管理后台「免费会员额度配置」（free_member_quota 表）。
  // 兜底：若后端未下发 free_quota，回退到 current（仅免费用户场景下正确，付费用户场景下会显示其档位额度，
  // 这是历史行为，但前端已优先消费 free_quota）。
  const freeVals = freeQuota ?? {
    max_managed: current.max_managed,
    ai_outbound_call_count: current.ai_outbound_call_count,
    emergency_ai_call_count: current.emergency_ai_call_count,
  };
  // 按 price_rank 升序排列付费套餐
  const sortedPaidPlans = useMemo(() => {
    return [...plans].sort((a, b) => {
      const ra = ranks[String(a.id)] ?? 0;
      const rb = ranks[String(b.id)] ?? 0;
      return ra - rb;
    });
  }, [plans, ranks]);

  if (sortedPaidPlans.length === 0) {
    // 后台无启用付费套餐时不渲染对比表
    return null;
  }

  // 行：与「我的会员权益」3 实卡同源；free 列改从 freeQuota（管理后台「免费会员额度配置」）取
  // [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30 C2/C5]
  //   权益项命名：「可管理健康档案」→「家庭守护成员」；不写「含本人/不含本人」
  const rows: Array<{
    key: string;
    label: string;
    free: number;
    getPaid: (p: PlanBrief) => number;
    fmt?: (v: number | null | undefined) => string;
  }> = [
    {
      key: 'max_managed',
      label: '家庭守护成员',
      free: freeVals.max_managed,
      getPaid: (p: PlanBrief) => p.max_managed,
      fmt: fmtArchiveVal,
    },
    {
      key: 'ai_outbound_call_count',
      label: 'AI 外呼提醒',
      free: freeVals.ai_outbound_call_count,
      getPaid: (p: PlanBrief) => p.ai_outbound_call_count,
    },
    {
      key: 'emergency_ai_call_count',
      label: '紧急 AI 呼叫',
      free: freeVals.emergency_ai_call_count,
      getPaid: (p: PlanBrief) => p.emergency_ai_call_count,
    },
  ];

  const getPaidColor = (idx: number): string => {
    if (idx < PAID_GRADIENT.length) return PAID_GRADIENT[idx];
    return PAID_GRADIENT[PAID_GRADIENT.length - 1];
  };

  return (
    <div style={{ margin: '20px 16px 0' }} data-testid="mc-benefits-compare">
      {/* 标题：与「我的会员权益」标题风格统一 —— 紫色短竖条 + 黑色加粗 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 10,
          padding: '0 4px',
        }}
      >
        <span
          style={{
            display: 'inline-block',
            width: 4,
            height: 16,
            background: PRIMARY,
            borderRadius: 2,
          }}
        />
        <span style={{ fontSize: 16, fontWeight: 700, color: TEXT_DARK }}>权益对比</span>
      </div>

      {/* 白底圆角卡片 + 横向滚动 */}
      <div
        style={{
          background: '#fff',
          borderRadius: 16,
          padding: '4px 0',
          border: `1px solid ${BORDER_LIGHT}`,
          overflowX: 'auto',
          WebkitOverflowScrolling: 'touch',
        }}
        data-testid="mc-benefits-compare-scroll"
      >
        <table
          style={{
            width: '100%',
            minWidth: 320,
            borderCollapse: 'collapse',
            fontSize: 13,
          }}
        >
          <thead>
            <tr>
              <th
                style={{
                  padding: '12px 12px',
                  textAlign: 'left',
                  fontWeight: 600,
                  color: '#FFFFFF',
                  fontSize: 12,
                  background: PRIMARY,
                  borderBottom: `1px solid ${BORDER_LIGHT}`,
                  whiteSpace: 'nowrap',
                  minWidth: 96,
                }}
              >
                权益项
              </th>
              <th
                style={{
                  padding: '12px 12px',
                  textAlign: 'center',
                  fontWeight: 700,
                  color: '#FFFFFF',
                  fontSize: 13,
                  background: current.level === 'free' ? PRIMARY_DARK : PRIMARY,
                  borderBottom: `1px solid ${BORDER_LIGHT}`,
                  whiteSpace: 'nowrap',
                  minWidth: 96,
                  position: 'relative',
                }}
                data-testid="mc-compare-col-free"
                data-current={current.level === 'free' ? '1' : '0'}
              >
                {current.level === 'free' && (
                  <div
                    style={{
                      position: 'absolute',
                      top: -10,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      background: '#FFFFFF',
                      color: PRIMARY,
                      fontSize: 10,
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 999,
                      border: `1px solid ${PRIMARY}`,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    当前
                  </div>
                )}
                免费会员
              </th>
              {sortedPaidPlans.map((p, idx) => {
                const color = getPaidColor(idx);
                const isCurrent = current.level === 'paid' && current.plan_id === p.id;
                return (
                  <th
                    key={p.id}
                    style={{
                      padding: '12px 12px',
                      textAlign: 'center',
                      fontWeight: 700,
                      color: isCurrent ? '#FFFFFF' : color,
                      fontSize: 13,
                      background: isCurrent ? PRIMARY : '#FFFFFF',
                      borderBottom: `1px solid ${BORDER_LIGHT}`,
                      whiteSpace: 'nowrap',
                      minWidth: 96,
                      position: 'relative',
                    }}
                    data-testid={`mc-compare-col-${p.id}`}
                    data-current={isCurrent ? '1' : '0'}
                  >
                    {isCurrent && (
                      <div
                        style={{
                          position: 'absolute',
                          top: -10,
                          left: '50%',
                          transform: 'translateX(-50%)',
                          background: '#FFFFFF',
                          color: PRIMARY,
                          fontSize: 10,
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 999,
                          border: `1px solid ${PRIMARY}`,
                          whiteSpace: 'nowrap',
                        }}
                      >
                        当前
                      </div>
                    )}
                    {p.name}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={r.key} data-testid={`mc-compare-row-${r.key}`}>
                <td
                  style={{
                    padding: '12px 12px',
                    color: TEXT_GRAY,
                    borderBottom: ri < rows.length - 1 ? `1px solid ${BORDER_LIGHT}` : 'none',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {r.label}
                </td>
                <td
                  style={{
                    padding: '12px 12px',
                    textAlign: 'center',
                    color: current.level === 'free' ? PRIMARY_DARK : TEXT_GRAY,
                    fontWeight: current.level === 'free' ? 700 : 400,
                    background: current.level === 'free' ? PRIMARY_BG_LIGHT : 'transparent',
                    borderBottom: ri < rows.length - 1 ? `1px solid ${BORDER_LIGHT}` : 'none',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {(r.fmt || fmtVal)(r.free)}
                </td>
                {sortedPaidPlans.map((p, idx) => {
                  const color = getPaidColor(idx);
                  const isCurrent = current.level === 'paid' && current.plan_id === p.id;
                  return (
                    <td
                      key={p.id}
                      style={{
                        padding: '12px 12px',
                        textAlign: 'center',
                        color: isCurrent ? PRIMARY_DARK : color,
                        fontWeight: 700,
                        background: isCurrent ? PRIMARY_BG_LIGHT : 'transparent',
                        borderBottom: ri < rows.length - 1 ? `1px solid ${BORDER_LIGHT}` : 'none',
                        whiteSpace: 'nowrap',
                      }}
                      data-testid={`mc-compare-cell-${r.key}-${p.id}`}
                    >
                      {(r.fmt || fmtVal)(r.getPaid(p))}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

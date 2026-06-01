'use client';

/**
 * [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药提醒页（打卡主页面）
 *
 * 路由：/ai-home/medication-reminder
 *
 * 功能：
 *  - 顶部 Banner：今日 · MM 月 DD 日 周 X + 大字「还有 X 次用药」+ 下一次提醒 + 三统计
 *  - 即将服用：橙色高亮卡片 + 「立即服用」主按钮 + 倒计时
 *  - 时间线：按时间排序，状态徽章（done/upcoming/pending）
 *  - 打卡：调 POST /api/medication-check-in；撤销：POST /api/medication-check-in/:id/revoke
 *  - 右下浮动 + 按钮 → /ai-home/medication-plans/new
 *  - ← 返回 → /health-profile?focus=medication
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';

interface TimelineItem {
  plan_id: number;
  scheduled_time: string;
  // [BUG-MED-V1 2026-05-21 Bug3] 新增 overdue 状态（已超时未打卡）
  status: 'done' | 'upcoming' | 'pending' | 'overdue';
  actual_time?: string | null;
  name: string;
  dosage?: string;
  timing?: string;
  check_in_id?: number | null;
}

interface BannerData {
  date_str: string;
  total_remaining: number;
  next_reminder: { time: string; name: string } | null;
  done_count: number;
  remaining_count: number;
  total_today?: number;
  // [BUG-MED-V1 2026-05-21 Bug2] 新增「今日完成率」，前端展示此字段替代 monthly_compliance
  today_completion_rate?: number;
  monthly_compliance: number;
}

interface TodayResponse {
  banner: BannerData;
  upcoming: {
    plan_id: number;
    name: string;
    scheduled_time: string;
    dosage?: string;
    timing?: string;
  } | null;
  timeline: TimelineItem[];
}

const ORANGE = '#FF8A3D';
const GREEN = '#22c55e';
const BLUE = '#4A9EE0';
const GRAY = '#94A3B8';
// [BUG-MED-V1 2026-05-21 Bug3] 已超时颜色
const RED = '#EF4444';
const TEXT = '#111827';
const SUB = '#6B7280';

export default function MedicationReminderPage() {
  const router = useRouter();
  const [data, setData] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState<Date>(new Date());
  const reloadingRef = useRef(false);

  const load = useCallback(async () => {
    if (reloadingRef.current) return;
    reloadingRef.current = true;
    try {
      // [PRD-MED-OPTIM-V2 2026-05-21 优化点3] consultant_id 仅从 URL 参数获取，不从 sessionStorage 读取。
      // [BUGFIX-AI-HOME-BELL-SELF-V2 2026-06-01] 无参兜底为本人(0)，与铃铛口径保持 100% 一致。
      //   后端语义：不传 = 不过滤（本人+全部家庭成员），0 = 仅本人。无参默认本人，避免混入家庭成员用药。
      //   只有从首页带参跳转（如 ?consultant_id=5）时才按指定成员过滤。
      let consultantId: string = '';
      try {
        if (typeof window !== 'undefined') {
          const urlParams = new URLSearchParams(window.location.search);
          const urlCid = urlParams.get('consultant_id');
          if (urlCid !== null && urlCid !== '') {
            consultantId = urlCid;
          }
        }
      } catch {
        consultantId = '';
      }
      const qs = consultantId !== ''
        ? `?consultant_id=${encodeURIComponent(consultantId)}`
        : '?consultant_id=0';
      const res: any = await api.get(`/api/medication-plans/today${qs}`);
      setData(res.data || res);
    } catch (e: any) {
      showToast('加载失败，请稍后重试', 'fail');
    } finally {
      setLoading(false);
      reloadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => setNow(new Date()), 30 * 1000);
    return () => clearInterval(t);
  }, [load]);

  const handleCheckIn = async (planId: number, scheduledTime: string) => {
    try {
      await api.post('/api/medication-check-in', { plan_id: planId, scheduled_time: scheduledTime });
      showToast('已打卡');
      load();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '打卡失败', 'fail');
    }
  };

  const handleRevoke = async (item: TimelineItem) => {
    if (!item.check_in_id) return;
    const confirmed = await Dialog.confirm({
      content: `确认撤销「${item.name} ${item.scheduled_time}」的打卡？仅 5 分钟内可撤销。`,
    });
    if (!confirmed) return;
    try {
      await api.post(`/api/medication-check-in/${item.check_in_id}/revoke`);
      showToast('已撤销');
      load();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const code = typeof detail === 'object' ? detail?.code : '';
      showToast(code === 'REVOKE_TIMEOUT' ? '超过 5 分钟，无法撤销' : '撤销失败', 'fail');
    }
  };

  const goBack = () => router.push('/health-profile?focus=medication');

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: SUB }}>加载中…</div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: SUB }}>暂无数据</div>
    );
  }

  const { banner, upcoming, timeline } = data;

  return (
    <div
      data-testid="med-reminder-page"
      style={{ minHeight: '100vh', background: '#F4F6F9', paddingBottom: 100 }}
    >
      {/* 顶部 NavBar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '12px 16px',
          background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        }}
      >
        <span
          onClick={goBack}
          style={{ fontSize: 24, color: TEXT, cursor: 'pointer', padding: 4 }}
          data-testid="med-reminder-back"
        >
          ←
        </span>
        <span style={{ flex: 1, textAlign: 'center', fontSize: 16, fontWeight: 600 }}>
          用药提醒
        </span>
        <span style={{ width: 32 }} />
      </div>

      {/* Banner */}
      <div
        style={{
          margin: 16,
          padding: 20,
          borderRadius: 16,
          background: 'linear-gradient(135deg, #4A9EE0 0%, #22c55e 100%)',
          color: '#fff',
        }}
        data-testid="med-reminder-banner"
      >
        <div style={{ fontSize: 13, opacity: 0.92 }}>{banner.date_str}</div>
        <div style={{ fontSize: 32, fontWeight: 700, marginTop: 8 }}>
          {banner.total_remaining > 0 ? `还有 ${banner.total_remaining} 次用药` : '今日用药已完成'}
        </div>
        {banner.next_reminder && (
          <div style={{ fontSize: 13, marginTop: 8, opacity: 0.92 }}>
            下一次提醒：{banner.next_reminder.time} · {banner.next_reminder.name}
          </div>
        )}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 16,
            paddingTop: 12,
            borderTop: '1px solid rgba(255,255,255,0.3)',
          }}
        >
          <Stat label="已服用" value={banner.done_count} />
          <Stat label="待服用" value={banner.remaining_count} />
          {/* [BUG-MED-V1 2026-05-21 Bug2] 「本月依从」改为「今日完成率」 */}
          <Stat
            label="今日完成率"
            value={`${banner.today_completion_rate ?? 0}%`}
          />
        </div>
      </div>

      {/* 即将服用 */}
      {upcoming && (
        <div
          data-testid="med-reminder-upcoming"
          style={{
            margin: '0 16px 16px',
            padding: 16,
            borderRadius: 12,
            background: '#FFF7ED',
            border: `1px solid ${ORANGE}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                background: ORANGE,
                color: '#fff',
                fontSize: 11,
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 10,
              }}
            >
              即将
            </span>
            <span style={{ fontSize: 15, fontWeight: 600, color: TEXT }}>{upcoming.name}</span>
          </div>
          <div style={{ marginTop: 8, fontSize: 13, color: SUB }}>
            {upcoming.dosage && <span>{upcoming.dosage} · </span>}
            {upcoming.timing && <span>{upcoming.timing} · </span>}
            <span>计划时间 {upcoming.scheduled_time}</span>
          </div>
          <button
            onClick={() => handleCheckIn(upcoming.plan_id, upcoming.scheduled_time)}
            data-testid="med-reminder-checkin-btn"
            style={{
              marginTop: 12,
              width: '100%',
              padding: '12px 0',
              background: ORANGE,
              color: '#fff',
              border: 'none',
              borderRadius: 24,
              fontSize: 15,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            立即服用
          </button>
        </div>
      )}

      {/* 时间线 */}
      <div style={{ margin: '0 16px' }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: TEXT, margin: '8px 0' }}>今日时间线</div>
        {timeline.length === 0 ? (
          <div
            style={{
              background: '#fff',
              padding: 32,
              borderRadius: 12,
              textAlign: 'center',
              color: SUB,
              fontSize: 14,
            }}
          >
            今日暂无用药安排
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {timeline.map((it, idx) => (
              <TimelineRow
                key={`${it.plan_id}-${it.scheduled_time}-${idx}`}
                item={it}
                onCheckIn={() => handleCheckIn(it.plan_id, it.scheduled_time)}
                onRevoke={() => handleRevoke(it)}
              />
            ))}
          </div>
        )}
      </div>

      {/* 浮动 + 按钮 */}
      <div
        onClick={() => router.push('/ai-home/medication-plans/new')}
        data-testid="med-reminder-fab"
        style={{
          position: 'fixed',
          right: 20,
          bottom: 24,
          width: 56,
          height: 56,
          borderRadius: 28,
          background: BLUE,
          color: '#fff',
          fontSize: 28,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px rgba(74,158,224,0.4)',
          cursor: 'pointer',
        }}
      >
        +
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 20, fontWeight: 700 }}>{value}</div>
      <div style={{ fontSize: 11, opacity: 0.85, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function TimelineRow({
  item,
  onCheckIn,
  onRevoke,
}: {
  item: TimelineItem;
  onCheckIn: () => void;
  onRevoke: () => void;
}) {
  // [BUG-MED-V1 2026-05-21 Bug3] 状态颜色 + 文案 + 已超时
  const dot =
    item.status === 'done'
      ? GREEN
      : item.status === 'upcoming'
      ? ORANGE
      : item.status === 'overdue'
      ? RED
      : GRAY;
  const badgeText =
    item.status === 'done'
      ? '已服用'
      : item.status === 'upcoming'
      ? '即将服用'
      : item.status === 'overdue'
      ? '⚠️ 已超时'
      : '未到时间';
  return (
    <div
      data-testid={`med-timeline-${item.plan_id}-${item.scheduled_time}`}
      style={{
        background: '#fff',
        padding: 14,
        borderRadius: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
      }}
    >
      <div style={{ width: 56, textAlign: 'center' }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: TEXT }}>{item.scheduled_time}</div>
        <div
          style={{
            display: 'inline-block',
            marginTop: 4,
            width: 8,
            height: 8,
            borderRadius: 4,
            background: dot,
          }}
        />
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: TEXT }}>{item.name}</div>
        <div style={{ fontSize: 12, color: SUB, marginTop: 2 }}>
          {item.dosage && <span>{item.dosage} · </span>}
          {item.timing}
        </div>
      </div>
      <div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: dot,
            padding: '2px 8px',
            borderRadius: 10,
            background: '#F3F4F6',
            display: 'inline-block',
            marginRight: 8,
          }}
        >
          {badgeText}
        </span>
        {item.status === 'done' ? (
          <button
            onClick={onRevoke}
            data-testid={`med-revoke-${item.check_in_id}`}
            style={{
              padding: '6px 12px',
              background: '#fff',
              border: `1px solid ${GREEN}`,
              color: GREEN,
              borderRadius: 14,
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            ✓ 完成
          </button>
        ) : (
          <button
            onClick={onCheckIn}
            data-testid={`med-checkin-${item.plan_id}-${item.scheduled_time}`}
            style={{
              padding: '6px 12px',
              background:
                item.status === 'overdue'
                  ? RED
                  : item.status === 'upcoming'
                  ? ORANGE
                  : BLUE,
              color: '#fff',
              border: 'none',
              borderRadius: 14,
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            {item.status === 'overdue' ? '补打卡' : '打卡'}
          </button>
        )}
      </div>
    </div>
  );
}

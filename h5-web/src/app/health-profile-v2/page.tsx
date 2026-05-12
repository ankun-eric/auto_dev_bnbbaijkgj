'use client';

/**
 * [PRD-469 2026-05-12] 健康档案 v2 优化 —— 对齐 v5 设计稿
 *
 * 信息架构：
 *   家庭成员条（"+"按钮）→ Hero 卡 → 我的设备 → 粘性 5 Tab（滚动联动）
 *     Tab 1 今日数据 6 宫格
 *     Tab 2 健康信息（既往病史 / 过敏史 / 家族病史 / 个人习惯）
 *     Tab 3 用药计划
 *     Tab 4 共管与提醒
 *     Tab 5 健康事件
 *
 * 视觉规范：v5 健康绿主色 + 圆角 12/16px + 病历卡左侧 3px 竖线
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import NewFamilyMemberModal from '@/components/health-profile-v5/NewFamilyMemberModal';
import DeviceListBlock from '@/components/health-profile-v5/DeviceListBlock';
import HealthInfoBlock from '@/components/health-profile-v5/HealthInfoBlock';
import CareReminderBlock from '@/components/health-profile-v5/CareReminderBlock';
import HealthEventsBlock from '@/components/health-profile-v5/HealthEventsBlock';

// ─── v5 设计 Token（健康绿主色） ──────────────────────────────────────────
const T = {
  brand50: '#f0fdf4',
  brand100: '#dcfce7',
  brand200: '#bbf7d0',
  brand300: '#86efac',
  brand400: '#4ade80',
  brand500: '#22c55e',
  brand600: '#16a34a',
  brand700: '#15803d',
  brand800: '#166534',
  yellow: '#f59e0b',
  warn: '#ef4444',
  textPrimary: '#1f2937',
  textSecondary: '#6b7280',
  cardLineGreen: '3px solid #22c55e',
  cardLineYellow: '3px solid #f59e0b',
  shadow: '0 2px 8px rgba(0,0,0,0.06)',
  gradient: 'linear-gradient(135deg, #4ade80 0%, #16a34a 100%)',
};

const TAB_LIST = [
  { id: 'today-data', label: '今日数据' },
  { id: 'health-info', label: '健康信息' },
  { id: 'medication-plan', label: '用药计划' },
  { id: 'care-reminder', label: '共管与提醒' },
  { id: 'health-events', label: '健康事件' },
];

interface FamilyMember {
  id: number;
  user_id: number;
  is_self: boolean;
  nickname: string;
  relationship_type?: string;
  relation_type_name?: string;
  birthday?: string;
  gender?: string;
  height?: number;
  weight?: number;
  member_user_id?: number | null;
}

interface HealthProfileBasic {
  id: number;
  name?: string;
  gender?: string;
  birthday?: string;
  height?: number | null;
  weight?: number | null;
  blood_type?: string;
}

interface MetricSnapshot {
  metric_type: string;
  value: Record<string, any> | null;
  measured_at: string | null;
  source: string | null;
  is_abnormal: boolean;
}

interface TodayMetricsResponse {
  profile_id: number;
  blood_pressure: MetricSnapshot;
  blood_glucose: MetricSnapshot;
  heart_rate: MetricSnapshot;
  sleep: MetricSnapshot;
  spo2: MetricSnapshot;
  medication: { checked: number; total: number; has_overdue: boolean };
}

interface MedicationPlanCard {
  plan_id: number;
  drug_name: string;
  dosage?: string;
  schedule: string[];
  time_chips: { scheduled_time: string; checked: boolean }[];
  weekly_completed: number;
  weekly_total: number;
  weekly_rate: number;
}

// ─── 病历卡组件（v5 风格） ─────────────────────────────────────────────────
export function V5Card({
  children,
  abnormal = false,
  onClick,
  testid,
  style,
}: {
  children: React.ReactNode;
  abnormal?: boolean;
  onClick?: () => void;
  testid?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      data-testid={testid}
      onClick={onClick}
      style={{
        background: '#FFFFFF',
        borderLeft: abnormal ? T.cardLineYellow : T.cardLineGreen,
        borderRadius: 12,
        padding: 16,
        boxShadow: T.shadow,
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export const HP_V5_TOKEN = T;

export default function HealthProfileV2Page() {
  const router = useRouter();

  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [profile, setProfile] = useState<HealthProfileBasic | null>(null);
  const [todayMetrics, setTodayMetrics] = useState<TodayMetricsResponse | null>(null);
  const [medications, setMedications] = useState<MedicationPlanCard[]>([]);
  const [activeTab, setActiveTab] = useState<string>('today-data');
  const isScrollingRef = useRef(false);
  const [isLinked, setIsLinked] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);

  const fetchMembers = useCallback(async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      const items: FamilyMember[] = Array.isArray(data.items) ? data.items : [];
      setMembers(items);
      if (items.length > 0 && selectedMemberId == null) {
        const self = items.find((m) => m.is_self) || items[0];
        setSelectedMemberId(self.id);
      }
    } catch {
      setMembers([]);
    }
  }, [selectedMemberId]);

  const fetchProfile = useCallback(async (memberId: number) => {
    try {
      const res: any = await api.get(`/api/health/profile/member/${memberId}`);
      const data = res.data || res;
      setProfile(data);
      return data?.id as number | undefined;
    } catch {
      setProfile(null);
      return undefined;
    }
  }, []);

  const fetchTodayMetrics = useCallback(async (profileId: number) => {
    try {
      const res: any = await api.get(`/api/health-profile-v3/${profileId}/today-metrics`);
      const data = res.data || res;
      setTodayMetrics(data);
    } catch {
      setTodayMetrics(null);
    }
  }, []);

  const fetchMedication = useCallback(async (profileId: number) => {
    try {
      const res: any = await api.get(`/api/health-profile-v3/${profileId}/medication-plan`);
      const data = res.data || res;
      setMedications(Array.isArray(data.items) ? data.items : []);
    } catch {
      setMedications([]);
    }
  }, []);

  const fetchLinkStatus = useCallback(async (memberId: number) => {
    try {
      const res: any = await api.get('/api/family/management');
      const data = res.data || res;
      const items = Array.isArray(data.items) ? data.items : [];
      setIsLinked(items.some((it: any) => it.managed_member_id === memberId && it.status === 'active'));
    } catch {
      setIsLinked(false);
    }
  }, []);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  useEffect(() => {
    if (selectedMemberId == null) return;
    (async () => {
      const profileId = await fetchProfile(selectedMemberId);
      if (profileId != null) {
        await Promise.all([
          fetchTodayMetrics(profileId),
          fetchMedication(profileId),
          fetchLinkStatus(selectedMemberId),
        ]);
      }
    })();
  }, [selectedMemberId, fetchProfile, fetchTodayMetrics, fetchMedication, fetchLinkStatus]);

  // [PRD-469 M5] 修复：从添加用药页返回时，强制刷新用药计划
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        const flag = sessionStorage.getItem('medication_changed');
        if (flag && profile?.id != null) {
          sessionStorage.removeItem('medication_changed');
          fetchMedication(profile.id);
        }
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);
    // 挂载时也检测一次
    onVisible();
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }, [profile?.id, fetchMedication]);

  // 滚动联动 Tab
  useEffect(() => {
    const onScroll = () => {
      if (isScrollingRef.current) return;
      const trigger = window.innerHeight / 3 + 60;
      for (const tab of TAB_LIST) {
        const el = document.getElementById(tab.id);
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        if (rect.top <= trigger && rect.bottom >= trigger) {
          setActiveTab(tab.id);
          break;
        }
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleTabClick = useCallback((id: string) => {
    setActiveTab(id);
    isScrollingRef.current = true;
    const el = document.getElementById(id);
    if (el) {
      const top = el.getBoundingClientRect().top + window.scrollY - 100;
      window.scrollTo({ top, behavior: 'smooth' });
    }
    setTimeout(() => { isScrollingRef.current = false; }, 800);
  }, []);

  const selectedMember = useMemo(
    () => members.find((m) => m.id === selectedMemberId) || null,
    [members, selectedMemberId]
  );

  // ─── 成员条（头像化 + "+" 添加按钮）─────────────────────────────────
  const renderMemberBar = () => (
    <div
      data-testid="prd469-member-bar"
      style={{ background: T.brand50, padding: '12px 16px', display: 'flex', gap: 12, overflowX: 'auto' }}
    >
      {members.map((m) => {
        const active = m.id === selectedMemberId;
        const hasLink = !!m.member_user_id;
        const avatar = m.is_self ? '🙂' : relationEmoji(m.relation_type_name || m.relationship_type || '');
        return (
          <div
            key={m.id}
            onClick={() => setSelectedMemberId(m.id)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              minWidth: 64, cursor: 'pointer', position: 'relative',
            }}
          >
            <div
              style={{
                width: 48, height: 48, borderRadius: '50%',
                background: active ? T.brand500 : '#fff',
                color: active ? '#fff' : T.brand700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 22, fontWeight: 600,
                border: active ? `2px solid ${T.brand600}` : `1px solid ${T.brand200}`,
                boxShadow: active ? '0 4px 12px rgba(34,197,94,0.25)' : 'none',
              }}
            >{avatar}</div>
            {hasLink && (
              <div
                style={{
                  width: 10, height: 10, borderRadius: '50%', background: T.brand500,
                  position: 'absolute', top: 0, right: 6, border: '2px solid #fff',
                }}
              />
            )}
            <span style={{ fontSize: 13, color: T.brand800, marginTop: 4 }}>
              {m.is_self ? '本人' : (m.relation_type_name || m.nickname)}
            </span>
          </div>
        );
      })}
      <div
        onClick={() => setShowAddMember(true)}
        data-testid="prd469-add-member-btn"
        style={{
          minWidth: 64, display: 'flex', flexDirection: 'column',
          alignItems: 'center', cursor: 'pointer',
        }}
      >
        <div
          style={{
            width: 48, height: 48, borderRadius: '50%',
            background: '#fff', border: `2px dashed ${T.brand400}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24, color: T.brand500,
          }}
        >+</div>
        <span style={{ fontSize: 13, color: T.brand800, marginTop: 4 }}>添加</span>
      </div>
    </div>
  );

  // ─── Hero ──────────────────────────────────────────────────────────
  const renderHero = () => {
    if (!profile) return null;
    const age = profile.birthday ? calcAge(profile.birthday) : null;
    const fields = [
      { label: '性别', value: profile.gender || '未填' },
      { label: '年龄', value: age != null ? `${age} 岁` : '未填' },
      { label: '身高', value: profile.height ? `${profile.height} cm` : '未填' },
      { label: '体重', value: profile.weight ? `${profile.weight} kg` : '未填' },
      { label: '血型', value: profile.blood_type || '未填' },
    ];
    return (
      <div style={{ padding: '12px 16px' }}>
        <div
          data-testid="prd469-hero-card"
          style={{
            background: T.gradient, color: '#fff', borderRadius: 16, padding: 20,
            boxShadow: T.shadow,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div
              style={{
                width: 64, height: 64, borderRadius: '50%',
                background: 'rgba(255,255,255,0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 32, fontWeight: 700,
              }}
            >
              {selectedMember?.is_self ? '🙂' : relationEmoji(selectedMember?.relation_type_name || '')}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>{profile.name || '未填'}</div>
              <div style={{ fontSize: 13, opacity: 0.9 }}>
                {selectedMember?.is_self ? '本人' : (selectedMember?.relation_type_name || '家庭成员')}
                {isLinked && (
                  <span
                    style={{
                      marginLeft: 8, padding: '2px 8px', borderRadius: 10,
                      background: 'rgba(255,255,255,0.3)', fontSize: 11, fontWeight: 600,
                    }}
                  >✓ 已关联</span>
                )}
              </div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8, marginTop: 16 }}>
            {fields.map((f) => (
              <div key={f.label} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, opacity: 0.85 }}>{f.label}</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{f.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // ─── 粘性 Tab ──────────────────────────────────────────────────────
  const renderStickyTabs = () => (
    <div
      data-testid="prd469-sticky-tabs"
      style={{
        position: 'sticky', top: 56, zIndex: 10, background: '#fff',
        borderBottom: `1px solid ${T.brand200}`,
      }}
    >
      <div style={{ display: 'flex', overflowX: 'auto' }}>
        {TAB_LIST.map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => handleTabClick(t.id)}
              data-testid={`prd469-tab-${t.id}`}
              style={{
                flex: '0 0 auto', padding: '12px 16px',
                background: 'none', border: 'none',
                fontSize: 16, fontWeight: active ? 700 : 500,
                color: active ? T.brand600 : T.textSecondary,
                borderBottom: active ? `2px solid ${T.brand600}` : '2px solid transparent',
                cursor: 'pointer',
              }}
            >{t.label}</button>
          );
        })}
      </div>
    </div>
  );

  // ─── Tab 1：今日数据 6 宫格 ─────────────────────────────────────────
  const renderTodayMetrics = () => {
    const tm = todayMetrics;
    const cells = [
      {
        id: 'blood_pressure',
        label: '血压',
        unit: 'mmHg',
        icon: '💓',
        value: tm?.blood_pressure?.value
          ? `${tm.blood_pressure.value.systolic || '-'}/${tm.blood_pressure.value.diastolic || '-'}`
          : '—',
        abnormal: tm?.blood_pressure?.is_abnormal,
      },
      {
        id: 'blood_glucose',
        label: '血糖',
        unit: 'mmol/L',
        icon: '🩸',
        value: tm?.blood_glucose?.value?.value ?? '—',
        abnormal: tm?.blood_glucose?.is_abnormal,
      },
      {
        id: 'heart_rate',
        label: '心率',
        unit: 'bpm',
        icon: '❤️',
        value: tm?.heart_rate?.value?.value ?? '—',
        abnormal: tm?.heart_rate?.is_abnormal,
      },
      {
        id: 'sleep',
        label: '睡眠',
        unit: 'h',
        icon: '🌙',
        value: tm?.sleep?.value?.duration_h ?? '—',
        abnormal: tm?.sleep?.is_abnormal,
      },
      {
        id: 'spo2',
        label: '血氧',
        unit: '%',
        icon: '🫁',
        value: tm?.spo2?.value?.value ?? '—',
        abnormal: tm?.spo2?.is_abnormal,
      },
    ];

    return (
      <div id="today-data" data-testid="prd469-today-data" style={{ padding: '12px 16px' }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>今日数据</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          {cells.map((c) => (
            <V5Card
              key={c.id}
              abnormal={!!c.abnormal}
              testid={`prd469-metric-${c.id}`}
              onClick={() => router.push(`/health-metric/${c.id}?profileId=${profile?.id || ''}`)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <span style={{ fontSize: 13, color: T.textSecondary }}>{c.icon} {c.label}</span>
                {c.abnormal && (
                  <span
                    style={{
                      fontSize: 11, fontWeight: 600, color: '#fff', background: T.yellow,
                      padding: '2px 6px', borderRadius: 6,
                    }}
                  >异常</span>
                )}
              </div>
              <div style={{ marginTop: 8 }}>
                <span style={{ fontSize: 22, fontWeight: 700, color: T.textPrimary }}>{c.value}</span>
                <span style={{ fontSize: 13, color: T.textSecondary, marginLeft: 4 }}>{c.unit}</span>
              </div>
              <div style={{ position: 'absolute', top: 12, right: 12, fontSize: 14, color: T.brand500 }}>›</div>
            </V5Card>
          ))}
          <V5Card
            abnormal={!!tm?.medication?.has_overdue}
            testid="prd469-metric-medication"
            onClick={() => handleTabClick('medication-plan')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <span style={{ fontSize: 13, color: T.textSecondary }}>💊 用药提醒</span>
              {tm?.medication?.has_overdue && (
                <span
                  style={{
                    fontSize: 11, fontWeight: 600, color: '#fff', background: T.yellow,
                    padding: '2px 6px', borderRadius: 6,
                  }}
                >待服</span>
              )}
            </div>
            <div style={{ marginTop: 8 }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: T.textPrimary }}>
                {tm?.medication?.checked ?? 0}/{tm?.medication?.total ?? 0}
              </span>
              <span style={{ fontSize: 13, color: T.textSecondary, marginLeft: 4 }}>已服</span>
            </div>
            <div style={{ height: 6, background: T.brand100, borderRadius: 3, marginTop: 8 }}>
              <div
                style={{
                  width: `${tm?.medication?.total ? (tm.medication.checked / tm.medication.total) * 100 : 0}%`,
                  height: '100%', background: T.brand500, borderRadius: 3,
                }}
              />
            </div>
          </V5Card>
        </div>
      </div>
    );
  };

  // ─── Tab 3：用药计划 ───────────────────────────────────────────────
  const renderMedicationPlan = () => (
    <div id="medication-plan" data-testid="prd469-medication-plan" style={{ padding: '12px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '8px 0 12px' }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: 0 }}>用药计划</h3>
        <button
          onClick={() => router.push('/health-plan/medications/add')}
          data-testid="prd469-add-medication-btn"
          style={{
            padding: '6px 14px', background: T.brand500, color: '#fff',
            border: 'none', borderRadius: 16, fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}
        >+ 添加用药</button>
      </div>
      {medications.length === 0 ? (
        <V5Card>
          <div style={{ textAlign: 'center', color: T.textSecondary, padding: '24px 0', fontSize: 14 }}>
            暂无用药计划
            <div
              onClick={() => router.push('/health-plan/medications/add')}
              style={{
                marginTop: 12, padding: '10px 20px', background: T.brand500, color: '#fff',
                borderRadius: 22, display: 'inline-block', cursor: 'pointer', fontSize: 14,
              }}
            >+ 添加用药</div>
          </div>
        </V5Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {medications.map((m) => (
            <V5Card key={m.plan_id} testid={`prd469-med-${m.plan_id}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 17, fontWeight: 600, color: T.textPrimary }}>
                  💊 {m.drug_name} {m.dosage}
                </span>
                <span style={{ fontSize: 13, color: T.textSecondary }}>{`每日 ${m.schedule.length} 次`}</span>
              </div>
              <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
                {m.time_chips.map((c) => (
                  <div
                    key={c.scheduled_time}
                    style={{
                      padding: '8px 12px', borderRadius: 8,
                      background: c.checked ? T.brand100 : '#fee2e2',
                      color: c.checked ? T.brand700 : '#991b1b',
                      fontSize: 14, fontWeight: 600,
                    }}
                  >
                    {c.checked ? '✓ ' : '⏰ '}{c.scheduled_time}
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 13, color: T.textSecondary, marginBottom: 4 }}>
                  本周完成率 {m.weekly_rate}%（{m.weekly_completed}/{m.weekly_total}）
                </div>
                <div style={{ height: 6, background: T.brand100, borderRadius: 3 }}>
                  <div style={{ width: `${m.weekly_rate}%`, height: '100%', background: T.brand500, borderRadius: 3 }} />
                </div>
              </div>
            </V5Card>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div style={{ background: T.brand50, minHeight: '100vh', paddingBottom: 80 }}>
      <GreenNavBar>我的健康档案</GreenNavBar>
      {renderMemberBar()}
      {renderHero()}
      <DeviceListBlock token={T} />
      {renderStickyTabs()}
      {renderTodayMetrics()}
      <HealthInfoBlock profileId={profile?.id} token={T} />
      {renderMedicationPlan()}
      <CareReminderBlock profileId={profile?.id} token={T} isLinked={isLinked} />
      <HealthEventsBlock profileId={profile?.id} token={T} />

      {showAddMember && (
        <NewFamilyMemberModal
          onClose={() => setShowAddMember(false)}
          onSuccess={() => {
            setShowAddMember(false);
            fetchMembers();
            Toast.show({ content: '已添加家庭成员', icon: 'success' });
          }}
        />
      )}
    </div>
  );
}

// ──────────── 辅助：关系 emoji 映射 ─────────────────────────────────
function relationEmoji(name: string): string {
  const map: Record<string, string> = {
    '本人': '🙂', '爸爸': '👨', '妈妈': '👩',
    '老公': '🤵', '老婆': '👰', '儿子': '👦', '女儿': '👧',
    '哥哥': '🧑', '弟弟': '👨', '姐姐': '👩', '妹妹': '👧',
    '爷爷': '👴', '奶奶': '👵', '外公': '👴', '外婆': '👵',
    '其他': '🧑',
  };
  return map[name] || '🧑';
}

function calcAge(birthday: string): number | null {
  try {
    const b = new Date(birthday);
    if (Number.isNaN(b.getTime())) return null;
    const now = new Date();
    let age = now.getFullYear() - b.getFullYear();
    const m = now.getMonth() - b.getMonth();
    if (m < 0 || (m === 0 && now.getDate() < b.getDate())) age--;
    return age;
  } catch {
    return null;
  }
}

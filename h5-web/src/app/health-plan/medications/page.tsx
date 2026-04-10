'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Button, Dialog, Toast, SpinLoading, SwipeAction } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface MedicationItem {
  id: number;
  name: string;
  dosage: string;
  note: string;
  time: string;
  period: string;
  is_checked: boolean;
  checked_at: string | null;
}

interface PeriodGroup {
  period: string;
  label: string;
  emoji: string;
  time: string;
  items: MedicationItem[];
}

const PERIOD_META: Record<string, { label: string; emoji: string; order: number }> = {
  morning: { label: '早晨', emoji: '🌅', order: 0 },
  noon: { label: '中午', emoji: '🌞', order: 1 },
  evening: { label: '晚上', emoji: '🌙', order: 2 },
  bedtime: { label: '睡前', emoji: '😴', order: 3 },
};

function isPeriodPassed(time: string): boolean {
  if (!time) return false;
  const now = new Date();
  const [h, m] = time.split(':').map(Number);
  return now.getHours() > h || (now.getHours() === h && now.getMinutes() > m);
}

export default function MedicationsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState<PeriodGroup[]>([]);

  const fetchData = useCallback(async () => {
    try {
      const res: any = await api.get('/api/health-plan/medications');
      const data = res.data || res;
      const groupsData: Record<string, any[]> = data.groups || {};
      const result: PeriodGroup[] = [];
      Object.entries(groupsData).forEach(([period, items]: [string, any[]]) => {
        const meta = PERIOD_META[period] || { label: period, emoji: '💊', order: 99 };
        const mapped: MedicationItem[] = (items || []).map((r: any) => ({
          id: r.id,
          name: r.medicine_name,
          dosage: r.dosage || '',
          note: r.notes || '',
          time: r.remind_time || '',
          period: r.time_period || period,
          is_checked: r.today_checked || false,
          checked_at: null,
        }));
        result.push({
          period,
          label: meta.label,
          emoji: meta.emoji,
          time: mapped[0]?.time || '',
          items: mapped,
        });
      });
      const sorted = result.sort(
        (a, b) => (PERIOD_META[a.period]?.order ?? 99) - (PERIOD_META[b.period]?.order ?? 99)
      );
      setGroups(sorted);
    } catch {
      Toast.show({ content: '加载失败', icon: 'fail' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCheck = async (item: MedicationItem) => {
    try {
      await api.post(`/api/health-plan/medications/${item.id}/checkin`);
      Toast.show({ content: '打卡成功', icon: 'success' });
      fetchData();
    } catch {
      Toast.show({ content: '打卡失败', icon: 'fail' });
    }
  };

  const handleDelete = async (item: MedicationItem) => {
    const confirmed = await Dialog.confirm({ content: `确定删除「${item.name}」吗？` });
    if (confirmed) {
      try {
        await api.delete(`/api/health-plan/medications/${item.id}`);
        Toast.show({ content: '删除成功', icon: 'success' });
        fetchData();
      } catch {
        Toast.show({ content: '删除失败', icon: 'fail' });
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>用药提醒</NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>用药提醒</NavBar>

      <div className="px-4 py-4" style={{ background: 'linear-gradient(135deg, #fa8c16, #f5af19)' }}>
        <div className="text-white text-center">
          <div className="text-lg font-bold">💊 用药提醒</div>
          <div className="text-xs opacity-80 mt-1">按时服药，守护健康</div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        {groups.length === 0 ? (
          <Card style={{ borderRadius: 12, textAlign: 'center', padding: '40px 20px' }}>
            <div className="text-4xl mb-3">💊</div>
            <div className="text-gray-400 text-sm mb-4">暂无用药提醒</div>
            <Button
              color="primary"
              size="small"
              style={{ borderRadius: 20, background: 'linear-gradient(135deg, #fa8c16, #f5af19)', border: 'none' }}
              onClick={() => router.push('/health-plan/medications/add')}
            >
              添加用药提醒
            </Button>
          </Card>
        ) : (
          groups.map((group) => {
            const passed = isPeriodPassed(group.time);
            return (
              <Card
                key={group.period}
                style={{ borderRadius: 12, marginBottom: 12, opacity: passed ? 0.7 : 1 }}
              >
                <div className="flex items-center mb-3">
                  <span className="text-xl mr-2">{group.emoji}</span>
                  <span className="font-bold text-sm">{group.label}</span>
                  {group.time && (
                    <span className="ml-2 text-xs text-gray-400">{group.time}</span>
                  )}
                  {passed && (
                    <span className="ml-auto text-xs text-gray-400">已过时段</span>
                  )}
                </div>
                {group.items.map((item) => (
                  <SwipeAction
                    key={item.id}
                    rightActions={[
                      {
                        key: 'edit',
                        text: '编辑',
                        color: 'primary',
                        onClick: () => router.push(`/health-plan/medications/add?id=${item.id}`),
                      },
                      {
                        key: 'delete',
                        text: '删除',
                        color: 'danger',
                        onClick: () => handleDelete(item),
                      },
                    ]}
                  >
                    <div
                      className="flex items-center py-3 border-b border-gray-50 last:border-b-0"
                      onClick={() => !item.is_checked && handleCheck(item)}
                    >
                      <div
                        className="w-5 h-5 rounded-full border-2 flex items-center justify-center mr-3 shrink-0"
                        style={{
                          borderColor: item.is_checked ? '#52c41a' : '#ddd',
                          background: item.is_checked ? '#52c41a' : 'transparent',
                        }}
                      >
                        {item.is_checked && <span className="text-white text-xs">✓</span>}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className={`text-sm ${item.is_checked ? 'text-gray-400 line-through' : ''}`}>
                          {item.name}
                          {item.dosage && <span className="text-gray-400 ml-1">{item.dosage}</span>}
                        </div>
                        {item.note && (
                          <div className="text-xs text-gray-400 mt-0.5">{item.note}</div>
                        )}
                      </div>
                      {item.is_checked && (
                        <span className="text-xs text-green-500 ml-2">已服用</span>
                      )}
                    </div>
                  </SwipeAction>
                ))}
              </Card>
            );
          })
        )}
      </div>

      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white" style={{ maxWidth: 750, margin: '0 auto', boxShadow: '0 -2px 8px rgba(0,0,0,0.06)', paddingBottom: 'calc(16px + env(safe-area-inset-bottom))' }}>
        <Button
          block
          color="primary"
          size="large"
          style={{ borderRadius: 12, background: 'linear-gradient(135deg, #fa8c16, #f5af19)', border: 'none', height: 48 }}
          onClick={() => router.push('/health-plan/medications/add')}
        >
          <AddOutline /> 添加用药提醒
        </Button>
      </div>
    </div>
  );
}

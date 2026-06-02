'use client';

/**
 * [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 健康打卡（重做版）落地页
 *
 * 落地页直接是打卡首页：顶部横幅 + 总览卡 + 我的计划列表 + 右下角浮动「+」新建按钮。
 * 不再经过「用药提醒/健康打卡/自定义计划」三块的总目录页。
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, SpinLoading, Popover, Dialog, FloatingBubble, Button } from 'antd-mobile';
import { MoreOutline, AddOutline } from 'antd-mobile-icons';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface CheckInItem {
  id: number;
  name: string;
  repeat_frequency: string;
  weekly_target_count?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  status: string;
  today_completed?: boolean;
}

interface Overview {
  active_count: number;
  today_done_count: number;
  week_completion_rate: number;
}

function freqLabel(item: CheckInItem): string {
  if (item.repeat_frequency === 'weekly' && item.weekly_target_count) {
    return `每周 ${item.weekly_target_count} 次`;
  }
  return '每天';
}

function periodLabel(item: CheckInItem): string {
  if (!item.start_date && !item.end_date) return '长期';
  const s = item.start_date || '今起';
  const e = item.end_date || '不限期';
  return `${s} ~ ${e}`;
}

export default function HealthPlanLandingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<CheckInItem[]>([]);
  const [overview, setOverview] = useState<Overview>({
    active_count: 0,
    today_done_count: 0,
    week_completion_rate: 0,
  });
  const [checkingId, setCheckingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [listRes, ovRes] = await Promise.allSettled([
        api.get('/api/health-plan/checkin-items'),
        api.get('/api/health-plan/checkin-overview'),
      ]);
      const listData: any =
        listRes.status === 'fulfilled' ? ((listRes.value as any).data || listRes.value) : {};
      const ovData: any =
        ovRes.status === 'fulfilled' ? ((ovRes.value as any).data || ovRes.value) : {};
      setItems((listData.items || []) as CheckInItem[]);
      setOverview({
        active_count: ovData.active_count ?? 0,
        today_done_count: ovData.today_done_count ?? 0,
        week_completion_rate: ovData.week_completion_rate ?? 0,
      });
    } catch {
      showToast('加载失败', 'fail');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCheckin = async (item: CheckInItem) => {
    if (item.today_completed) return;
    setCheckingId(item.id);
    try {
      await api.post(`/api/health-plan/checkin-items/${item.id}/checkin`, {});
      showToast('打卡成功', 'success');
      load();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '打卡失败';
      showToast(String(msg), 'fail');
    } finally {
      setCheckingId(null);
    }
  };

  const handleEdit = (item: CheckInItem) => {
    router.push(`/health-plan/edit?id=${item.id}`);
  };

  const handleDelete = async (item: CheckInItem) => {
    const confirmed = await Dialog.confirm({
      title: '删除计划',
      content: `确定删除该计划吗？该计划的打卡记录也会一并清除。`,
      confirmText: '删除',
      cancelText: '取消',
    });
    if (!confirmed) return;
    try {
      await api.delete(`/api/health-plan/checkin-items/${item.id}`);
      showToast('已删除', 'success');
      load();
    } catch {
      showToast('删除失败', 'fail');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>健康计划</GreenNavBar>
        <div
          className="flex items-center justify-center"
          style={{ height: 'calc(100vh - 45px)' }}
        >
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen pb-24"
      style={{ background: '#F5F5F7' }}
      data-testid="health-plan-landing-v1"
    >
      <GreenNavBar>健康计划</GreenNavBar>

      {/* 顶部蓝紫色横幅 */}
      <div
        className="px-4 py-6"
        style={{
          background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
          color: '#fff',
        }}
      >
        <div className="text-xl font-bold mb-1">健康计划</div>
        <div className="text-xs opacity-90">每天一勾，养成更健康的自己</div>
      </div>

      {/* 总览卡 */}
      <div className="px-4 -mt-4">
        <Card
          style={{ borderRadius: 14, boxShadow: '0 4px 12px rgba(99,102,241,0.10)' }}
        >
          <div className="flex items-center justify-around text-center py-2">
            <div>
              <div className="text-xl font-bold" style={{ color: '#6366F1' }}>
                {overview.active_count}
              </div>
              <div className="text-xs text-gray-400 mt-1">进行中计划</div>
            </div>
            <div style={{ width: 1, height: 32, background: '#f0f0f0' }} />
            <div>
              <div className="text-xl font-bold" style={{ color: '#8B5CF6' }}>
                {overview.today_done_count}
              </div>
              <div className="text-xs text-gray-400 mt-1">今天已打卡</div>
            </div>
            <div style={{ width: 1, height: 32, background: '#f0f0f0' }} />
            <div>
              <div className="text-xl font-bold" style={{ color: '#A855F7' }}>
                {overview.week_completion_rate}%
              </div>
              <div className="text-xs text-gray-400 mt-1">本周完成率</div>
            </div>
          </div>
        </Card>
      </div>

      {/* 我的计划 */}
      <div className="px-4 pt-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-base font-bold">我的计划</div>
          <div
            className="text-xs cursor-pointer"
            style={{ color: '#6366F1' }}
            onClick={() => router.push('/health-plan/result')}
          >
            查看成果 ›
          </div>
        </div>

        {items.length === 0 ? (
          <Card style={{ borderRadius: 12, textAlign: 'center', padding: '40px 20px' }}>
            <div className="text-4xl mb-3">✅</div>
            <div className="text-gray-400 text-sm mb-4">还没有计划，创建一个开始打卡吧</div>
            <Button
              color="primary"
              style={{ borderRadius: 8, background: '#6366F1', border: 'none' }}
              onClick={() => router.push('/health-plan/edit')}
              data-testid="empty-create-btn"
            >
              新建计划
            </Button>
          </Card>
        ) : (
          items.map((item) => {
            const done = !!item.today_completed;
            return (
              <Card
                key={item.id}
                style={{ borderRadius: 12, marginBottom: 12, padding: 0 }}
                bodyStyle={{ padding: 0 }}
              >
                <div className="flex items-center p-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <div className="font-bold text-base truncate">{item.name}</div>
                      <Popover.Menu
                        actions={[
                          { key: 'edit', text: '编辑' },
                          { key: 'delete', text: '删除' },
                        ]}
                        onAction={(node: any) => {
                          if (node.key === 'edit') handleEdit(item);
                          else if (node.key === 'delete') handleDelete(item);
                        }}
                        placement="bottom-end"
                        trigger="click"
                      >
                        <div
                          className="px-2 py-1 cursor-pointer"
                          data-testid={`plan-more-${item.id}`}
                        >
                          <MoreOutline fontSize={20} color="#999" />
                        </div>
                      </Popover.Menu>
                    </div>
                    <div className="text-xs text-gray-400 mb-1">
                      {freqLabel(item)} · {periodLabel(item)}
                    </div>
                  </div>

                  <div className="ml-3 shrink-0">
                    <Button
                      size="small"
                      disabled={done}
                      loading={checkingId === item.id}
                      onClick={() => handleCheckin(item)}
                      style={{
                        borderRadius: 18,
                        height: 32,
                        minWidth: 72,
                        background: done
                          ? '#E5E7EB'
                          : 'linear-gradient(135deg, #6366F1, #8B5CF6)',
                        color: done ? '#9CA3AF' : '#fff',
                        border: 'none',
                        fontWeight: 600,
                      }}
                      data-testid={`plan-checkin-${item.id}`}
                    >
                      {done ? '已打卡' : '打卡'}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })
        )}
      </div>

      {/* 右下角浮动「+」按钮 */}
      <FloatingBubble
        style={{
          '--initial-position-bottom': '80px',
          '--initial-position-right': '24px',
          '--edge-distance': '24px',
          '--background': 'linear-gradient(135deg, #6366F1, #8B5CF6)',
        }}
        onClick={() => router.push('/health-plan/edit')}
        data-testid="floating-add-btn"
      >
        <AddOutline fontSize={28} />
      </FloatingBubble>
    </div>
  );
}

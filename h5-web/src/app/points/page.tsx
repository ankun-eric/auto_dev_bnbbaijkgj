'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Button, List, Tag, Toast, Grid, SpinLoading, InfiniteScroll } from 'antd-mobile';
import api from '@/lib/api';

interface PointRecord {
  id: number;
  type: string;
  points: number;
  description: string;
  created_at: string;
}

const CHECKIN_TYPE_ICONS: Record<string, string> = {
  checkin: '✅',
  medication_checkin: '💊',
  sign_in: '📅',
  task: '📋',
};

function getTypeLabel(type: string): string {
  const map: Record<string, string> = {
    checkin: '打卡',
    medication_checkin: '用药打卡',
    sign_in: '签到',
    task: '任务',
    redeem: '兑换',
  };
  return map[type] || type;
}

export default function PointsPage() {
  const router = useRouter();
  const [signedToday, setSignedToday] = useState(false);
  const [totalPoints, setTotalPoints] = useState(0);
  const [signDays, setSignDays] = useState(0);
  const [records, setRecords] = useState<PointRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);

  const fetchPointsData = useCallback(async () => {
    try {
      const [summaryRes, recordsRes]: any[] = await Promise.allSettled([
        api.get('/api/points/summary'),
        api.get('/api/points/records?page=1&per_page=20'),
      ]);
      if (summaryRes.status === 'fulfilled') {
        const summary = summaryRes.value?.data || summaryRes.value;
        setTotalPoints(summary?.total_points ?? 0);
        setSignDays(summary?.sign_days ?? 0);
        setSignedToday(summary?.signed_today ?? false);
      }
      if (recordsRes.status === 'fulfilled') {
        const data = recordsRes.value?.data || recordsRes.value;
        const items = data?.items || data?.records || data || [];
        setRecords(Array.isArray(items) ? items : []);
        setHasMore((data?.has_more ?? false) || (data?.total_pages > 1));
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPointsData(); }, [fetchPointsData]);

  const loadMore = async () => {
    const nextPage = page + 1;
    try {
      const res: any = await api.get(`/api/points/records?page=${nextPage}&per_page=20`);
      const data = res.data || res;
      const items = data?.items || data?.records || data || [];
      setRecords((prev) => [...prev, ...(Array.isArray(items) ? items : [])]);
      setPage(nextPage);
      setHasMore(data?.has_more ?? (nextPage < (data?.total_pages ?? 1)));
    } catch {
      // ignore
    }
  };

  const handleSign = async () => {
    if (signedToday) return;
    try {
      await api.post('/api/points/sign-in');
      setSignedToday(true);
      Toast.show({ content: '签到成功 +10积分' });
      fetchPointsData();
    } catch {
      Toast.show({ content: '签到失败', icon: 'fail' });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        积分中心
      </NavBar>

      <div
        className="px-4 py-6 text-center"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="text-white/70 text-sm">我的积分</div>
        <div className="text-white text-4xl font-bold my-2">{totalPoints}</div>
        <div className="text-white/70 text-xs">已连续签到 {signDays} 天</div>
      </div>

      <div className="px-4 -mt-4">
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">每日签到</div>
              <div className="text-xs text-gray-400 mt-1">连续签到7天额外奖励50积分</div>
            </div>
            <Button
              size="small"
              disabled={signedToday}
              onClick={handleSign}
              style={{
                background: signedToday ? '#e8e8e8' : 'linear-gradient(135deg, #52c41a, #13c2c2)',
                color: signedToday ? '#999' : '#fff',
                border: 'none',
                borderRadius: 20,
              }}
            >
              {signedToday ? '已签到' : '签到 +10'}
            </Button>
          </div>
          <div className="flex justify-between mt-4">
            {[1, 2, 3, 4, 5, 6, 7].map((d) => (
              <div key={d} className="text-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs ${
                    d <= signDays ? 'bg-primary text-white' : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {d <= signDays ? '✓' : d}
                </div>
                <div className="text-xs text-gray-400 mt-1">第{d}天</div>
              </div>
            ))}
          </div>
        </Card>

        <Grid columns={2} gap={12} style={{ marginBottom: 12 }}>
          <Grid.Item>
            <Card
              style={{ borderRadius: 12, textAlign: 'center' }}
              onClick={() => router.push('/points/mall')}
            >
              <div className="text-2xl mb-1">🎁</div>
              <div className="text-sm font-medium">积分商城</div>
              <div className="text-xs text-gray-400">好礼兑不停</div>
            </Card>
          </Grid.Item>
          <Grid.Item>
            <Card
              style={{ borderRadius: 12, textAlign: 'center' }}
              onClick={() => router.push('/health-plan')}
            >
              <div className="text-2xl mb-1">📋</div>
              <div className="text-sm font-medium">赚取积分</div>
              <div className="text-xs text-gray-400">完成任务得积分</div>
            </Card>
          </Grid.Item>
        </Grid>

        <div className="section-title">积分记录</div>
        <Card style={{ borderRadius: 12 }}>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <SpinLoading color="primary" />
            </div>
          ) : records.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-8">暂无积分记录</div>
          ) : (
            <List style={{ '--border-top': 'none', '--border-bottom': 'none', '--padding-left': '0' }}>
              {records.map((r) => {
                const isEarn = r.points > 0;
                const icon = CHECKIN_TYPE_ICONS[r.type] || (isEarn ? '🪙' : '🎁');
                return (
                  <List.Item
                    key={r.id}
                    prefix={<span style={{ fontSize: 20 }}>{icon}</span>}
                    extra={
                      <span
                        className="font-bold"
                        style={{ color: isEarn ? '#52c41a' : '#f5222d' }}
                      >
                        {isEarn ? '+' : ''}{r.points}
                      </span>
                    }
                    description={
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">
                          {r.created_at ? new Date(r.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                        {r.type === 'checkin' && (
                          <Tag color="success" fill="outline" style={{ fontSize: 10 }}>{getTypeLabel(r.type)}</Tag>
                        )}
                      </div>
                    }
                  >
                    <span className="text-sm">{r.description || getTypeLabel(r.type)}</span>
                  </List.Item>
                );
              })}
            </List>
          )}
          {!loading && records.length > 0 && (
            <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
          )}
        </Card>
      </div>
    </div>
  );
}

'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, List, InfiniteScroll, Empty, Tag } from 'antd-mobile';
import api from '@/lib/api';

interface PointsRecord {
  id: number;
  points: number;
  type: string;
  description?: string;
  created_at: string;
}

const TYPE_LABEL: Record<string, string> = {
  signin: '每日签到',
  checkin: '健康打卡',
  completeProfile: '完善档案',
  invite: '邀请奖励',
  firstOrder: '首次下单',
  reviewService: '订单评价',
  exchange: '积分兑换',
  consume: '积分消费',
};

export default function PointsRecordsPage() {
  const router = useRouter();
  const [records, setRecords] = useState<PointsRecord[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const loadMore = useCallback(async () => {
    try {
      const res: any = await api.get('/api/points/records', {
        params: { page, page_size: 20 },
      });
      const data = res?.data || res || {};
      const items: PointsRecord[] = data?.records || data?.items || data || [];
      setRecords((prev) => (page === 1 ? items : [...prev, ...items]));
      setHasMore(items.length >= 20);
      setPage((p) => p + 1);
    } catch {
      setHasMore(false);
    }
  }, [page]);

  useEffect(() => {
    // initial load
    loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        积分明细
      </NavBar>
      {records.length === 0 && !hasMore ? (
        <Empty description="暂无积分记录" style={{ marginTop: 80 }} />
      ) : (
        <List style={{ background: '#fff', marginTop: 8 }}>
          {records.map((r) => (
            <List.Item
              key={r.id}
              extra={
                <span
                  style={{
                    color: r.points >= 0 ? '#52c41a' : '#ff4d4f',
                    fontWeight: 600,
                  }}
                >
                  {r.points >= 0 ? '+' : ''}
                  {r.points}
                </span>
              }
              description={r.created_at?.replace('T', ' ').slice(0, 19)}
            >
              <div className="flex items-center gap-2">
                <span>{r.description || TYPE_LABEL[r.type] || r.type}</span>
                <Tag color="primary" fill="outline" style={{ fontSize: 10 }}>
                  {TYPE_LABEL[r.type] || r.type}
                </Tag>
              </div>
            </List.Item>
          ))}
        </List>
      )}
      <InfiniteScroll loadMore={loadMore} hasMore={hasMore} />
    </div>
  );
}

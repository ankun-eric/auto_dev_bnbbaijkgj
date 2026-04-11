'use client';

import React, { useEffect, useState } from 'react';
import { ProgressBar } from 'antd-mobile';
import api from '@/lib/api';

interface ProgressData {
  earned_today: number;
  daily_limit: number;
  is_limit_reached: boolean;
  enabled: boolean;
}

export default function CheckinPointsProgress({ refreshKey }: { refreshKey?: number }) {
  const [data, setData] = useState<ProgressData | null>(null);

  useEffect(() => {
    const fetchProgress = async () => {
      try {
        const res: any = await api.get('/api/points/checkin/today-progress');
        setData(res.data || res);
      } catch {
        // ignore
      }
    };
    fetchProgress();
  }, [refreshKey]);

  if (!data || !data.enabled) return null;

  const percent = data.daily_limit > 0 ? Math.min((data.earned_today / data.daily_limit) * 100, 100) : 0;

  return (
    <div style={{
      padding: '12px 16px',
      background: data.is_limit_reached ? '#f6ffed' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      borderRadius: 12,
      margin: '0 0 12px 0',
      color: data.is_limit_reached ? '#52c41a' : '#fff',
    }}>
      <div style={{ fontSize: 13, marginBottom: 6, fontWeight: 500 }}>
        {data.is_limit_reached
          ? '今日打卡积分已满 ✓'
          : `今日打卡积分：${data.earned_today} / ${data.daily_limit}`
        }
      </div>
      <ProgressBar
        percent={percent}
        style={{
          '--track-color': data.is_limit_reached ? '#d9f7be' : 'rgba(255,255,255,0.3)',
          '--fill-color': data.is_limit_reached ? '#52c41a' : '#fff',
          '--track-width': '6px',
        }}
      />
    </div>
  );
}

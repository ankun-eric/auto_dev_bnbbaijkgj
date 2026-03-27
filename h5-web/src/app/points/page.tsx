'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Button, List, Tag, Toast, Grid } from 'antd-mobile';

const mockRecords = [
  { id: 1, title: '每日签到', points: '+10', time: '2024-03-15 08:00', type: 'earn' },
  { id: 2, title: '完成健康任务', points: '+20', time: '2024-03-14 18:30', type: 'earn' },
  { id: 3, title: '兑换优惠券', points: '-50', time: '2024-03-13 10:00', type: 'spend' },
  { id: 4, title: '邀请好友', points: '+100', time: '2024-03-12 15:20', type: 'earn' },
  { id: 5, title: '健康问答', points: '+5', time: '2024-03-11 09:00', type: 'earn' },
];

export default function PointsPage() {
  const router = useRouter();
  const [signedToday, setSignedToday] = useState(false);
  const totalPoints = 680;
  const signDays = 7;

  const handleSign = () => {
    if (signedToday) return;
    setSignedToday(true);
    Toast.show({ content: '签到成功 +10积分' });
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
          <List style={{ '--border-top': 'none', '--border-bottom': 'none', '--padding-left': '0' }}>
            {mockRecords.map((r) => (
              <List.Item
                key={r.id}
                extra={
                  <span
                    className="font-bold"
                    style={{ color: r.type === 'earn' ? '#52c41a' : '#f5222d' }}
                  >
                    {r.points}
                  </span>
                }
                description={<span className="text-xs text-gray-400">{r.time}</span>}
              >
                <span className="text-sm">{r.title}</span>
              </List.Item>
            ))}
          </List>
        </Card>
      </div>
    </div>
  );
}

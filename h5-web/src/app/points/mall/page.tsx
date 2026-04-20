'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, Grid, Button, Toast, Dialog } from 'antd-mobile';

import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

const mockGoods = [
  { id: 1, name: '10元体检优惠券', points: 200, image: '🎫', stock: 50 },
  { id: 2, name: '定制保温杯', points: 500, image: '🥤', stock: 20 },
  { id: 3, name: '健康食谱电子书', points: 100, image: '📚', stock: 999 },
  { id: 4, name: '按摩仪体验券', points: 300, image: '💆', stock: 30 },
  { id: 5, name: '有机茶叶礼盒', points: 800, image: '🍵', stock: 15 },
  { id: 6, name: '5元话费充值', points: 150, image: '📱', stock: 100 },
];

export default function PointsMallPage() {
  const router = useRouter();
  // Bug#4：可用积分统一走 /api/points/summary，兼容字段 available_points / total_points
  const [userPoints, setUserPoints] = useState(0);

  useEffect(() => {
    api.get('/api/points/summary')
      .then((res: any) => {
        const data = res?.data || res || {};
        const pts = data.available_points ?? data.total_points ?? 0;
        setUserPoints(Number(pts) || 0);
      })
      .catch(() => {});
  }, []);

  const handleExchange = (item: typeof mockGoods[0]) => {
    if (userPoints < item.points) {
      Toast.show({ content: '积分不足' });
      return;
    }
    Dialog.confirm({
      content: `确认使用 ${item.points} 积分兑换「${item.name}」？`,
      confirmText: '确认兑换',
      cancelText: '取消',
      onConfirm: () => {
        Toast.show({ content: '兑换成功' });
      },
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar>
        积分商城
      </GreenNavBar>

      <div
        className="px-4 py-4 flex items-center justify-between"
        style={{ background: 'linear-gradient(135deg, #FFF8E1 0%, #FFE7A8 100%)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 12, color: '#8C6D1F' }}>可用积分</div>
            <div
              style={{
                fontSize: 26,
                fontWeight: 'bold',
                color: '#B8860B',
                lineHeight: 1.2,
                marginTop: 2,
              }}
            >
              {userPoints}
            </div>
          </div>
          <span
            style={{
              marginLeft: 10,
              fontSize: 22,
              filter: 'drop-shadow(0 1px 1px rgba(184,134,11,0.35))',
            }}
            aria-label="member-badge"
          >
            ⭐
          </span>
        </div>
        <Button
          size="small"
          onClick={() => router.push('/points')}
          style={{
            background: 'rgba(184,134,11,0.15)',
            color: '#8C6D1F',
            border: '1px solid rgba(184,134,11,0.35)',
            borderRadius: 16,
          }}
        >
          积分记录
        </Button>
      </div>

      <div className="px-4 pt-4">
        <Grid columns={2} gap={12}>
          {mockGoods.map((item) => (
            <Grid.Item key={item.id}>
              <Card style={{ borderRadius: 12 }}>
                <div className="text-center">
                  <div className="text-4xl mb-2">{item.image}</div>
                  <div className="text-sm font-medium truncate">{item.name}</div>
                  <div className="text-primary font-bold mt-1">{item.points} 积分</div>
                  <div className="text-xs text-gray-400 mt-1">库存 {item.stock}</div>
                  <Button
                    size="mini"
                    onClick={() => handleExchange(item)}
                    disabled={userPoints < item.points}
                    style={{
                      marginTop: 8,
                      borderRadius: 16,
                      background: userPoints >= item.points
                        ? 'linear-gradient(135deg, #52c41a, #13c2c2)'
                        : '#e8e8e8',
                      color: userPoints >= item.points ? '#fff' : '#999',
                      border: 'none',
                      fontSize: 12,
                    }}
                  >
                    {userPoints >= item.points ? '立即兑换' : '积分不足'}
                  </Button>
                </div>
              </Card>
            </Grid.Item>
          ))}
        </Grid>
      </div>
    </div>
  );
}

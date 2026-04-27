'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Avatar, Tag, Card, Grid, Button, Dialog, Toast, Divider } from 'antd-mobile';
import api from '@/lib/api';

interface ExpertDetail {
  id: number;
  name: string;
  title: string;
  department: string;
  hospital: string;
  rating: number;
  consultCount: number;
  price: number;
  tags: string[];
  desc: string;
  education: string;
  experience: string;
  product_id?: number | null;
  product_status?: string;
  schedule: { day: string; times: string[] }[];
  reviews: { user: string; content: string; rating: number; time: string }[];
}

const fallbackExpert: ExpertDetail = {
  id: 1,
  name: '王医生',
  title: '主任中医师',
  department: '中医内科',
  hospital: '宾尼中医诊所',
  rating: 4.9,
  consultCount: 2360,
  price: 198,
  tags: ['中医调理', '慢病管理', '体质辨识'],
  desc: '从事中医临床30余年，擅长中医内科疾病诊治，尤其在慢性病中医调理、体质辨识等方面有丰富经验。',
  education: '北京中医药大学 博士',
  experience: '30年',
  product_id: null,
  product_status: undefined,
  schedule: [
    { day: '周一', times: ['09:00', '10:00', '14:00', '15:00'] },
    { day: '周三', times: ['09:00', '10:00', '11:00'] },
    { day: '周五', times: ['14:00', '15:00', '16:00'] },
  ],
  reviews: [
    { user: '张**', content: '王医生很专业，调理方案很有效果', rating: 5, time: '2024-03-10' },
    { user: '李**', content: '讲解很耐心，中药调理一个月效果明显', rating: 5, time: '2024-03-05' },
  ],
};

export default function ExpertDetailPage() {
  const router = useRouter();
  const params = useParams();
  const [selectedDay, setSelectedDay] = useState('');
  const [selectedTime, setSelectedTime] = useState('');
  const [expert, setExpert] = useState<ExpertDetail>(fallbackExpert);

  useEffect(() => {
    if (params.id) {
      api.get(`/api/experts/${params.id}`).then((res: any) => {
        const data = res.data || res;
        setExpert({
          ...fallbackExpert,
          ...data,
          product_id: data.product_id ?? null,
          product_status: data.product_info?.status ?? undefined,
        });
      }).catch(() => {});
    }
  }, [params.id]);

  const canBook = !!expert.product_id && expert.product_status !== 'offline';
  const isOffline = expert.product_id && expert.product_status === 'offline';

  const handleBook = () => {
    if (!expert.product_id) return;
    if (isOffline) {
      Toast.show({ content: '该专家暂停预约' });
      return;
    }
    router.push(`/product/${expert.product_id}`);
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        专家详情
      </NavBar>

      <div
        className="px-4 py-6"
        style={{ background: 'linear-gradient(135deg, #5B6CFF, #8B5CF6)' }}
      >
        <div className="flex items-center">
          <Avatar
            src=""
            style={{
              '--size': '72px',
              '--border-radius': '50%',
              border: '3px solid rgba(255,255,255,0.3)',
            }}
          />
          <div className="ml-4 text-white">
            <div className="text-xl font-bold">{expert.name}</div>
            <div className="text-sm opacity-80 mt-1">{expert.title} · {expert.department}</div>
            <div className="text-xs opacity-70 mt-1">{expert.hospital}</div>
          </div>
        </div>
        <Grid columns={3} gap={0} className="mt-4">
          <Grid.Item>
            <div className="text-center text-white">
              <div className="font-bold">★ {expert.rating}</div>
              <div className="text-xs opacity-70">评分</div>
            </div>
          </Grid.Item>
          <Grid.Item>
            <div className="text-center text-white">
              <div className="font-bold">{expert.consultCount}</div>
              <div className="text-xs opacity-70">接诊</div>
            </div>
          </Grid.Item>
          <Grid.Item>
            <div className="text-center text-white">
              <div className="font-bold">{expert.experience}</div>
              <div className="text-xs opacity-70">从业</div>
            </div>
          </Grid.Item>
        </Grid>
      </div>

      <div className="px-4 -mt-3">
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="section-title">专家简介</div>
          <p className="text-sm text-gray-600">{expert.desc}</p>
          <div className="flex flex-wrap gap-1 mt-3">
            {expert.tags.map((tag) => (
              <Tag key={tag} style={{
                '--background-color': '#5B6CFF15',
                '--text-color': '#5B6CFF',
                '--border-color': 'transparent',
              }}>
                {tag}
              </Tag>
            ))}
          </div>
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="section-title">排班时间</div>
          <div className="flex gap-2 mb-3">
            {expert.schedule.map((s) => (
              <div
                key={s.day}
                className={`px-4 py-2 rounded-xl text-sm cursor-pointer`}
                style={{
                  background: selectedDay === s.day ? '#5B6CFF' : '#f5f5f5',
                  color: selectedDay === s.day ? '#fff' : '#666',
                }}
                onClick={() => { setSelectedDay(s.day); setSelectedTime(''); }}
              >
                {s.day}
              </div>
            ))}
          </div>
          {selectedDay && (
            <div className="flex flex-wrap gap-2">
              {expert.schedule.find((s) => s.day === selectedDay)?.times.map((t) => (
                <div
                  key={t}
                  className={`px-4 py-2 rounded-lg text-sm cursor-pointer`}
                  style={{
                    background: selectedTime === t ? '#5B6CFF' : '#fafafa',
                    color: selectedTime === t ? '#fff' : '#666',
                    border: selectedTime === t ? 'none' : '1px solid #e8e8e8',
                  }}
                  onClick={() => setSelectedTime(t)}
                >
                  {t}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="section-title">患者评价</div>
          {expert.reviews.map((r, i) => (
            <div key={i} className={`py-3 ${i > 0 ? 'border-t border-gray-50' : ''}`}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{r.user}</span>
                <span className="text-xs text-yellow-500">{'★'.repeat(r.rating)}</span>
              </div>
              <p className="text-sm text-gray-500 mt-1">{r.content}</p>
              <p className="text-xs text-gray-300 mt-1">{r.time}</p>
            </div>
          ))}
        </Card>
      </div>

      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3 flex items-center justify-between"
        style={{ maxWidth: 750, paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
      >
        <div>
          <span className="text-2xl font-bold text-red-500">¥{expert.price}</span>
          <span className="text-xs text-gray-400">/次</span>
        </div>
        {expert.product_id ? (
          <Button
            onClick={handleBook}
            disabled={!!isOffline}
            style={{
              background: isOffline ? '#ccc' : 'linear-gradient(135deg, #5B6CFF, #8B5CF6)',
              color: '#fff',
              border: 'none',
              borderRadius: 24,
              height: 44,
              width: 160,
            }}
          >
            {isOffline ? '暂停预约' : '预约'}
          </Button>
        ) : (
          <Button
            disabled
            style={{
              background: '#eee',
              color: '#bbb',
              border: 'none',
              borderRadius: 24,
              height: 44,
              width: 160,
            }}
          >
            预约
          </Button>
        )}
      </div>
    </div>
  );
}

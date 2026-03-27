'use client';

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Avatar, Tag, Card, Grid, Button, Dialog, Toast, Divider } from 'antd-mobile';

const mockExpert = {
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

  const handleBook = () => {
    if (!selectedDay || !selectedTime) {
      Toast.show({ content: '请选择预约时间' });
      return;
    }
    Dialog.confirm({
      content: `确认预约${mockExpert.name}？\n时间：${selectedDay} ${selectedTime}\n费用：¥${mockExpert.price}`,
      confirmText: '确认预约',
      cancelText: '取消',
      onConfirm: () => {
        Toast.show({ content: '预约成功' });
        router.push('/orders');
      },
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        专家详情
      </NavBar>

      <div
        className="px-4 py-6"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
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
            <div className="text-xl font-bold">{mockExpert.name}</div>
            <div className="text-sm opacity-80 mt-1">{mockExpert.title} · {mockExpert.department}</div>
            <div className="text-xs opacity-70 mt-1">{mockExpert.hospital}</div>
          </div>
        </div>
        <Grid columns={3} gap={0} className="mt-4">
          <Grid.Item>
            <div className="text-center text-white">
              <div className="font-bold">★ {mockExpert.rating}</div>
              <div className="text-xs opacity-70">评分</div>
            </div>
          </Grid.Item>
          <Grid.Item>
            <div className="text-center text-white">
              <div className="font-bold">{mockExpert.consultCount}</div>
              <div className="text-xs opacity-70">接诊</div>
            </div>
          </Grid.Item>
          <Grid.Item>
            <div className="text-center text-white">
              <div className="font-bold">{mockExpert.experience}</div>
              <div className="text-xs opacity-70">从业</div>
            </div>
          </Grid.Item>
        </Grid>
      </div>

      <div className="px-4 -mt-3">
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="section-title">专家简介</div>
          <p className="text-sm text-gray-600">{mockExpert.desc}</p>
          <div className="flex flex-wrap gap-1 mt-3">
            {mockExpert.tags.map((tag) => (
              <Tag key={tag} style={{
                '--background-color': '#52c41a15',
                '--text-color': '#52c41a',
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
            {mockExpert.schedule.map((s) => (
              <div
                key={s.day}
                className={`px-4 py-2 rounded-xl text-sm cursor-pointer ${
                  selectedDay === s.day ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'
                }`}
                onClick={() => { setSelectedDay(s.day); setSelectedTime(''); }}
              >
                {s.day}
              </div>
            ))}
          </div>
          {selectedDay && (
            <div className="flex flex-wrap gap-2">
              {mockExpert.schedule.find((s) => s.day === selectedDay)?.times.map((t) => (
                <div
                  key={t}
                  className={`px-4 py-2 rounded-lg text-sm cursor-pointer ${
                    selectedTime === t ? 'bg-primary text-white' : 'bg-gray-50 text-gray-600 border border-gray-200'
                  }`}
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
          {mockExpert.reviews.map((r, i) => (
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
        style={{ maxWidth: 750 }}
      >
        <div>
          <span className="text-2xl font-bold text-red-500">¥{mockExpert.price}</span>
          <span className="text-xs text-gray-400">/次</span>
        </div>
        <Button
          onClick={handleBook}
          style={{
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 'none',
            borderRadius: 24,
            height: 44,
            width: 160,
          }}
        >
          立即预约
        </Button>
      </div>
    </div>
  );
}

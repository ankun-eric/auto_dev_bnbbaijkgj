'use client';

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Button, Tag, Toast, Dialog, Divider, Rate } from 'antd-mobile';

const mockService = {
  id: 1,
  title: '基础体检套餐',
  desc: '适合18-40岁年轻人的基础体检方案，包含18项常规检查',
  price: 298,
  originalPrice: 450,
  tag: '热销',
  sales: 3200,
  rating: 4.8,
  images: [],
  details: [
    '一般检查（身高、体重、血压等）',
    '血常规（25项）',
    '尿常规（12项）',
    '肝功能（6项）',
    '肾功能（3项）',
    '血脂（4项）',
    '空腹血糖',
    '心电图',
    '胸部X光',
    '腹部B超',
  ],
  notes: [
    '体检前一天请勿饮酒、进食油腻食物',
    '体检当天请空腹（禁食8小时以上）',
    '请携带有效身份证件',
    '预约后可在体检中心前台核销',
  ],
  location: '宾尼健康体检中心（各分店通用）',
  validDays: 90,
};

export default function ServiceDetailPage() {
  const router = useRouter();
  const params = useParams();
  const [buying, setBuying] = useState(false);

  const handleBuy = async () => {
    Dialog.confirm({
      content: `确认预约「${mockService.title}」？费用 ¥${mockService.price}`,
      confirmText: '确认预约',
      cancelText: '取消',
      onConfirm: async () => {
        setBuying(true);
        setTimeout(() => {
          setBuying(false);
          Toast.show({ content: '预约成功' });
          router.push('/orders');
        }, 1000);
      },
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        服务详情
      </NavBar>

      <div
        className="h-48 flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg, #52c41a30, #13c2c230)' }}
      >
        <div className="text-center">
          <div className="text-5xl mb-2">🏥</div>
          <p className="text-sm text-gray-500">服务图片</p>
        </div>
      </div>

      <div className="px-4 pt-4">
        <div className="card">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h1 className="text-lg font-bold">{mockService.title}</h1>
              <div className="flex items-center mt-1">
                <Tag
                  style={{
                    '--background-color': '#52c41a15',
                    '--text-color': '#52c41a',
                    '--border-color': 'transparent',
                    fontSize: 10,
                  }}
                >
                  {mockService.tag}
                </Tag>
                <span className="text-xs text-gray-400 ml-2">已售{mockService.sales}</span>
              </div>
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-red-500">¥{mockService.price}</span>
            <span className="text-sm text-gray-300 line-through ml-2">¥{mockService.originalPrice}</span>
          </div>
          <p className="text-sm text-gray-500 mt-2">{mockService.desc}</p>
        </div>

        <div className="card">
          <div className="section-title">服务包含</div>
          <div className="space-y-2">
            {mockService.details.map((item, i) => (
              <div key={i} className="flex items-start text-sm">
                <span className="text-primary mr-2">✓</span>
                <span className="text-gray-600">{item}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="section-title">预约须知</div>
          <div className="space-y-2">
            {mockService.notes.map((note, i) => (
              <div key={i} className="flex items-start text-sm">
                <span className="text-orange-400 mr-2">•</span>
                <span className="text-gray-600">{note}</span>
              </div>
            ))}
          </div>
          <Divider />
          <div className="text-sm text-gray-500">
            <p>📍 服务地点：{mockService.location}</p>
            <p className="mt-1">📅 有效期：购买后{mockService.validDays}天内有效</p>
          </div>
        </div>
      </div>

      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3 flex gap-3"
        style={{ maxWidth: 750 }}
      >
        <Button
          onClick={() => router.push('/customer-service')}
          style={{ flex: 1, borderRadius: 24, height: 44, borderColor: '#52c41a', color: '#52c41a' }}
        >
          咨询客服
        </Button>
        <Button
          loading={buying}
          onClick={handleBuy}
          style={{
            flex: 2,
            borderRadius: 24,
            height: 44,
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 'none',
          }}
        >
          立即预约
        </Button>
      </div>
    </div>
  );
}

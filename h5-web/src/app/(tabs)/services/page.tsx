'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Tabs, Card, Tag, Image, SearchBar } from 'antd-mobile';

const categories = [
  { key: 'food', title: '健康食品' },
  { key: 'dental', title: '口腔服务' },
  { key: 'checkup', title: '体检服务' },
  { key: 'expert', title: '专家咨询' },
  { key: 'elderly', title: '养老服务' },
];

const services: Record<string, Array<{
  id: number;
  title: string;
  desc: string;
  price: number;
  originalPrice?: number;
  tag?: string;
  sales: number;
}>> = {
  food: [
    { id: 1, title: '有机五谷杂粮礼盒', desc: '精选有机种植，营养均衡', price: 168, originalPrice: 238, tag: '热销', sales: 520 },
    { id: 2, title: '低脂高蛋白代餐粉', desc: '科学配比，适合控糖人群', price: 128, sales: 380 },
    { id: 3, title: '养生花茶组合装', desc: '枸杞菊花茶/玫瑰花茶', price: 68, originalPrice: 98, sales: 890 },
  ],
  dental: [
    { id: 4, title: '超声波洁牙', desc: '专业洁牙，深度清洁', price: 128, originalPrice: 198, tag: '推荐', sales: 1200 },
    { id: 5, title: '牙齿美白', desc: '冷光美白，安全无痛', price: 998, originalPrice: 1580, sales: 350 },
    { id: 6, title: '口腔全面检查', desc: '含拍片+医生诊断', price: 58, tag: '特惠', sales: 2100 },
  ],
  checkup: [
    { id: 7, title: '基础体检套餐', desc: '18项检查，适合年轻人', price: 298, originalPrice: 450, tag: '热销', sales: 3200 },
    { id: 8, title: '深度体检套餐', desc: '36项检查，全面了解身体', price: 698, originalPrice: 980, sales: 1560 },
    { id: 9, title: '防癌筛查套餐', desc: '肿瘤标志物+影像检查', price: 1280, originalPrice: 1800, sales: 890 },
  ],
  expert: [
    { id: 10, title: '中医专家视频问诊', desc: '30分钟在线面诊', price: 198, tag: '推荐', sales: 560 },
    { id: 11, title: '营养师定制方案', desc: '个性化饮食指导', price: 128, sales: 780 },
    { id: 12, title: '心理咨询师一对一', desc: '专业心理疏导', price: 258, sales: 320 },
  ],
  elderly: [
    { id: 13, title: '居家上门护理', desc: '专业护工上门服务', price: 298, tag: '新品', sales: 120 },
    { id: 14, title: '老年人健康监测', desc: '血压血糖定期监测', price: 98, sales: 450 },
    { id: 15, title: '康复理疗服务', desc: '专业理疗师上门', price: 398, sales: 230 },
  ],
};

export default function ServicesPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('food');
  const [search, setSearch] = useState('');

  const currentServices = (services[activeTab] || []).filter(
    (s) => !search || s.title.includes(search) || s.desc.includes(search)
  );

  return (
    <div className="pb-20">
      <div className="gradient-header pb-4">
        <h1 className="text-xl font-bold mb-3">健康服务</h1>
        <SearchBar
          placeholder="搜索服务"
          value={search}
          onChange={setSearch}
          style={{
            '--border-radius': '20px',
            '--background': 'rgba(255,255,255,0.9)',
            '--height': '36px',
          }}
        />
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{
          '--active-line-color': '#52c41a',
          '--active-title-color': '#52c41a',
          position: 'sticky',
          top: 0,
          zIndex: 10,
          background: '#fff',
        }}
      >
        {categories.map((cat) => (
          <Tabs.Tab key={cat.key} title={cat.title} />
        ))}
      </Tabs>

      <div className="px-4 pt-3">
        {currentServices.map((svc) => (
          <Card
            key={svc.id}
            onClick={() => router.push(`/service/${svc.id}`)}
            style={{ marginBottom: 12, borderRadius: 12 }}
          >
            <div className="flex">
              <div
                className="w-24 h-24 rounded-lg flex items-center justify-center text-3xl flex-shrink-0"
                style={{ background: 'linear-gradient(135deg, #f0fff0, #e8fce8)' }}
              >
                🏥
              </div>
              <div className="flex-1 ml-3 min-w-0">
                <div className="flex items-center">
                  <span className="font-medium text-sm truncate">{svc.title}</span>
                  {svc.tag && (
                    <Tag
                      style={{
                        '--background-color': '#52c41a15',
                        '--text-color': '#52c41a',
                        '--border-color': 'transparent',
                        fontSize: 10,
                        marginLeft: 6,
                      }}
                    >
                      {svc.tag}
                    </Tag>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-1">{svc.desc}</p>
                <div className="flex items-end justify-between mt-3">
                  <div>
                    <span className="text-primary font-bold">¥{svc.price}</span>
                    {svc.originalPrice && (
                      <span className="text-xs text-gray-300 line-through ml-1">
                        ¥{svc.originalPrice}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">已售{svc.sales}</span>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

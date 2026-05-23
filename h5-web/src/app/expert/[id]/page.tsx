'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';

interface ExpertDetail {
  id: number;
  name: string;
  title: string;
  department: string;
  hospital: string;
  avatar?: string;
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
      showToast('该专家暂停预约');
      return;
    }
    router.push(`/product/${expert.product_id}`);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#F5F5F5', paddingBottom: 80 }}>
      {/* 英雄区 gradient-hero-dark */}
      <div style={{
        background: 'linear-gradient(135deg, #0C4A6E, #0284C7)',
        minHeight: 240, padding: '0 0 24px 0', position: 'relative',
      }}>
        {/* 顶栏 */}
        <div style={{
          display: 'flex', alignItems: 'center', height: 48,
          paddingTop: 'env(safe-area-inset-top)', padding: '0 16px',
        }}>
          <div onClick={() => router.back()} style={{ cursor: 'pointer', fontSize: 20, color: '#fff' }}>←</div>
          <div style={{ flex: 1, textAlign: 'center', fontSize: 17, fontWeight: 700, color: '#fff' }}>专家详情</div>
          <div style={{ width: 20 }} />
        </div>

        {/* 头像 + 信息 */}
        <div style={{ display: 'flex', alignItems: 'center', padding: '20px 20px 0' }}>
          <div style={{
            width: 80, height: 80, borderRadius: '50%',
            border: '3px solid #fff', background: '#E0F2FE',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 32, color: '#0284C7', flexShrink: 0,
            overflow: 'hidden',
          }}>
            {expert.avatar
              ? <img src={expert.avatar} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : expert.name.slice(-1)}
          </div>
          <div style={{ marginLeft: 16 }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#fff' }}>{expert.name}</div>
            <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.8)', marginTop: 4 }}>
              {expert.department} · {expert.title}
            </div>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)', marginTop: 2 }}>{expert.hospital}</div>
          </div>
        </div>

        {/* 3 项统计 */}
        <div style={{
          display: 'flex', justifyContent: 'space-around', marginTop: 20, padding: '0 20px',
        }}>
          {[
            { value: `★ ${expert.rating}`, label: '评分' },
            { value: String(expert.consultCount), label: '接诊' },
            { value: expert.experience, label: '从业' },
          ].map((item) => (
            <div key={item.label} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: '#fff' }}>{item.value}</div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 内容区 */}
      <div style={{ padding: '16px 16px 0', marginTop: -12 }}>
        {/* 标签 */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
          {expert.tags.map((tag) => (
            <span key={tag} style={{
              background: '#E0F2FE', color: '#0284C7',
              borderRadius: 16, padding: '4px 12px', fontSize: 12,
            }}>{tag}</span>
          ))}
        </div>

        {/* 专家简介 */}
        <div style={{
          background: '#fff', borderRadius: 12, padding: 16, marginBottom: 12,
        }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1F2937', marginBottom: 8 }}>专家简介</div>
          <p style={{ fontSize: 14, color: '#6B7280', lineHeight: 1.6, margin: 0 }}>{expert.desc}</p>
        </div>

        {/* 排班时间 */}
        <div style={{
          background: '#fff', borderRadius: 12, padding: 16, marginBottom: 12,
        }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1F2937', marginBottom: 12 }}>排班时间</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {expert.schedule.map((s) => (
              <span key={s.day} style={{
                background: '#F0F9FF', color: '#0284C7', borderRadius: 8,
                padding: '6px 14px', fontSize: 13,
              }}>
                {s.day}：{s.times.join('、')}
              </span>
            ))}
          </div>
        </div>

        {/* 患者评价 */}
        <div style={{
          background: '#fff', borderRadius: 12, padding: 16, marginBottom: 12,
        }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1F2937', marginBottom: 12 }}>患者评价</div>
          {expert.reviews.map((r, i) => (
            <div key={i} style={{
              paddingTop: i > 0 ? 12 : 0, marginTop: i > 0 ? 12 : 0,
              borderTop: i > 0 ? '1px solid #F3F4F6' : 'none',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 500, color: '#1F2937' }}>{r.user}</span>
                <span style={{ fontSize: 12, color: '#F59E0B' }}>{'★'.repeat(r.rating)}</span>
              </div>
              <p style={{ fontSize: 13, color: '#6B7280', margin: '6px 0 2px' }}>{r.content}</p>
              <div style={{ fontSize: 12, color: '#9CA3AF' }}>{r.time}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 底部按钮 */}
      <div style={{
        position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
        width: '100%', maxWidth: 750, background: '#fff',
        borderTop: '1px solid #E5E7EB',
        padding: '12px 16px calc(12px + env(safe-area-inset-bottom))',
      }}>
        <button
          type="button"
          onClick={handleBook}
          disabled={!canBook}
          style={{
            width: '100%', height: 48, borderRadius: 12, border: 'none',
            background: canBook
              ? 'linear-gradient(135deg, #38BDF8, #0284C7)'
              : '#D1D5DB',
            color: '#fff', fontSize: 16, fontWeight: 600,
            cursor: canBook ? 'pointer' : 'not-allowed',
          }}
        >
          {isOffline ? '暂停预约' : '预约问诊'}
        </button>
      </div>
    </div>
  );
}

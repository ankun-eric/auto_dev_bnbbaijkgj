'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Card, Button, SpinLoading, Toast, Empty, Grid } from 'antd-mobile';
import api from '@/lib/api';

interface DiagnosisDetail {
  id: number;
  constitution_type: string;
  description: string;
  features: string;
  diet_suggestion: string;
  exercise_suggestion: string;
  lifestyle_suggestion: string;
  created_at: string;
  family_member?: {
    id: number;
    nickname: string;
    relationship_type: string;
    is_self?: boolean;
    relation_type_name?: string;
  } | null;
}

interface Product {
  id: number;
  name: string;
  description: string;
  price: number;
  image_url: string;
  category: string;
}

const CONSTITUTION_COLORS: Record<string, string> = {
  '气虚质': '#fa8c16',
  '阳虚质': '#1890ff',
  '阴虚质': '#eb2f96',
  '痰湿质': '#13c2c2',
  '湿热质': '#f5222d',
  '血瘀质': '#722ed1',
  '气郁质': '#2f54eb',
  '特禀质': '#faad14',
  '平和质': '#52c41a',
};

function getColor(type: string): string {
  return CONSTITUTION_COLORS[type] || '#52c41a';
}

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function getMemberLabel(member: DiagnosisDetail['family_member']): string {
  if (!member) return '本人';
  if (member.is_self) return '本人';
  return member.nickname || member.relation_type_name || member.relationship_type || '本人';
}

export default function DiagnosisDetailPage() {
  const router = useRouter();
  const params = useParams();
  const diagnosisId = params.id as string;

  const [detail, setDetail] = useState<DiagnosisDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get(`/api/tcm/diagnosis/${diagnosisId}`);
      const data = res.data || res;
      setDetail(data);

      if (data.constitution_type) {
        fetchProducts(data.constitution_type);
      }
    } catch {
      Toast.show({ content: '加载失败', icon: 'fail' });
    } finally {
      setLoading(false);
    }
  }, [diagnosisId]);

  const fetchProducts = async (constitutionType: string) => {
    setProductsLoading(true);
    try {
      const res: any = await api.get('/api/products', {
        params: { constitution_type: constitutionType, page: 1, page_size: 6 },
      });
      const data = res.data || res;
      setProducts(data.items || []);
    } catch {
      setProducts([]);
    } finally {
      setProductsLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const handleConsultAI = async () => {
    if (!detail) return;
    try {
      const memberId = detail.family_member && !detail.family_member.is_self ? detail.family_member.id : null;
      const res: any = await api.post('/api/chat/sessions', {
        session_type: 'constitution',
        title: `体质调理-${detail.constitution_type}`,
        family_member_id: memberId,
      });
      const data = res.data || res;
      router.push(`/chat/${data.id}?type=constitution`);
    } catch {
      Toast.show({ content: '创建会话失败', icon: 'fail' });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>体质分析详情</NavBar>
        <div className="flex items-center justify-center py-20">
          <SpinLoading style={{ '--size': '32px', '--color': '#52c41a' }} />
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>体质分析详情</NavBar>
        <div className="px-4 pt-10">
          <Empty description="记录不存在" />
        </div>
      </div>
    );
  }

  const color = getColor(detail.constitution_type);
  const memberLabel = getMemberLabel(detail.family_member);

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        体质分析详情
      </NavBar>

      {/* Constitution result card */}
      <div className="px-4 pt-4">
        <div
          className="rounded-2xl p-5"
          style={{ background: `linear-gradient(135deg, ${color}15, ${color}08)`, border: `1px solid ${color}30` }}
        >
          <div className="flex items-center gap-4 mb-4">
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ background: `${color}20`, border: `2px solid ${color}` }}
            >
              <span className="text-lg font-bold" style={{ color }}>
                {detail.constitution_type.replace('质', '')}
              </span>
            </div>
            <div>
              <div className="text-xl font-bold" style={{ color }}>{detail.constitution_type}</div>
              <div className="flex items-center gap-2 mt-1">
                <span
                  className="text-[11px] px-2 py-0.5 rounded-full"
                  style={{ background: `${color}15`, color }}
                >
                  {memberLabel}
                </span>
                <span className="text-xs text-gray-400">{formatTime(detail.created_at)}</span>
              </div>
            </div>
          </div>

          {detail.description && (
            <div className="text-sm text-gray-600 mb-3">{detail.description}</div>
          )}
        </div>

        {/* Detail sections */}
        <div className="mt-4 space-y-3">
          {detail.features && (
            <Card style={{ borderRadius: 12 }}>
              <div className="flex items-center gap-2 mb-2">
                <span style={{ color, fontSize: 16 }}>📋</span>
                <span className="text-sm font-semibold text-gray-800">体质特征</span>
              </div>
              <div className="text-sm text-gray-600 leading-relaxed">{detail.features}</div>
            </Card>
          )}

          {detail.diet_suggestion && (
            <Card style={{ borderRadius: 12 }}>
              <div className="flex items-center gap-2 mb-2">
                <span style={{ color, fontSize: 16 }}>🥗</span>
                <span className="text-sm font-semibold text-gray-800">饮食建议</span>
              </div>
              <div className="text-sm text-gray-600 leading-relaxed">{detail.diet_suggestion}</div>
            </Card>
          )}

          {detail.exercise_suggestion && (
            <Card style={{ borderRadius: 12 }}>
              <div className="flex items-center gap-2 mb-2">
                <span style={{ color, fontSize: 16 }}>🏃</span>
                <span className="text-sm font-semibold text-gray-800">运动建议</span>
              </div>
              <div className="text-sm text-gray-600 leading-relaxed">{detail.exercise_suggestion}</div>
            </Card>
          )}

          {detail.lifestyle_suggestion && (
            <Card style={{ borderRadius: 12 }}>
              <div className="flex items-center gap-2 mb-2">
                <span style={{ color, fontSize: 16 }}>🌙</span>
                <span className="text-sm font-semibold text-gray-800">起居建议</span>
              </div>
              <div className="text-sm text-gray-600 leading-relaxed">{detail.lifestyle_suggestion}</div>
            </Card>
          )}
        </div>

        {/* Recommended products */}
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-gray-700">推荐商品/服务</span>
            {products.length > 0 && (
              <button
                className="text-xs px-3 py-1 rounded-full"
                style={{ color: '#52c41a', background: '#f0faf0' }}
                onClick={() => router.push(`/products?constitution_type=${encodeURIComponent(detail.constitution_type)}`)}
              >
                查看更多
              </button>
            )}
          </div>

          {productsLoading ? (
            <div className="flex items-center justify-center py-8">
              <SpinLoading style={{ '--size': '24px', '--color': '#52c41a' }} />
            </div>
          ) : products.length === 0 ? (
            <div className="bg-white rounded-xl py-6 text-center">
              <Empty
                description="暂无推荐商品"
                style={{ '--description-font-size': '12px' } as React.CSSProperties}
              />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {products.map((product) => (
                <div
                  key={product.id}
                  className="bg-white rounded-xl overflow-hidden shadow-sm active:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => router.push(`/products/${product.id}`)}
                >
                  <div className="aspect-square bg-gray-100 relative">
                    {product.image_url ? (
                      <img
                        src={product.image_url}
                        alt={product.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-3xl text-gray-300">📦</div>
                    )}
                  </div>
                  <div className="p-2.5">
                    <div className="text-sm font-medium text-gray-800 truncate">{product.name}</div>
                    {product.description && (
                      <div className="text-xs text-gray-400 mt-0.5 truncate">{product.description}</div>
                    )}
                    {product.price > 0 && (
                      <div className="text-sm font-bold mt-1" style={{ color: '#f5222d' }}>
                        ¥{product.price.toFixed(2)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom consult button */}
      <div className="fixed bottom-0 left-0 right-0 bg-white px-4 py-3 safe-area-bottom" style={{ boxShadow: '0 -2px 8px rgba(0,0,0,0.06)' }}>
        <Button
          block
          onClick={handleConsultAI}
          style={{
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 'none',
            borderRadius: 24,
            height: 46,
            fontSize: 15,
            fontWeight: 500,
          }}
        >
          咨询 AI 调理方案
        </Button>
      </div>
    </div>
  );
}

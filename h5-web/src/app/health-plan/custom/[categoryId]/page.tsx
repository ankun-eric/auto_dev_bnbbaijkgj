'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Card, Button, ProgressBar, SpinLoading, Toast, Tag } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface RecommendedPlan {
  id: number;
  name: string;
  description: string;
  target_audience: string;
  duration_days: number;
  task_count: number;
}

interface UserPlan {
  id: number;
  name: string;
  description: string;
  current_day: number;
  total_days: number | null;
  progress: number;
  status: string;
}

interface CategoryDetail {
  id: number;
  name: string;
  description: string;
  icon: string;
  recommended_plans: RecommendedPlan[];
  user_plans: UserPlan[];
}

export default function CategoryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const categoryId = params.categoryId as string;

  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<CategoryDetail | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res: any = await api.get(`/api/health-plan/template-categories/${categoryId}`);
        const raw = res.data || res;
        const category = raw.category || raw;
        const recommendedPlans = (raw.recommended_plans || []).map((p: any) => ({
          ...p,
          name: p.name || p.plan_name,
        }));
        const userPlans = (raw.user_plans || []).map((p: any) => ({
          ...p,
          name: p.plan_name || p.name,
          total_days: p.duration_days || p.total_days,
          progress: 0,
        }));
        setDetail({
          ...category,
          recommended_plans: recommendedPlans,
          user_plans: userPlans,
        });
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [categoryId]);

  const handleAICustomize = () => {
    Toast.show({ content: 'AI正在为您定制计划...', icon: 'loading' });
    setTimeout(() => {
      const sessionId = `plan-${Date.now()}`;
      const msg = detail
        ? `请根据我的健康档案，为我定制一份${detail.name}方案`
        : '请根据我的健康档案为我定制计划';
      router.push(`/chat/${sessionId}?type=health&msg=${encodeURIComponent(msg)}`);
    }, 1000);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>加载中...</NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>模板详情</NavBar>
        <div className="flex flex-col items-center justify-center py-20">
          <div className="text-4xl mb-3">😔</div>
          <div className="text-gray-400 text-sm">模板不存在</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>{detail.name}</NavBar>

      <div className="px-4 py-4" style={{ background: 'linear-gradient(135deg, #1890ff, #40a9ff)' }}>
        <div className="text-white text-center mb-3">
          <div className="text-3xl mb-1">{detail.icon || '📋'}</div>
          <div className="text-lg font-bold">{detail.name}</div>
          <div className="text-xs opacity-80 mt-1">{detail.description}</div>
        </div>
        <div
          onClick={handleAICustomize}
          className="flex items-center justify-center py-3 rounded-xl cursor-pointer"
          style={{ background: 'rgba(255,255,255,0.95)', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
        >
          <span className="text-xl mr-2">🤖</span>
          <span className="text-base font-bold" style={{ color: '#1890ff' }}>AI 为我定制{detail.name}</span>
        </div>
      </div>

      <div className="px-4 -mt-3">
        <div className="section-title mt-4">📋 推荐计划</div>
        {(!detail.recommended_plans || detail.recommended_plans.length === 0) ? (
          <Card style={{ borderRadius: 12, textAlign: 'center', padding: '20px' }}>
            <div className="text-gray-400 text-sm">暂无推荐计划</div>
          </Card>
        ) : (
          detail.recommended_plans.map((plan) => (
            <Card
              key={plan.id}
              onClick={() => router.push(`/health-plan/custom/plan/${plan.id}`)}
              style={{ borderRadius: 12, marginBottom: 12 }}
            >
              <div className="flex items-start justify-between mb-2">
                <span className="font-bold text-sm">{plan.name}</span>
                <Tag
                  style={{
                    '--background-color': '#1890ff15',
                    '--text-color': '#1890ff',
                    '--border-color': 'transparent',
                    fontSize: 10,
                  }}
                >
                  {plan.duration_days}天
                </Tag>
              </div>
              <div className="text-xs text-gray-400 mb-2">{plan.description}</div>
              <div className="flex items-center justify-between">
                {plan.target_audience && (
                  <span className="text-xs text-gray-400">适合: {plan.target_audience}</span>
                )}
                <span className="text-xs text-gray-400">{plan.task_count}个每日任务</span>
              </div>
            </Card>
          ))
        )}

        <div className="section-title mt-4">📌 我的计划</div>
        {(!detail.user_plans || detail.user_plans.length === 0) ? (
          <Card style={{ borderRadius: 12, textAlign: 'center', padding: '20px' }}>
            <div className="text-gray-400 text-sm mb-3">暂无计划</div>
            <Button
              size="small"
              style={{ borderRadius: 20, color: '#1890ff', borderColor: '#1890ff' }}
              onClick={() => router.push(`/health-plan/custom/create?categoryId=${categoryId}`)}
            >
              创建第一个计划
            </Button>
          </Card>
        ) : (
          <>
            {detail.user_plans.map((plan) => (
              <Card
                key={plan.id}
                onClick={() => router.push(`/health-plan/custom/my-plan/${plan.id}`)}
                style={{ borderRadius: 12, marginBottom: 12 }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-sm">{plan.name}</span>
                  <Tag
                    style={{
                      '--background-color': plan.status === 'active' ? '#52c41a15' : '#99999915',
                      '--text-color': plan.status === 'active' ? '#52c41a' : '#999',
                      '--border-color': 'transparent',
                      fontSize: 10,
                    }}
                  >
                    {plan.status === 'active' ? '进行中' : plan.status === 'completed' ? '已完成' : '已暂停'}
                    {plan.total_days && ` 第${plan.current_day}/${plan.total_days}天`}
                  </Tag>
                </div>
                {plan.description && (
                  <div className="text-xs text-gray-400 mb-2">{plan.description}</div>
                )}
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-400">进度</span>
                  <span className="text-xs" style={{ color: '#52c41a' }}>{plan.progress}%</span>
                </div>
                <ProgressBar
                  percent={plan.progress}
                  style={{ '--track-width': '6px', '--fill-color': '#52c41a' }}
                />
              </Card>
            ))}
          </>
        )}

        <div
          className="card cursor-pointer flex items-center justify-center py-4 mt-2"
          style={{ background: '#f0f7ff', border: '1px dashed #1890ff40' }}
          onClick={() => router.push(`/health-plan/custom/create?categoryId=${categoryId}`)}
        >
          <AddOutline style={{ color: '#1890ff', marginRight: 4 }} />
          <span className="text-sm font-medium" style={{ color: '#1890ff' }}>创建新计划</span>
        </div>
      </div>
    </div>
  );
}

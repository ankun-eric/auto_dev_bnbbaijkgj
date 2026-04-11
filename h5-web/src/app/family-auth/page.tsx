'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Toast, Button, Dialog, Result } from 'antd-mobile';
import api from '@/lib/api';

interface InvitationDetail {
  invite_code: string;
  status: string;
  inviter_nickname?: string;
  member_nickname?: string;
  expires_at: string;
  created_at: string;
}

type PageStatus = 'loading' | 'confirm' | 'accepted' | 'rejected' | 'error';

export default function FamilyAuthPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-gray-400">加载中...</div>}>
      <FamilyAuthContent />
    </Suspense>
  );
}

function FamilyAuthContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get('code');

  const [status, setStatus] = useState<PageStatus>('loading');
  const [invitation, setInvitation] = useState<InvitationDetail | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const returnUrl = `${basePath}/family-auth?code=${code || ''}`;
      router.replace(`/login?redirect=${encodeURIComponent(returnUrl)}`);
      return;
    }
    if (!code) {
      setErrorMsg('无效的邀请链接');
      setStatus('error');
      return;
    }
    fetchInvitation();
  }, [code]);

  const fetchInvitation = async () => {
    setStatus('loading');
    try {
      const res: any = await api.get(`/api/family/invitation/${code}`);
      const data: InvitationDetail = res.data || res;
      setInvitation(data);

      if (data.status === 'accepted') {
        setErrorMsg('该邀请已被接受');
        setStatus('error');
      } else if (data.status === 'expired') {
        setErrorMsg('邀请已过期，请联系对方重新发送');
        setStatus('error');
      } else if (data.status === 'cancelled') {
        setErrorMsg('邀请已取消');
        setStatus('error');
      } else if (data.status === 'pending') {
        setStatus('confirm');
      } else {
        setErrorMsg('邀请状态异常');
        setStatus('error');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '获取邀请信息失败';
      setErrorMsg(detail);
      setStatus('error');
    }
  };

  const handleAccept = async () => {
    setSubmitting(true);
    try {
      await api.post(`/api/family/invitation/${code}/accept`);
      setStatus('accepted');
      Toast.show({ content: '已接受邀请', icon: 'success' });
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '操作失败，请重试';
      Toast.show({ content: detail, icon: 'fail' });
    }
    setSubmitting(false);
  };

  const handleReject = async () => {
    const result = await Dialog.confirm({
      title: '拒绝邀请',
      content: '确定要拒绝此共管邀请吗？',
    });
    if (!result) return;
    setSubmitting(true);
    try {
      await api.post(`/api/family/invitation/${code}/reject`);
      setStatus('rejected');
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '操作失败，请重试';
      Toast.show({ content: detail, icon: 'fail' });
    }
    setSubmitting(false);
  };

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}>
      <NavBar onBack={() => router.back()} style={{ background: 'transparent' }}>
        授权确认
      </NavBar>

      <div className="px-4 pt-4 pb-8">
        {status === 'loading' && (
          <div className="text-center py-20 text-gray-400 text-sm">加载中...</div>
        )}

        {status === 'error' && (
          <div className="pt-12">
            <Result
              status="warning"
              title="无法处理邀请"
              description={errorMsg}
            />
            <div className="mt-6 px-8">
              <Button
                block
                style={{
                  background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 24,
                  height: 44,
                  fontWeight: 600,
                }}
                onClick={() => router.replace('/')}
              >
                返回首页
              </Button>
            </div>
          </div>
        )}

        {status === 'confirm' && invitation && (
          <div className="pt-6">
            {/* Invitation card */}
            <div
              className="rounded-3xl overflow-hidden mx-auto"
              style={{
                maxWidth: 340,
                background: '#fff',
                boxShadow: '0 8px 32px rgba(82, 196, 26, 0.12)',
              }}
            >
              <div
                className="px-6 pt-8 pb-6 text-center"
                style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
              >
                <div className="text-5xl mb-3">🤝</div>
                <div className="text-white text-lg font-bold">健康档案共管邀请</div>
              </div>

              <div className="px-6 py-6">
                <div className="text-center mb-6">
                  <div className="text-base text-gray-800 leading-relaxed">
                    <span className="font-bold" style={{ color: '#52c41a' }}>
                      {invitation.inviter_nickname || '对方'}
                    </span>
                    {' '}邀请您共同管理健康档案
                  </div>
                  <div className="text-xs text-gray-400 mt-3">
                    同意后，对方将可以查看和管理您的健康档案数据
                  </div>
                </div>

                <div
                  className="rounded-xl px-4 py-3 mb-6"
                  style={{ background: '#f6ffed', border: '1px solid #d9f7be' }}
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">邀请人</span>
                    <span className="text-gray-800 font-medium">{invitation.inviter_nickname || '未知'}</span>
                  </div>
                  {invitation.member_nickname && (
                    <div className="flex items-center justify-between text-sm mt-2">
                      <span className="text-gray-500">关联成员</span>
                      <span className="text-gray-800 font-medium">{invitation.member_nickname}</span>
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <Button
                    block
                    loading={submitting}
                    style={{
                      background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 24,
                      height: 44,
                      fontWeight: 600,
                    }}
                    onClick={handleAccept}
                  >
                    同意授权
                  </Button>
                  <Button
                    block
                    disabled={submitting}
                    style={{
                      background: '#f5f5f5',
                      color: '#999',
                      border: 'none',
                      borderRadius: 24,
                      height: 44,
                    }}
                    onClick={handleReject}
                  >
                    拒绝
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {status === 'accepted' && (
          <div className="pt-12">
            <Result
              status="success"
              title="授权成功"
              description="您已同意共管邀请，对方可以查看和管理您的健康档案"
            />
            <div className="mt-6 px-8">
              <Button
                block
                style={{
                  background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 24,
                  height: 44,
                  fontWeight: 600,
                }}
                onClick={() => router.replace('/health-profile')}
              >
                查看健康档案
              </Button>
            </div>
          </div>
        )}

        {status === 'rejected' && (
          <div className="pt-12">
            <Result
              status="info"
              title="已拒绝"
              description="您已拒绝此共管邀请"
            />
            <div className="mt-6 px-8">
              <Button
                block
                style={{
                  background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 24,
                  height: 44,
                  fontWeight: 600,
                }}
                onClick={() => router.replace('/')}
              >
                返回首页
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

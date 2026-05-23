'use client';

import { useState, useEffect, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Button, Dialog, Result } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';

interface InvitationDetail {
  invite_code: string;
  status: string;
  inviter_nickname?: string;
  member_nickname?: string;
  expires_at: string;
  created_at: string;
}

interface ReverseInvitationDetail {
  invite_code: string;
  status: string;
  invitee_user_id: number;
  invitee_nickname?: string | null;
  invitee_avatar?: string | null;
  max_uses: number;
  used_count: number;
  expires_at: string;
  created_at: string;
  check_result?: string | null;
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
  const inviteType = searchParams.get('type');
  const isReverse = inviteType === 'reverse';

  const [status, setStatus] = useState<PageStatus>('loading');
  const [invitation, setInvitation] = useState<InvitationDetail | null>(null);
  const [reverseInvitation, setReverseInvitation] = useState<ReverseInvitationDetail | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const wechatCheckedRef = useRef(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const returnUrl = `${basePath}/family-auth?code=${code || ''}${isReverse ? '&type=reverse' : ''}`;
      router.replace(`/login?redirect=${encodeURIComponent(returnUrl)}`);
      return;
    }
    if (!code) {
      setErrorMsg('无效的邀请链接');
      setStatus('error');
      return;
    }

    if (!isReverse) {
      const isWechat = /MicroMessenger/i.test(navigator.userAgent);
      if (isWechat && !wechatCheckedRef.current) {
        wechatCheckedRef.current = true;
        const schemeUrl = `weixin://dl/business/?appid=wx_placeholder&path=/pages/family-auth/index&query=code%3D${code}`;
        window.location.href = schemeUrl;
        setTimeout(() => {
          fetchInvitation();
        }, 3000);
        return;
      }
    }

    if (isReverse) {
      fetchReverseInvitation();
    } else {
      fetchInvitation();
    }
  }, [code, isReverse]);

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

  const fetchReverseInvitation = async () => {
    setStatus('loading');
    try {
      const res: any = await api.get(`/api/reverse-guardian/invite/${code}`);
      const data: ReverseInvitationDetail = res.data || res;
      setReverseInvitation(data);

      const cr = data.check_result;
      if (cr === 'expired' || data.status === 'expired') {
        setErrorMsg('邀请已过期，请联系对方重新发送');
        setStatus('error');
      } else if (cr === 'full') {
        setErrorMsg('邀请名额已满');
        setStatus('error');
      } else if (cr === 'already_guardian') {
        setErrorMsg('你已经是对方的守护者了');
        setStatus('error');
      } else if (cr === 'self_invite') {
        setErrorMsg('不能守护自己哦');
        setStatus('error');
      } else if (data.status !== 'pending') {
        setErrorMsg('邀请状态异常');
        setStatus('error');
      } else {
        setStatus('confirm');
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
      if (isReverse) {
        await api.post(`/api/reverse-guardian/invite/${code}/accept`);
        setStatus('accepted');
        showToast('已成为守护者', 'success');
      } else {
        await api.post(`/api/family/invitation/${code}/accept`);
        setStatus('accepted');
        showToast('已接受邀请', 'success');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '操作失败，请重试';
      showToast(detail, 'fail');
    }
    setSubmitting(false);
  };

  const handleReject = async () => {
    const result = await Dialog.confirm({
      title: isReverse ? '拒绝守护' : '拒绝邀请',
      content: isReverse ? '确定要拒绝守护对方的健康吗？' : '确定要拒绝此守护邀请吗？',
    });
    if (!result) return;
    setSubmitting(true);
    try {
      if (isReverse) {
        setStatus('rejected');
      } else {
        await api.post(`/api/family/invitation/${code}/reject`);
        setStatus('rejected');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '操作失败，请重试';
      showToast(detail, 'fail');
    }
    setSubmitting(false);
  };

  const handleOpenMiniProgram = () => {
    const schemeUrl = `weixin://dl/business/?appid=wx_placeholder&path=/pages/family-auth/index&query=code%3D${code}`;
    window.location.href = schemeUrl;
  };

  const displayInviterName = isReverse
    ? (reverseInvitation?.invitee_nickname || '对方')
    : (invitation?.inviter_nickname || '对方');

  const displayInviterChar = (displayInviterName || '对')[0];

  return (
    <div className="min-h-screen" style={{ background: isReverse ? 'linear-gradient(160deg, #E8F5E9 0%, #e8f4ff 100%)' : 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}>
      <NavBar onBack={() => router.back()} style={{ background: 'transparent' }}>
        {isReverse ? '守护确认' : '授权确认'}
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
                  background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
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

        {status === 'confirm' && (invitation || reverseInvitation) && (
          <div className="pt-6">
            <div
              className="rounded-3xl overflow-hidden mx-auto"
              style={{
                maxWidth: 340,
                background: '#fff',
                boxShadow: '0 8px 32px rgba(56,189,248, 0.12)',
              }}
            >
              <div className="px-6 pt-10 pb-6 text-center">
                <div
                  className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                  style={{ background: isReverse ? 'linear-gradient(135deg, #4CAF50, #66BB6A)' : 'linear-gradient(135deg, #0EA5E9, #38BDF8)' }}
                >
                  <span className="text-white text-2xl font-bold">
                    {displayInviterChar}
                  </span>
                </div>
                <div className="text-lg font-bold text-gray-800 mb-2">
                  {displayInviterName}
                </div>
                <div className="text-sm text-gray-500">
                  {isReverse
                    ? `${displayInviterName} 邀请你守护 TA 的健康`
                    : 'TA 邀请你加入家庭健康圈'}
                </div>
              </div>

              <div className="px-6 pb-8">
                <div className="space-y-3">
                  <Button
                    block
                    loading={submitting}
                    style={{
                      background: isReverse ? 'linear-gradient(135deg, #4CAF50, #66BB6A)' : 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 24,
                      height: 48,
                      fontWeight: 600,
                      fontSize: 16,
                    }}
                    onClick={handleAccept}
                  >
                    {isReverse ? '同意守护' : '同意'}
                  </Button>
                  <Button
                    block
                    disabled={submitting}
                    style={{
                      background: '#f5f5f5',
                      color: '#999',
                      border: 'none',
                      borderRadius: 24,
                      height: 48,
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
          <div className="pt-6">
            <div
              className="rounded-3xl overflow-hidden mx-auto"
              style={{
                maxWidth: 340,
                background: '#fff',
                boxShadow: '0 8px 32px rgba(56,189,248, 0.12)',
              }}
            >
              <div className="px-6 pt-10 pb-8 text-center">
                <div
                  className="w-20 h-20 rounded-full mx-auto mb-4 flex items-center justify-center"
                  style={{ background: isReverse ? 'linear-gradient(135deg, #4CAF50, #66BB6A)' : 'linear-gradient(135deg, #0EA5E9, #38BDF8)' }}
                >
                  <span className="text-white text-3xl font-bold">
                    {displayInviterChar}
                  </span>
                </div>
                <div className="text-lg font-bold text-gray-800 mb-2">
                  {displayInviterName}
                </div>
                <div className="text-sm text-gray-500 mb-6">
                  {isReverse
                    ? `你已成为 ${displayInviterName} 的守护者`
                    : `${displayInviterName} 已成为你的家人`}
                </div>

                <div
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs mb-8"
                  style={{ background: isReverse ? '#E8F5E9' : '#F0F9FF', color: isReverse ? '#2E7D32' : '#0EA5E9', border: isReverse ? '1px solid #C8E6C9' : '1px solid #d9f7be' }}
                >
                  <span>✓</span>
                  <span>{isReverse ? '守护成功' : '授权成功'}</span>
                </div>

                <div className="space-y-3">
                  {!isReverse && (
                    <Button
                      block
                      style={{
                        background: '#07c160',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 24,
                        height: 48,
                        fontWeight: 600,
                        fontSize: 16,
                      }}
                      onClick={handleOpenMiniProgram}
                    >
                      打开小程序查看
                    </Button>
                  )}
                  <div
                    className="text-center text-sm text-gray-400 py-2 cursor-pointer"
                    onClick={() => router.replace('/health-profile')}
                  >
                    {isReverse ? '返回健康档案' : '稍后再说'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {status === 'rejected' && (
          <div className="pt-12">
            <Result
              status="info"
              title="已拒绝"
              description={isReverse ? '您已拒绝守护对方的健康' : '您已拒绝此守护邀请'}
            />
            <div className="mt-6 px-8">
              <Button
                block
                style={{
                  background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
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

'use client';

import { useState, useEffect, useRef, Suspense, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Button, Dialog, Result } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';

interface InvitationDetail {
  invite_code: string;
  status: string;
  inviter_nickname?: string;
  inviter_real_name?: string;
  inviter_avatar?: string;
  relation_type?: string;
  invite_type?: string;
  member_nickname?: string;
  expires_at: string;
  created_at: string;
  is_self_invite?: boolean;
  invalid_reason?: string;
}

interface ReverseInvitationDetail {
  invite_code: string;
  status: string;
  invitee_user_id: number;
  invitee_nickname?: string | null;
  invitee_avatar?: string | null;
  inviter_real_name?: string | null;
  relation_type?: string | null;
  max_uses: number;
  used_count: number;
  expires_at: string;
  created_at: string;
  check_result?: string | null;
}

type PageStatus = 'loading' | 'confirm' | 'accepted' | 'rejected' | 'error';

function ProtocolDrawer({
  visible,
  title,
  protocolKey,
  onClose,
}: {
  visible: boolean;
  title: string;
  protocolKey: string;
  onClose: () => void;
}) {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (visible && protocolKey) {
      setLoading(true);
      setError(false);
      api
        .get(`/api/public/protocol/${protocolKey}`)
        .then((res: any) => {
          const data = res.data || res;
          setContent(typeof data === 'string' ? data : data.content || data.text || JSON.stringify(data));
        })
        .catch(() => {
          setError(true);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [visible, protocolKey]);

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-end',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0,0,0,0.5)',
        }}
        onClick={onClose}
      />
      <div
        style={{
          position: 'relative',
          background: '#fff',
          borderRadius: '16px 16px 0 0',
          maxHeight: '70vh',
          display: 'flex',
          flexDirection: 'column',
          animation: 'slideUp 0.3s ease',
        }}
      >
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid #f0f0f0',
            fontWeight: 600,
            fontSize: 16,
            textAlign: 'center',
          }}
        >
          {title}
        </div>
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: '16px 20px',
            fontSize: 14,
            lineHeight: 1.8,
            color: '#333',
            whiteSpace: 'pre-wrap',
          }}
        >
          {loading && <div style={{ textAlign: 'center', color: '#999' }}>加载中...</div>}
          {error && <div style={{ textAlign: 'center', color: '#ff4d4f' }}>协议加载失败，请重试</div>}
          {!loading && !error && content}
        </div>
        <div style={{ padding: '12px 20px 24px' }}>
          <Button
            block
            style={{
              borderRadius: 24,
              height: 44,
              fontWeight: 600,
            }}
            onClick={onClose}
          >
            关闭
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function FamilyAuthPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-gray-400">加载中...</div>}>
      <FamilyAuthContent />
      <style jsx global>{`
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
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

  const [agreedProtocol, setAgreedProtocol] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [drawerTitle, setDrawerTitle] = useState('');
  const [drawerKey, setDrawerKey] = useState('');

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

      if (data.is_self_invite || data.invalid_reason === 'self') {
        setErrorMsg('无法接受自己发起的邀请');
        setStatus('error');
      } else if (data.status === 'accepted') {
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
        setErrorMsg('无法接受自己发起的邀请');
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

  const openProtocol = useCallback((title: string, key: string) => {
    setDrawerTitle(title);
    setDrawerKey(key);
    setDrawerVisible(true);
  }, []);

  // F8: Priority display - inviter_real_name → inviter_nickname → '对方'
  const displayInviterName = isReverse
    ? (reverseInvitation?.inviter_real_name || reverseInvitation?.invitee_nickname || '对方')
    : (invitation?.inviter_real_name || invitation?.inviter_nickname || '对方');

  const displayInviterChar = (displayInviterName || '对')[0];

  // F6: Dynamic copy with relation type
  const relationType = isReverse
    ? reverseInvitation?.relation_type
    : invitation?.relation_type;

  const getInviteDescription = () => {
    if (isReverse) {
      if (relationType) {
        return `${displayInviterName} 想让你成为 TA 的守护人（${relationType}）`;
      }
      return `${displayInviterName} 邀请你守护 TA 的健康`;
    } else {
      if (relationType) {
        return `${displayInviterName} 想把你添加为 TA 的${relationType}`;
      }
      return 'TA 邀请你加入家庭健康圈';
    }
  };

  return (
    <div className="min-h-screen" style={{ background: isReverse ? 'linear-gradient(160deg, #E8F5E9 0%, #e8f4ff 100%)' : 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}>
      <NavBar onBack={() => router.back()} style={{ background: 'transparent' }}>
        {isReverse ? '守护确认' : '授权确认'}
      </NavBar>

      {/* F10: Brand identity bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '12px 16px',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 22 }}>🌿</span>
        <span style={{ fontSize: 15, fontWeight: 500, color: '#2E7D32' }}>
          宾尼小康AI健康管家
        </span>
      </div>

      <div className="px-4 pt-2 pb-8">
        {status === 'loading' && (
          <div className="text-center py-20 text-gray-400 text-sm">加载中...</div>
        )}

        {status === 'error' && (() => {
          // [Bug-5] 根据后端返回的 detail 内容区分不同错误场景展示不同标题
          const getErrorTitle = () => {
            const msg = errorMsg || '';
            if (msg.includes('已是该家庭的成员') || msg.includes('您已是对方的守护者') || msg.includes('重复绑定')) {
              return '您已在守护关系中';
            }
            if (msg.includes('已过期')) {
              return '邀请已过期';
            }
            if (msg.includes('已取消') || msg.includes('已失效')) {
              return '邀请已取消';
            }
            if (msg.includes('不能接受自己')) {
              return '无法处理邀请';
            }
            if (msg.includes('已达上限')) {
              return '无法处理邀请';
            }
            if (msg.includes('已接受') || msg.includes('已被接受')) {
              return '邀请已失效';
            }
            if (msg.includes('状态异常')) {
              return '邀请状态异常';
            }
            return '无法处理邀请';
          };
          return (
          <div className="pt-12">
            <Result
              status="warning"
              title={getErrorTitle()}
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
          );
        })()}

        {status === 'confirm' && (invitation || reverseInvitation) && (
          <div className="pt-4">
            <div
              className="rounded-3xl overflow-hidden mx-auto"
              style={{
                maxWidth: 340,
                background: '#fff',
                boxShadow: '0 8px 32px rgba(56,189,248, 0.12)',
              }}
            >
              {/* F7: Horizontal layout - avatar left, name + description right */}
              <div style={{ padding: '24px 24px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: '50%',
                    background: isReverse ? 'linear-gradient(135deg, #4CAF50, #66BB6A)' : 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <span style={{ color: '#fff', fontSize: 20, fontWeight: 700 }}>
                    {displayInviterChar}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: '#1f2937', marginBottom: 4 }}>
                    {displayInviterName}
                  </div>
                  <div style={{ fontSize: 13, color: '#6b7280', lineHeight: 1.4 }}>
                    {getInviteDescription()}
                  </div>
                </div>
              </div>

              {/* F9: Protocol checkbox */}
              <div style={{ padding: '12px 24px 8px' }}>
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 8,
                    cursor: 'pointer',
                    fontSize: 12,
                    color: '#6b7280',
                    lineHeight: 1.6,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={agreedProtocol}
                    onChange={(e) => setAgreedProtocol(e.target.checked)}
                    style={{
                      width: 16,
                      height: 16,
                      marginTop: 2,
                      flexShrink: 0,
                      accentColor: '#2E7D32',
                    }}
                  />
                  <span>
                    我已阅读并同意
                    <span
                      style={{ color: '#0EA5E9', cursor: 'pointer' }}
                      onClick={(e) => { e.preventDefault(); openProtocol('用户服务协议', 'userAgreement'); }}
                    >
                      《用户服务协议》
                    </span>
                    和
                    <span
                      style={{ color: '#0EA5E9', cursor: 'pointer' }}
                      onClick={(e) => { e.preventDefault(); openProtocol('健康数据授权协议', 'healthDataAuthorization'); }}
                    >
                      《健康数据授权协议》
                    </span>
                  </span>
                </label>
              </div>

              <div className="px-6 pb-8 pt-4">
                <div className="space-y-3">
                  <Button
                    block
                    loading={submitting}
                    disabled={!agreedProtocol}
                    style={{
                      background: agreedProtocol
                        ? (isReverse ? 'linear-gradient(135deg, #4CAF50, #66BB6A)' : 'linear-gradient(135deg, #0EA5E9, #38BDF8)')
                        : '#d1d5db',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 24,
                      height: 48,
                      fontWeight: 600,
                      fontSize: 16,
                      opacity: agreedProtocol ? 1 : 0.7,
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

      <ProtocolDrawer
        visible={drawerVisible}
        title={drawerTitle}
        protocolKey={drawerKey}
        onClose={() => setDrawerVisible(false)}
      />
    </div>
  );
}

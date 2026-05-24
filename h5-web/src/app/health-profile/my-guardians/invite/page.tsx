'use client';

import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import { QRCodeCanvas } from 'qrcode.react';
import api from '@/lib/api';
import { RELATION_DEFS } from '@/lib/family-relation';

interface InviteData {
  invite_code: string;
  qr_url: string;
  expires_at: string;
  max_uses?: number;
  used_count?: number;
}

const RELATION_OPTIONS = RELATION_DEFS.map((d) => d.name);

function InvitePageInner() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [invite, setInvite] = useState<InviteData | null>(null);
  const [error, setError] = useState('');

  const [selectedRelation, setSelectedRelation] = useState<string>('');
  const [customRelation, setCustomRelation] = useState('');
  const customRelationTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [profileChecked, setProfileChecked] = useState(false);
  const [showProfileDrawer, setShowProfileDrawer] = useState(false);
  const [profileName, setProfileName] = useState('');
  const [profileId, setProfileId] = useState<number | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);

  const THEME = {
    gradientStart: '#4CAF50',
    gradientEnd: '#66BB6A',
  };

  useEffect(() => {
    checkProfile();
  }, []);

  const checkProfile = async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      const items: any[] = Array.isArray(data.items) ? data.items : [];
      const selfMember = items.find((x: any) => x.is_self === true);
      if (selfMember) {
        const hp = selfMember.health_profile || selfMember.healthProfile;
        if (hp && !hp.name) {
          setProfileId(hp.id || selfMember.health_profile_id || null);
          setShowProfileDrawer(true);
          return;
        }
      }
    } catch {}
    setProfileChecked(true);
  };

  const handleSaveProfile = async () => {
    if (!profileName.trim()) {
      showToast('请输入姓名', 'fail');
      return;
    }
    setSavingProfile(true);
    try {
      if (profileId) {
        await api.put(`/api/health-profile/${profileId}`, { name: profileName.trim() });
      }
      showToast('保存成功');
      setShowProfileDrawer(false);
      setProfileChecked(true);
    } catch {
      showToast('保存失败，请重试', 'fail');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSkipProfile = () => {
    setShowProfileDrawer(false);
    setProfileChecked(true);
  };

  const createInvite = useCallback(async (relationOverride?: string) => {
    setLoading(true);
    setError('');
    try {
      const body: any = {};
      const rel = relationOverride !== undefined ? relationOverride : (selectedRelation === '其他' ? customRelation : selectedRelation);
      if (rel) body.relation_type = rel;
      const res: any = await api.post('/api/reverse-guardian/invite', body);
      const data = res.data || res;
      setInvite(data);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '生成邀请失败';
      setError(String(msg));
      showToast(String(msg), 'fail');
    } finally {
      setLoading(false);
    }
  }, [selectedRelation, customRelation]);

  const handleRelationSelect = (rel: string) => {
    setSelectedRelation(rel);
    if (rel !== '其他') {
      setCustomRelation('');
      createInvite(rel);
    } else {
      setInvite(null);
    }
  };

  const handleCustomRelationChange = (val: string) => {
    const trimmed = val.slice(0, 8);
    setCustomRelation(trimmed);
    if (customRelationTimer.current) clearTimeout(customRelationTimer.current);
    if (trimmed.length > 0) {
      customRelationTimer.current = setTimeout(() => {
        createInvite(trimmed);
      }, 500);
    } else {
      setInvite(null);
    }
  };

  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const inviteLink = invite
    ? (invite.qr_url || `${typeof window !== 'undefined' ? window.location.origin : ''}${basePath}/family-auth?code=${invite.invite_code}&type=reverse`)
    : '';

  const qrContentUrl = inviteLink;
  const qrCanvasRef = useRef<HTMLDivElement>(null);

  const handleCopyLink = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      showToast('链接已复制');
    } catch {
      showToast('复制失败，请手动复制', 'fail');
    }
  };

  const handleSaveImage = useCallback(() => {
    const canvas = qrCanvasRef.current?.querySelector('canvas');
    if (!canvas) {
      showToast('二维码未生成', 'fail');
      return;
    }
    try {
      const url = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.download = `bini-health-guardian-invite-${invite?.invite_code?.slice(0, 8) || 'qr'}.png`;
      link.href = url;
      link.click();
      showToast('图片已保存');
    } catch {
      showToast('保存失败，请截图保存', 'fail');
    }
  }, [invite]);

  const handleShareWechat = () => {
    showToast('请点击右上角"..."分享给微信好友');
  };

  const canShowQr = selectedRelation && (selectedRelation !== '其他' || customRelation.length > 0);

  return (
    <div style={{ background: '#F0F5FF', minHeight: '100vh', paddingBottom: 40 }}>
      {/* Nav bar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
        padding: '12px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        color: '#fff',
        boxShadow: '0 2px 8px rgba(76,175,80,0.3)',
      }}>
        <button
          onClick={() => router.back()}
          style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff', fontSize: 18 }}
        >←</button>
        <span style={{ flex: 1, fontSize: 17, fontWeight: 700, textAlign: 'center' }}>邀请 TA 守护我的健康</span>
        <span style={{ width: 36 }} />
      </div>

      {/* Brand bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '12px 16px', background: '#fff', gap: 8,
      }}>
        <span style={{ fontSize: 22 }}>🌿</span>
        <span style={{ fontSize: 15, fontWeight: 600, color: '#333' }}>宾尼小康AI健康管家</span>
      </div>

      <div style={{ padding: '16px 16px' }}>
        {/* Relation selector - always shown */}
        {profileChecked && (
          <div style={{
            background: '#fff', borderRadius: 16, padding: '16px 16px 12px',
            marginBottom: 16, boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#333', marginBottom: 12 }}>
              请选择 TA 与您的关系
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {RELATION_OPTIONS.map((rel) => (
                <button
                  key={rel}
                  onClick={() => handleRelationSelect(rel)}
                  style={{
                    padding: '6px 14px', borderRadius: 16,
                    border: selectedRelation === rel ? `1.5px solid ${THEME.gradientStart}` : '1.5px solid #E5E7EB',
                    background: selectedRelation === rel ? '#E8F5E9' : '#F9FAFB',
                    color: selectedRelation === rel ? THEME.gradientStart : '#4B5563',
                    fontSize: 13, fontWeight: 500, cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >{rel}</button>
              ))}
            </div>
            {/* Custom input for "其他" */}
            {selectedRelation === '其他' && (
              <div style={{ marginTop: 12 }}>
                <input
                  type="text"
                  value={customRelation}
                  onChange={(e) => handleCustomRelationChange(e.target.value)}
                  placeholder="请输入关系名称（1~8字）"
                  maxLength={8}
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 10,
                    border: `1.5px solid ${THEME.gradientStart}`, outline: 'none',
                    fontSize: 14, color: '#333', boxSizing: 'border-box',
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* Main content */}
        {!profileChecked ? (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>正在检查资料…</div>
        ) : loading ? (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>正在生成邀请…</div>
        ) : error && canShowQr ? (
          <div style={{
            background: '#fff', borderRadius: 16, padding: '40px 20px',
            textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 14, color: '#6B7280', marginBottom: 16 }}>{error}</div>
            <button
              onClick={() => createInvite()}
              style={{
                padding: '10px 24px', borderRadius: 20,
                background: THEME.gradientStart, color: '#fff',
                border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >重新生成</button>
          </div>
        ) : invite && canShowQr ? (
          <>
            {/* Gradient Card */}
            <div style={{
              background: '#fff', borderRadius: 20, overflow: 'hidden',
              boxShadow: '0 8px 32px rgba(76,175,80,0.12)',
              maxWidth: 360, margin: '0 auto',
            }}>
              {/* Card Header */}
              <div style={{
                background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                padding: '24px 20px 18px', textAlign: 'center', color: '#fff',
              }}>
                <div style={{ fontSize: 19, fontWeight: 700, marginBottom: 10 }}>邀请 TA 守护我的健康</div>
                <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
                  {[
                    { icon: '📋', text: '档案管理' },
                    { icon: '💊', text: '用药提醒' },
                    { icon: '🔔', text: '异常提醒' },
                  ].map((tag) => (
                    <span key={tag.text} style={{
                      background: 'rgba(255,255,255,0.22)',
                      padding: '4px 12px', borderRadius: 14,
                      fontSize: 12, fontWeight: 500, color: '#fff',
                    }}>{tag.icon} {tag.text}</span>
                  ))}
                </div>
              </div>

              {/* Card Body */}
              <div style={{ padding: '20px 24px 24px', textAlign: 'center' }}>
                <div
                  ref={qrCanvasRef}
                  style={{
                    display: 'inline-flex', padding: 10, borderRadius: 14,
                    border: '2px solid #E8F5E9', background: '#fff',
                  }}
                >
                  <QRCodeCanvas
                    value={qrContentUrl}
                    size={164}
                    level="M"
                    includeMargin={false}
                    bgColor="#ffffff"
                    fgColor="#333333"
                  />
                </div>

                <div style={{ marginTop: 14, fontSize: 12, color: '#9CA3AF' }}>
                  邀请有效期：24小时
                </div>

                <div style={{
                  marginTop: 10, padding: '8px 14px', borderRadius: 10,
                  background: '#F0FDF4', fontSize: 13, color: '#166534',
                }}>
                  💚 让 TA 随时关注我的健康
                </div>

                {/* Buttons */}
                <div style={{ marginTop: 18 }}>
                  <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
                    <button
                      onClick={handleSaveImage}
                      style={{
                        flex: 1, padding: '12px 0', borderRadius: 22,
                        background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                        color: '#fff', border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                      }}
                    >保存到本地</button>
                    <button
                      onClick={handleCopyLink}
                      style={{
                        flex: 1, padding: '12px 0', borderRadius: 22,
                        background: '#fff', color: THEME.gradientStart,
                        border: `1.5px solid ${THEME.gradientStart}`,
                        fontSize: 14, fontWeight: 600, cursor: 'pointer',
                      }}
                    >复制链接</button>
                  </div>
                  <button
                    onClick={handleShareWechat}
                    style={{
                      width: '100%', padding: '12px 0', borderRadius: 22,
                      background: '#07c160', color: '#fff',
                      border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                    }}
                  >转发微信好友</button>
                </div>
              </div>
            </div>
          </>
        ) : profileChecked && !canShowQr ? (
          <div style={{
            background: '#fff', borderRadius: 16, padding: '32px 20px',
            textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
            color: '#9CA3AF', fontSize: 14,
          }}>
            请先选择关系类型，选择后将生成邀请二维码
          </div>
        ) : null}
      </div>

      {/* Profile Drawer */}
      {showProfileDrawer && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,0.4)',
          display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
        }}>
          <div style={{
            background: '#fff', borderRadius: '20px 20px 0 0',
            width: '100%', maxWidth: 500, padding: '24px 20px 32px',
            animation: 'slideUp 0.3s ease',
          }}>
            <div style={{ fontSize: 17, fontWeight: 700, color: '#333', marginBottom: 20, textAlign: 'center' }}>
              完善个人资料
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, color: '#6B7280', marginBottom: 6, display: 'block' }}>姓名（必填）</label>
              <input
                type="text"
                value={profileName}
                onChange={(e) => setProfileName(e.target.value)}
                placeholder="请输入您的姓名"
                style={{
                  width: '100%', padding: '12px 14px', borderRadius: 10,
                  border: '1.5px solid #E5E7EB', outline: 'none',
                  fontSize: 15, color: '#333', boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 13, color: '#6B7280', marginBottom: 6, display: 'block' }}>关系</label>
              <div style={{
                padding: '12px 14px', borderRadius: 10,
                background: '#F3F4F6', fontSize: 15, color: '#6B7280',
              }}>本人</div>
            </div>
            <button
              onClick={handleSaveProfile}
              disabled={savingProfile}
              style={{
                width: '100%', padding: '14px 0', borderRadius: 22,
                background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                color: '#fff', border: 'none', fontSize: 15, fontWeight: 600,
                cursor: savingProfile ? 'not-allowed' : 'pointer',
                opacity: savingProfile ? 0.7 : 1,
              }}
            >{savingProfile ? '保存中...' : '保存并继续邀请'}</button>
            <button
              onClick={handleSkipProfile}
              style={{
                width: '100%', padding: '12px 0', marginTop: 10,
                background: 'transparent', color: '#9CA3AF',
                border: 'none', fontSize: 13, cursor: 'pointer',
              }}
            >跳过</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function InviteGuardianPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <InvitePageInner />
    </Suspense>
  );
}

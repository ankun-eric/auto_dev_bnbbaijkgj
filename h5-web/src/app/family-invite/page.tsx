'use client';

import { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import { QRCodeCanvas } from 'qrcode.react';
import api from '@/lib/api';
import { RELATION_DEFS } from '@/lib/family-relation';
import { validateNickname, validateRelation } from '@/utils/nicknameValidator';

interface InvitationData {
  invite_code: string;
  qr_url: string;
  qr_content_url?: string;
  expires_at: string;
}

// [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G1] 保留以兼容旧实现引用，但页面不再渲染胶囊选择器
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const RELATION_OPTIONS = RELATION_DEFS.map((d) => d.name);

export default function FamilyInvitePage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>加载中...</div>}>
      <FamilyInviteContent />
    </Suspense>
  );
}

function FamilyInviteContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const memberId = searchParams.get('member_id');

  const [loading, setLoading] = useState(false);
  const [invitation, setInvitation] = useState<InvitationData | null>(null);
  const [error, setError] = useState('');
  const [memberName, setMemberName] = useState<string>('');

  // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G1] 场景 2 改用文本输入框 + 校验后
  // 主动提交。原有"关系胶囊 + 其他文字框"组件不再使用，但保留 state 以兼容 createInvitation
  // 的旧签名（默认空串，等价于不填）。
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [selectedRelation, _setSelectedRelation] = useState<string>('');
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [customRelation, _setCustomRelation] = useState('');
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const customRelationTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G1] 场景 2 入口（无 member_id）
  //   场景需求：姓名 + 关系 都用文本输入框，必填红星，校验三端一致后才能生成邀请。
  //   关系下拉不带默认值（D4），用户必须显式选择。
  const [inviteNickname, setInviteNickname] = useState('');
  const [inviteRelation, setInviteRelation] = useState('');
  const [submittingInvite, setSubmittingInvite] = useState(false);

  const [profileChecked, setProfileChecked] = useState(false);
  const [showProfileDrawer, setShowProfileDrawer] = useState(false);
  const [profileName, setProfileName] = useState('');
  const [profileId, setProfileId] = useState<number | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);

  const THEME = {
    gradientStart: '#0EA5E9',
    gradientEnd: '#38BDF8',
  };

  useEffect(() => {
    checkProfile();
  }, []);

  useEffect(() => {
    if (!memberId) return;
    (async () => {
      try {
        const res: any = await api.get('/api/family/members');
        const data = res.data || res;
        const items: any[] = Array.isArray(data.items) ? data.items : [];
        const m = items.find((x: any) => String(x.id) === memberId);
        if (m) setMemberName(m.nickname || m.name || '');
      } catch {}
    })();
  }, [memberId]);

  useEffect(() => {
    if (!profileChecked) return;
    // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G1] 仅在有 member_id 时（从档案卡片
    // 直接邀请）才自动进入"生成二维码"流程。无 member_id 时（场景 2 入口）必须先
    // 在表单填写姓名 + 关系，由用户主动点击"生成邀请码"。
    if (memberId) {
      createInvitation();
    }
  }, [profileChecked, memberId]);

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

  const createInvitation = async (
    relationOverride?: string,
    nicknameOverride?: string,
  ) => {
    setLoading(true);
    setError('');
    try {
      const body: any = {};
      if (memberId) body.member_id = Number(memberId);
      const rel =
        relationOverride !== undefined
          ? relationOverride
          : selectedRelation === '其他'
          ? customRelation
          : selectedRelation;
      if (rel) body.relation_type = rel;
      // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G1] 场景 2 入口提交 nickname
      if (nicknameOverride && nicknameOverride.trim()) {
        body.nickname = nicknameOverride.trim();
      }
      const res: any = await api.post('/api/family/invitation', body);
      const data = res.data || res;
      setInvitation(data);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '生成邀请失败，请重试';
      setError(detail);
      showToast(detail, 'fail');
    }
    setLoading(false);
  };

  // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G1] 场景 2：表单提交
  const handleInviteSubmit = async () => {
    const nv = validateNickname(inviteNickname);
    if (!nv.ok) {
      showToast(nv.msg, 'fail');
      return;
    }
    const rv = validateRelation(inviteRelation);
    if (!rv.ok) {
      showToast(rv.msg, 'fail');
      return;
    }
    setSubmittingInvite(true);
    try {
      await createInvitation(inviteRelation.trim(), inviteNickname.trim());
    } finally {
      setSubmittingInvite(false);
    }
  };

  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const inviteLink = invitation
    ? `${typeof window !== 'undefined' ? window.location.origin : ''}${basePath}/family-auth?code=${invitation.invite_code}`
    : '';

  const qrContentUrl = invitation
    ? (invitation.qr_content_url || inviteLink)
    : '';

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
      link.download = `bini-health-invite-${invitation?.invite_code?.slice(0, 8) || 'qr'}.png`;
      link.href = url;
      link.click();
      showToast('图片已保存');
    } catch {
      showToast('保存失败，请截图保存', 'fail');
    }
  }, [invitation]);

  const handleShareWechat = () => {
    showToast('请点击右上角"..."分享给微信好友');
  };

  // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G1] 无 member_id（场景 2）：
  //   渲染"姓名 + 关系"输入框，由用户主动提交后才进入二维码状态。
  const needInviteForm = !memberId;
  const canShowQr = memberId ? true : Boolean(invitation);

  return (
    <div style={{ background: '#F0F5FF', minHeight: '100vh', paddingBottom: 40 }}>
      {/* Nav bar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
        padding: '12px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        color: '#fff',
        boxShadow: '0 2px 8px rgba(14,165,233,0.3)',
      }}>
        <button
          onClick={() => router.back()}
          style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff', fontSize: 18 }}
        >←</button>
        <span style={{ flex: 1, fontSize: 17, fontWeight: 700, textAlign: 'center' }}>邀请 TA 成为被守护人</span>
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
        {/* [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G1]
            场景 2 入口（无 member_id 且未生成二维码）：渲染姓名 + 关系输入框。
            UI 与 i-guard InviteGuardianDrawer 完全一致，校验三端字符级对齐。 */}
        {needInviteForm && profileChecked && !invitation && (
          <div
            data-testid="family-invite-form"
            style={{
              background: '#fff', borderRadius: 16, padding: '16px 16px 18px',
              marginBottom: 16, boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: '#333', marginBottom: 14 }}>
              填写邀请信息
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 6 }}>
                姓名 <span style={{ color: '#EF4444' }}>*</span>
              </div>
              <input
                data-testid="family-invite-nickname"
                type="text"
                value={inviteNickname}
                onChange={(e) => setInviteNickname(e.target.value)}
                placeholder="如：张妈妈 / 李叔叔"
                maxLength={20}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 10,
                  border: '1px solid #E2E8F0', outline: 'none',
                  fontSize: 14, color: '#333', boxSizing: 'border-box',
                }}
              />
              {!inviteNickname.trim() && (
                <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4 }}>姓名不能为空</div>
              )}
            </div>

            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 6 }}>
                关系 <span style={{ color: '#EF4444' }}>*</span>
              </div>
              <input
                data-testid="family-invite-relation"
                type="text"
                value={inviteRelation}
                onChange={(e) => setInviteRelation(e.target.value)}
                placeholder="如：父亲、母亲、配偶"
                maxLength={10}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 10,
                  border: '1px solid #E2E8F0', outline: 'none',
                  fontSize: 14, color: '#333', boxSizing: 'border-box',
                }}
              />
            </div>

            <button
              data-testid="family-invite-submit"
              disabled={submittingInvite || loading}
              onClick={handleInviteSubmit}
              style={{
                width: '100%', padding: '12px 0', borderRadius: 22,
                background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                color: '#fff', border: 'none', fontSize: 15, fontWeight: 600,
                cursor: submittingInvite || loading ? 'not-allowed' : 'pointer',
                opacity: submittingInvite || loading ? 0.7 : 1,
              }}
            >
              {submittingInvite || loading ? '生成中…' : '生成邀请码'}
            </button>
          </div>
        )}

        {/* Main content */}
        {!profileChecked ? (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>正在检查资料…</div>
        ) : loading && memberId ? (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>正在生成邀请…</div>
        ) : error && memberId ? (
          <div style={{
            background: '#fff', borderRadius: 16, padding: '40px 20px',
            textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 14, color: '#6B7280', marginBottom: 16 }}>{error}</div>
            <button
              onClick={() => createInvitation()}
              style={{
                padding: '10px 24px', borderRadius: 20,
                background: THEME.gradientStart, color: '#fff',
                border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >重新生成</button>
          </div>
        ) : invitation && canShowQr ? (
          <>
            {/* Gradient Card */}
            <div style={{
              background: '#fff', borderRadius: 20, overflow: 'hidden',
              boxShadow: '0 8px 32px rgba(14,165,233,0.12)',
              maxWidth: 360, margin: '0 auto',
            }}>
              {/* Card Header */}
              <div style={{
                background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
                padding: '24px 20px 18px', textAlign: 'center', color: '#fff',
              }}>
                <div style={{ fontSize: 19, fontWeight: 700, marginBottom: 10 }}>邀请 TA 成为我守护的人</div>
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
                    border: '2px solid #E0F2FE', background: '#fff',
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
                  background: '#F0F9FF', fontSize: 13, color: '#0369A1',
                }}>
                  {memberId && memberName
                    ? `🔗 将绑定到「${memberName}」的档案`
                    : '➕ 对方确认后将为 TA 新建档案'}
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

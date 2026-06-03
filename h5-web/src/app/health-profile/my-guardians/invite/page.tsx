'use client';

import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Dialog } from 'antd-mobile';
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
  // [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02]
  guardian_name?: string | null;
  relation_type?: string | null;
}

const RELATION_OPTIONS = RELATION_DEFS.map((d) => d.name);
const LIST_PATH = '/health-profile/my-guardians';

function InvitePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 查看已有邀请的二维码：通过 ?code=xxx 进入
  const viewCode = searchParams?.get('code') || '';

  const [loading, setLoading] = useState(false);
  const [invite, setInvite] = useState<InviteData | null>(null);
  const [error, setError] = useState('');

  const [selectedRelation, setSelectedRelation] = useState<string>('');
  const [customRelation, setCustomRelation] = useState('');
  // [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 名字必填
  const [guardianName, setGuardianName] = useState('');
  const customRelationTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [profileChecked, setProfileChecked] = useState(false);
  const [showProfileDrawer, setShowProfileDrawer] = useState(false);
  const [profileName, setProfileName] = useState('');
  const [profileId, setProfileId] = useState<number | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);

  // [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 分两步：'form' | 'qrcode'
  // 'form'：填写关系+名字；'qrcode'：仅展示二维码
  // 查看模式（带 ?code=）直接进入 qrcode 步骤
  const [step, setStep] = useState<'form' | 'qrcode'>(viewCode ? 'qrcode' : 'form');
  const viewMode = !!viewCode;

  // 上限提示
  const [limitInfo, setLimitInfo] = useState<{ x: number; y: number } | null>(null);

  const THEME = {
    gradientStart: '#4CAF50',
    gradientEnd: '#66BB6A',
  };

  useEffect(() => {
    if (viewCode) {
      loadExistingInvite(viewCode);
    } else {
      checkProfile();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewCode]);

  const loadExistingInvite = async (code: string) => {
    setLoading(true);
    setError('');
    try {
      const res: any = await api.get(`/api/reverse-guardian/invite/${encodeURIComponent(code)}`);
      const data = res.data || res;
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const qrUrl = `${origin}${basePath}/family-auth?code=${data.invite_code}&type=reverse`;
      setInvite({
        invite_code: data.invite_code,
        qr_url: qrUrl,
        expires_at: data.expires_at,
        guardian_name: data.guardian_name,
        relation_type: data.relation_type,
      });
      if (data.relation_type) {
        setSelectedRelation(RELATION_OPTIONS.includes(data.relation_type) ? data.relation_type : '其他');
        if (!RELATION_OPTIONS.includes(data.relation_type)) setCustomRelation(data.relation_type);
      }
      if (data.guardian_name) setGuardianName(data.guardian_name);
      setProfileChecked(true);
      setStep('qrcode');
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : '邀请已失效或不存在';
      setError(msg);
      showToast(msg, 'fail');
    } finally {
      setLoading(false);
    }
  };

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

  // [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 第一步「确认」按钮：创建后切到第二步
  const handleConfirm = useCallback(async () => {
    const finalName = guardianName.trim();
    if (!finalName) {
      showToast('请输入对方名字', 'fail');
      return;
    }
    const rel = selectedRelation === '其他' ? customRelation.trim() : selectedRelation;
    if (!rel) {
      showToast('请选择关系', 'fail');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const body: any = { guardian_name: finalName, relation_type: rel };
      const res: any = await api.post('/api/reverse-guardian/invite', body);
      const data = res.data || res;
      setInvite(data);
      setLimitInfo(null);
      setStep('qrcode');
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      let msg = '生成邀请失败';
      let isLimit = false;
      let curX: number | undefined;
      let curY: number | undefined;
      if (detail && typeof detail === 'object') {
        if (detail.code === 'GUARDIAN_LIMIT_REACHED' || detail.code === 'WARD_LIMIT_REACHED') {
          isLimit = true;
          curX = detail.x;
          curY = detail.y;
          msg = detail.message || `守护者已达上限（${detail.x}/${detail.y}），请先升级会员或解绑现有守护者`;
        } else if (detail.message) {
          msg = String(detail.message);
        }
      } else if (typeof detail === 'string') {
        msg = detail;
      } else if (e?.message) {
        msg = String(e.message);
      }
      setError(msg);
      if (isLimit) {
        setLimitInfo({ x: curX ?? 0, y: curY ?? 0 });
        const confirmed = await Dialog.confirm({
          title: '您的守护者已达上限',
          content: `当前已有 ${curX ?? '-'} 位守护者（含邀请中），上限 ${curY ?? '-'} 位。升级会员可提升上限，或先解绑现有守护者。`,
          cancelText: '取消',
          confirmText: '升级会员',
        });
        if (confirmed) {
          router.push('/membership');
        }
      } else {
        showToast(msg, 'fail');
      }
    } finally {
      setLoading(false);
    }
  }, [guardianName, selectedRelation, customRelation, router]);

  const handleRelationSelect = (rel: string) => {
    setSelectedRelation(rel);
    if (rel !== '其他') setCustomRelation('');
  };

  const handleCustomRelationChange = (val: string) => {
    setCustomRelation(val.slice(0, 8));
    if (customRelationTimer.current) clearTimeout(customRelationTimer.current);
  };

  const handleGuardianNameChange = (val: string) => {
    setGuardianName(val);
  };

  // [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 第二步「返回」：直接回列表页（不回第一步）
  const goBackToList = useCallback(() => {
    router.replace(LIST_PATH);
  }, [router]);

  const handleNavBack = () => {
    if (step === 'qrcode') {
      // 第二步：直接回列表，不回第一步
      goBackToList();
    } else {
      router.back();
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

  const relationFilled = !!selectedRelation && (selectedRelation !== '其他' || customRelation.trim().length > 0);
  const nameFilled = guardianName.trim().length > 0;
  const canConfirm = relationFilled && nameFilled && !viewMode;

  // 已知名字+关系（来自表单或回填）
  const finalName = (invite?.guardian_name || guardianName || '').trim();
  const finalRel = (invite?.relation_type
    || (selectedRelation === '其他' ? customRelation : selectedRelation)
    || '').trim();
  const inviteeLabel = finalName
    ? (finalRel ? `${finalName}（${finalRel}）` : finalName)
    : '—';

  return (
    <div style={{ background: '#F0F5FF', minHeight: '100vh', paddingBottom: 40 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`,
        padding: '12px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        color: '#fff',
        boxShadow: '0 2px 8px rgba(76,175,80,0.3)',
      }}>
        <button
          data-testid="invite-back-btn"
          onClick={handleNavBack}
          style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff', fontSize: 18 }}
        >←</button>
        <span style={{ flex: 1, fontSize: 17, fontWeight: 700, textAlign: 'center' }}>
          {step === 'qrcode' ? '邀请二维码' : '邀请 TA 守护我的健康'}
        </span>
        <span style={{ width: 36 }} />
      </div>

      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '12px 16px', background: '#fff', gap: 8,
      }}>
        <span style={{ fontSize: 22 }}>🌿</span>
        <span style={{ fontSize: 15, fontWeight: 600, color: '#333' }}>宾尼小康AI健康管家</span>
      </div>

      <div style={{ padding: '16px 16px' }}>
        {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 第一步：表单 */}
        {step === 'form' && profileChecked && (
          <div style={{
            background: '#fff', borderRadius: 16, padding: '16px 16px 16px',
            marginBottom: 16, boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#333', marginBottom: 12 }}>
              请选择 TA 与您的关系
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {RELATION_OPTIONS.map((rel) => (
                <button
                  key={rel}
                  data-testid={`relation-opt-${rel}`}
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
            {selectedRelation === '其他' && (
              <div style={{ marginTop: 12 }}>
                <input
                  type="text"
                  data-testid="custom-relation-input"
                  value={customRelation}
                  onChange={(e) => handleCustomRelationChange(e.target.value)}
                  placeholder="请输入关系名称（1~8字）"
                  maxLength={8}
                  style={{
                    width: '100%', padding: '10px 14px', borderRadius: 10,
                    border: `1.5px solid ${THEME.gradientStart}`, outline: 'none',
                    fontSize: 14, color: '#333', boxSizing: 'border-box',
                    background: '#fff',
                  }}
                />
              </div>
            )}

            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#333', marginBottom: 8 }}>
                名字 <span style={{ color: '#DC2626' }}>*</span>
              </div>
              <input
                type="text"
                data-testid="guardian-name-input"
                value={guardianName}
                onChange={(e) => handleGuardianNameChange(e.target.value)}
                placeholder="请输入对方的名字（必填）"
                maxLength={50}
                style={{
                  width: '100%', padding: '10px 14px', borderRadius: 10,
                  border: '1.5px solid #E5E7EB', outline: 'none',
                  fontSize: 14, color: '#333', boxSizing: 'border-box',
                  background: '#fff',
                }}
              />
            </div>

            {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 确认按钮 */}
            <div style={{ marginTop: 18 }}>
              <button
                data-testid="guardian-invite-confirm"
                onClick={handleConfirm}
                disabled={!canConfirm || loading}
                style={{
                  width: '100%', padding: '12px 0', borderRadius: 22,
                  background: canConfirm && !loading
                    ? `linear-gradient(135deg, ${THEME.gradientStart}, ${THEME.gradientEnd})`
                    : '#E5E7EB',
                  color: canConfirm && !loading ? '#fff' : '#9CA3AF',
                  border: 'none', fontSize: 15, fontWeight: 600,
                  cursor: canConfirm && !loading ? 'pointer' : 'not-allowed',
                }}
              >{loading ? '提交中…' : '确认'}</button>
              {limitInfo && (
                <div style={{ marginTop: 8, fontSize: 12, color: '#DC2626', textAlign: 'center' }}>
                  已达上限 {limitInfo.x}/{limitInfo.y}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 加载/检查中提示 */}
        {!profileChecked && step === 'form' && (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>正在检查资料…</div>
        )}

        {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 第二步：仅展示二维码 + 信息 + 返回 */}
        {step === 'qrcode' && (
          loading ? (
            <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>正在生成邀请…</div>
          ) : error && !invite ? (
            <div style={{
              background: '#fff', borderRadius: 16, padding: '40px 20px',
              textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
            }}>
              <div style={{ fontSize: 14, color: '#6B7280', marginBottom: 16 }}>{error}</div>
              <button
                onClick={goBackToList}
                style={{
                  padding: '10px 24px', borderRadius: 20,
                  background: THEME.gradientStart, color: '#fff',
                  border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >返回列表</button>
            </div>
          ) : invite ? (
            <>
              <div style={{
                background: '#fff', borderRadius: 20, overflow: 'hidden',
                boxShadow: '0 8px 32px rgba(76,175,80,0.12)',
                maxWidth: 360, margin: '0 auto',
              }}>
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

                <div style={{ padding: '20px 24px 24px', textAlign: 'center' }}>
                  <div
                    ref={qrCanvasRef}
                    data-testid="invite-qrcode"
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

                  {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 邀请对象 + 24h 提示 */}
                  <div style={{ marginTop: 14, fontSize: 14, color: '#333', fontWeight: 500 }}>
                    邀请对象：{inviteeLabel}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12, color: '#9CA3AF' }}>
                    24 小时内有效
                  </div>

                  <div style={{
                    marginTop: 10, padding: '8px 14px', borderRadius: 10,
                    background: '#F0FDF4', fontSize: 13, color: '#166534',
                  }}>
                    💚 让 TA 随时关注我的健康
                  </div>

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

              {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 底部「完成/返回列表」 */}
              <div style={{ maxWidth: 360, margin: '20px auto 0' }}>
                <button
                  data-testid="invite-return-list-btn"
                  onClick={goBackToList}
                  style={{
                    width: '100%', padding: '14px 0', borderRadius: 24,
                    background: '#fff', color: THEME.gradientStart,
                    border: `1.5px solid ${THEME.gradientStart}`,
                    fontSize: 15, fontWeight: 600, cursor: 'pointer',
                  }}
                >完成 / 返回列表</button>
              </div>
            </>
          ) : null
        )}
      </div>

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

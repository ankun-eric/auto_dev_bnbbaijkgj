'use client';

export const dynamic = 'force-dynamic';
export const dynamicParams = true;

/**
 * [PRD-HOME-SAFETY-V1 2026-05-27] 智能硬件绑定 · 居家安全设备 v1.0
 * [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 数据按家庭成员隔离 + 类型分组卡片 + 迁移提示条
 */
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';
import { formatDateTime } from '@/lib/datetime';

const DEVICE_TYPES = [
  {
    type: 1,
    label: '紧急呼叫器',
    color: '#E53935',
    light: '#FFEBEE',
    gradient: 'linear-gradient(135deg, #FFEBEE 0%, #FFCDD2 100%)',
    icon: '🚨',
  },
  {
    type: 2,
    label: '烟雾报警器',
    color: '#FB8C00',
    light: '#FFF3E0',
    gradient: 'linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%)',
    icon: '🔥',
  },
  {
    type: 7,
    label: '水位报警器',
    color: '#FBC02D',
    light: '#FFFDE7',
    gradient: 'linear-gradient(135deg, #FFFDE7 0%, #FFF9C4 100%)',
    icon: '💧',
  },
];

interface BindingItem {
  id: number;
  device_type: number;
  device_type_label: string;
  gateway_sn: string;
  gateway_id?: string;
  gateway_sn_mask: string;
  device_sn: string;
  verify_status: number;
  bound_at: string;
  status?: number;
  status_label?: string;
  invalid_reason?: string | null;
  emergency_phone?: string;
  emergency_phone_mask?: string;
  emergency_phone_filled?: boolean;
  member_id?: number | null;
  migrated_to_self?: boolean;
}
interface MemberItem {
  id: number;
  nickname: string;
  relationship_type: string;
  is_self: boolean;
}

export default function HomeSafetyPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center' }}>加载中…</div>}>
      <HomeSafetyPageInner />
    </Suspense>
  );
}

function HomeSafetyPageInner() {
  const searchParams = useSearchParams();
  const initialMemberId = useMemo(() => {
    const v = searchParams?.get('member_id');
    if (!v) return null;
    const n = parseInt(v, 10);
    return Number.isFinite(n) ? n : null;
  }, [searchParams]);

  const [members, setMembers] = useState<MemberItem[]>([]);
  const [activeMemberId, setActiveMemberId] = useState<number | null>(initialMemberId);
  const [bindings, setBindings] = useState<BindingItem[]>([]);
  const [hasMigrated, setHasMigrated] = useState(false);
  const [showBindModal, setShowBindModal] = useState(false);
  const [bindDeviceType, setBindDeviceType] = useState<number>(1);
  const [bindMemberId, setBindMemberId] = useState<number | null>(null);
  const [gw, setGw] = useState('');
  const [dev, setDev] = useState('');
  const [ephone, setEphone] = useState('');
  const [defaultPhone, setDefaultPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [migrateHintHidden, setMigrateHintHidden] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState<BindingItem | null>(null);

  // ── 加载成员列表 ──
  const loadMembers = useCallback(async () => {
    try {
      const r: any = await api.get('/api/home_safety/members');
      const items: MemberItem[] = (r as any)?.items ?? (r as any)?.data?.items ?? [];
      setMembers(items);
      // 如未指定 activeMemberId，则默认本人
      if (activeMemberId == null) {
        const selfM = items.find((m) => m.is_self);
        if (selfM) setActiveMemberId(selfM.id);
      }
    } catch (e: any) {
      console.error('[HOME-SAFETY] loadMembers error:', e?.message);
    }
  }, [activeMemberId]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  // ── 加载该成员的设备 ──
  const loadDevices = useCallback(async () => {
    if (activeMemberId == null) return;
    try {
      const r: any = await api.get(`/api/home_safety/devices?member_id=${activeMemberId}`);
      const groups: any[] = (r as any)?.groups ?? (r as any)?.data?.groups ?? [];
      const all: BindingItem[] = [];
      for (const g of groups) {
        for (const it of g.items || []) all.push(it);
      }
      setBindings(all);
      const hasMig =
        (r as any)?.has_migrated_to_self_devices ??
        (r as any)?.data?.has_migrated_to_self_devices ??
        false;
      setHasMigrated(Boolean(hasMig));
    } catch (e: any) {
      console.error('[HOME-SAFETY] loadDevices error:', e?.message);
    }
  }, [activeMemberId]);

  useEffect(() => {
    loadDevices();
  }, [loadDevices]);

  // ── 提示条本地保存键 ──
  const dismissKey = useMemo(() => {
    if (typeof window === 'undefined') return '';
    let uid = '';
    try {
      uid = window.localStorage.getItem('user_id') || '';
    } catch {}
    return `home_safety_migrate_hint_dismissed_${uid || 'anon'}`;
  }, []);

  useEffect(() => {
    if (!dismissKey) return;
    try {
      const v = window.localStorage.getItem(dismissKey);
      if (v === '1') setMigrateHintHidden(true);
    } catch {}
  }, [dismissKey]);

  const dismissMigrateHint = () => {
    setMigrateHintHidden(true);
    try {
      if (dismissKey) window.localStorage.setItem(dismissKey, '1');
    } catch {}
  };

  // ── 当前成员是不是"本人" ──
  const activeMember = members.find((m) => m.id === activeMemberId) || null;
  const isSelfActive = activeMember ? activeMember.is_self : true;
  const showMigrateHint =
    isSelfActive &&
    hasMigrated &&
    !migrateHintHidden &&
    bindings.some((b) => b.migrated_to_self);
  const migratedCount = bindings.filter((b) => b.migrated_to_self).length;

  // ── 打开绑定弹窗 ──
  const openBindModal = useCallback(
    async (devType: number) => {
      setBindDeviceType(devType);
      setBindMemberId(activeMemberId);
      setGw('');
      setDev('');
      setEphone('');
      setShowBindModal(true);
      try {
        const r: any = await api.get('/api/home_safety/devices/bind/defaults');
        const dp =
          (r as any)?.default_emergency_phone ?? (r as any)?.data?.default_emergency_phone ?? '';
        if (dp) {
          setDefaultPhone(String(dp));
          setEphone(String(dp));
        }
      } catch {}
    },
    [activeMemberId],
  );

  const doBind = async () => {
    if (!/^[A-Z0-9]{8}$/.test(gw)) {
      showToast('网关ID 必须为 8 位字母或数字');
      return;
    }
    if (!/^[A-Za-z0-9]{8}$/.test(dev)) {
      showToast('设备 SN 必须为 8 位字母+数字');
      return;
    }
    if (!/^1[3-9]\d{9}$/.test(ephone)) {
      showToast('请输入有效的 11 位手机号');
      return;
    }
    if (bindMemberId == null) {
      showToast('请选择归属家庭成员');
      return;
    }
    setLoading(true);
    try {
      await api.post('/api/home_safety/devices/bind', {
        device_type: bindDeviceType,
        gateway_id: gw,
        gateway_sn: gw,
        device_sn: dev,
        emergency_phone: ephone,
        member_id: bindMemberId,
      });
      showToast('绑定成功');
      setShowBindModal(false);
      // 切到绑定的成员 Tab
      if (bindMemberId !== activeMemberId) setActiveMemberId(bindMemberId);
      else loadDevices();
    } catch (e: any) {
      const detail = String(e?.response?.data?.detail || '绑定失败');
      if (detail.includes('invalid_gateway_id')) showToast('网关ID 必须为 8 位字母或数字');
      else if (detail.includes('invalid_emergency_phone')) showToast('请输入有效的 11 位手机号');
      else if (detail.includes('emergency_phone_required')) showToast('紧急联系手机为必填项');
      else if (detail.includes('member_not_found')) showToast('成员不存在或不属于当前账号');
      else showToast(detail);
    } finally {
      setLoading(false);
    }
  };

  const doUnbind = async (id: number) => {
    if (!confirm('确认解绑该设备？')) return;
    try {
      await api.post(`/api/home_safety/devices/${id}/unbind`);
      showToast('已解绑');
      loadDevices();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '解绑失败');
    }
  };

  const doTransfer = async (binding: BindingItem, newMemberId: number) => {
    try {
      await api.patch(`/api/home_safety/devices/${binding.id}/transfer`, {
        member_id: newMemberId,
      });
      showToast('归属已调整');
      setShowTransferModal(null);
      loadDevices();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '调整失败');
    }
  };

  // ── 按设备类型分组 ──
  const groupedBindings = DEVICE_TYPES.map((d) => ({
    ...d,
    items: bindings.filter((b) => b.device_type === d.type && (b.status ?? 1) !== 0),
  }));

  return (
    <div style={{ minHeight: '100vh', background: '#F4F6F8', paddingBottom: 80 }}>
      {/* 顶部 Header */}
      <div
        style={{
          background: 'linear-gradient(135deg,#1F8FE6,#2EC4B6)',
          color: '#fff',
          padding: '20px 16px 16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={() => history.back()}
            style={{
              background: 'transparent',
              color: '#fff',
              border: 'none',
              fontSize: 18,
              cursor: 'pointer',
            }}
          >
            ←
          </button>
          <div style={{ fontSize: 18, fontWeight: 600 }}>居家安全设备</div>
        </div>
        <div style={{ marginTop: 6, fontSize: 12, opacity: 0.9 }}>
          按家庭成员管理设备 · 实时报警 · 紧急联系人
        </div>
      </div>

      {/* 成员 Tab */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: '12px 16px',
          overflowX: 'auto',
          background: '#fff',
          borderBottom: '1px solid #EEE',
        }}
      >
        {members.map((m) => (
          <button
            key={m.id}
            onClick={() => setActiveMemberId(m.id)}
            style={{
              flex: '0 0 auto',
              padding: '8px 16px',
              background: activeMemberId === m.id ? '#1F8FE6' : '#F4F6F8',
              color: activeMemberId === m.id ? '#fff' : '#333',
              border: 'none',
              borderRadius: 16,
              fontSize: 13,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              fontWeight: activeMemberId === m.id ? 600 : 400,
            }}
          >
            {m.is_self ? '本人' : m.nickname}
          </button>
        ))}
        <button
          onClick={() => {
            // 跳转到健康档案页添加成员（项目已有页面）
            try {
              window.location.href = '/health-archive';
            } catch {}
          }}
          style={{
            flex: '0 0 auto',
            padding: '8px 12px',
            background: '#F4F6F8',
            color: '#666',
            border: '1px dashed #BBB',
            borderRadius: 16,
            fontSize: 13,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          + 添加
        </button>
      </div>

      {/* 迁移提示条（仅本人 Tab） */}
      {showMigrateHint ? (
        <div
          style={{
            background: '#FFF8E1',
            color: '#8D6E00',
            padding: '10px 16px',
            fontSize: 13,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            borderBottom: '1px solid #FFE082',
          }}
        >
          <span>ⓘ</span>
          <span style={{ flex: 1 }}>
            有 {migratedCount} 台设备默认归属本人，
            <span
              style={{ color: '#1F8FE6', cursor: 'pointer', fontWeight: 600 }}
              onClick={() => {
                // 滚动到第一个迁移设备并提示用户调整
                const first = bindings.find((b) => b.migrated_to_self);
                if (first) setShowTransferModal(first);
              }}
            >
              去调整 →
            </span>
          </span>
          <span
            style={{ cursor: 'pointer', fontSize: 16, color: '#999' }}
            onClick={dismissMigrateHint}
          >
            ×
          </span>
        </div>
      ) : null}

      {/* 设备分组列表 */}
      <div style={{ padding: '16px' }}>
        {groupedBindings.map((g) => (
          <div key={g.type} style={{ marginBottom: 24 }}>
            {/* 分组头 */}
            <div
              style={{
                background: g.gradient,
                borderRadius: 12,
                padding: '14px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                height: 72,
                boxSizing: 'border-box',
              }}
            >
              <div style={{ fontSize: 28 }}>{g.icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 18, fontWeight: 600, color: g.color }}>{g.label}</div>
                <div style={{ fontSize: 13, color: '#666', marginTop: 2 }}>
                  已绑定 {g.items.length} 台
                </div>
              </div>
              <button
                onClick={() => openBindModal(g.type)}
                style={{
                  padding: '6px 12px',
                  background: '#fff',
                  color: g.color,
                  border: `1px solid ${g.color}`,
                  borderRadius: 16,
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                + 添加
              </button>
            </div>

            {/* 卡片列表 */}
            <div style={{ marginTop: 12 }}>
              {g.items.length === 0 ? (
                <div
                  style={{
                    background: '#fff',
                    borderRadius: 12,
                    padding: 24,
                    textAlign: 'center',
                    color: '#999',
                    fontSize: 13,
                  }}
                >
                  暂无设备
                  <button
                    onClick={() => openBindModal(g.type)}
                    style={{
                      display: 'inline-block',
                      marginLeft: 12,
                      padding: '4px 12px',
                      background: g.color,
                      color: '#fff',
                      border: 'none',
                      borderRadius: 12,
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    + 添加
                  </button>
                </div>
              ) : (
                g.items.map((b, idx) => {
                  const isInvalid = (b.status ?? 1) === 2;
                  return (
                    <div
                      key={b.id}
                      style={{
                        background: isInvalid ? '#FAFAFA' : '#fff',
                        padding: 16,
                        borderRadius: 12,
                        marginBottom: 12,
                        boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                        position: 'relative',
                      }}
                    >
                      {/* 序号 + 在线状态 */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: 8,
                        }}
                      >
                        <span
                          style={{
                            background: '#F0F0F0',
                            color: '#666',
                            padding: '2px 8px',
                            borderRadius: 10,
                            fontSize: 11,
                            fontWeight: 500,
                          }}
                        >
                          {idx + 1} / {g.items.length}
                        </span>
                        <span
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: 11,
                            color: isInvalid ? '#9E9E9E' : '#43A047',
                          }}
                        >
                          <span
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: '50%',
                              background: isInvalid ? '#9E9E9E' : '#43A047',
                              display: 'inline-block',
                            }}
                          />
                          {isInvalid ? '离线' : '在线'}
                        </span>
                      </div>

                      <div style={{ fontSize: 16, fontWeight: 600, color: '#333' }}>
                        {b.device_type_label}
                        {isInvalid ? (
                          <span
                            style={{
                              marginLeft: 8,
                              fontSize: 11,
                              background: '#FFEBEE',
                              color: '#E53935',
                              padding: '2px 6px',
                              borderRadius: 4,
                            }}
                          >
                            失效需重绑
                          </span>
                        ) : null}
                      </div>

                      <div style={{ marginTop: 8, fontSize: 13, color: '#333' }}>
                        <div style={{ marginBottom: 4 }}>
                          <span style={{ fontSize: 12, color: '#999' }}>网关 ID：</span>
                          <span style={{ fontWeight: 500 }}>{b.gateway_id || b.gateway_sn}</span>
                        </div>
                        <div style={{ marginBottom: 4 }}>
                          <span style={{ fontSize: 12, color: '#999' }}>设备 SN：</span>
                          <span style={{ fontWeight: 500 }}>{b.device_sn}</span>
                        </div>
                        {b.emergency_phone_filled ? (
                          <div style={{ marginBottom: 4 }}>
                            <span style={{ fontSize: 12, color: '#999' }}>紧急联系手机：</span>
                            <span style={{ fontWeight: 500 }}>{b.emergency_phone_mask}</span>
                          </div>
                        ) : (
                          <div
                            style={{
                              fontSize: 12,
                              color: '#fff',
                              background: '#E53935',
                              marginTop: 6,
                              padding: '4px 8px',
                              borderRadius: 4,
                              display: 'inline-block',
                            }}
                          >
                            紧急联系手机未填写
                          </div>
                        )}
                        <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                          绑定时间：{formatDateTime(b.bound_at)}
                        </div>
                      </div>

                      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <button
                          onClick={() => setShowTransferModal(b)}
                          style={{
                            padding: '4px 12px',
                            fontSize: 12,
                            background: '#fff',
                            color: '#1F8FE6',
                            border: '1px solid #1F8FE6',
                            borderRadius: 4,
                            cursor: 'pointer',
                          }}
                        >
                          调整归属
                        </button>
                        <button
                          onClick={() => doUnbind(b.id)}
                          style={{
                            padding: '4px 12px',
                            fontSize: 12,
                            background: '#fff',
                            color: '#E53935',
                            border: '1px solid #E53935',
                            borderRadius: 4,
                            cursor: 'pointer',
                          }}
                        >
                          解绑
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 底部固定添加按钮 */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          padding: 16,
          background: 'rgba(255,255,255,0.96)',
          borderTop: '1px solid #EEE',
        }}
      >
        <button
          onClick={() => openBindModal(1)}
          style={{
            width: '100%',
            padding: 12,
            background: 'linear-gradient(135deg,#1F8FE6,#2EC4B6)',
            color: '#fff',
            border: 'none',
            borderRadius: 24,
            fontSize: 15,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          + 添加设备
        </button>
      </div>

      {/* 绑定弹窗 */}
      {showBindModal ? (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 999,
          }}
          onClick={() => setShowBindModal(false)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 20,
              width: '88%',
              maxWidth: 360,
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>添加设备</div>

            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>设备类型</div>
            <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              {DEVICE_TYPES.map((d) => (
                <button
                  key={d.type}
                  onClick={() => setBindDeviceType(d.type)}
                  style={{
                    flex: 1,
                    padding: '8px 0',
                    background: bindDeviceType === d.type ? d.color : '#fff',
                    color: bindDeviceType === d.type ? '#fff' : '#333',
                    border: `1px solid ${bindDeviceType === d.type ? d.color : '#DDD'}`,
                    borderRadius: 6,
                    fontSize: 12,
                    cursor: 'pointer',
                  }}
                >
                  {d.label}
                </button>
              ))}
            </div>

            {/* 归属成员 */}
            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
              归属家庭成员（必填）
            </div>
            <select
              value={bindMemberId ?? ''}
              onChange={(e) =>
                setBindMemberId(e.target.value ? parseInt(e.target.value, 10) : null)
              }
              style={{
                width: '100%',
                padding: '10px 12px',
                fontSize: 14,
                border: '1px solid #ddd',
                borderRadius: 6,
                marginBottom: 12,
                boxSizing: 'border-box',
                background: '#fff',
              }}
            >
              <option value="">请选择</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.is_self ? '本人' : m.nickname}
                </option>
              ))}
            </select>

            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
              网关ID（8 位字母或数字）
            </div>
            <input
              value={gw}
              onChange={(e) => {
                const v = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8);
                setGw(v);
              }}
              maxLength={8}
              style={{
                width: '100%',
                padding: '10px 12px',
                fontSize: 14,
                border: '1px solid #ddd',
                borderRadius: 6,
                marginBottom: 12,
                boxSizing: 'border-box',
              }}
              placeholder="例如：ABCD1234"
            />

            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
              设备 SN（8 位字母+数字）
            </div>
            <input
              value={dev}
              onChange={(e) => setDev(e.target.value.trim())}
              maxLength={8}
              style={{
                width: '100%',
                padding: '10px 12px',
                fontSize: 14,
                border: '1px solid #ddd',
                borderRadius: 6,
                marginBottom: 12,
                boxSizing: 'border-box',
              }}
              placeholder="例如：ABCD1234"
            />

            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
              紧急联系手机（11 位中国大陆手机号）
            </div>
            <input
              value={ephone}
              onChange={(e) => {
                const v = e.target.value.replace(/[^\d]/g, '').slice(0, 11);
                setEphone(v);
              }}
              maxLength={11}
              style={{
                width: '100%',
                padding: '10px 12px',
                fontSize: 14,
                border: '1px solid #ddd',
                borderRadius: 6,
                marginBottom: 6,
                boxSizing: 'border-box',
              }}
              placeholder="如：13800001234"
            />
            {defaultPhone ? (
              <div style={{ fontSize: 11, color: '#999', marginBottom: 16 }}>
                已自动带入您的注册手机号，可修改
              </div>
            ) : (
              <div style={{ marginBottom: 16 }} />
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowBindModal(false)}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: '#fff',
                  border: '1px solid #ccc',
                  borderRadius: 6,
                  cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                onClick={doBind}
                disabled={loading}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: '#1F8FE6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                }}
              >
                {loading ? '提交中…' : '确认绑定'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* 调整归属弹窗 */}
      {showTransferModal ? (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setShowTransferModal(null)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 20,
              width: '88%',
              maxWidth: 360,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
              调整设备归属
            </div>
            <div style={{ fontSize: 13, color: '#666', marginBottom: 12 }}>
              选择 {showTransferModal.device_type_label}（{showTransferModal.device_sn}）
              的新归属成员：
            </div>
            <div style={{ marginBottom: 12 }}>
              {members.map((m) => (
                <button
                  key={m.id}
                  onClick={() => doTransfer(showTransferModal, m.id)}
                  style={{
                    width: '100%',
                    padding: 12,
                    marginBottom: 6,
                    textAlign: 'left',
                    background: m.id === showTransferModal.member_id ? '#E3F2FD' : '#F4F6F8',
                    color: '#333',
                    border:
                      m.id === showTransferModal.member_id
                        ? '1px solid #1F8FE6'
                        : '1px solid transparent',
                    borderRadius: 8,
                    fontSize: 14,
                    cursor: 'pointer',
                  }}
                >
                  {m.is_self ? '本人' : m.nickname}
                  {m.id === showTransferModal.member_id ? (
                    <span style={{ color: '#1F8FE6', marginLeft: 6 }}>（当前）</span>
                  ) : null}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowTransferModal(null)}
              style={{
                width: '100%',
                padding: 10,
                background: '#fff',
                border: '1px solid #ccc',
                borderRadius: 6,
                cursor: 'pointer',
              }}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

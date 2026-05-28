'use client';

export const dynamic = 'force-dynamic';
export const dynamicParams = true;

/**
 * [PRD-HOME-SAFETY-V1 2026-05-27] 智能硬件绑定 · 居家安全设备 v1.0
 * 用户端主页：3 Tab（紧急呼叫器/烟雾报警器/水位报警器）+ 我绑定的设备 + 报警记录 + 紧急联系人
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';
import { formatDateTime } from '@/lib/datetime';

const DEVICE_TYPES = [
  { type: 1, label: '紧急呼叫器', color: '#E53935', light: '#FFEBEE' },
  { type: 2, label: '烟雾报警器', color: '#FB8C00', light: '#FFF3E0' },
  { type: 7, label: '水位报警器', color: '#FBC02D', light: '#FFFDE7' },
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
}
interface AlarmItem {
  id: number;
  device_type: number;
  device_type_label: string;
  device_sn: string;
  alarm_at: string;
  dedupe_count: number;
  read_status: number;
  handle_status: number;
  handle_note: string | null;
  notify_ai_call: number;
}
interface ContactItem {
  guardian_id: number;
  nickname: string | null;
  phone: string | null;
  is_primary: boolean;
  is_primary_locked: boolean;
  selected: boolean;
  enabled_for_emergency: boolean;
  enabled_for_smoke: boolean;
  enabled_for_water: boolean;
}

export default function HomeSafetyPage() {
  const [activeTab, setActiveTab] = useState<number>(1);
  const [bindings, setBindings] = useState<BindingItem[]>([]);
  const [alarms, setAlarms] = useState<AlarmItem[]>([]);
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [showBindModal, setShowBindModal] = useState(false);
  const [gw, setGw] = useState('');
  const [dev, setDev] = useState('');
  // [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 设备级紧急联系手机
  const [ephone, setEphone] = useState('');
  const [defaultPhone, setDefaultPhone] = useState('');
  const [loading, setLoading] = useState(false);

  // 修改紧急联系手机的弹窗
  const [showEditEphone, setShowEditEphone] = useState<null | BindingItem>(null);
  const [editEphone, setEditEphone] = useState('');

  // 历史 NULL 补填强制弹窗
  const [forceFillTarget, setForceFillTarget] = useState<BindingItem | null>(null);

  const loadAll = useCallback(async (tabOverride?: number) => {
    const tab = tabOverride ?? activeTab;
    try {
      const [d, a, c] = await Promise.all([
        api.get('/api/home_safety/devices'),
        api.get(`/api/home_safety/alarms?device_type=${tab}`),
        api.get('/api/home_safety/emergency_contacts'),
      ]);
      // [PRD-HOME-SAFETY-V1 BUGFIX 2026-05-27] H5 axios 响应拦截器已 `(response) => response.data`，
      // 所以 d 直接就是后端响应体；保留 d.data 兜底以防其它端调用方式不同。
      const groups: any[] = (d as any)?.groups ?? (d as any)?.data?.groups ?? [];
      const grp = groups.find((x: any) => x.device_type === tab);
      setBindings(grp?.items || []);
      const alarmItems = (a as any)?.items ?? (a as any)?.data?.items ?? [];
      setAlarms(alarmItems);
      const contactItems = (c as any)?.contacts ?? (c as any)?.data?.contacts ?? [];
      setContacts(contactItems);
    } catch (e: any) {
      console.error('[HOME-SAFETY] loadAll error:', e?.message, e?.response?.status, e?.response?.data);
    }
  }, [activeTab]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 打开绑定弹窗时拉取注册手机号作为默认紧急联系手机
  const openBindModal = useCallback(async () => {
    setGw('');
    setDev('');
    setEphone('');
    setShowBindModal(true);
    try {
      const r: any = await api.get('/api/home_safety/devices/bind/defaults');
      const dp = (r as any)?.default_emergency_phone ?? (r as any)?.data?.default_emergency_phone ?? '';
      if (dp) {
        setDefaultPhone(String(dp));
        setEphone(String(dp));
      }
    } catch (e) {
      // 静默，用户也可手工填
    }
  }, []);

  // [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 进入页面时，若存在未补填紧急联系手机的有效绑定，强制弹窗
  useEffect(() => {
    const missing = bindings.find(
      (b) => (b.status ?? 1) === 1 && !b.emergency_phone_filled,
    );
    if (missing && !forceFillTarget && !showEditEphone) {
      setForceFillTarget(missing);
      setEditEphone('');
    }
  }, [bindings, forceFillTarget, showEditEphone]);

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
    setLoading(true);
    try {
      await api.post('/api/home_safety/devices/bind', {
        device_type: activeTab,
        gateway_id: gw,
        gateway_sn: gw,
        device_sn: dev,
        emergency_phone: ephone,
      });
      showToast('绑定成功');
      setShowBindModal(false);
      setGw('');
      setDev('');
      setEphone('');
      // [PRD-HOME-SAFETY-V1 BUGFIX] 显式传入 activeTab，避免闭包旧值
      await loadAll(activeTab);
    } catch (e: any) {
      const detail = String(e?.response?.data?.detail || '绑定失败');
      if (detail.includes('invalid_gateway_id')) showToast('网关ID 必须为 8 位字母或数字');
      else if (detail.includes('invalid_emergency_phone')) showToast('请输入有效的 11 位手机号');
      else if (detail.includes('emergency_phone_required')) showToast('紧急联系手机为必填项');
      else showToast(detail);
    } finally {
      setLoading(false);
    }
  };

  // [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 修改紧急联系手机
  const submitEditEphone = async (binding: BindingItem, phone: string) => {
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      showToast('请输入有效的 11 位手机号');
      return;
    }
    try {
      await api.patch(`/api/home_safety/devices/${binding.id}/emergency_phone`, {
        emergency_phone: phone,
      });
      showToast('已保存');
      setShowEditEphone(null);
      setForceFillTarget(null);
      setEditEphone('');
      await loadAll(activeTab);
    } catch (e: any) {
      const detail = String(e?.response?.data?.detail || '保存失败');
      if (detail.includes('invalid_emergency_phone')) showToast('请输入有效的 11 位手机号');
      else showToast(detail);
    }
  };

  const doUnbind = async (id: number) => {
    if (!confirm('确认解绑该设备？')) return;
    try {
      await api.post(`/api/home_safety/devices/${id}/unbind`);
      showToast('已解绑');
      loadAll();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '解绑失败');
    }
  };

  const doMarkRead = async (id: number) => {
    try {
      await api.post(`/api/home_safety/alarms/${id}/read`);
      loadAll();
    } catch (e: any) {
      showToast('操作失败');
    }
  };

  const doHandle = async (id: number) => {
    const note = prompt('请输入处置备注（可选）：') || '';
    try {
      await api.post(`/api/home_safety/alarms/${id}/handle`, { note });
      showToast('已标记处置');
      loadAll();
    } catch (e: any) {
      showToast('操作失败');
    }
  };

  const saveContacts = async (newSelected: number[]) => {
    try {
      await api.post('/api/home_safety/emergency_contacts', {
        guardian_ids: newSelected,
      });
      showToast('已保存');
      loadAll();
    } catch (e: any) {
      showToast('保存失败');
    }
  };

  const cur = DEVICE_TYPES.find((d) => d.type === activeTab)!;

  const otherContacts = contacts.filter((c) => !c.is_primary);
  const selectedOtherIds = otherContacts.filter((c) => c.selected).map((c) => c.guardian_id);

  const toggleOther = (gid: number) => {
    let next = [...selectedOtherIds];
    if (next.includes(gid)) {
      next = next.filter((x) => x !== gid);
    } else {
      if (next.length >= 2) {
        showToast('其他守护人最多勾选 2 位');
        return;
      }
      next.push(gid);
    }
    saveContacts(next);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#F4F6F8', paddingBottom: 40 }}>
      <div
        style={{
          background: 'linear-gradient(135deg,#1F8FE6,#2EC4B6)',
          color: '#fff',
          padding: '20px 16px 24px',
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
        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.9 }}>
          自助绑定/解绑·实时报警·紧急联系人
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, padding: '12px 16px' }}>
        {DEVICE_TYPES.map((d) => (
          <button
            key={d.type}
            onClick={() => setActiveTab(d.type)}
            style={{
              flex: 1,
              padding: '10px 0',
              background: activeTab === d.type ? d.color : '#fff',
              color: activeTab === d.type ? '#fff' : '#333',
              border: `1px solid ${activeTab === d.type ? d.color : '#E0E0E0'}`,
              borderRadius: 8,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            {d.label}
          </button>
        ))}
      </div>

      <div style={{ padding: '0 16px' }}>
        <button
          onClick={openBindModal}
          style={{
            width: '100%',
            padding: '12px 0',
            background: cur.color,
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            fontSize: 14,
            cursor: 'pointer',
          }}
        >
          + 绑定新设备
        </button>
      </div>

      {/* 我绑定的设备 */}
      <div style={{ padding: '16px' }}>
        <div style={{ fontSize: 13, color: '#666', marginBottom: 8 }}>── 我绑定的设备 ──</div>
        {bindings.length === 0 ? (
          <div
            style={{
              padding: 24,
              background: '#fff',
              borderRadius: 8,
              textAlign: 'center',
              color: '#999',
              fontSize: 13,
            }}
          >
            暂未绑定 {cur.label}
          </div>
        ) : (
          [...bindings]
            .sort((a, b) => {
              // 撞号失效（status=2）置顶
              const sa = (a.status ?? 1) === 2 ? 0 : 1;
              const sb = (b.status ?? 1) === 2 ? 0 : 1;
              return sa - sb;
            })
            .map((b) => {
              const isInvalid = (b.status ?? 1) === 2;
              return (
                <div
                  key={b.id}
                  style={{
                    background: isInvalid ? '#EFEFEF' : '#fff',
                    padding: 12,
                    borderRadius: 8,
                    marginBottom: 8,
                    borderLeft: `4px solid ${isInvalid ? '#999' : cur.color}`,
                    opacity: isInvalid ? 0.85 : 1,
                  }}
                >
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: isInvalid ? '#777' : '#333',
                    }}
                  >
                    {b.device_type_label}
                    {isInvalid ? (
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: 11,
                          background: '#EEE',
                          color: '#777',
                          padding: '2px 6px',
                          borderRadius: 4,
                        }}
                      >
                        失效需重绑
                      </span>
                    ) : null}
                  </div>
                  {isInvalid ? (
                    <div style={{ fontSize: 12, color: '#E53935', marginTop: 4 }}>
                      {b.invalid_reason || '此设备需要重新绑定才能继续使用'}
                    </div>
                  ) : null}
                  <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                    网关ID: {b.gateway_id || b.gateway_sn}
                  </div>
                  <div style={{ fontSize: 12, color: '#666' }}>设备 SN: {b.device_sn}</div>
                  {/* [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 紧急联系手机 */}
                  {b.emergency_phone_filled ? (
                    <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                      紧急联系手机：{b.emergency_phone_mask}
                      {!isInvalid ? (
                        <button
                          onClick={() => {
                            setShowEditEphone(b);
                            setEditEphone(b.emergency_phone || '');
                          }}
                          style={{
                            marginLeft: 8,
                            padding: '2px 8px',
                            fontSize: 11,
                            background: '#fff',
                            color: '#1F8FE6',
                            border: '1px solid #1F8FE6',
                            borderRadius: 4,
                            cursor: 'pointer',
                          }}
                        >
                          修改
                        </button>
                      ) : null}
                    </div>
                  ) : (
                    <div
                      style={{
                        fontSize: 12,
                        color: '#fff',
                        background: '#E53935',
                        marginTop: 4,
                        padding: '4px 6px',
                        borderRadius: 4,
                        display: 'inline-block',
                        cursor: 'pointer',
                      }}
                      onClick={() => {
                        setShowEditEphone(b);
                        setEditEphone('');
                      }}
                    >
                      紧急联系手机未填写，点击补填
                    </div>
                  )}
                  <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                    绑定时间: {formatDateTime(b.bound_at)}
                  </div>
                  <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                    {isInvalid ? (
                      <button
                        onClick={openBindModal}
                        style={{
                          padding: '4px 12px',
                          fontSize: 12,
                          background: cur.color,
                          color: '#fff',
                          border: 'none',
                          borderRadius: 4,
                          cursor: 'pointer',
                        }}
                      >
                        重新绑定
                      </button>
                    ) : (
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
                    )}
                  </div>
                </div>
              );
            })
        )}
      </div>

      {/* 报警记录 */}
      <div style={{ padding: '0 16px' }}>
        <div style={{ fontSize: 13, color: '#666', marginBottom: 8 }}>── 报警记录 ──</div>
        {alarms.length === 0 ? (
          <div
            style={{
              padding: 24,
              background: '#fff',
              borderRadius: 8,
              textAlign: 'center',
              color: '#999',
              fontSize: 13,
            }}
          >
            暂无报警记录
          </div>
        ) : (
          alarms.map((a) => (
            <div
              key={a.id}
              style={{
                background: '#fff',
                padding: 12,
                borderRadius: 8,
                marginBottom: 8,
                borderLeft: `4px solid ${cur.color}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: cur.color, fontSize: 14 }}>●</span>
                <span style={{ fontSize: 13, color: '#333' }}>
                  {formatDateTime(a.alarm_at)}
                </span>
                {a.dedupe_count > 1 ? (
                  <span style={{ fontSize: 11, color: '#999' }}>
                    （5 分钟内共 {a.dedupe_count} 次）
                  </span>
                ) : null}
              </div>
              <div style={{ fontSize: 13, marginTop: 6 }}>
                {a.device_type_label}触发报警
              </div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                AI 外呼:{' '}
                {a.notify_ai_call === 1
                  ? '已发起，等待回调…'
                  : a.notify_ai_call === 2
                  ? '成功'
                  : a.notify_ai_call === 3
                  ? '失败'
                  : '未发起'}
              </div>
              {a.handle_note ? (
                <div style={{ fontSize: 12, color: '#0666c8', marginTop: 4 }}>
                  备注: {a.handle_note}
                </div>
              ) : null}
              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                {a.read_status === 0 ? (
                  <button
                    onClick={() => doMarkRead(a.id)}
                    style={{
                      padding: '4px 12px',
                      fontSize: 12,
                      background: '#fff',
                      color: '#333',
                      border: '1px solid #ccc',
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                  >
                    标记已读
                  </button>
                ) : (
                  <span style={{ fontSize: 12, color: '#1FA168' }}>✓ 已读</span>
                )}
                {a.handle_status === 0 ? (
                  <button
                    onClick={() => doHandle(a.id)}
                    style={{
                      padding: '4px 12px',
                      fontSize: 12,
                      background: '#fff',
                      color: '#333',
                      border: '1px solid #ccc',
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                  >
                    处置备注
                  </button>
                ) : (
                  <span style={{ fontSize: 12, color: '#1FA168' }}>✓ 已处置</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* 紧急联系人 */}
      <div style={{ padding: '16px' }}>
        <div style={{ fontSize: 13, color: '#666', marginBottom: 8 }}>
          ── 紧急联系人（共用，最多主守护人 1 + 其他 2 位）──
        </div>
        <div style={{ background: '#fff', padding: 12, borderRadius: 8 }}>
          {contacts.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', fontSize: 13, padding: 12 }}>
              暂无守护人，请先在「守护人体系」中添加
            </div>
          ) : (
            contacts.map((c) => (
              <div
                key={c.guardian_id}
                style={{
                  padding: '8px 0',
                  borderBottom: '1px solid #F0F0F0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <input
                  type="checkbox"
                  disabled={c.is_primary}
                  checked={c.selected}
                  onChange={() => toggleOther(c.guardian_id)}
                />
                <span style={{ fontSize: 14 }}>
                  {c.nickname || c.phone || `用户${c.guardian_id}`}
                </span>
                {c.is_primary ? (
                  <span
                    style={{
                      fontSize: 11,
                      background: '#FFD54F',
                      color: '#5D4037',
                      padding: '2px 6px',
                      borderRadius: 4,
                    }}
                  >
                    主守护人（强制）
                  </span>
                ) : (
                  <span style={{ fontSize: 11, color: '#999' }}>守护人</span>
                )}
              </div>
            ))
          )}
          <div style={{ fontSize: 12, color: '#999', marginTop: 8 }}>
            ⚠️ 主守护人默认强制选中；其他守护人最多再勾 2 位。
          </div>
        </div>
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
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
              绑定 {cur.label}
            </div>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
              网关ID（8 位字母或数字，手工输入，大小写不敏感）
            </div>
            <input
              value={gw}
              onChange={(e) => {
                // [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 自动小写转大写 + 过滤非法字符
                const v = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8);
                setGw(v);
              }}
              inputMode="latin"
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
            {/* [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 紧急联系手机 */}
            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
              紧急联系手机（11 位中国大陆手机号，必填）
            </div>
            <input
              value={ephone}
              onChange={(e) => {
                const v = e.target.value.replace(/[^\d]/g, '').slice(0, 11);
                setEphone(v);
              }}
              inputMode="tel"
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
                  background: cur.color,
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

      {/* [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 修改紧急联系手机弹窗 */}
      {showEditEphone ? (
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
          onClick={() => setShowEditEphone(null)}
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
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
              修改紧急联系手机
            </div>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
              请输入 11 位中国大陆手机号
            </div>
            <input
              value={editEphone}
              onChange={(e) => {
                const v = e.target.value.replace(/[^\d]/g, '').slice(0, 11);
                setEditEphone(v);
              }}
              inputMode="tel"
              maxLength={11}
              style={{
                width: '100%',
                padding: '10px 12px',
                fontSize: 14,
                border: '1px solid #ddd',
                borderRadius: 6,
                marginBottom: 16,
                boxSizing: 'border-box',
              }}
              placeholder="如：13800001234"
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowEditEphone(null)}
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
                onClick={() => {
                  if (showEditEphone) submitEditEphone(showEditEphone, editEphone);
                }}
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
                保存
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 强制补填弹窗 */}
      {forceFillTarget ? (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1100,
          }}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 20,
              width: '88%',
              maxWidth: 360,
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
              请补填紧急联系手机
            </div>
            <div style={{ fontSize: 13, color: '#666', marginBottom: 12 }}>
              为了保障告警可及时触达，请先补填本设备（{forceFillTarget.device_type_label}）的紧急联系手机。
            </div>
            <input
              value={editEphone}
              onChange={(e) => {
                const v = e.target.value.replace(/[^\d]/g, '').slice(0, 11);
                setEditEphone(v);
              }}
              inputMode="tel"
              maxLength={11}
              style={{
                width: '100%',
                padding: '10px 12px',
                fontSize: 14,
                border: '1px solid #ddd',
                borderRadius: 6,
                marginBottom: 16,
                boxSizing: 'border-box',
              }}
              placeholder="如：13800001234"
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => {
                  setForceFillTarget(null);
                  history.back();
                }}
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
                onClick={() => {
                  if (forceFillTarget) submitEditEphone(forceFillTarget, editEphone);
                }}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: '#E53935',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                }}
              >
                立即补填
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

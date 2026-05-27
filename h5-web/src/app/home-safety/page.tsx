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
  gateway_sn_mask: string;
  device_sn: string;
  verify_status: number;
  bound_at: string;
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
  const [loading, setLoading] = useState(false);

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

  const doBind = async () => {
    if (!/^[A-Za-z0-9]{12}$/.test(gw)) {
      showToast('网关 SN 必须为 12 位字母+数字');
      return;
    }
    if (!/^[A-Za-z0-9]{8}$/.test(dev)) {
      showToast('设备 SN 必须为 8 位字母+数字');
      return;
    }
    setLoading(true);
    try {
      await api.post('/api/home_safety/devices/bind', {
        device_type: activeTab,
        gateway_sn: gw,
        device_sn: dev,
      });
      showToast('绑定成功');
      setShowBindModal(false);
      setGw('');
      setDev('');
      // [PRD-HOME-SAFETY-V1 BUGFIX] 显式传入 activeTab，避免闭包旧值
      await loadAll(activeTab);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '绑定失败');
    } finally {
      setLoading(false);
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
          onClick={() => setShowBindModal(true)}
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
          bindings.map((b) => (
            <div
              key={b.id}
              style={{
                background: '#fff',
                padding: 12,
                borderRadius: 8,
                marginBottom: 8,
                borderLeft: `4px solid ${cur.color}`,
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 600 }}>{b.device_type_label}</div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                网关 SN: {b.gateway_sn_mask}
              </div>
              <div style={{ fontSize: 12, color: '#666' }}>设备 SN: {b.device_sn}</div>
              <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                绑定时间: {formatDateTime(b.bound_at)}
              </div>
              <div style={{ marginTop: 8 }}>
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
          ))
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
              网关 SN（12 位字母+数字，手工输入）
            </div>
            <input
              value={gw}
              onChange={(e) => setGw(e.target.value.trim())}
              maxLength={12}
              style={{
                width: '100%',
                padding: '10px 12px',
                fontSize: 14,
                border: '1px solid #ddd',
                borderRadius: 6,
                marginBottom: 12,
                boxSizing: 'border-box',
              }}
              placeholder="例如：ABCD12345678"
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
                marginBottom: 16,
                boxSizing: 'border-box',
              }}
              placeholder="例如：ABCD1234"
            />
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
    </div>
  );
}

'use client';

// [PRD-SAFETY-ROPE-V1 2026-06-03] 数字安全绳（独居守护）H5 页面
// [BUGFIX-SAFETY-ROPE-V1 2026-06-03] v2 锁死版：
//  - Bug2 阈值选中态：绿色填充 + 加粗 + 右上角白底绿勾 ✓
//  - Bug3 紧急联系人表单：删除邮箱字段；手机号必填 + 注册校验 + 保存按钮置灰联动；关系 7 芯片单选
//  - Bug4 签到后顶部 banner：立即 refetch；改为"上次签到 + 下次截止"两行

import { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { formatFriendlyTime } from '@/lib/datetime';

interface Contact {
  id: number;
  name: string;
  email?: string | null;
  phone?: string | null;
  relation?: string | null;
  wechat_openid?: string | null;
  sort_order: number;
  matched_user_id?: number | null;
}

interface StatusResp {
  config: {
    threshold_hours: number;
    status: 'normal' | 'alerting' | 'paused';
    paused_until?: string | null;
  };
  last_checkin: {
    checkin_at: string | null;
    location_address: string | null;
    location_lat?: number | null;
    location_lng?: number | null;
  } | null;
  runtime_status: 'normal' | 'near_timeout' | 'alerting' | 'paused';
  next_checkin_at: string | null;
  remaining_hours: number | null;
  today_checked: boolean;
  contacts_count: number;
}

interface AlertItem {
  id: number;
  triggered_at: string;
  last_checkin_at: string | null;
  last_location: string | null;
  notified_contacts: any[];
  resolved_at: string | null;
  resolved_location: string | null;
}

// 7 芯片关系选项
const RELATION_CHIPS = ['子女', '配偶', '父母', '邻居', '朋友', '护工', '其他'] as const;

function formatDt(s: string | null | undefined): string {
  if (!s) return '—';
  const result = formatFriendlyTime(s);
  return result || s;
}

const PHONE_RE = /^1[3-9]\d{9}$/;

export default function SafetyRopePage() {
  const router = useRouter();

  const [status, setStatus] = useState<StatusResp | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkinLoading, setCheckinLoading] = useState(false);
  const [feedback, setFeedback] = useState<string>('');

  // 联系人编辑
  const [editingContact, setEditingContact] = useState<Partial<Contact> | null>(null);
  const [editingMode, setEditingMode] = useState<'create' | 'edit'>('create');
  const [phoneCheck, setPhoneCheck] = useState<{
    state: 'idle' | 'checking' | 'ok' | 'fail';
    msg: string;
    matched_name?: string;
  }>({ state: 'idle', msg: '' });

  const [pauseConfirm, setPauseConfirm] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const phoneCheckTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [s, c, a] = await Promise.all([
        api.get('/api/safety-rope/status'),
        api.get('/api/safety-rope/contacts'),
        api.get('/api/safety-rope/alerts'),
      ]);
      setStatus(s);
      setContacts(c?.items || []);
      setAlerts(a?.items || []);
    } catch (e: any) {
      console.warn('safety-rope load', e?.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const showFeedback = (msg: string) => {
    setFeedback(msg);
    setTimeout(() => setFeedback(''), 2500);
  };

  const handleCheckin = async () => {
    if (checkinLoading) return;
    setCheckinLoading(true);
    try {
      let payload: any = {};
      if (typeof navigator !== 'undefined' && navigator.geolocation) {
        await new Promise<void>((resolve) => {
          navigator.geolocation.getCurrentPosition(
            async (pos) => {
              payload.location_lat = pos.coords.latitude;
              payload.location_lng = pos.coords.longitude;
              try {
                const rg = await api.post('/api/maps/user/reverse-geocoding', {
                  latitude: pos.coords.latitude,
                  longitude: pos.coords.longitude,
                });
                if (rg?.address) payload.location_address = rg.address;
              } catch {}
              resolve();
            },
            () => resolve(),
            { timeout: 5000, maximumAge: 60000 }
          );
        });
      }
      const resp = await api.post('/api/safety-rope/checkin', payload);
      if (resp?.alert_resolved) {
        showFeedback('已平安解除预警 ❤ 已通知联系人');
      } else {
        showFeedback('收到你的平安信号 ❤ 今天也要照顾好自己哦');
      }
      // [Bug4] 签到成功立即 refetch，确保顶部 banner 立即更新
      await loadAll();
    } catch (e: any) {
      showFeedback('签到失败：' + (e?.response?.data?.detail || e?.message));
    } finally {
      setCheckinLoading(false);
    }
  };

  const handleThresholdChange = async (h: number) => {
    try {
      await api.put('/api/safety-rope/config', { threshold_hours: h });
      showFeedback(`已设置为 ${h} 小时`);
      await loadAll();
    } catch (e: any) {
      showFeedback('设置失败：' + (e?.response?.data?.detail || e?.message));
    }
  };

  const handlePauseToggle = async () => {
    const isPaused = status?.config.status === 'paused';
    if (!isPaused) {
      setPauseConfirm(true);
      return;
    }
    try {
      await api.put('/api/safety-rope/config', { paused: false });
      showFeedback('守护已恢复');
      await loadAll();
    } catch (e: any) {
      showFeedback('恢复失败：' + (e?.response?.data?.detail || e?.message));
    }
  };

  const confirmPause = async (days?: number) => {
    try {
      await api.put('/api/safety-rope/config', { paused: true, paused_days: days });
      setPauseConfirm(false);
      showFeedback('守护已暂停');
      await loadAll();
    } catch (e: any) {
      showFeedback('暂停失败：' + (e?.response?.data?.detail || e?.message));
    }
  };

  // [Bug3] 手机号失焦校验
  const checkPhone = useCallback(async (phone: string) => {
    if (!phone) {
      setPhoneCheck({ state: 'idle', msg: '' });
      return;
    }
    if (!PHONE_RE.test(phone)) {
      setPhoneCheck({ state: 'fail', msg: '请填写正确的 11 位手机号' });
      return;
    }
    setPhoneCheck({ state: 'checking', msg: '校验中…' });
    try {
      const resp = await api.get('/api/safety-rope/contacts/check-phone', {
        params: { phone },
      });
      const r = resp;
      if (r?.registered) {
        setPhoneCheck({
          state: 'ok',
          msg: r.reason || `✓ 已识别用户：${r.name}`,
          matched_name: r.name,
        });
      } else {
        setPhoneCheck({
          state: 'fail',
          msg: r?.reason || '该手机号还未注册 bini-health，请先邀请 TA 注册',
        });
      }
    } catch (e: any) {
      setPhoneCheck({
        state: 'fail',
        msg: '校验失败：' + (e?.response?.data?.detail || e?.message),
      });
    }
  }, []);

  const onPhoneChange = (value: string) => {
    setEditingContact((c) => (c ? { ...c, phone: value } : c));
    setPhoneCheck({ state: 'idle', msg: '' });
    // 防抖：用户输入 500ms 后自动校验
    if (phoneCheckTimer.current) clearTimeout(phoneCheckTimer.current);
    if (value.length >= 11) {
      phoneCheckTimer.current = setTimeout(() => checkPhone(value), 400);
    }
  };

  const handleContactSubmit = async () => {
    if (!editingContact) return;
    if (!editingContact.name || !editingContact.name.trim()) {
      showFeedback('请填写姓名');
      return;
    }
    if (!editingContact.phone || !PHONE_RE.test(editingContact.phone)) {
      showFeedback('请填写正确的 11 位手机号');
      return;
    }
    if (editingMode === 'create' && phoneCheck.state !== 'ok') {
      showFeedback('请先确认手机号已注册');
      return;
    }
    try {
      if (editingMode === 'create') {
        const payload = {
          name: editingContact.name.trim(),
          phone: editingContact.phone.trim(),
          relation: editingContact.relation || undefined,
        };
        await api.post('/api/safety-rope/contacts', payload);
        showFeedback('联系人已添加');
      } else if (editingContact.id) {
        const payload: any = {
          name: editingContact.name?.trim(),
          phone: editingContact.phone?.trim(),
          relation: editingContact.relation,
        };
        await api.put(`/api/safety-rope/contacts/${editingContact.id}`, payload);
        showFeedback('联系人已更新');
      }
      setEditingContact(null);
      setPhoneCheck({ state: 'idle', msg: '' });
      await loadAll();
    } catch (e: any) {
      showFeedback('保存失败：' + (e?.response?.data?.detail || e?.message));
    }
  };

  const handleContactDelete = async (id: number) => {
    if (!confirm('确认删除该联系人？')) return;
    try {
      await api.delete(`/api/safety-rope/contacts/${id}`);
      showFeedback('已删除');
      await loadAll();
    } catch {}
  };

  // [Bug4] 顶部状态条：上次签到 + 下次截止
  const checkinBanner = () => {
    if (!status) return null;
    if (status.runtime_status === 'paused') {
      return (
        <div data-testid="sr-banner-paused"
             style={{ background: '#fff8e1', color: '#8d6e00', padding: '12px 16px',
                      borderRadius: 12, marginBottom: 12, fontSize: 15 }}>
          🌙 守护已暂停，需要时记得手动开启
        </div>
      );
    }
    const lastAt = status.last_checkin?.checkin_at;
    const nextAt = status.next_checkin_at;
    if (status.runtime_status === 'alerting') {
      return (
        <div data-testid="sr-banner-alerting"
             style={{ background: '#ffebee', color: '#c62828', padding: '12px 16px',
                      borderRadius: 12, marginBottom: 12, fontSize: 15, fontWeight: 600 }}>
          ⚠ 您已超时未签到，已通知您的紧急联系人。请尽快签到解除预警。
        </div>
      );
    }
    if (lastAt) {
      const bg = status.runtime_status === 'near_timeout' ? '#fff3e0' : '#e8f5e9';
      const color = status.runtime_status === 'near_timeout' ? '#bf6d00' : '#1b5e20';
      return (
        <div data-testid="sr-banner-checked"
             style={{ background: bg, color, padding: '12px 16px',
                      borderRadius: 12, marginBottom: 12, fontSize: 14, lineHeight: 1.6 }}>
          <div style={{ fontWeight: 700 }}>✅ 上次签到：{formatDt(lastAt)}</div>
          {nextAt && <div>⏰ 下次签到截止：{formatDt(nextAt)}</div>}
        </div>
      );
    }
    return (
      <div data-testid="sr-banner-empty"
           style={{ background: '#e3f2fd', color: '#0d47a1', padding: '12px 16px',
                    borderRadius: 12, marginBottom: 12, fontSize: 14 }}>
        👋 还没有签到过，点下方按钮报个平安吧
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#888' }}>加载中…</div>
    );
  }

  return (
    <div data-testid="safety-rope-page"
         style={{ minHeight: '100vh', background: '#f5f6fa', paddingBottom: 40 }}>
      {/* 顶栏 */}
      <div style={{ padding: '16px 20px', display: 'flex', alignItems: 'center',
                     background: 'linear-gradient(135deg, #74b9a6 0%, #4a9b8e 100%)',
                     color: '#fff' }}>
        <span onClick={() => router.back()} style={{ fontSize: 22, cursor: 'pointer', marginRight: 8 }}>‹</span>
        <span style={{ fontSize: 18, fontWeight: 700 }}>数字安全绳</span>
        <span style={{ marginLeft: 'auto', fontSize: 13, opacity: 0.9 }}>每日平安守护</span>
      </div>

      <div style={{ padding: '16px' }}>
        {checkinBanner()}

        {/* 大签到按钮 */}
        <div style={{ background: '#fff', borderRadius: 16, padding: '24px 16px',
                       textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
                       marginBottom: 16 }}>
          <button
            data-testid="sr-checkin-btn"
            disabled={checkinLoading}
            onClick={handleCheckin}
            style={{
              width: 200,
              height: 200,
              borderRadius: '50%',
              border: 'none',
              background: status?.today_checked
                ? 'linear-gradient(135deg, #b2dfdb 0%, #80cbc4 100%)'
                : 'linear-gradient(135deg, #66bb6a 0%, #43a047 100%)',
              color: '#fff',
              fontSize: 22,
              fontWeight: 800,
              cursor: 'pointer',
              boxShadow: '0 6px 20px rgba(76,175,80,0.35)',
              margin: '12px auto',
              transition: 'all 0.2s',
            }}
          >
            {checkinLoading ? '签到中…' : '我今天平安 ✋'}
          </button>
          {status?.last_checkin?.location_address && (
            <div style={{ fontSize: 12, color: '#888', marginTop: 8 }}>
              📍 上次位置：{status.last_checkin.location_address}
            </div>
          )}
        </div>

        {/* 阈值 / 暂停 */}
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, marginBottom: 16 }}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>守护设置</div>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 14, color: '#666', marginBottom: 8 }}>超时阈值</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {[24, 48].map((h) => {
                const selected = status?.config.threshold_hours === h;
                return (
                  <button
                    key={h}
                    data-testid={`sr-threshold-${h}`}
                    data-selected={selected ? 'true' : 'false'}
                    onClick={() => handleThresholdChange(h)}
                    style={{
                      flex: 1,
                      position: 'relative',
                      padding: '12px 0',
                      borderRadius: 10,
                      border: selected ? '2px solid #2e7d32' : '1px solid #e0e0e0',
                      // [Bug2] 选中态：绿色填充 + 加粗
                      background: selected
                        ? 'linear-gradient(135deg, #43a047 0%, #2e7d32 100%)'
                        : '#f5f5f5',
                      color: selected ? '#fff' : '#666',
                      fontWeight: selected ? 800 : 500,
                      fontSize: 15,
                      cursor: 'pointer',
                      boxShadow: selected
                        ? '0 4px 12px rgba(67,160,71,0.35)'
                        : 'none',
                      transition: 'all 0.2s',
                    }}
                  >
                    {h} 小时
                    {selected && (
                      // [Bug2] 右上角白底绿勾 ✓
                      <span
                        data-testid={`sr-threshold-${h}-check`}
                        style={{
                          position: 'absolute',
                          top: -8,
                          right: -8,
                          width: 22,
                          height: 22,
                          borderRadius: '50%',
                          background: '#fff',
                          color: '#2e7d32',
                          fontSize: 14,
                          fontWeight: 900,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                          border: '2px solid #2e7d32',
                        }}
                      >
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 14, color: '#333' }}>
                {status?.config.status === 'paused' ? '守护已暂停' : '守护进行中'}
              </div>
              {status?.config.paused_until && (
                <div style={{ fontSize: 12, color: '#888' }}>
                  截止 {formatDt(status.config.paused_until)}
                </div>
              )}
            </div>
            <button
              data-testid="sr-pause-toggle"
              onClick={handlePauseToggle}
              style={{
                padding: '8px 18px',
                borderRadius: 8,
                border: '1px solid #4a9b8e',
                background: status?.config.status === 'paused' ? '#4a9b8e' : '#fff',
                color: status?.config.status === 'paused' ? '#fff' : '#4a9b8e',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {status?.config.status === 'paused' ? '恢复守护' : '暂停守护'}
            </button>
          </div>
        </div>

        {/* 紧急联系人 */}
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 16, fontWeight: 700 }}>紧急联系人 ({contacts.length}/3)</div>
            {contacts.length < 3 && (
              <button
                data-testid="sr-contact-add"
                onClick={() => {
                  setEditingContact({});
                  setEditingMode('create');
                  setPhoneCheck({ state: 'idle', msg: '' });
                }}
                style={{ marginLeft: 'auto', padding: '6px 12px', borderRadius: 8,
                         border: 'none', background: '#4a9b8e', color: '#fff', cursor: 'pointer' }}
              >
                + 添加
              </button>
            )}
          </div>
          {contacts.length === 0 ? (
            <div style={{ fontSize: 13, color: '#999', padding: '12px 0' }}>
              还没有紧急联系人，至少添加 1 位才能在超时时收到通知
            </div>
          ) : (
            contacts.map((c) => {
              // 手机号脱敏：13********9
              const maskedPhone = c.phone
                ? c.phone.replace(/^(\d{3})\d{4}(\d{4})$/, '$1****$2')
                : '';
              return (
                <div key={c.id} data-testid={`sr-contact-${c.id}`}
                     style={{ padding: '12px 0', borderBottom: '1px solid #f0f0f0',
                              display: 'flex', alignItems: 'center' }}>
                  {/* 圆头像 */}
                  <div style={{
                    width: 40, height: 40, borderRadius: '50%',
                    background: 'linear-gradient(135deg, #74b9a6 0%, #4a9b8e 100%)',
                    color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 16, fontWeight: 700, flexShrink: 0,
                  }}>
                    {(c.name || '?').slice(0, 1)}
                  </div>
                  <div style={{ flex: 1, marginLeft: 12, minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span>{c.name}</span>
                      {c.relation && (
                        <span style={{
                          fontSize: 11,
                          color: '#2e7d32',
                          background: '#e8f5e9',
                          borderRadius: 6,
                          padding: '1px 6px',
                          fontWeight: 500,
                        }}>
                          {c.relation}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                      📱 {maskedPhone || '未填写'}
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setEditingContact(c);
                      setEditingMode('edit');
                      setPhoneCheck({ state: 'idle', msg: '' });
                    }}
                    style={{ marginRight: 8, padding: '4px 10px', border: 'none',
                             background: 'transparent', color: '#4a9b8e', cursor: 'pointer' }}
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => handleContactDelete(c.id)}
                    style={{ padding: '4px 10px', border: 'none',
                             background: 'transparent', color: '#e57373', cursor: 'pointer' }}
                  >
                    删除
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* 历史预警 */}
        <div style={{ background: '#fff', borderRadius: 16, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 16, fontWeight: 700 }}>历史预警 ({alerts.length})</div>
            <button
              data-testid="sr-history-toggle"
              onClick={() => setHistoryOpen(!historyOpen)}
              style={{ marginLeft: 'auto', padding: '4px 10px', border: 'none',
                       background: 'transparent', color: '#4a9b8e', cursor: 'pointer' }}
            >
              {historyOpen ? '收起' : '展开'}
            </button>
          </div>
          {alerts.length === 0 ? (
            <div style={{ fontSize: 13, color: '#999' }}>暂无预警记录 ✨</div>
          ) : historyOpen ? (
            alerts.map((a) => (
              <div key={a.id} data-testid={`sr-alert-${a.id}`}
                   style={{ padding: '12px 0', borderBottom: '1px solid #f0f0f0' }}>
                <div style={{ fontSize: 14, color: '#c62828', fontWeight: 600 }}>
                  ⚠ {formatDt(a.triggered_at)} 触发预警
                </div>
                <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                  最后签到位置：{a.last_location || '（未提供）'}
                </div>
                <div style={{ fontSize: 12, color: '#666', marginTop: 2 }}>
                  通知联系人：{(a.notified_contacts || []).map((n: any) => n.name).join('、') || '无'}
                </div>
                {a.resolved_at && (
                  <div style={{ fontSize: 12, color: '#43a047', marginTop: 4 }}>
                    ✅ 已于 {formatDt(a.resolved_at)} 解除
                  </div>
                )}
              </div>
            ))
          ) : (
            <div style={{ fontSize: 13, color: '#888' }}>
              最近一次：{formatDt(alerts[0]?.triggered_at)}
            </div>
          )}
        </div>
      </div>

      {/* 反馈 toast */}
      {feedback && (
        <div data-testid="sr-feedback"
             style={{ position: 'fixed', top: 80, left: '50%', transform: 'translateX(-50%)',
                      background: 'rgba(0,0,0,0.85)', color: '#fff', padding: '10px 20px',
                      borderRadius: 22, fontSize: 14, zIndex: 1000 }}>
          {feedback}
        </div>
      )}

      {/* 联系人弹窗 */}
      {editingContact && (
        <div onClick={() => { setEditingContact(null); setPhoneCheck({ state: 'idle', msg: '' }); }}
             style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                      display: 'flex', alignItems: 'flex-end', zIndex: 1100 }}>
          <div onClick={(e) => e.stopPropagation()}
               data-testid="sr-contact-modal"
               style={{ width: '100%', background: '#fff', padding: 20,
                        borderTopLeftRadius: 18, borderTopRightRadius: 18,
                        maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>
              {editingMode === 'create' ? '添加紧急联系人' : '编辑联系人'}
            </div>

            {/* 姓名 */}
            <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>姓名 <span style={{ color: '#e53935' }}>*</span></div>
            <input data-testid="sr-contact-name" placeholder="如：张儿子"
                   value={editingContact.name || ''}
                   onChange={(e) => setEditingContact({ ...editingContact, name: e.target.value })}
                   style={{ width: '100%', padding: 12, marginBottom: 12, borderRadius: 8,
                            border: '1px solid #ddd', fontSize: 15, boxSizing: 'border-box' }} />

            {/* 手机号 + 注册校验 */}
            <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>
              手机号 <span style={{ color: '#e53935' }}>*</span>
              <span style={{ color: '#999', fontSize: 11, marginLeft: 4 }}>（必须是 bini-health 已注册用户）</span>
            </div>
            <input data-testid="sr-contact-phone" placeholder="11 位手机号"
                   inputMode="tel"
                   value={editingContact.phone || ''}
                   onChange={(e) => onPhoneChange(e.target.value)}
                   onBlur={(e) => checkPhone(e.target.value)}
                   style={{
                     width: '100%',
                     padding: 12,
                     marginBottom: phoneCheck.msg ? 4 : 12,
                     borderRadius: 8,
                     border: phoneCheck.state === 'ok'
                       ? '2px solid #43a047'
                       : phoneCheck.state === 'fail'
                       ? '2px solid #e53935'
                       : '1px solid #ddd',
                     fontSize: 15,
                     boxSizing: 'border-box',
                   }} />
            {phoneCheck.msg && (
              <div data-testid="sr-contact-phone-check"
                   style={{
                     fontSize: 12,
                     marginBottom: 12,
                     color: phoneCheck.state === 'ok' ? '#2e7d32' :
                            phoneCheck.state === 'fail' ? '#c62828' : '#888',
                   }}>
                {phoneCheck.msg}
              </div>
            )}

            {/* 关系 — 7 芯片单选 */}
            <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>关系（选填）</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 18 }}>
              {RELATION_CHIPS.map((r) => {
                const selected = editingContact.relation === r;
                return (
                  <button
                    key={r}
                    data-testid={`sr-relation-${r}`}
                    data-selected={selected ? 'true' : 'false'}
                    onClick={() => setEditingContact({ ...editingContact, relation: selected ? '' : r })}
                    style={{
                      padding: '8px 16px',
                      borderRadius: 22,
                      border: selected ? '2px solid #2e7d32' : '1px solid #ddd',
                      background: selected ? '#43a047' : '#fff',
                      color: selected ? '#fff' : '#555',
                      fontSize: 14,
                      fontWeight: selected ? 700 : 500,
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                  >
                    {r}
                  </button>
                );
              })}
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => { setEditingContact(null); setPhoneCheck({ state: 'idle', msg: '' }); }}
                      style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid #ddd',
                               background: '#fff', cursor: 'pointer' }}>取消</button>
              <button data-testid="sr-contact-save"
                      onClick={handleContactSubmit}
                      disabled={editingMode === 'create' && phoneCheck.state !== 'ok'}
                      style={{
                        flex: 1,
                        padding: 12,
                        borderRadius: 8,
                        border: 'none',
                        background: editingMode === 'create' && phoneCheck.state !== 'ok'
                          ? '#bdbdbd'
                          : '#4a9b8e',
                        color: '#fff',
                        fontWeight: 600,
                        cursor: editingMode === 'create' && phoneCheck.state !== 'ok' ? 'not-allowed' : 'pointer',
                      }}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 暂停确认 */}
      {pauseConfirm && (
        <div onClick={() => setPauseConfirm(false)}
             style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100 }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ background: '#fff', borderRadius: 14, padding: 20,
                        width: '85%', maxWidth: 360 }}>
            <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 12 }}>暂停守护？</div>
            <div style={{ fontSize: 14, color: '#666', marginBottom: 16 }}>
              暂停期间将不会通知您的紧急联系人。请选择暂停时长：
            </div>
            {[
              { label: '3 天', days: 3 },
              { label: '7 天', days: 7 },
              { label: '14 天', days: 14 },
              { label: '无限期', days: undefined },
            ].map((opt) => (
              <button
                key={opt.label}
                data-testid={`sr-pause-${opt.days ?? 'forever'}`}
                onClick={() => confirmPause(opt.days)}
                style={{ width: '100%', padding: 12, marginBottom: 8,
                         borderRadius: 8, border: '1px solid #4a9b8e',
                         background: '#fff', color: '#4a9b8e', fontWeight: 600,
                         cursor: 'pointer' }}
              >
                {opt.label}
              </button>
            ))}
            <button onClick={() => setPauseConfirm(false)}
                    style={{ width: '100%', padding: 12, borderRadius: 8, border: 'none',
                             background: '#eee', color: '#555', cursor: 'pointer' }}>
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

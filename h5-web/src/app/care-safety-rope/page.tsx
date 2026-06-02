'use client';

// [PRD-SAFETY-ROPE-V1 2026-06-03] 数字安全绳（独居守护）H5 页面
// 入口：关怀模式首页 → "数字安全绳" 卡片；独立 URL /care-safety-rope

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface Contact {
  id: number;
  name: string;
  email: string;
  phone?: string | null;
  relation?: string | null;
  wechat_openid?: string | null;
  sort_order: number;
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

function formatDt(s: string | null | undefined): string {
  if (!s) return '—';
  try {
    const d = new Date(s);
    if (isNaN(d.getTime())) return s;
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return s;
  }
}

export default function SafetyRopePage() {
  const router = useRouter();
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const [status, setStatus] = useState<StatusResp | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkinLoading, setCheckinLoading] = useState(false);
  const [feedback, setFeedback] = useState<string>('');

  // 联系人编辑
  const [editingContact, setEditingContact] = useState<Partial<Contact> | null>(null);
  const [editingMode, setEditingMode] = useState<'create' | 'edit'>('create');

  // 暂停确认
  const [pauseConfirm, setPauseConfirm] = useState(false);

  // 历史抽屉
  const [historyOpen, setHistoryOpen] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [s, c, a] = await Promise.all([
        api.get('/api/safety-rope/status'),
        api.get('/api/safety-rope/contacts'),
        api.get('/api/safety-rope/alerts'),
      ]);
      setStatus(s.data);
      setContacts(c.data?.items || []);
      setAlerts(a.data?.items || []);
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
      // 尝试拿位置（不强制）
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
                if (rg.data?.address) payload.location_address = rg.data.address;
              } catch {}
              resolve();
            },
            () => resolve(),
            { timeout: 5000, maximumAge: 60000 }
          );
        });
      }
      const resp = await api.post('/api/safety-rope/checkin', payload);
      if (resp.data?.alert_resolved) {
        showFeedback('已平安解除预警 ❤ 已通知联系人');
      } else {
        showFeedback('收到你的平安信号 ❤ 今天也要照顾好自己哦');
      }
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

  const handleContactSubmit = async () => {
    if (!editingContact || !editingContact.name || !editingContact.email) {
      showFeedback('请填写姓名和邮箱');
      return;
    }
    try {
      if (editingMode === 'create') {
        await api.post('/api/safety-rope/contacts', editingContact);
        showFeedback('联系人已添加');
      } else if (editingContact.id) {
        await api.put(`/api/safety-rope/contacts/${editingContact.id}`, editingContact);
        showFeedback('联系人已更新');
      }
      setEditingContact(null);
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

  const statusBanner = () => {
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
    if (status.runtime_status === 'alerting') {
      return (
        <div data-testid="sr-banner-alerting"
             style={{ background: '#ffebee', color: '#c62828', padding: '12px 16px',
                      borderRadius: 12, marginBottom: 12, fontSize: 15, fontWeight: 600 }}>
          ⚠ 您已超时未签到，已通知您的紧急联系人。请尽快签到解除预警。
        </div>
      );
    }
    if (status.runtime_status === 'near_timeout') {
      return (
        <div data-testid="sr-banner-near"
             style={{ background: '#fff3e0', color: '#bf6d00', padding: '12px 16px',
                      borderRadius: 12, marginBottom: 12, fontSize: 15 }}>
          ⏰ 还有不到 1 小时就到签到时间，记得签到哦~
        </div>
      );
    }
    return null;
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
        {statusBanner()}

        {/* 大签到按钮 */}
        <div style={{ background: '#fff', borderRadius: 16, padding: '24px 16px',
                       textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
                       marginBottom: 16 }}>
          <div style={{ fontSize: 14, color: '#888', marginBottom: 8 }}>
            {status?.today_checked
              ? `今天已签到 · 上次签到 ${formatDt(status?.last_checkin?.checkin_at)}`
              : '今天还没签到'}
          </div>
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
              {[24, 48].map((h) => (
                <button
                  key={h}
                  data-testid={`sr-threshold-${h}`}
                  onClick={() => handleThresholdChange(h)}
                  style={{
                    flex: 1,
                    padding: '10px 0',
                    borderRadius: 10,
                    border: 'none',
                    background:
                      status?.config.threshold_hours === h ? '#4a9b8e' : '#eee',
                    color: status?.config.threshold_hours === h ? '#fff' : '#555',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  {h} 小时
                </button>
              ))}
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
                onClick={() => { setEditingContact({}); setEditingMode('create'); }}
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
            contacts.map((c) => (
              <div key={c.id} data-testid={`sr-contact-${c.id}`}
                   style={{ padding: '12px 0', borderBottom: '1px solid #f0f0f0',
                            display: 'flex', alignItems: 'center' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>
                    {c.name} <span style={{ fontSize: 12, color: '#888', fontWeight: 400 }}>
                      · {c.relation || '其他'}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                    {c.email}{c.phone ? ` · ${c.phone}` : ''}
                  </div>
                </div>
                <button
                  onClick={() => { setEditingContact(c); setEditingMode('edit'); }}
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
            ))
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
        <div onClick={() => setEditingContact(null)}
             style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                      display: 'flex', alignItems: 'flex-end', zIndex: 1100 }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ width: '100%', background: '#fff', padding: 20,
                        borderTopLeftRadius: 18, borderTopRightRadius: 18 }}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>
              {editingMode === 'create' ? '添加紧急联系人' : '编辑联系人'}
            </div>
            <input data-testid="sr-contact-name" placeholder="姓名 *"
                   value={editingContact.name || ''}
                   onChange={(e) => setEditingContact({ ...editingContact, name: e.target.value })}
                   style={{ width: '100%', padding: 12, marginBottom: 10, borderRadius: 8,
                            border: '1px solid #ddd', fontSize: 15 }} />
            <input data-testid="sr-contact-email" placeholder="邮箱 *"
                   value={editingContact.email || ''}
                   onChange={(e) => setEditingContact({ ...editingContact, email: e.target.value })}
                   style={{ width: '100%', padding: 12, marginBottom: 10, borderRadius: 8,
                            border: '1px solid #ddd', fontSize: 15 }} />
            <input placeholder="手机号（选填）"
                   value={editingContact.phone || ''}
                   onChange={(e) => setEditingContact({ ...editingContact, phone: e.target.value })}
                   style={{ width: '100%', padding: 12, marginBottom: 10, borderRadius: 8,
                            border: '1px solid #ddd', fontSize: 15 }} />
            <select value={editingContact.relation || ''}
                    onChange={(e) => setEditingContact({ ...editingContact, relation: e.target.value })}
                    style={{ width: '100%', padding: 12, marginBottom: 16, borderRadius: 8,
                             border: '1px solid #ddd', fontSize: 15, background: '#fff' }}>
              <option value="">请选择关系</option>
              <option value="子女">子女</option>
              <option value="配偶">配偶</option>
              <option value="邻居">邻居</option>
              <option value="朋友">朋友</option>
              <option value="社区">社区</option>
              <option value="其他">其他</option>
            </select>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setEditingContact(null)}
                      style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid #ddd',
                               background: '#fff', cursor: 'pointer' }}>取消</button>
              <button data-testid="sr-contact-save" onClick={handleContactSubmit}
                      style={{ flex: 1, padding: 12, borderRadius: 8, border: 'none',
                               background: '#4a9b8e', color: '#fff', fontWeight: 600,
                               cursor: 'pointer' }}>保存</button>
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

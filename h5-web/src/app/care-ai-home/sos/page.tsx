'use client';

// [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式 → 紧急呼叫 SOS 页
// - 顶部大红色「长按 3 秒」SOS 按钮 + 定位条
// - 紧急联系人：儿子 / 女儿 / 家庭医生（来自后端，可维护）
// - 一键呼叫 120 / 110
// - 分享位置
// - 紧急联系人维护入口（弹窗内 CRUD）

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface Contact {
  id: number;
  name: string;
  relation: string;
  phone: string;
}

export default function CareSosPage() {
  const router = useRouter();

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [location, setLocation] = useState<string>('正在获取定位…');
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [holding, setHolding] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const [toast, setToast] = useState('');
  const [maintainOpen, setMaintainOpen] = useState(false);

  const holdTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2200);
  };

  const loadContacts = async () => {
    try {
      const res: any = await api.get('/api/care-card/contacts');
      setContacts(res?.data?.items ?? res?.items ?? []);
    } catch {
      setContacts([]);
    }
  };

  useEffect(() => {
    loadContacts();
    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
          setLocation(`当前位置：${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}`);
        },
        () => setLocation('定位未授权，请手动告知位置'),
        { timeout: 8000 }
      );
    } else {
      setLocation('当前设备不支持定位');
    }
  }, []);

  const callPhone = (phone: string) => {
    if (!phone) {
      showToast('该联系人未填写电话');
      return;
    }
    window.location.href = `tel:${phone}`;
  };

  // 长按 3 秒触发 SOS
  const startHold = () => {
    setHolding(true);
    setHoldProgress(0);
    let elapsed = 0;
    holdTimer.current = setInterval(() => {
      elapsed += 100;
      setHoldProgress(Math.min(100, (elapsed / 3000) * 100));
      if (elapsed >= 3000) {
        endHold();
        triggerSos();
      }
    }, 100);
  };

  const endHold = () => {
    if (holdTimer.current) {
      clearInterval(holdTimer.current);
      holdTimer.current = null;
    }
    setHolding(false);
    setHoldProgress(0);
  };

  const triggerSos = () => {
    const first = contacts.find((c) => c.phone);
    if (first) {
      showToast(`正在呼叫紧急联系人：${first.name || first.relation || '联系人'}`);
      setTimeout(() => callPhone(first.phone), 600);
    } else {
      showToast('未设置紧急联系人，正在拨打 120');
      setTimeout(() => callPhone('120'), 600);
    }
  };

  const shareLocation = async () => {
    const text = coords
      ? `我现在的位置：https://uri.amap.com/marker?position=${coords.lng},${coords.lat}`
      : '我需要帮助，请联系我（当前未获取到定位）';
    try {
      if (navigator.share) {
        await navigator.share({ title: 'SOS 位置共享', text });
      } else {
        await navigator.clipboard.writeText(text);
        showToast('位置已复制，可粘贴发送给家人');
      }
    } catch {
      showToast('分享已取消');
    }
  };

  return (
    <div
      style={{ minHeight: '100vh', background: '#FFF5F5', paddingBottom: 32, color: '#212121' }}
      data-testid="care-sos-page"
    >
      {/* 顶栏 */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          background: '#FFFFFF',
          borderBottom: '1px solid #FFE0E0',
          height: 52,
          display: 'flex',
          alignItems: 'center',
          padding: '0 12px',
        }}
      >
        <button
          aria-label="返回"
          onClick={() => router.back()}
          style={{ background: 'transparent', border: 'none', fontSize: 22, cursor: 'pointer', width: 40, height: 40 }}
        >
          ‹
        </button>
        <div style={{ flex: 1, textAlign: 'center', fontSize: 18, fontWeight: 700, color: '#C62828', marginRight: 40 }}>
          紧急求助 · SOS
        </div>
      </div>

      {/* 上半截：SOS 大按钮 + 定位条 */}
      <div style={{ padding: '24px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <button
          data-testid="care-sos-button"
          onMouseDown={startHold}
          onMouseUp={endHold}
          onMouseLeave={endHold}
          onTouchStart={startHold}
          onTouchEnd={endHold}
          style={{
            position: 'relative',
            width: 200,
            height: 200,
            borderRadius: '50%',
            background: holding
              ? 'radial-gradient(circle, #C62828 0%, #B71C1C 100%)'
              : 'radial-gradient(circle, #EF5350 0%, #E53935 100%)',
            color: '#FFF',
            border: 'none',
            boxShadow: '0 10px 28px rgba(229,57,53,0.5)',
            cursor: 'pointer',
            userSelect: 'none',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
          }}
        >
          <span style={{ fontSize: 52, fontWeight: 800, letterSpacing: 2 }}>SOS</span>
          <span style={{ fontSize: 16 }}>长按 3 秒</span>
          {holding && (
            <span style={{ position: 'absolute', bottom: 28, fontSize: 13 }}>
              {Math.round(holdProgress)}%
            </span>
          )}
        </button>

        <div
          data-testid="care-sos-location"
          style={{
            marginTop: 22,
            background: '#FFFFFF',
            borderRadius: 12,
            padding: '12px 16px',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 14,
            color: '#555',
            boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
          }}
        >
          <span aria-hidden="true">📍</span>
          <span style={{ flex: 1 }}>{location}</span>
        </div>
      </div>

      {/* 紧急联系人 */}
      <div style={{ padding: '0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>紧急联系人</h3>
          <button
            data-testid="care-sos-maintain-entry"
            onClick={() => setMaintainOpen(true)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#1976D2',
              fontSize: 14,
              cursor: 'pointer',
            }}
          >
            维护 ›
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }} data-testid="care-sos-contacts">
          {contacts.length === 0 ? (
            <div style={{ background: '#FFFFFF', borderRadius: 14, padding: 16, color: '#999', fontSize: 14, textAlign: 'center' }}>
              暂无紧急联系人，点击右上角「维护」添加
            </div>
          ) : (
            contacts.map((c) => (
              <div
                key={c.id}
                style={{
                  background: '#FFFFFF',
                  borderRadius: 14,
                  padding: '14px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 17, fontWeight: 600 }}>
                    {c.name || '未填写'}{c.relation ? `（${c.relation}）` : ''}
                  </div>
                  <div style={{ fontSize: 14, color: '#999', marginTop: 2 }}>{c.phone || '暂无电话'}</div>
                </div>
                <button
                  onClick={() => callPhone(c.phone)}
                  style={{
                    background: '#43A047',
                    color: '#FFF',
                    border: 'none',
                    borderRadius: 24,
                    padding: '10px 18px',
                    fontSize: 15,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  📞 呼叫
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 下半截：一键 120/110 + 分享位置 */}
      <div style={{ padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            data-testid="care-sos-call-120"
            onClick={() => callPhone('120')}
            style={{
              flex: 1,
              background: '#E53935',
              color: '#FFF',
              border: 'none',
              borderRadius: 14,
              padding: '16px 0',
              fontSize: 18,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            🚑 呼叫 120
          </button>
          <button
            data-testid="care-sos-call-110"
            onClick={() => callPhone('110')}
            style={{
              flex: 1,
              background: '#1565C0',
              color: '#FFF',
              border: 'none',
              borderRadius: 14,
              padding: '16px 0',
              fontSize: 18,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            🚓 呼叫 110
          </button>
        </div>
        <button
          data-testid="care-sos-share-location"
          onClick={shareLocation}
          style={{
            background: '#FFFFFF',
            color: '#1976D2',
            border: '1px solid #1976D2',
            borderRadius: 14,
            padding: '14px 0',
            fontSize: 16,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          📍 分享我的位置
        </button>
      </div>

      {/* 紧急联系人维护弹窗 */}
      {maintainOpen && (
        <ContactMaintainModal
          contacts={contacts}
          onClose={() => setMaintainOpen(false)}
          onChanged={loadContacts}
          showToast={showToast}
        />
      )}

      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'rgba(0,0,0,0.8)',
            color: '#FFF',
            padding: '10px 20px',
            borderRadius: 8,
            fontSize: 14,
            zIndex: 300,
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}

function ContactMaintainModal({
  contacts,
  onClose,
  onChanged,
  showToast,
}: {
  contacts: Contact[];
  onClose: () => void;
  onChanged: () => void;
  showToast: (m: string) => void;
}) {
  const [name, setName] = useState('');
  const [relation, setRelation] = useState('');
  const [phone, setPhone] = useState('');
  const [saving, setSaving] = useState(false);
  const [homeAddress, setHomeAddress] = useState('');
  const [addrSaving, setAddrSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res: any = await api.get('/api/care-card/info');
        const data = res?.data ?? res ?? {};
        setHomeAddress(data.home_address || '');
      } catch {
        /* ignore */
      }
    })();
  }, []);

  const saveAddress = async () => {
    setAddrSaving(true);
    try {
      await api.put('/api/care-card/home-address', { home_address: homeAddress });
      showToast('家庭住址已保存');
    } catch {
      showToast('保存失败，请重试');
    } finally {
      setAddrSaving(false);
    }
  };

  const add = async () => {
    if (!name && !phone) {
      showToast('请填写姓名或电话');
      return;
    }
    setSaving(true);
    try {
      await api.post('/api/care-card/contacts', { name, relation, phone });
      setName('');
      setRelation('');
      setPhone('');
      await onChanged();
      showToast('已添加');
    } catch {
      showToast('添加失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await api.delete(`/api/care-card/contacts/${id}`);
      await onChanged();
      showToast('已删除');
    } catch {
      showToast('删除失败');
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    border: '1px solid #E0E0E0',
    borderRadius: 10,
    padding: '12px 14px',
    fontSize: 15,
    marginBottom: 10,
    boxSizing: 'border-box',
  };

  return (
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 250, display: 'flex', alignItems: 'flex-end' }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        data-testid="care-sos-maintain-modal"
        style={{
          width: '100%',
          maxHeight: '85vh',
          overflowY: 'auto',
          background: '#FFFFFF',
          borderRadius: '20px 20px 0 0',
          padding: 20,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>紧急联系人维护</h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', fontSize: 22, cursor: 'pointer' }}>✕</button>
        </div>

        {/* 家庭住址 */}
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 10 }}>家庭住址</div>
        <input
          style={inputStyle}
          placeholder="请填写家庭住址（用于个人信息卡展示）"
          value={homeAddress}
          onChange={(e) => setHomeAddress(e.target.value)}
          data-testid="care-sos-input-address"
        />
        <button
          onClick={saveAddress}
          disabled={addrSaving}
          data-testid="care-sos-save-address-btn"
          style={{
            width: '100%',
            background: '#FFFFFF',
            color: '#1976D2',
            border: '1px solid #1976D2',
            borderRadius: 12,
            padding: '12px 0',
            fontSize: 15,
            fontWeight: 600,
            cursor: addrSaving ? 'default' : 'pointer',
            marginBottom: 18,
          }}
        >
          {addrSaving ? '保存中…' : '保存家庭住址'}
        </button>

        {/* 已有联系人 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
          {contacts.map((c) => (
            <div
              key={c.id}
              style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#F7F8FA', borderRadius: 10, padding: '12px 14px' }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 600 }}>
                  {c.name || '未填写'}{c.relation ? `（${c.relation}）` : ''}
                </div>
                <div style={{ fontSize: 13, color: '#999' }}>{c.phone || '暂无电话'}</div>
              </div>
              <button
                onClick={() => remove(c.id)}
                style={{ background: 'transparent', border: 'none', color: '#E53935', fontSize: 14, cursor: 'pointer' }}
              >
                删除
              </button>
            </div>
          ))}
        </div>

        {/* 新增 */}
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 10 }}>新增联系人</div>
        <input style={inputStyle} placeholder="姓名" value={name} onChange={(e) => setName(e.target.value)} data-testid="care-sos-input-name" />
        <input style={inputStyle} placeholder="关系（如 儿子 / 女儿 / 家庭医生）" value={relation} onChange={(e) => setRelation(e.target.value)} data-testid="care-sos-input-relation" />
        <input style={inputStyle} placeholder="电话" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" data-testid="care-sos-input-phone" />
        <button
          onClick={add}
          disabled={saving}
          data-testid="care-sos-add-btn"
          style={{
            width: '100%',
            background: '#1976D2',
            color: '#FFF',
            border: 'none',
            borderRadius: 12,
            padding: '14px 0',
            fontSize: 16,
            fontWeight: 600,
            cursor: saving ? 'default' : 'pointer',
          }}
        >
          {saving ? '保存中…' : '＋ 添加联系人'}
        </button>
      </div>
    </div>
  );
}

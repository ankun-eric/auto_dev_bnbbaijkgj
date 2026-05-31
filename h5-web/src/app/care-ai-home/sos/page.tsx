'use client';

// [PRD-CARE-MODE-OPTIM-V4 2026-05-31] 关怀模式 → 紧急呼叫 SOS 页（最终定稿）
// 需求 10：
//  - 10.1 动态扩散圈 SOS：中间红色大 SOS 按钮，外面一圈圈往外扩散的红色光圈（水波/雷达）
//  - 10.2 长按 3 秒触发 + 进度环：长按过程进度环跟着转，转满 3 秒才发出求助（防误触）
//  - 10.3 绿色定位条：定位中=灰色「定位中…」；定位成功=绿色「● 定位已就绪 · 具体地址」（不再展示精度米数）
//  - 10.4 紧急联系人列表：右上角「管理」，每个联系人含名字、优先标签、绿色拨打按钮
// 需求 7：坐标 → 中文地址（沿用项目现用地图服务，后端 /api/maps/reverse-geocoding 高德优先 OSM 兜底）
// 需求 8：紧急联系人维护（家庭住址必填、新建联系人电话必填）+ 分享我的位置（静态位置，微信发给好友）

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface Contact {
  id: number;
  name: string;
  relation: string;
  phone: string;
}

type LocStatus = 'loading' | 'ready' | 'failed';

export default function CareSosPage() {
  const router = useRouter();
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [locStatus, setLocStatus] = useState<LocStatus>('loading');
  const [address, setAddress] = useState<string>('');
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

  // 坐标 → 中文地址（需求7）
  const resolveAddress = async (lat: number, lng: number) => {
    try {
      const res: any = await api.post('/api/maps/reverse-geocoding', { latitude: lat, longitude: lng });
      const data = res?.data ?? res ?? {};
      const addr = data.formatted_address || [data.province, data.city, data.district].filter(Boolean).join('') || '';
      if (addr) {
        setAddress(addr);
        setLocStatus('ready');
        return addr;
      }
    } catch {
      /* 解析失败时退回坐标兜底 */
    }
    const fallback = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    setAddress(fallback);
    setLocStatus('ready');
    return fallback;
  };

  useEffect(() => {
    loadContacts();
    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          setCoords({ lat, lng });
          resolveAddress(lat, lng);
        },
        () => setLocStatus('failed'),
        { timeout: 8000, enableHighAccuracy: true }
      );
    } else {
      setLocStatus('failed');
    }
  }, []);

  const callPhone = (phone: string) => {
    if (!phone) {
      showToast('该联系人未填写电话');
      return;
    }
    window.location.href = `tel:${phone}`;
  };

  // 长按 3 秒触发 SOS（需求10.2）
  const startHold = () => {
    if (holdTimer.current) return;
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

  // 进度环参数（SVG）
  const RING = 96; // 半径
  const CIRC = 2 * Math.PI * RING;

  // 绿色定位条文案
  const locText =
    locStatus === 'ready'
      ? `定位已就绪 · ${address}`
      : locStatus === 'failed'
      ? '定位失败，请手动告知位置'
      : '定位中…';

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

      {/* 上半截：动态扩散圈 SOS 大按钮 + 长按进度环 */}
      <div style={{ padding: '28px 20px 16px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ position: 'relative', width: 260, height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {/* 扩散光圈（雷达/水波） */}
          <span className="care-sos-ripple care-sos-ripple-1" />
          <span className="care-sos-ripple care-sos-ripple-2" />
          <span className="care-sos-ripple care-sos-ripple-3" />

          {/* 长按进度环（SVG） */}
          <svg width={216} height={216} style={{ position: 'absolute', transform: 'rotate(-90deg)' }}>
            <circle cx={108} cy={108} r={RING} fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth={10} />
            <circle
              cx={108}
              cy={108}
              r={RING}
              fill="none"
              stroke="#FFFFFF"
              strokeWidth={10}
              strokeLinecap="round"
              strokeDasharray={CIRC}
              strokeDashoffset={CIRC * (1 - holdProgress / 100)}
              style={{ transition: holding ? 'stroke-dashoffset 0.1s linear' : 'none' }}
              data-testid="care-sos-progress-ring"
            />
          </svg>

          <button
            data-testid="care-sos-button"
            onMouseDown={startHold}
            onMouseUp={endHold}
            onMouseLeave={endHold}
            onTouchStart={startHold}
            onTouchEnd={endHold}
            style={{
              position: 'relative',
              zIndex: 2,
              width: 184,
              height: 184,
              borderRadius: '50%',
              background: holding
                ? 'radial-gradient(circle, #C62828 0%, #B71C1C 100%)'
                : 'radial-gradient(circle, #EF5350 0%, #E53935 100%)',
              color: '#FFF',
              border: 'none',
              boxShadow: '0 10px 28px rgba(229,57,53,0.5)',
              cursor: 'pointer',
              userSelect: 'none',
              WebkitUserSelect: 'none',
              touchAction: 'none',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            <span style={{ fontSize: 50, fontWeight: 800, letterSpacing: 2 }}>SOS</span>
            <span style={{ fontSize: 15 }}>{holding ? `松开取消 · ${Math.round(holdProgress)}%` : '长按 3 秒求助'}</span>
          </button>
        </div>

        {/* 绿色定位条（需求10.3） */}
        <div
          data-testid="care-sos-location"
          data-status={locStatus}
          style={{
            marginTop: 24,
            background: locStatus === 'ready' ? '#E8F5E9' : '#F1F3F5',
            border: locStatus === 'ready' ? '1px solid #A5D6A7' : '1px solid #E0E0E0',
            borderRadius: 12,
            padding: '12px 16px',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 14,
            color: locStatus === 'ready' ? '#2E7D32' : '#888',
            fontWeight: locStatus === 'ready' ? 600 : 400,
          }}
        >
          <span aria-hidden="true" style={{ color: locStatus === 'ready' ? '#43A047' : '#BBB', fontSize: 16 }}>
            ●
          </span>
          <span style={{ flex: 1 }}>{locText}</span>
        </div>
      </div>

      {/* 紧急联系人列表（需求10.4） */}
      <div style={{ padding: '0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>紧急联系人</h3>
          <button
            data-testid="care-sos-maintain-entry"
            onClick={() => setMaintainOpen(true)}
            style={{ background: 'transparent', border: 'none', color: '#1976D2', fontSize: 14, cursor: 'pointer' }}
          >
            管理 ›
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }} data-testid="care-sos-contacts">
          {contacts.length === 0 ? (
            <div style={{ background: '#FFFFFF', borderRadius: 14, padding: 16, color: '#999', fontSize: 14, textAlign: 'center' }}>
              暂无紧急联系人，点击右上角「管理」添加
            </div>
          ) : (
            contacts.map((c, idx) => (
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
                <div
                  style={{
                    flexShrink: 0,
                    width: 44,
                    height: 44,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg,#42A5F5,#1976D2)',
                    color: '#FFF',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 18,
                    fontWeight: 700,
                  }}
                  aria-hidden="true"
                >
                  {(c.name || c.relation || '人').slice(0, 1)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 17, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span>{c.name || '未填写'}</span>
                    {idx === 0 && (
                      <span style={{ fontSize: 11, color: '#E65100', background: '#FFF3E0', borderRadius: 6, padding: '1px 6px' }}>
                        优先
                      </span>
                    )}
                    {c.relation && (
                      <span style={{ fontSize: 12, color: '#1976D2', background: '#E3F2FD', borderRadius: 6, padding: '1px 6px' }}>
                        {c.relation}
                      </span>
                    )}
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
            style={{ flex: 1, background: '#E53935', color: '#FFF', border: 'none', borderRadius: 14, padding: '16px 0', fontSize: 18, fontWeight: 700, cursor: 'pointer' }}
          >
            🚑 呼叫 120
          </button>
          <button
            data-testid="care-sos-call-110"
            onClick={() => callPhone('110')}
            style={{ flex: 1, background: '#1565C0', color: '#FFF', border: 'none', borderRadius: 14, padding: '16px 0', fontSize: 18, fontWeight: 700, cursor: 'pointer' }}
          >
            🚓 呼叫 110
          </button>
        </div>
      </div>

      {/* 紧急联系人维护弹窗 */}
      {maintainOpen && (
        <ContactMaintainModal
          contacts={contacts}
          coords={coords}
          address={address}
          basePath={basePath}
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
            maxWidth: '80%',
            textAlign: 'center',
          }}
        >
          {toast}
        </div>
      )}

      <style jsx>{`
        .care-sos-ripple {
          position: absolute;
          width: 184px;
          height: 184px;
          border-radius: 50%;
          background: rgba(229, 57, 53, 0.28);
          animation: care-sos-spread 2.1s ease-out infinite;
        }
        .care-sos-ripple-2 {
          animation-delay: 0.7s;
        }
        .care-sos-ripple-3 {
          animation-delay: 1.4s;
        }
        @keyframes care-sos-spread {
          0% {
            transform: scale(1);
            opacity: 0.55;
          }
          100% {
            transform: scale(1.4);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}

function ContactMaintainModal({
  contacts,
  coords,
  address,
  basePath,
  onClose,
  onChanged,
  showToast,
}: {
  contacts: Contact[];
  coords: { lat: number; lng: number } | null;
  address: string;
  basePath: string;
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
  const [sharing, setSharing] = useState(false);

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
    // [需求8.1] 家庭住址必填
    if (!homeAddress.trim()) {
      showToast('请先填写家庭住址');
      return;
    }
    setAddrSaving(true);
    try {
      await api.put('/api/care-card/home-address', { home_address: homeAddress.trim() });
      showToast('家庭住址已保存');
    } catch {
      showToast('保存失败，请重试');
    } finally {
      setAddrSaving(false);
    }
  };

  const add = async () => {
    // [需求8.2] 新建联系人电话必填
    if (!phone.trim()) {
      showToast('请填写联系人电话');
      return;
    }
    setSaving(true);
    try {
      await api.post('/api/care-card/contacts', { name: name.trim(), relation: relation.trim(), phone: phone.trim() });
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

  // [需求8.3] 分享我的位置（静态位置，微信发给好友）
  const shareMyLocation = async () => {
    if (sharing) return;
    setSharing(true);
    try {
      const res: any = await api.post('/api/care-card/share-location', {
        latitude: coords?.lat ?? null,
        longitude: coords?.lng ?? null,
        address: address || '',
      });
      const token = res?.data?.token ?? res?.token;
      if (!token) {
        showToast('生成分享链接失败，请重试');
        return;
      }
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const shareUrl = `${origin}${basePath}/care-ai-home/share-location/${token}`;

      // 小程序 web-view 内：通过 wx.miniProgram 触发原生「转发给好友」
      const wxmp: any = (typeof window !== 'undefined' && (window as any).wx && (window as any).wx.miniProgram) || null;
      if (wxmp && typeof wxmp.postMessage === 'function') {
        wxmp.postMessage({ data: { action: 'shareLocation', url: shareUrl, address: address || '我的位置' } });
        // 跳转到小程序内的分享中转页，由小程序原生 onShareAppMessage 转发给微信好友
        if (typeof wxmp.navigateTo === 'function') {
          wxmp.navigateTo({ url: `/pages/care-share-location/index?token=${encodeURIComponent(token)}&address=${encodeURIComponent(address || '我的位置')}` });
          return;
        }
      }

      // 浏览器/H5 兜底：系统分享或复制链接
      if (typeof navigator !== 'undefined' && (navigator as any).share) {
        await (navigator as any).share({ title: '我的位置', text: `我现在的位置：${address || ''}`, url: shareUrl });
      } else if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(shareUrl);
        showToast('位置链接已复制，可粘贴发送给微信好友');
      } else {
        showToast('请复制链接发送给好友：' + shareUrl);
      }
    } catch {
      showToast('分享失败，请重试');
    } finally {
      setSharing(false);
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
        style={{ width: '100%', maxHeight: '88vh', overflowY: 'auto', background: '#FFFFFF', borderRadius: '20px 20px 0 0', padding: 20 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>紧急联系人维护</h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', fontSize: 22, cursor: 'pointer' }}>✕</button>
        </div>

        {/* 分享我的位置 */}
        <button
          onClick={shareMyLocation}
          disabled={sharing}
          data-testid="care-sos-share-location"
          style={{
            width: '100%',
            background: '#07c160',
            color: '#FFF',
            border: 'none',
            borderRadius: 12,
            padding: '13px 0',
            fontSize: 15,
            fontWeight: 700,
            cursor: sharing ? 'default' : 'pointer',
            marginBottom: 18,
          }}
        >
          {sharing ? '生成中…' : '📍 分享我的位置（微信发给好友）'}
        </button>

        {/* 家庭住址 */}
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 10 }}>
          家庭住址 <span style={{ color: '#E53935', fontSize: 13 }}>* 必填</span>
        </div>
        <input
          style={inputStyle}
          placeholder="请填写家庭住址（必填，用于个人信息卡展示）"
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
            <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#F7F8FA', borderRadius: 10, padding: '12px 14px' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 600 }}>
                  {c.name || '未填写'}{c.relation ? `（${c.relation}）` : ''}
                </div>
                <div style={{ fontSize: 13, color: '#999' }}>{c.phone || '暂无电话'}</div>
              </div>
              <button onClick={() => remove(c.id)} style={{ background: 'transparent', border: 'none', color: '#E53935', fontSize: 14, cursor: 'pointer' }}>
                删除
              </button>
            </div>
          ))}
        </div>

        {/* 新增 */}
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 10 }}>新增联系人</div>
        <input style={inputStyle} placeholder="姓名" value={name} onChange={(e) => setName(e.target.value)} data-testid="care-sos-input-name" />
        <input style={inputStyle} placeholder="关系（如 儿子 / 女儿 / 家庭医生）" value={relation} onChange={(e) => setRelation(e.target.value)} data-testid="care-sos-input-relation" />
        <input
          style={inputStyle}
          placeholder="电话（必填）"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          inputMode="tel"
          data-testid="care-sos-input-phone"
        />
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

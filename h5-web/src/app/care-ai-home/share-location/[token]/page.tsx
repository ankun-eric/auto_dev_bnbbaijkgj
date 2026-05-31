'use client';

// [PRD-CARE-MODE-OPTIM-V4 2026-05-31] 关怀模式 → 分享位置 · 对方查看页
// 需求 8.3：对方在微信打开小程序后，看到：地图（坐标已转为可读地址）+ 精简个人信息卡
//  - 信息卡复用现有 care-info-card 风格（含头像、姓名、当前位置、紧急联系人、一键拨打）
//  - 免登录，用原生 fetch 读 /api/care-card/share-location/{token}

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

interface Contact {
  id: number;
  name: string;
  relation: string;
  phone: string;
}

interface CardInfo {
  name?: string | null;
  age?: number | null;
  gender?: string | null;
  home_address?: string | null;
  chronic_diseases?: string[];
  allergies?: string[];
  emergency_contacts?: Contact[];
}

interface ShareData {
  location: { latitude: number | null; longitude: number | null; address: string | null };
  card: CardInfo;
  shared_at?: string | null;
}

const EMPTY = '暂无 / 未填写';
function fmt(v: any): string {
  if (v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0)) return EMPTY;
  if (Array.isArray(v)) return v.join('、');
  return String(v);
}

export default function ShareLocationViewPage() {
  const params = useParams();
  const token = (params?.token as string) || '';
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const [data, setData] = useState<ShareData | null>(null);
  const [mapUrl, setMapUrl] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const resp = await fetch(`${basePath}/api/care-card/share-location/${token}`);
        if (!resp.ok) {
          setError('位置分享不存在或已失效');
          return;
        }
        const body = await resp.json();
        const d: ShareData = body?.data ?? null;
        setData(d);
        const lat = d?.location?.latitude;
        const lng = d?.location?.longitude;
        if (lat != null && lng != null) {
          try {
            const m = await fetch(`${basePath}/api/maps/static-map?lat=${lat}&lng=${lng}&zoom=16&width=640&height=360`);
            if (m.ok) {
              const mj = await m.json();
              if (mj?.url) setMapUrl(mj.url);
            }
          } catch {
            /* 地图加载失败不阻塞 */
          }
        }
      } catch {
        setError('网络异常，请稍后重试');
      } finally {
        setLoading(false);
      }
    };
    if (token) load();
  }, [token, basePath]);

  const card = data?.card ?? {};
  const contacts = card.emergency_contacts ?? [];
  const firstPhone = contacts.find((c) => c.phone)?.phone || '';
  const loc = data?.location;

  return (
    <div
      style={{ minHeight: '100vh', background: 'linear-gradient(160deg, #1976D2 0%, #43A047 100%)', padding: '20px 16px 120px', boxSizing: 'border-box' }}
      data-testid="care-share-location-page"
    >
      <div style={{ textAlign: 'center', color: '#FFF', marginBottom: 16 }}>
        <div style={{ fontSize: 22, fontWeight: 800 }}>宾尼小康 · 位置分享</div>
        <div style={{ fontSize: 13, opacity: 0.9, marginTop: 4 }}>对方分享了 TA 的当前位置，请尽快联系</div>
      </div>

      {loading ? (
        <div style={{ background: '#FFF', borderRadius: 18, padding: '40px 0', textAlign: 'center', color: '#999', maxWidth: 480, margin: '0 auto' }}>加载中…</div>
      ) : error ? (
        <div style={{ background: '#FFF', borderRadius: 18, padding: '40px 0', textAlign: 'center', color: '#E53935', maxWidth: 480, margin: '0 auto' }} data-testid="care-share-location-error">
          {error}
        </div>
      ) : (
        <div style={{ maxWidth: 480, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* 地图 + 地址 */}
          <div style={{ background: '#FFF', borderRadius: 18, overflow: 'hidden', boxShadow: '0 8px 28px rgba(0,0,0,0.18)' }} data-testid="care-share-location-map">
            {mapUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={mapUrl} alt="位置地图" style={{ width: '100%', display: 'block', height: 200, objectFit: 'cover' }} />
            ) : (
              <div style={{ width: '100%', height: 200, background: '#EAF1F7', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#90A4AE', fontSize: 14 }}>
                📍 地图加载中或暂不可用
              </div>
            )}
            <div style={{ padding: '14px 16px' }}>
              <div style={{ fontSize: 13, color: '#94A3B8', marginBottom: 4 }}>当前位置</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#0C4A6E' }}>{fmt(loc?.address)}</div>
              {loc?.latitude != null && loc?.longitude != null && (
                <a
                  href={`https://uri.amap.com/marker?position=${loc.longitude},${loc.latitude}`}
                  style={{ display: 'inline-block', marginTop: 8, fontSize: 13, color: '#1976D2', textDecoration: 'none' }}
                >
                  在地图中查看 ›
                </a>
              )}
            </div>
          </div>

          {/* 精简个人信息卡（复用 care-info-card 风格） */}
          <div style={{ background: '#FFF', borderRadius: 18, padding: 18, boxShadow: '0 8px 28px rgba(0,0,0,0.18)' }} data-testid="care-info-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
              <div
                style={{ width: 56, height: 56, borderRadius: '50%', background: 'linear-gradient(135deg,#42A5F5,#1976D2)', color: '#FFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, fontWeight: 800, flexShrink: 0 }}
                aria-hidden="true"
              >
                {(card.name || '康').slice(0, 1)}
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#0C4A6E' }}>{fmt(card.name) === EMPTY ? '未填写姓名' : card.name}</div>
                <div style={{ fontSize: 13, color: '#94A3B8', marginTop: 2 }}>
                  {card.age != null ? `${card.age} 岁` : ''}{card.gender ? ` · ${card.gender}` : ''}
                </div>
              </div>
            </div>

            <InfoRow label="家庭住址" value={fmt(card.home_address)} />
            <InfoRow label="既往病史" value={fmt(card.chronic_diseases)} />
            <InfoRow label="过敏史" value={fmt(card.allergies)} />

            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 14, color: '#94A3B8', marginBottom: 8 }}>紧急联系人</div>
              {contacts.length === 0 ? (
                <div style={{ fontSize: 14, color: '#C4CDD5' }}>{EMPTY}</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {contacts.map((c) => (
                    <div key={c.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#EAF3FF', borderRadius: 10, padding: '10px 12px' }}>
                      <span style={{ fontSize: 15, fontWeight: 600, color: '#1F2937' }}>
                        {c.name || '未填写'}{c.relation ? `（${c.relation}）` : ''}
                      </span>
                      {c.phone ? (
                        <a href={`tel:${c.phone}`} style={{ fontSize: 14, color: '#1976D2', textDecoration: 'none', fontWeight: 600 }}>📞 {c.phone}</a>
                      ) : (
                        <span style={{ fontSize: 14, color: '#C4CDD5' }}>暂无电话</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 底部一键拨打紧急联系人 */}
      {!loading && !error && firstPhone && (
        <div style={{ position: 'fixed', left: 0, right: 0, bottom: 0, padding: '14px 16px calc(14px + env(safe-area-inset-bottom))', background: 'rgba(255,255,255,0.95)' }}>
          <a
            href={`tel:${firstPhone}`}
            data-testid="care-share-location-call"
            style={{ display: 'block', textAlign: 'center', background: '#E53935', color: '#FFF', borderRadius: 14, padding: '16px 0', fontSize: 18, fontWeight: 700, textDecoration: 'none', maxWidth: 480, margin: '0 auto' }}
          >
            📞 一键拨打紧急联系人
          </a>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', padding: '9px 0', borderBottom: '1px dashed #E3EDF7', fontSize: 15 }}>
      <span style={{ width: 80, flexShrink: 0, color: '#94A3B8' }}>{label}</span>
      <span style={{ flex: 1, color: value === EMPTY ? '#C4CDD5' : '#1F2937', fontWeight: value === EMPTY ? 400 : 600, wordBreak: 'break-all' }}>{value}</span>
    </div>
  );
}

'use client';

// [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 个人信息卡二维码公开网页
// - 扫码后打开，无需登录
// - 展示卡片完整信息（身份 + 健康 + 联系人）
// - 含电话按钮，可直接拨打紧急联系人电话
// 用原生 fetch（不走会注入 token / 401 跳登录的 api 客户端）

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
  birthday?: string | null;
  gender?: string | null;
  chronic_diseases?: string[];
  allergies?: string[];
  home_address?: string | null;
  emergency_contacts?: Contact[];
}

const EMPTY = '暂无 / 未填写';

function fmt(v: any): string {
  if (v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0)) return EMPTY;
  if (Array.isArray(v)) return v.join('、');
  return String(v);
}

export default function CardViewPage() {
  const params = useParams();
  const token = (params?.token as string) || '';
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const [info, setInfo] = useState<CardInfo | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const resp = await fetch(`${basePath}/api/care-card/public/${token}`);
        if (!resp.ok) {
          setError('卡片不存在或已失效');
          return;
        }
        const body = await resp.json();
        setInfo(body?.data ?? {});
      } catch {
        setError('网络异常，请稍后重试');
      } finally {
        setLoading(false);
      }
    };
    if (token) load();
  }, [token, basePath]);

  const rows: { label: string; value: string }[] = [
    { label: '姓名', value: fmt(info?.name) },
    { label: '年龄', value: info?.age != null ? `${info.age} 岁` : EMPTY },
    { label: '出生日期', value: fmt(info?.birthday) },
    { label: '性别', value: fmt(info?.gender) },
    { label: '既往病史', value: fmt(info?.chronic_diseases) },
    { label: '过敏史', value: fmt(info?.allergies) },
    { label: '家庭住址', value: fmt(info?.home_address) },
  ];

  const contacts = info?.emergency_contacts ?? [];
  const firstPhone = contacts.find((c) => c.phone)?.phone || '';

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(160deg, #1976D2 0%, #43A047 100%)',
        padding: '24px 16px 120px',
        boxSizing: 'border-box',
      }}
      data-testid="care-card-view-page"
    >
      <div style={{ textAlign: 'center', color: '#FFF', marginBottom: 18 }}>
        <div style={{ fontSize: 22, fontWeight: 800 }}>宾尼小康 · 健康名片</div>
        <div style={{ fontSize: 13, opacity: 0.9, marginTop: 4 }}>本页用于紧急情况下快速了解持卡人信息</div>
      </div>

      <div
        style={{
          background: '#FFFFFF',
          borderRadius: 20,
          padding: 20,
          boxShadow: '0 8px 28px rgba(0,0,0,0.18)',
          maxWidth: 480,
          margin: '0 auto',
        }}
      >
        {loading ? (
          <div style={{ textAlign: 'center', color: '#999', padding: '40px 0' }}>加载中…</div>
        ) : error ? (
          <div style={{ textAlign: 'center', color: '#E53935', padding: '40px 0' }} data-testid="care-card-view-error">
            {error}
          </div>
        ) : (
          <>
            <div style={{ fontSize: 24, fontWeight: 800, color: '#0C4A6E', marginBottom: 14 }}>
              {fmt(info?.name) === EMPTY ? '未填写姓名' : info?.name}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {rows.map((r) => (
                <div key={r.label} style={{ display: 'flex', padding: '10px 0', borderBottom: '1px dashed #E3EDF7', fontSize: 15 }}>
                  <span style={{ width: 84, flexShrink: 0, color: '#94A3B8' }}>{r.label}</span>
                  <span style={{ flex: 1, color: r.value === EMPTY ? '#C4CDD5' : '#1F2937', fontWeight: r.value === EMPTY ? 400 : 600, wordBreak: 'break-all' }}>
                    {r.value}
                  </span>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 14, color: '#94A3B8', marginBottom: 8 }}>紧急联系人</div>
              {contacts.length === 0 ? (
                <div style={{ fontSize: 14, color: '#C4CDD5' }}>{EMPTY}</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {contacts.map((c) => (
                    <div
                      key={c.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        background: '#EAF3FF',
                        borderRadius: 10,
                        padding: '10px 12px',
                      }}
                    >
                      <span style={{ fontSize: 15, fontWeight: 600, color: '#1F2937' }}>
                        {c.name || '未填写'}{c.relation ? `（${c.relation}）` : ''}
                      </span>
                      {c.phone ? (
                        <a
                          href={`tel:${c.phone}`}
                          style={{ fontSize: 14, color: '#1976D2', textDecoration: 'none', fontWeight: 600 }}
                        >
                          📞 {c.phone}
                        </a>
                      ) : (
                        <span style={{ fontSize: 14, color: '#C4CDD5' }}>暂无电话</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* 底部一键拨打 */}
      {!loading && !error && firstPhone && (
        <div
          style={{
            position: 'fixed',
            left: 0,
            right: 0,
            bottom: 0,
            padding: '14px 16px calc(14px + env(safe-area-inset-bottom))',
            background: 'rgba(255,255,255,0.95)',
          }}
        >
          <a
            href={`tel:${firstPhone}`}
            data-testid="care-card-view-call"
            style={{
              display: 'block',
              textAlign: 'center',
              background: '#E53935',
              color: '#FFF',
              borderRadius: 14,
              padding: '16px 0',
              fontSize: 18,
              fontWeight: 700,
              textDecoration: 'none',
              maxWidth: 480,
              margin: '0 auto',
            }}
          >
            📞 拨打紧急联系人
          </a>
        </div>
      )}
    </div>
  );
}

'use client';

// [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式 → 个人信息卡
// - 进入即一张证件/名片式卡片图
// - 展示：姓名/年龄/出生日期/性别 + 既往病史/过敏史 + 家庭住址 + 紧急联系人姓名+电话
// - 数据自动从本人健康档案读取（/api/care-card/info）
// - 空字段仍显示，内容写「暂无 / 未填写」
// - 右上角二维码：扫码打开公开网页展示完整信息
// - 底部：分享图片 / 保存图片

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { QRCodeCanvas } from 'qrcode.react';
import { toPng } from 'html-to-image';
import api from '@/lib/api';

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
  qr_token?: string;
}

const EMPTY = '暂无 / 未填写';

function fmt(v: any): string {
  if (v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0)) return EMPTY;
  if (Array.isArray(v)) return v.join('、');
  return String(v);
}

export default function CareInfoCardPage() {
  const router = useRouter();
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const [info, setInfo] = useState<CardInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');
  const [qrUrl, setQrUrl] = useState('');
  const cardRef = useRef<HTMLDivElement | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2200);
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res: any = await api.get('/api/care-card/info');
        const data: CardInfo = res?.data ?? res ?? {};
        setInfo(data);
        if (data.qr_token && typeof window !== 'undefined') {
          const origin = window.location.origin;
          setQrUrl(`${origin}${basePath}/care-ai-home/card-view/${data.qr_token}`);
        }
      } catch {
        setInfo({});
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [basePath]);

  const captureImage = async (): Promise<string | null> => {
    if (!cardRef.current) return null;
    try {
      return await toPng(cardRef.current, { pixelRatio: 2, backgroundColor: '#ffffff', cacheBust: true });
    } catch {
      return null;
    }
  };

  const saveImage = async () => {
    const dataUrl = await captureImage();
    if (!dataUrl) {
      showToast('生成图片失败，请重试');
      return;
    }
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `个人信息卡_${info?.name || ''}.png`;
    a.click();
    showToast('已保存到相册/下载');
  };

  const shareImage = async () => {
    const dataUrl = await captureImage();
    if (!dataUrl) {
      showToast('生成图片失败，请重试');
      return;
    }
    try {
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], '个人信息卡.png', { type: 'image/png' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: '个人信息卡' });
        return;
      }
    } catch {
      /* 落到下载兜底 */
    }
    // 兜底：直接下载
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `个人信息卡_${info?.name || ''}.png`;
    a.click();
    showToast('当前环境不支持直接分享，已为你保存图片');
  };

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

  return (
    <div
      style={{ minHeight: '100vh', background: '#F5F7FA', paddingBottom: 110, color: '#212121' }}
      data-testid="care-info-card-page"
    >
      {/* 顶栏 */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          background: '#FFFFFF',
          borderBottom: '1px solid #EEF1F4',
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
        <div style={{ flex: 1, textAlign: 'center', fontSize: 18, fontWeight: 700, marginRight: 40 }}>
          个人信息卡
        </div>
      </div>

      {/* 名片式卡片 */}
      <div style={{ padding: 16 }}>
        <div
          ref={cardRef}
          data-testid="care-info-card"
          style={{
            background: 'linear-gradient(160deg, #FFFFFF 0%, #F3F8FF 100%)',
            borderRadius: 20,
            padding: 20,
            boxShadow: '0 6px 24px rgba(25,118,210,0.12)',
            border: '1px solid #E3EDF7',
            position: 'relative',
          }}
        >
          {/* 卡头：标题 + 二维码 */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 13, color: '#1976D2', fontWeight: 600, letterSpacing: 1 }}>宾尼小康 · 健康名片</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#0C4A6E', marginTop: 6 }}>
                {fmt(info?.name) === EMPTY ? '未填写姓名' : info?.name}
              </div>
            </div>
            <div
              data-testid="care-info-card-qr"
              style={{ background: '#FFFFFF', borderRadius: 10, padding: 6, border: '1px solid #E3EDF7' }}
            >
              {qrUrl ? (
                <QRCodeCanvas value={qrUrl} size={84} level="M" includeMargin={false} />
              ) : (
                <div style={{ width: 84, height: 84, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: '#999' }}>
                  二维码加载中
                </div>
              )}
            </div>
          </div>

          {/* 基本信息行 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {rows.map((r) => (
              <div
                key={r.label}
                style={{
                  display: 'flex',
                  padding: '10px 0',
                  borderBottom: '1px dashed #E3EDF7',
                  fontSize: 15,
                }}
              >
                <span style={{ width: 84, flexShrink: 0, color: '#94A3B8' }}>{r.label}</span>
                <span style={{ flex: 1, color: r.value === EMPTY ? '#C4CDD5' : '#1F2937', fontWeight: r.value === EMPTY ? 400 : 600, wordBreak: 'break-all' }}>
                  {loading ? '加载中…' : r.value}
                </span>
              </div>
            ))}
          </div>

          {/* 紧急联系人 */}
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
                    <span style={{ fontSize: 14, color: '#1976D2' }}>{c.phone || '暂无电话'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ marginTop: 16, fontSize: 11, color: '#B0BEC5', textAlign: 'center' }}>
            扫描右上角二维码可查看完整信息并一键拨打紧急联系人
          </div>
        </div>
      </div>

      {/* 底部按钮 */}
      <div
        style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          maxWidth: 750,
          margin: '0 auto',
          padding: '12px 16px calc(12px + env(safe-area-inset-bottom))',
          background: '#FFFFFF',
          borderTop: '1px solid #EEF1F4',
          display: 'flex',
          gap: 12,
        }}
      >
        <button
          data-testid="care-info-card-share"
          onClick={shareImage}
          style={{
            flex: 1,
            background: '#1976D2',
            color: '#FFF',
            border: 'none',
            borderRadius: 14,
            padding: '14px 0',
            fontSize: 16,
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          分享图片
        </button>
        <button
          data-testid="care-info-card-save"
          onClick={saveImage}
          style={{
            flex: 1,
            background: '#FFFFFF',
            color: '#1976D2',
            border: '1px solid #1976D2',
            borderRadius: 14,
            padding: '14px 0',
            fontSize: 16,
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          保存图片
        </button>
      </div>

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

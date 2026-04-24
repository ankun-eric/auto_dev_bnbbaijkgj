'use client';

// [2026-04-24] 移动端 - 核销页 PRD §4.4（核心页）
// C3 设计：扫码为主 + 输码兜底
// 使用已安装的 html5-qrcode 库

import React, { Suspense, useEffect, useRef, useState } from 'react';
import { Tabs, Input, Button, Toast, Dialog, Empty } from 'antd-mobile';
import { useRouter, useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import { getCurrentStoreId } from '../mobile-lib';

type TabKey = 'scan' | 'input';

export default function VerifyMobilePageWrapper() {
  return (
    <Suspense fallback={<div style={{ padding: 24, textAlign: 'center', color: '#999' }}>加载中...</div>}>
      <VerifyMobilePage />
    </Suspense>
  );
}

function VerifyMobilePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const prefillOrderNo = searchParams?.get('order_no') || '';

  const [tab, setTab] = useState<TabKey>(prefillOrderNo ? 'input' : 'scan');
  const [code, setCode] = useState(prefillOrderNo);
  const [loading, setLoading] = useState(false);
  const [scanError, setScanError] = useState<string>('');
  const [isHttps, setIsHttps] = useState(true);
  const [scanning, setScanning] = useState(false);
  const scannerRef = useRef<any>(null);
  const scanContainerId = 'merchant-m-verify-scanner';

  // HTTPS 检测
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const ok = window.location.protocol === 'https:' || window.location.hostname === 'localhost' || window.location.hostname.startsWith('127.');
      setIsHttps(ok);
    }
  }, []);

  // 启动/停止扫码
  const startScanner = async () => {
    if (!isHttps) {
      setScanError('当前连接非 HTTPS，无法使用扫码功能，请联系管理员或切换到输码模式');
      return;
    }
    try {
      setScanError('');
      const { Html5Qrcode } = await import('html5-qrcode');
      if (scannerRef.current) {
        try { await scannerRef.current.stop(); } catch {}
        try { scannerRef.current.clear(); } catch {}
        scannerRef.current = null;
      }
      const scanner = new Html5Qrcode(scanContainerId);
      scannerRef.current = scanner;
      setScanning(true);
      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        async (decodedText: string) => {
          // 扫到即暂停
          try { await scanner.pause(true); } catch {}
          await handleScanned(decodedText);
        },
        () => { /* ignore scanning errors */ }
      );
    } catch (e: any) {
      setScanning(false);
      const msg = e?.message || String(e);
      if (/permission/i.test(msg) || /NotAllowed/i.test(msg)) {
        setScanError('摄像头权限被拒绝，请在系统设置中允许访问摄像头，或切换到输码模式');
      } else if (/NotFound/i.test(msg)) {
        setScanError('未找到摄像头，请切换到输码模式');
      } else {
        setScanError('扫码启动失败：' + msg);
      }
    }
  };

  const stopScanner = async () => {
    if (scannerRef.current) {
      try { await scannerRef.current.stop(); } catch {}
      try { scannerRef.current.clear(); } catch {}
      scannerRef.current = null;
    }
    setScanning(false);
  };

  useEffect(() => {
    if (tab === 'scan' && isHttps) {
      startScanner();
    } else {
      stopScanner();
    }
    return () => { stopScanner(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, isHttps]);

  const handleScanned = async (text: string) => {
    try {
      // 会员码扫到 → 先验证
      if (text.startsWith('MEMBER:') || /^\d{10,}$/.test(text)) {
        const res: any = await api.post('/api/verify/member-qrcode', { qr_code: text });
        Toast.show({ icon: 'success', content: '识别成功：' + (res?.nickname || '会员') });
        // 成功后停止扫描并显示结果；这里做简化跳转：切换输码面板等待后续流程
        await stopScanner();
        setTab('input');
        Dialog.alert({ title: '会员已识别', content: `姓名：${res?.nickname || '-'}\n手机号：${res?.phone_mask || '-'}\n请在收银页选择对应订单进行核销。` });
        return;
      }
      // 订单码 → redeem
      const sid = getCurrentStoreId();
      const res: any = await api.post('/api/verify/redeem', {
        code: text,
        store_id: sid || undefined,
      });
      Toast.show({ icon: 'success', content: '核销成功' });
      Dialog.alert({
        title: '核销成功',
        content: `订单：${res?.order_no || text}`,
        onConfirm: async () => {
          setCode('');
          await stopScanner();
          setTab('scan');
          startScanner();
        },
      });
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '核销失败';
      Dialog.alert({
        title: '核销失败',
        content: msg,
        onConfirm: async () => {
          await stopScanner();
          startScanner();
        },
      });
    }
  };

  const submitCode = async () => {
    if (!code.trim()) {
      Toast.show({ content: '请输入核销码' });
      return;
    }
    setLoading(true);
    try {
      const sid = getCurrentStoreId();
      const res: any = await api.post('/api/verify/redeem', {
        code: code.trim(),
        store_id: sid || undefined,
      });
      Toast.show({ icon: 'success', content: '核销成功' });
      Dialog.alert({ title: '核销成功', content: `订单：${res?.order_no || code}` });
      setCode('');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '核销失败';
      Dialog.alert({ title: '核销失败', content: msg });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#000' }}>
      <div style={{ background: '#fff', position: 'sticky', top: 0, zIndex: 10 }}>
        <Tabs activeKey={tab} onChange={(k) => setTab(k as TabKey)}>
          <Tabs.Tab title="扫一扫" key="scan" />
          <Tabs.Tab title="手动输码" key="input" />
        </Tabs>
      </div>

      {tab === 'scan' && (
        <div style={{ position: 'relative', minHeight: 'calc(100vh - 120px)' }}>
          {!isHttps ? (
            <div style={{ padding: 20, color: '#fff' }}>
              <Empty
                description={
                  <div style={{ color: '#fff' }}>
                    <div>当前连接非 HTTPS，无法使用扫码功能</div>
                    <div style={{ marginTop: 10 }}>
                      <Button color="primary" size="small" onClick={() => setTab('input')}>
                        切换到输码模式
                      </Button>
                    </div>
                  </div>
                }
              />
            </div>
          ) : (
            <>
              <div
                id={scanContainerId}
                style={{
                  width: '100%',
                  height: 'calc(100vh - 160px)',
                  background: '#000',
                }}
              />
              {scanError && (
                <div
                  style={{
                    position: 'absolute',
                    top: 20,
                    left: 20,
                    right: 20,
                    background: 'rgba(255,77,79,0.9)',
                    color: '#fff',
                    padding: 12,
                    borderRadius: 8,
                    textAlign: 'center',
                    fontSize: 13,
                  }}
                >
                  {scanError}
                  <div style={{ marginTop: 8 }}>
                    <Button size="mini" color="primary" onClick={() => setTab('input')}>
                      切换到输码模式
                    </Button>
                  </div>
                </div>
              )}
              <div
                style={{
                  position: 'absolute',
                  bottom: 16,
                  left: 0,
                  right: 0,
                  textAlign: 'center',
                  color: '#fff',
                  fontSize: 13,
                  textShadow: '0 1px 4px rgba(0,0,0,0.6)',
                }}
              >
                将二维码对准取景框{scanning ? '（扫描中…）' : ''}
              </div>
            </>
          )}
        </div>
      )}

      {tab === 'input' && (
        <div style={{ padding: 20, background: '#f7f8fa', minHeight: 'calc(100vh - 120px)' }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 20 }}>
            <div style={{ fontSize: 14, color: '#666', marginBottom: 12 }}>请输入订单号或核销码</div>
            <Input
              placeholder="请输入核销码/订单号"
              value={code}
              onChange={setCode}
              clearable
              style={
                {
                  '--font-size': '22px',
                  fontWeight: 600,
                  letterSpacing: 2,
                } as any
              }
            />
            <Button
              block
              color="primary"
              size="large"
              style={{ marginTop: 24, height: 48, fontSize: 16 }}
              loading={loading}
              onClick={submitCode}
            >
              确认核销
            </Button>
            <div style={{ color: '#999', fontSize: 12, marginTop: 16, textAlign: 'center' }}>
              提示：扫码需 HTTPS 环境且授予摄像头权限，失败时请使用此处输码兜底。
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

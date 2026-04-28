'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { NavBar, Toast, Button, DotLoading, Result } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { getCurrentStoreId } from '../mobile-lib';

type BindStatus = 'loading' | 'unbound' | 'bound';

export default function WechatBinddingMobilePage() {
  const router = useRouter();
  const [status, setStatus] = useState<BindStatus>('loading');
  const [qrcodeUrl, setQrcodeUrl] = useState<string>('');
  const [qrcodeLoading, setQrcodeLoading] = useState(false);
  const [unbinding, setUnbinding] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkStatus = useCallback(async () => {
    try {
      const storeId = getCurrentStoreId();
      const params: any = {};
      if (storeId) params.store_id = storeId;
      const res: any = await api.get('/api/merchant/bindding/wechat/status', { params });
      if (res?.is_bound) {
        setStatus('bound');
        stopPolling();
      } else {
        setStatus('unbound');
      }
    } catch {
      setStatus('unbound');
    }
  }, []);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPolling = () => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const storeId = getCurrentStoreId();
        const params: any = {};
        if (storeId) params.store_id = storeId;
        const res: any = await api.get('/api/merchant/bindding/wechat/status', { params });
        if (res?.is_bound) {
          setStatus('bound');
          stopPolling();
          Toast.show({ icon: 'success', content: '绑定成功' });
        }
      } catch {}
    }, 3000);
  };

  const fetchQrcode = async () => {
    setQrcodeLoading(true);
    try {
      const storeId = getCurrentStoreId();
      const params: any = {};
      if (storeId) params.store_id = storeId;
      const res: any = await api.post('/api/merchant/bindding/wechat/qrcode', null, { params });
      setQrcodeUrl(res?.qrcode_url || res?.url || '');
      startPolling();
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '获取二维码失败' });
    } finally {
      setQrcodeLoading(false);
    }
  };

  const handleUnbind = async () => {
    setUnbinding(true);
    try {
      const storeId = getCurrentStoreId();
      const params: any = {};
      if (storeId) params.store_id = storeId;
      await api.delete('/api/merchant/bindding/wechat', { params });
      Toast.show({ icon: 'success', content: '已解绑' });
      setStatus('unbound');
      setQrcodeUrl('');
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '解绑失败' });
    } finally {
      setUnbinding(false);
    }
  };

  useEffect(() => {
    checkStatus();
    return () => stopPolling();
  }, [checkStatus]);

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <NavBar onBack={() => router.back()}>公众号通知绑定</NavBar>

      <div style={{ padding: 16 }}>
        {status === 'loading' && (
          <div style={{ textAlign: 'center', padding: 64 }}>
            <DotLoading color="primary" />
          </div>
        )}

        {status === 'bound' && (
          <div style={{ background: '#fff', borderRadius: 12, padding: 24, textAlign: 'center' }}>
            <Result
              status="success"
              title="已绑定公众号"
              description="您将通过微信公众号接收订单通知"
            />
            <Button
              color="danger"
              fill="outline"
              loading={unbinding}
              onClick={handleUnbind}
              style={{ marginTop: 16 }}
            >
              解除绑定
            </Button>
          </div>
        )}

        {status === 'unbound' && (
          <div style={{ background: '#fff', borderRadius: 12, padding: 24, textAlign: 'center' }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>绑定微信公众号</div>
            <div style={{ fontSize: 13, color: '#999', marginBottom: 20 }}>
              扫描下方二维码关注公众号，即可接收订单通知推送
            </div>

            {qrcodeUrl ? (
              <>
                <div style={{
                  width: 200, height: 200, margin: '0 auto 16px',
                  border: '1px solid #f0f0f0', borderRadius: 8,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  overflow: 'hidden',
                }}>
                  <img src={qrcodeUrl} alt="公众号二维码" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                </div>
                <div style={{ fontSize: 12, color: '#999', marginBottom: 12 }}>请使用微信扫描二维码</div>
                <Button size="small" fill="outline" onClick={fetchQrcode}>刷新二维码</Button>
              </>
            ) : (
              <Button color="primary" loading={qrcodeLoading} onClick={fetchQrcode}>
                获取绑定二维码
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Card, Typography, Button, Spin, Result, Space, message, QRCode } from 'antd';
import { WechatOutlined, CheckCircleOutlined, DisconnectOutlined } from '@ant-design/icons';
import api from '@/lib/api';
import { getCurrentStoreId } from '../lib';

const { Title, Text } = Typography;

type BindStatus = 'loading' | 'unbound' | 'bound';

export default function WechatBinddingPCPage() {
  const [status, setStatus] = useState<BindStatus>('loading');
  const [qrcodeUrl, setQrcodeUrl] = useState<string>('');
  const [qrcodeLoading, setQrcodeLoading] = useState(false);
  const [unbinding, setUnbinding] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

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
          message.success('公众号绑定成功');
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
      message.error(e?.response?.data?.detail || '获取二维码失败');
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
      message.success('已解除绑定');
      setStatus('unbound');
      setQrcodeUrl('');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '解绑失败');
    } finally {
      setUnbinding(false);
    }
  };

  useEffect(() => {
    checkStatus();
    return () => stopPolling();
  }, [checkStatus]);

  return (
    <div>
      <Title level={4}><WechatOutlined style={{ marginRight: 8, color: '#52c41a' }} />公众号通知绑定</Title>

      {status === 'loading' && (
        <div style={{ textAlign: 'center', padding: 64 }}><Spin /></div>
      )}

      {status === 'bound' && (
        <Card style={{ maxWidth: 480, margin: '24px auto', textAlign: 'center' }}>
          <Result
            status="success"
            icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            title="已绑定微信公众号"
            subTitle="您将通过微信公众号接收订单通知推送"
            extra={
              <Button
                danger
                icon={<DisconnectOutlined />}
                loading={unbinding}
                onClick={handleUnbind}
              >
                解除绑定
              </Button>
            }
          />
        </Card>
      )}

      {status === 'unbound' && (
        <Card style={{ maxWidth: 480, margin: '24px auto', textAlign: 'center' }}>
          <Title level={5}>绑定微信公众号</Title>
          <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
            扫描二维码关注公众号，即可接收订单通知推送
          </Text>

          {qrcodeUrl ? (
            <Space direction="vertical" size={16} align="center">
              <div style={{
                padding: 16,
                border: '1px solid #f0f0f0',
                borderRadius: 8,
                display: 'inline-block',
              }}>
                <img
                  src={qrcodeUrl}
                  alt="公众号二维码"
                  style={{ width: 200, height: 200, objectFit: 'contain' }}
                />
              </div>
              <Text type="secondary">请使用微信扫描二维码</Text>
              <Button onClick={fetchQrcode}>刷新二维码</Button>
            </Space>
          ) : (
            <Button
              type="primary"
              icon={<WechatOutlined />}
              loading={qrcodeLoading}
              onClick={fetchQrcode}
              size="large"
            >
              获取绑定二维码
            </Button>
          )}
        </Card>
      )}
    </div>
  );
}

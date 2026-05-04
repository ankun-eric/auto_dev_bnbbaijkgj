'use client';

/**
 * [2026-05-04 H5 支付链路 Bug 修复]
 * 支付宝 H5 沙盒收银台模拟页。
 *
 * 链路：
 *   后端 /api/orders/unified/{id}/pay 返回的 pay_url 为
 *     `${PROJECT_BASE_URL}/sandbox-pay?order_no=...&channel=alipay_h5`
 *   PROJECT_BASE_URL 与 H5 的 basePath 重合，浏览器跳转后命中本路由。
 *
 * 行为：
 *   - 顶部展示订单号、通道
 *   - 「确认支付」按钮 → 调 GET /api/orders/unified/sandbox-confirm，
 *     成功后取响应中的 order id 跳详情；若无 id 字段则回退到订单列表。
 *   - 「取消」按钮 → 回退或跳订单列表。
 *
 * 注意：sandbox-confirm 是后端的免认证回跳接口，前端不强制依赖登录态。
 */

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button, Card, Toast, NavBar, SpinLoading } from 'antd-mobile';
import api from '@/lib/api';

export default function SandboxPayWrapper() {
  return (
    <Suspense fallback={<div />}>
      <SandboxPayPage />
    </Suspense>
  );
}

function SandboxPayPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderNo = searchParams.get('order_no') || '';
  const channel = searchParams.get('channel') || '';

  const [confirming, setConfirming] = useState(false);

  const onConfirm = async () => {
    if (!orderNo) {
      Toast.show({ content: '订单号缺失' });
      return;
    }
    setConfirming(true);
    try {
      const res: any = await api.get('/api/orders/unified/sandbox-confirm', {
        params: { order_no: orderNo, channel },
      });
      const data = res?.data || res;
      const orderId = data?.id || data?.order_id || data?.data?.id;
      Toast.show({ content: '支付成功' });
      if (orderId) {
        router.replace(`/unified-order/${orderId}`);
      } else {
        router.replace('/unified-orders');
      }
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '支付确认失败' });
    } finally {
      setConfirming(false);
    }
  };

  const onCancel = () => {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.replace('/unified-orders');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={onCancel} style={{ background: '#fff' }}>
        支付宝沙盒收银台
      </NavBar>

      <div className="px-4 pt-6">
        <Card style={{ borderRadius: 12, marginBottom: 16 }}>
          <div style={{ textAlign: 'center', padding: '12px 0 16px' }}>
            <div style={{ fontSize: 14, color: '#999', marginBottom: 8 }}>当前为沙盒模拟环境</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#1677ff' }}>支付宝</div>
            <div style={{ fontSize: 12, color: '#bbb', marginTop: 4 }}>Alipay H5 Sandbox</div>
          </div>

          <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 14 }}>
              <span style={{ color: '#666' }}>订单号</span>
              <span style={{ color: '#333', fontFamily: 'monospace' }}>{orderNo || '-'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 14 }}>
              <span style={{ color: '#666' }}>支付通道</span>
              <span style={{ color: '#333' }}>{channel || '-'}</span>
            </div>
          </div>
        </Card>

        <div style={{ marginTop: 24 }}>
          <Button
            block
            loading={confirming}
            disabled={confirming || !orderNo}
            onClick={onConfirm}
            style={{
              borderRadius: 24,
              height: 48,
              background: '#52c41a',
              color: '#fff',
              border: 'none',
              fontSize: 16,
              fontWeight: 600,
            }}
          >
            {confirming ? <SpinLoading color="white" /> : '确认支付'}
          </Button>

          <Button
            block
            disabled={confirming}
            onClick={onCancel}
            style={{
              marginTop: 12,
              borderRadius: 24,
              height: 44,
              background: '#f0f0f0',
              color: '#666',
              border: 'none',
            }}
          >
            取消
          </Button>
        </div>

        <div style={{ marginTop: 20, fontSize: 12, color: '#bbb', textAlign: 'center', lineHeight: 1.6 }}>
          点击「确认支付」即模拟完成支付宝沙盒收银台支付，
          <br />
          实际生产环境将由支付宝官方页面承载。
        </div>
      </div>
    </div>
  );
}

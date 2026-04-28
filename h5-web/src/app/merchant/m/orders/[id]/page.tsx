'use client';

// [2026-04-24] 移动端 - 订单详情 PRD §4.3
// 字段：商品信息/金额/用户/下单时间/核销时间/门店/核销人 + 底部操作条

import React, { useEffect, useState } from 'react';
import { NavBar, Toast, Button, List, Dialog } from 'antd-mobile';
import { useRouter, useParams } from 'next/navigation';
import api from '@/lib/api';
import { statusMap } from '../../mobile-lib';

export default function OrderDetailMobilePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const orderId = params?.id;
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!orderId) return;
    setLoading(true);
    try {
      // 接口：列表里把单条带出来也可以；这里直接调用列表接口按订单号/ID 筛选
      const res: any = await api.get('/api/merchant/v1/orders', { params: { page: 1, page_size: 1, keyword: orderId } });
      const found =
        (res.items || []).find((x: any) => String(x.order_id || x.id) === String(orderId)) || (res.items || [])[0] || null;
      setDetail(found);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId]);

  const doVerify = () => {
    router.push(`/merchant/m/verify?order_no=${encodeURIComponent(detail?.order_no || '')}`);
  };

  const doRefund = () => {
    Dialog.alert({ title: '提示', content: '订单退款请使用电脑 PC 商家端操作。' });
  };

  const st = detail ? statusMap[detail.status] || { text: detail.status, color: '#999' } : null;

  return (
    <div style={{ minHeight: '100vh', paddingBottom: 72 }}>
      <NavBar onBack={() => router.back()}>订单详情</NavBar>

      {loading || !detail ? (
        <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>{loading ? '加载中...' : '未找到订单'}</div>
      ) : (
        <>
          <div style={{ background: '#fff', padding: '16px', margin: '12px', borderRadius: 10 }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 10 }}>{detail.product_name || '—'}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <span
                style={{
                  display: 'inline-block',
                  fontSize: 11,
                  padding: '2px 8px',
                  borderRadius: 10,
                  background: `${st?.color}22`,
                  color: st?.color,
                }}
              >
                {st?.text}
              </span>
              <span style={{ color: '#fa541c', fontSize: 20, fontWeight: 700 }}>¥{detail.amount || 0}</span>
            </div>
            <div style={{ fontSize: 12, color: '#999' }}>订单号：{detail.order_no}</div>
          </div>

          <List header="订单信息" style={{ margin: '12px', borderRadius: 10, overflow: 'hidden' }}>
            <List.Item extra={detail.user_display || '—'}>用户</List.Item>
            <List.Item extra={detail.store_name || '—'}>门店</List.Item>
            <List.Item extra={detail.created_at ? new Date(detail.created_at).toLocaleString('zh-CN') : '—'}>下单时间</List.Item>
            {detail.appointment_time && (
              <List.Item extra={new Date(detail.appointment_time).toLocaleString('zh-CN')}>预约时间</List.Item>
            )}
            {detail.verified_at && (
              <List.Item extra={new Date(detail.verified_at).toLocaleString('zh-CN')}>核销时间</List.Item>
            )}
            {detail.verifier_name && <List.Item extra={detail.verifier_name}>核销人</List.Item>}
            <List.Item extra={detail.attachment_count ?? 0}>附件数</List.Item>
          </List>
        </>
      )}

      {/* 底部操作条 */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          background: '#fff',
          padding: 12,
          borderTop: '1px solid #eee',
          display: 'flex',
          gap: 8,
          maxWidth: 768,
          margin: '0 auto',
          zIndex: 50,
        }}
      >
        {detail?.status === 'paid' && (
          <Button block color="primary" onClick={doVerify}>
            去核销
          </Button>
        )}
        <Button block fill="outline" onClick={doRefund}>
          申请退款
        </Button>
      </div>
    </div>
  );
}

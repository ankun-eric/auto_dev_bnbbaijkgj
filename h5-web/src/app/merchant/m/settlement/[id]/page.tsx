'use client';

// [2026-04-24] 移动端 - 对账详情 PRD §4.6

import React, { useEffect, useState } from 'react';
import { NavBar, List, Button, Toast, Dialog, TextArea } from 'antd-mobile';
import { useRouter, useParams } from 'next/navigation';
import api from '@/lib/api';

export default function SettlementDetailMobilePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sid = params?.id;
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!sid) return;
    setLoading(true);
    try {
      const res: any = await api.get(`/api/merchant/v1/settlements/${sid}`);
      setDetail(res);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sid]);

  const confirmSettle = async () => {
    const ok = await Dialog.confirm({ title: '确认对账', content: '确认后将标记为已确认，无法撤回' });
    if (!ok) return;
    try {
      await api.post(`/api/merchant/v1/settlements/${sid}/confirm`, {});
      Toast.show({ icon: 'success', content: '已确认' });
      load();
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '操作失败' });
    }
  };

  const dispute = async () => {
    let reason = '';
    const ok = await Dialog.confirm({
      title: '发起争议',
      content: (
        <div>
          <TextArea placeholder="请填写争议原因" rows={3} onChange={(v) => { reason = v; }} />
        </div>
      ) as any,
    });
    if (!ok) return;
    if (!reason.trim()) {
      Toast.show({ content: '请填写争议原因' });
      return;
    }
    try {
      await api.post(`/api/merchant/v1/settlements/${sid}/dispute`, { reason });
      Toast.show({ icon: 'success', content: '已提交争议' });
      load();
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '操作失败' });
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa', paddingBottom: 80 }}>
      <NavBar onBack={() => router.back()}>对账详情</NavBar>

      {loading || !detail ? (
        <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>{loading ? '加载中...' : '未找到对账单'}</div>
      ) : (
        <>
          <List header="基本信息" style={{ margin: 12, borderRadius: 10, overflow: 'hidden' }}>
            <List.Item extra={detail.period || detail.cycle || '-'}>对账周期</List.Item>
            <List.Item extra={`¥${Number(detail.amount || detail.total_amount || 0).toFixed(2)}`}>应结金额</List.Item>
            <List.Item extra={detail.status || '-'}>状态</List.Item>
            <List.Item extra={detail.order_count ?? '-'}>订单数量</List.Item>
          </List>

          <div style={{ margin: 12, background: '#fff', borderRadius: 10, padding: 16, fontSize: 12, color: '#666' }}>
            订单明细请在 PC 端查看。
          </div>
        </>
      )}

      {detail?.status === 'pending' && (
        <div
          style={{
            position: 'fixed',
            left: 0,
            right: 0,
            bottom: 0,
            background: '#fff',
            padding: 12,
            display: 'flex',
            gap: 8,
            borderTop: '1px solid #eee',
            maxWidth: 768,
            margin: '0 auto',
          }}
        >
          <Button block color="primary" onClick={confirmSettle}>
            确认对账
          </Button>
          <Button block fill="outline" color="danger" onClick={dispute}>
            发起争议
          </Button>
        </div>
      )}
    </div>
  );
}

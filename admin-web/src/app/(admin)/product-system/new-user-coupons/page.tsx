'use client';

import React, { useEffect, useState } from 'react';
import { Card, Button, Table, Tag, message, Typography, Modal, Transfer, Space } from 'antd';
import { get, put } from '@/lib/api';

const { Title, Paragraph } = Typography;

export default function NewUserCouponsPage() {
  const [loading, setLoading] = useState(false);
  const [couponIds, setCouponIds] = useState<number[]>([]);
  const [allCoupons, setAllCoupons] = useState<any[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [tempKeys, setTempKeys] = useState<string[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const [rule, list] = await Promise.all([
        get('/api/admin/new-user-coupons'),
        get('/api/admin/coupons', { page: 1, page_size: 200 }),
      ]);
      setCouponIds((rule as any)?.coupon_ids || []);
      setAllCoupons((list as any)?.items || []);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const save = async (ids: number[]) => {
    try {
      await put('/api/admin/new-user-coupons', { coupon_ids: ids });
      message.success('保存成功');
      setCouponIds(ids);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存失败');
    }
  };

  const inPool = allCoupons.filter(c => couponIds.includes(c.id));

  const openPicker = () => {
    setTempKeys(couponIds.map(String));
    setPickerOpen(true);
  };
  const confirmPicker = () => {
    save(tempKeys.map(Number));
    setPickerOpen(false);
  };

  return (
    <div>
      <Title level={4}>新人券池</Title>
      <Paragraph type="secondary">新用户注册成功后，将自动获得本池内所有券各 1 张（每人每券限领 1 次）</Paragraph>
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Button type="primary" onClick={openPicker}>选择券</Button>
          <span>当前池内 <b>{couponIds.length}</b> 张</span>
        </Space>
      </Card>
      <Table loading={loading} rowKey="id" dataSource={inPool}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 70 },
          { title: '名称', dataIndex: 'name' },
          { title: '类型', dataIndex: 'type', width: 110 },
          { title: '有效期', dataIndex: 'validity_days', width: 110, render: (v: number) => `${v || 30} 天` },
          { title: '状态', dataIndex: 'status', width: 90,
            render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '启用' : '停用'}</Tag> },
          { title: '操作', key: 'a', width: 100,
            render: (_: any, r: any) => (
              <Button type="link" danger onClick={() => save(couponIds.filter(id => id !== r.id))}>移出</Button>
            ) },
        ]} />

      <Modal title="选择新人券" open={pickerOpen} onOk={confirmPicker}
        onCancel={() => setPickerOpen(false)} width={760}>
        <Transfer
          dataSource={allCoupons.map(c => ({ key: String(c.id), title: `${c.name} (${c.validity_days || 30}天)` }))}
          targetKeys={tempKeys}
          onChange={(keys) => setTempKeys(keys as string[])}
          render={item => item.title}
          listStyle={{ width: 320, height: 400 }}
          titles={['全部券', '已选']}
        />
      </Modal>
    </div>
  );
}

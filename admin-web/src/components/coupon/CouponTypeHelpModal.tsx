'use client';

import React, { useEffect, useState } from 'react';
import { Modal, Card, Row, Col, Tag, Spin, Empty } from 'antd';
import { get } from '@/lib/api';

export interface CouponTypeDescription {
  key: string;
  name: string;
  icon: string;
  core_rule: string;
  key_fields: string;
  scenarios: string;
  example: string;
  note?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

/**
 * F1：优惠券「类型说明」弹窗
 * - 4 张并排卡片（大屏）/ 单列纵向（窄屏，由 Row gutter responsive 自适应）
 * - 数据从 GET /api/admin/coupons/type-descriptions 拉取，便于后续运营在后端文案中心动态维护
 */
export default function CouponTypeHelpModal({ open, onClose }: Props) {
  const [items, setItems] = useState<CouponTypeDescription[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    get('/api/admin/coupons/type-descriptions')
      .then((res: any) => setItems(res?.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [open]);

  const colorMap: Record<string, string> = {
    full_reduction: 'volcano',
    discount: 'blue',
    voucher: 'green',
    free_trial: 'purple',
  };

  return (
    <Modal
      title="优惠券类型说明"
      open={open}
      onCancel={onClose}
      onOk={onClose}
      okText="知道了"
      cancelButtonProps={{ style: { display: 'none' } }}
      width={720}
      destroyOnClose
    >
      <Spin spinning={loading}>
        {items.length === 0 && !loading ? (
          <Empty description="暂无类型说明" />
        ) : (
          <Row gutter={[12, 12]}>
            {items.map(it => (
              <Col xs={24} sm={12} md={12} key={it.key}>
                <Card
                  size="small"
                  title={
                    <span>
                      <span style={{ marginRight: 6 }}>{it.icon}</span>
                      <Tag color={colorMap[it.key]}>{it.name}</Tag>
                      <span style={{ color: '#999', fontSize: 12, marginLeft: 4 }}>{it.key}</span>
                    </span>
                  }
                  bodyStyle={{ padding: 12, fontSize: 13, lineHeight: 1.7 }}
                >
                  <div><b>核心规则：</b>{it.core_rule}</div>
                  <div><b>关键字段：</b>{it.key_fields}</div>
                  <div><b>典型场景：</b>{it.scenarios}</div>
                  <div><b>配置示例：</b>{it.example}</div>
                  {it.note && (
                    <div style={{ color: '#fa8c16', marginTop: 4 }}>
                      <b>注意：</b>{it.note}
                    </div>
                  )}
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </Modal>
  );
}

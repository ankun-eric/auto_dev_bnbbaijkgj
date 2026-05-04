'use client';

import React, { useEffect, useState } from 'react';
import { Modal, Form, DatePicker, Select, Switch, message } from 'antd';
import dayjs from 'dayjs';
import api from '@/lib/api';

interface RescheduleModalProps {
  open: boolean;
  storeId: number | null;
  orderItemId: number | null;
  currentTime?: string | null;
  currentProductId?: number | null;
  currentStaffId?: number | null;
  onClose: () => void;
  onSuccess?: () => void;
}

interface ProductOption {
  id: number;
  name: string;
}

export default function RescheduleModal({
  open,
  storeId,
  orderItemId,
  currentTime,
  currentProductId,
  currentStaffId,
  onClose,
  onSuccess,
}: RescheduleModalProps) {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [products, setProducts] = useState<ProductOption[]>([]);

  useEffect(() => {
    if (!open || !storeId) return;
    form.resetFields();
    form.setFieldsValue({
      new_appointment_time: currentTime ? dayjs(currentTime) : null,
      new_product_id: currentProductId ?? undefined,
      new_staff_id: currentStaffId ?? undefined,
      notify_customer: true,
    });
    // 拉取门店商品列表（复用商家订单接口里的商品；如无独立接口则简单从当日 items 推断）
    api
      .get('/api/merchant/products', { params: { store_id: storeId, page_size: 200 } })
      .then((res: any) => {
        const list = res?.items || res?.products || [];
        setProducts(
          list.map((p: any) => ({ id: p.id ?? p.product_id, name: p.name ?? p.product_name }))
        );
      })
      .catch(() => setProducts([]));
  }, [open, storeId, currentTime, currentProductId, currentStaffId, form]);

  const handleSubmit = async () => {
    if (!storeId || !orderItemId) return;
    try {
      const v = await form.validateFields();
      const payload: any = {
        notify_customer: !!v.notify_customer,
      };
      if (v.new_appointment_time) {
        payload.new_appointment_time = v.new_appointment_time.toISOString();
      }
      if (v.new_product_id) payload.new_product_id = v.new_product_id;
      if (v.new_staff_id) payload.new_staff_id = v.new_staff_id;

      if (
        !payload.new_appointment_time &&
        !payload.new_product_id &&
        !payload.new_staff_id
      ) {
        message.warning('请至少修改一项');
        return;
      }

      setSubmitting(true);
      const res: any = await api.post(
        `/api/merchant/booking/${orderItemId}/reschedule`,
        payload,
        { params: { store_id: storeId } }
      );
      message.success('改约成功');
      if (res?.notify_result === 'no_subscribe') {
        message.warning('顾客未授权订阅消息，未发送通知');
      } else if (res?.notify_result === 'fail') {
        message.warning('通知发送失败');
      }
      onSuccess?.();
      onClose();
    } catch (err: any) {
      if (err?.errorFields) return; // form validation
      message.error(err?.response?.data?.detail || '改约失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="改约"
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      confirmLoading={submitting}
      okText="提交"
      cancelText="取消"
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item label="新预约时间" name="new_appointment_time">
          <DatePicker showTime style={{ width: '100%' }} format="YYYY-MM-DD HH:mm" />
        </Form.Item>
        <Form.Item label="新服务项目" name="new_product_id">
          <Select
            placeholder="不变更请留空"
            allowClear
            showSearch
            optionFilterProp="label"
            options={products.map((p) => ({ label: p.name, value: p.id }))}
          />
        </Form.Item>
        <Form.Item label="新服务员工" name="new_staff_id">
          <Select placeholder="不变更请留空" allowClear options={[]} disabled />
        </Form.Item>
        <Form.Item label="通知顾客" name="notify_customer" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}

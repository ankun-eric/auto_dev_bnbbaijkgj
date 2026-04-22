'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, Button, Tag, Empty, SpinLoading, Toast, Dialog, Popup, Form, Input, Switch } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface Address {
  id: number;
  user_id: number;
  name: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  street: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export default function MyAddressesPage() {
  const router = useRouter();
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingAddress, setEditingAddress] = useState<Address | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchAddresses = () => {
    api.get('/api/addresses').then((res: any) => {
      const data = res.data || res;
      setAddresses(data.items || data || []);
    }).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { fetchAddresses(); }, []);

  const openAddForm = () => {
    if (addresses.length >= 10) {
      Toast.show({ content: '最多只能保存10个地址' });
      return;
    }
    setEditingAddress(null);
    form.resetFields();
    setShowForm(true);
  };

  const openEditForm = (addr: Address) => {
    setEditingAddress(addr);
    form.setFieldsValue({
      name: addr.name,
      phone: addr.phone,
      province: addr.province,
      city: addr.city,
      district: addr.district,
      street: addr.street,
      is_default: addr.is_default,
    });
    setShowForm(true);
  };

  const handleSubmit = async () => {
    try {
      const values = form.getFieldsValue();
      if (!values.name || !values.phone || !values.province || !values.city || !values.district || !values.street) {
        Toast.show({ content: '请填写完整地址信息' });
        return;
      }
      setSubmitting(true);
      if (editingAddress) {
        await api.put(`/api/addresses/${editingAddress.id}`, values);
        Toast.show({ content: '修改成功' });
      } else {
        await api.post('/api/addresses', values);
        Toast.show({ content: '添加成功' });
      }
      setShowForm(false);
      setLoading(true);
      fetchAddresses();
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '操作失败' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = (addrId: number) => {
    Dialog.confirm({
      content: '确认删除该地址？',
      onConfirm: async () => {
        try {
          await api.delete(`/api/addresses/${addrId}`);
          Toast.show({ content: '已删除' });
          setAddresses((prev) => prev.filter((a) => a.id !== addrId));
        } catch {
          Toast.show({ content: '删除失败' });
        }
      },
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <GreenNavBar>
        我的地址
      </GreenNavBar>

      <div className="px-4 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : addresses.length === 0 ? (
          <Empty description="暂无收货地址" style={{ padding: '80px 0' }} />
        ) : (
          addresses.map((addr) => (
            <Card key={addr.id} style={{ borderRadius: 12, marginBottom: 12 }}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center">
                    <span className="font-medium text-sm">{addr.name}</span>
                    <span className="text-sm text-gray-400 ml-2">{addr.phone}</span>
                    {addr.is_default && (
                      <Tag
                        style={{
                          '--background-color': '#52c41a15',
                          '--text-color': '#52c41a',
                          '--border-color': 'transparent',
                          fontSize: 10,
                          marginLeft: 6,
                        }}
                      >
                        默认
                      </Tag>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {addr.province}{addr.city}{addr.district}{addr.street}
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-3 pt-2 border-t border-gray-50">
                <Button
                  size="mini"
                  onClick={() => openEditForm(addr)}
                  style={{ borderRadius: 16, fontSize: 12, color: '#52c41a', borderColor: '#52c41a' }}
                >
                  编辑
                </Button>
                <Button
                  size="mini"
                  onClick={() => handleDelete(addr.id)}
                  style={{ borderRadius: 16, fontSize: 12 }}
                >
                  删除
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>

      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3"
        style={{ maxWidth: 750, paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
      >
        {/* PRD v1.0 2026-04-23：+新增地址（加号与文字无空格，文本水平+垂直居中） */}
        <Button
          block
          onClick={openAddForm}
          style={{
            borderRadius: 24,
            height: 44,
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            lineHeight: 1,
            padding: 0,
            textAlign: 'center',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}>
            +新增地址
          </span>
        </Button>
      </div>

      <Popup
        visible={showForm}
        onMaskClick={() => setShowForm(false)}
        bodyStyle={{
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          maxHeight: '80vh',
          overflow: 'auto',
        }}
      >
        <div className="p-4">
          <div className="font-medium text-base mb-4">
            {editingAddress ? '编辑地址' : '新增地址'}
          </div>
          <Form
            form={form}
            layout="horizontal"
            footer={
              <Button
                block
                loading={submitting}
                onClick={handleSubmit}
                style={{
                  borderRadius: 24,
                  height: 44,
                  background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                  color: '#fff',
                  border: 'none',
                }}
              >
                保存
              </Button>
            }
          >
            <Form.Item name="name" label="姓名" rules={[{ required: true }]}>
              <Input placeholder="请输入收货人姓名" />
            </Form.Item>
            <Form.Item name="phone" label="电话" rules={[{ required: true }]}>
              <Input placeholder="请输入手机号" type="tel" />
            </Form.Item>
            <Form.Item name="province" label="省份" rules={[{ required: true }]}>
              <Input placeholder="请输入省份" />
            </Form.Item>
            <Form.Item name="city" label="城市" rules={[{ required: true }]}>
              <Input placeholder="请输入城市" />
            </Form.Item>
            <Form.Item name="district" label="区县" rules={[{ required: true }]}>
              <Input placeholder="请输入区/县" />
            </Form.Item>
            <Form.Item name="street" label="详细地址" rules={[{ required: true }]}>
              <Input placeholder="请输入详细地址" />
            </Form.Item>
            <Form.Item name="is_default" label="设为默认" valuePropName="checked">
              <Switch style={{ '--checked-color': '#52c41a' }} />
            </Form.Item>
          </Form>
        </div>
      </Popup>
    </div>
  );
}

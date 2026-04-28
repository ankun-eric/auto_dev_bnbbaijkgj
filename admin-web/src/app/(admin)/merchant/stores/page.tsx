'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Button, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography, message } from 'antd';
import { get, post, put } from '@/lib/api';

const { Title } = Typography;

interface StoreItem {
  id: number;
  store_name: string;
  store_code: string;
  contact_name?: string;
  contact_phone?: string;
  address?: string;
  status: string;
  category_id?: number | null;
  category_code?: string | null;
  category_name?: string | null;
  business_scope?: number[];
}

interface CategoryItem {
  id: number;
  code: string;
  name: string;
}

interface ProductCategoryItem {
  id: number;
  name: string;
  level?: number;
}

export default function MerchantStoresPage() {
  const [items, setItems] = useState<StoreItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [productCategories, setProductCategories] = useState<ProductCategoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState<string | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<StoreItem | null>(null);
  const [form] = Form.useForm();

  const fetchCategories = async () => {
    try {
      const res = await get('/api/admin/merchant-categories');
      setCategories(Array.isArray(res) ? res : (res.items || []));
    } catch {
      // 静默
    }
  };

  const fetchProductCategories = useCallback(async () => {
    try {
      const res = await get('/api/admin/products/categories');
      const rawList = res?.items || res?.list || res || [];
      setProductCategories(Array.isArray(rawList) ? rawList : []);
    } catch {
      setProductCategories([]);
    }
  }, []);

  const fetchData = async (categoryCode?: string) => {
    setLoading(true);
    try {
      const url = categoryCode
        ? `/api/admin/merchant/stores?category_code=${encodeURIComponent(categoryCode)}`
        : '/api/admin/merchant/stores';
      const res = await get(url);
      setItems(res.items || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '门店列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCategories();
    fetchProductCategories();
    fetchData();
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    // 默认选中"自营门店"（如果存在）
    const defaultCat = categories.find((c) => c.code === 'self_store');
    form.setFieldsValue({ status: 'active', category_id: defaultCat?.id });
    setOpen(true);
  };

  const openEdit = (item: StoreItem) => {
    setEditing(item);
    form.setFieldsValue({
      ...item,
      category_id: item.category_id ?? undefined,
      business_scope: item.business_scope ?? [],
    });
    setOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    const { business_scope, ...storeValues } = values;
    try {
      let storeId: number;
      if (editing) {
        await put(`/api/admin/merchant/stores/${editing.id}`, storeValues);
        storeId = editing.id;
        message.success('门店更新成功');
      } else {
        const res = await post('/api/admin/merchant/stores', storeValues);
        storeId = res?.id ?? res?.data?.id;
        message.success('门店创建成功');
      }
      if (storeId && Array.isArray(business_scope) && business_scope.length > 0) {
        try {
          await put(`/api/admin/stores/${storeId}/business-scope`, { business_scope });
        } catch {
          message.warning('经营范围保存失败，请重试');
        }
      }
      setOpen(false);
      fetchData(filterCategory);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '保存失败');
    }
  };

  const toggleStatus = async (item: StoreItem) => {
    try {
      await put(`/api/admin/merchant/stores/${item.id}`, {
        status: item.status === 'active' ? 'disabled' : 'active',
      });
      message.success('状态已更新');
      fetchData(filterCategory);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '状态更新失败');
    }
  };

  const handleFilterChange = (value: string | undefined) => {
    setFilterCategory(value);
    fetchData(value);
  };

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>门店管理</Title>
        <Space>
          <Select
            allowClear
            placeholder="按类别筛选"
            style={{ width: 180 }}
            value={filterCategory}
            onChange={handleFilterChange}
            options={categories.map((c) => ({ label: c.name, value: c.code }))}
          />
          <Button type="primary" onClick={openCreate}>新建门店</Button>
        </Space>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={[
          { title: '门店名称', dataIndex: 'store_name' },
          { title: '门店编码', dataIndex: 'store_code' },
          {
            title: '所属类别',
            dataIndex: 'category_name',
            render: (_: any, row: StoreItem) =>
              row.category_name ? (
                <Tag color="blue">{row.category_name}</Tag>
              ) : (
                <Tag color="default">未分类</Tag>
              ),
          },
          { title: '联系人', dataIndex: 'contact_name' },
          { title: '联系电话', dataIndex: 'contact_phone' },
          { title: '地址', dataIndex: 'address', ellipsis: true },
          {
            title: '状态',
            dataIndex: 'status',
            render: (value: string) => (
              <Tag color={value === 'active' ? 'green' : 'red'}>
                {value === 'active' ? '启用' : '停用'}
              </Tag>
            ),
          },
          {
            title: '操作',
            render: (_: any, item: StoreItem) => (
              <Space>
                <Button type="link" onClick={() => openEdit(item)}>编辑</Button>
                <Popconfirm
                  title={item.status === 'active' ? '确认停用该门店？' : '确认启用该门店？'}
                  onConfirm={() => toggleStatus(item)}
                >
                  <Button type="link">{item.status === 'active' ? '停用' : '启用'}</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? '编辑门店' : '新建门店'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="store_name" label="门店名称" rules={[{ required: true, message: '请输入门店名称' }]}>
            <Input placeholder="请输入门店名称" />
          </Form.Item>
          <Form.Item name="store_code" label="门店编码" rules={[{ required: true, message: '请输入门店编码' }]}>
            <Input placeholder="请输入唯一门店编码" disabled={!!editing} />
          </Form.Item>
          <Form.Item
            name="category_id"
            label="所属类别"
            rules={[{ required: true, message: '请选择所属类别' }]}
          >
            <Select
              placeholder="请选择所属类别"
              options={categories.map((c) => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>
          <Form.Item name="contact_name" label="联系人">
            <Input placeholder="请输入联系人" />
          </Form.Item>
          <Form.Item name="contact_phone" label="联系电话">
            <Input placeholder="请输入联系电话" />
          </Form.Item>
          <Form.Item name="address" label="门店地址">
            <Input.TextArea rows={3} placeholder="请输入门店地址" />
          </Form.Item>
          <Form.Item name="business_scope" label="经营范围">
            <Select
              mode="multiple"
              placeholder="请选择经营的商品分类"
              showSearch
              optionFilterProp="label"
              options={productCategories.map(c => ({
                label: `${c.level === 2 ? '  └ ' : ''}${c.name}`,
                value: c.id,
              }))}
              maxTagCount="responsive"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

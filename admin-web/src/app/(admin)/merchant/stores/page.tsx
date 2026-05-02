'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Button, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Switch, Table, Tag, Typography, message } from 'antd';
import { get, post, put } from '@/lib/api';
import StoreMapPicker, { StoreMapPickerValue } from '@/components/StoreMapPicker';

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
  // [2026-05-01 门店地图能力 PRD v1.0]
  lat?: number | null;
  lng?: number | null;
  province?: string | null;
  city?: string | null;
  district?: string | null;
  // [2026-05-02 H5 下单流程优化 PRD v1.0]
  slot_capacity?: number | null;
  business_start?: string | null;
  business_end?: string | null;
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
  const [includeInactive, setIncludeInactive] = useState(false);
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

  const fetchData = async (categoryCode?: string, inactive?: boolean) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      const showInactive = inactive !== undefined ? inactive : includeInactive;
      params.set('include_inactive', String(showInactive));
      if (categoryCode) {
        params.set('category_code', categoryCode);
      }
      const url = `/api/admin/merchant/stores?${params.toString()}`;
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
    const defaultCat = categories.find((c) => c.code === 'self_store');
    form.setFieldsValue({
      status: 'active',
      category_id: defaultCat?.id,
      // [2026-05-01 门店地图能力 PRD v1.0] 地图选点初值
      map_point: {} as StoreMapPickerValue,
      // [2026-05-02 H5 下单流程优化 PRD v1.0]
      slot_capacity: 10,
      business_start: '09:00',
      business_end: '22:00',
    });
    setOpen(true);
  };

  const openEdit = (item: StoreItem) => {
    setEditing(item);
    form.setFieldsValue({
      ...item,
      category_id: item.category_id ?? undefined,
      business_scope: item.business_scope ?? [],
      // [2026-05-02 H5 下单流程优化 PRD v1.0]
      slot_capacity: item.slot_capacity ?? 10,
      business_start: item.business_start ?? '',
      business_end: item.business_end ?? '',
      // [2026-05-01 门店地图能力 PRD v1.0]
      map_point: {
        lat: item.lat ?? undefined,
        lng: item.lng ?? undefined,
        province: item.province ?? undefined,
        city: item.city ?? undefined,
        district: item.district ?? undefined,
        address: item.address ?? undefined,
      } as StoreMapPickerValue,
    });
    setOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    const { business_scope, map_point, ...storeValues } = values;
    // [2026-05-01 门店地图能力 PRD v1.0] 经纬度必填校验（仅新建强制；编辑可空）
    const mapPoint: StoreMapPickerValue | undefined = map_point;
    if (!editing) {
      if (!mapPoint || mapPoint.lat == null || mapPoint.lng == null) {
        message.error('请在地图上选择门店位置');
        return;
      }
    }
    if (mapPoint?.lat != null) storeValues.lat = mapPoint.lat;
    if (mapPoint?.lng != null) storeValues.lng = mapPoint.lng;
    if (mapPoint?.province) storeValues.province = mapPoint.province;
    if (mapPoint?.city) storeValues.city = mapPoint.city;
    if (mapPoint?.district) storeValues.district = mapPoint.district;
    // 若 admin 没有手动改过 address，且 map_point 有 address，沿用 map_point 的地址
    if ((!storeValues.address || storeValues.address.length === 0) && mapPoint?.address) {
      storeValues.address = mapPoint.address;
    }
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

  const handleIncludeInactiveChange = (checked: boolean) => {
    setIncludeInactive(checked);
    fetchData(filterCategory, checked);
  };

  // [2026-05-01 门店地图能力 PRD v1.0] map_point 变化时联动写回 province/city/district/address
  const onValuesChange = (changed: any, allValues: any) => {
    if (changed && Object.prototype.hasOwnProperty.call(changed, 'map_point')) {
      const mp: StoreMapPickerValue | undefined = changed.map_point;
      if (mp) {
        const next: any = {};
        if (mp.province) next.province = mp.province;
        if (mp.city) next.city = mp.city;
        if (mp.district) next.district = mp.district;
        if (mp.address) next.address = mp.address;
        if (Object.keys(next).length > 0) {
          form.setFieldsValue(next);
        }
      }
    }
  };

  return (
    <div>
      <style jsx>{`
        .store-row-inactive td {
          color: #BFBFBF !important;
          background-color: #FAFAFA !important;
        }
      `}</style>

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
          <Space size={4}>
            <span style={{ fontSize: 14 }}>显示已停用</span>
            <Switch checked={includeInactive} onChange={handleIncludeInactiveChange} />
          </Space>
          <Button type="primary" onClick={openCreate}>新建门店</Button>
        </Space>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        rowClassName={(record: StoreItem) =>
          record.status !== 'active' ? 'store-row-inactive' : ''
        }
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
              <Tag color={value === 'active' ? 'green' : 'default'}>
                {value === 'active' ? '营业中' : '已停用'}
              </Tag>
            ),
          },
          {
            title: '操作',
            render: (_: any, item: StoreItem) => (
              <Space>
                <Button
                  type="link"
                  disabled={item.status !== 'active'}
                  onClick={() => openEdit(item)}
                >
                  编辑
                </Button>
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
        width={760}
      >
        <Form form={form} layout="vertical" onValuesChange={onValuesChange}>
          <Form.Item name="store_name" label="门店名称" rules={[{ required: true, message: '请输入门店名称' }]}>
            <Input placeholder="请输入门店名称" />
          </Form.Item>
          {editing && (
            <Form.Item label="门店编码">
              <Input
                value={editing.store_code}
                disabled
                style={{ backgroundColor: '#f5f5f5', color: '#595959' }}
              />
            </Form.Item>
          )}
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
          {/* [2026-05-01 门店地图能力 PRD v1.0] 地图选点 — 搜索/拖拽/逆地理回填/手动经纬度 */}
          <Form.Item
            name="map_point"
            label="地图选点"
            tooltip="新建门店必须在地图上选点；选点后会自动回填省/市/区/详细地址"
            rules={[
              {
                validator: async (_, val: StoreMapPickerValue) => {
                  if (!editing) {
                    if (!val || val.lat == null || val.lng == null) {
                      throw new Error('请在地图上选择门店位置');
                    }
                  }
                },
              },
            ]}
          >
            <StoreMapPicker />
          </Form.Item>
          <Form.Item name="province" label="省份">
            <Input placeholder="（地图选点后自动回填，可手动修改）" />
          </Form.Item>
          <Form.Item name="city" label="城市">
            <Input placeholder="（地图选点后自动回填，可手动修改）" />
          </Form.Item>
          <Form.Item name="district" label="区/县">
            <Input placeholder="（地图选点后自动回填，可手动修改）" />
          </Form.Item>
          <Form.Item name="address" label="详细地址">
            <Input.TextArea rows={3} placeholder="请输入详细地址（地图选点后自动回填，可手动修改）" />
          </Form.Item>
          {/* [2026-05-02 H5 下单流程优化 PRD v1.0] 单时段最大接单数 + 营业起止时间 */}
          <Form.Item
            name="slot_capacity"
            label="单时段最大接单数"
            tooltip="同一日期同一时段允许的最大下单数（共享门店容量池），默认 10"
            rules={[{ required: true, message: '请填写单时段最大接单数' }]}
          >
            <InputNumber min={1} max={9999} style={{ width: 200 }} placeholder="默认 10" />
          </Form.Item>
          <Form.Item label="营业时间" tooltip="商品时段必须完全落在门店营业时段内才会出现在用户支付页">
            <Space>
              <Form.Item name="business_start" noStyle>
                <Input placeholder="09:00" maxLength={5} style={{ width: 100 }} />
              </Form.Item>
              <span>至</span>
              <Form.Item name="business_end" noStyle>
                <Input placeholder="22:00" maxLength={5} style={{ width: 100 }} />
              </Form.Item>
              <span style={{ color: '#999', fontSize: 12 }}>格式 HH:MM</span>
            </Space>
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

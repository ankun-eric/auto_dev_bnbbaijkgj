'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { get, post, put } from '@/lib/api';
import { useRouter } from 'next/navigation';
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

// [2026-05-03 营业时间 Bug 修复方案]
// 30 分钟粒度时间下拉：07:00 - 22:00
const BUSINESS_TIME_OPTIONS: { label: string; value: string }[] = (() => {
  const out: { label: string; value: string }[] = [];
  for (let h = 7; h <= 22; h++) {
    for (const m of [0, 30]) {
      if (h === 22 && m === 30) break;
      const v = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      out.push({ label: v, value: v });
    }
  }
  // 加上结束时间的 22:00（开始时间不能选 22:00 因为不能跨日）
  return out;
})();

const BUSINESS_END_OPTIONS: { label: string; value: string }[] = (() => {
  const out: { label: string; value: string }[] = [];
  for (let h = 7; h <= 22; h++) {
    for (const m of [0, 30]) {
      if (h === 7 && m === 0) continue;
      if (h === 22 && m === 30) break;
      const v = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      out.push({ label: v, value: v });
    }
  }
  out.push({ label: '22:00', value: '22:00' });
  return out;
})();

export default function MerchantStoresPage() {
  const router = useRouter();
  const [items, setItems] = useState<StoreItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [productCategories, setProductCategories] = useState<ProductCategoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState<string | undefined>(undefined);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<StoreItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
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
      // [2026-05-05 营业管理入口收敛 PRD v1.0 · N-02] slot_capacity 不再在编辑门店表单中维护
      business_start: '09:00',
      business_end: '22:00',
      business_scope: [],
    });
    setOpen(true);
  };

  // [2026-05-03 营业时间 Bug 修复] 编辑前从详情接口拉取，确保 business_scope 有值
  const openEdit = async (item: StoreItem) => {
    try {
      const detail = await get(`/api/admin/merchant/stores/${item.id}`);
      setEditing({ ...item, ...detail });
      form.setFieldsValue({
        ...item,
        ...detail,
        category_id: detail.category_id ?? item.category_id ?? undefined,
        business_scope: Array.isArray(detail.business_scope)
          ? detail.business_scope
          : (item.business_scope ?? []),
        // [2026-05-05 N-02] slot_capacity 已搬迁至「营业管理」页，编辑门店页不再展示与维护
        business_start: detail.business_start ?? item.business_start ?? '',
        business_end: detail.business_end ?? item.business_end ?? '',
        map_point: {
          lat: detail.lat ?? item.lat ?? undefined,
          lng: detail.lng ?? item.lng ?? undefined,
          province: detail.province ?? item.province ?? undefined,
          city: detail.city ?? item.city ?? undefined,
          district: detail.district ?? item.district ?? undefined,
          address: detail.address ?? item.address ?? undefined,
        } as StoreMapPickerValue,
      });
      setOpen(true);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '门店详情加载失败');
    }
  };

  const submit = async () => {
    let values: any;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    const { map_point, business_scope, ...storeValues } = values;

    // [2026-05-03 营业时间 Bug 修复] 前端最终拦截
    if (!storeValues.business_start || !storeValues.business_end) {
      message.error('请选择营业开始时间和结束时间');
      return;
    }
    if (storeValues.business_end <= storeValues.business_start) {
      message.error('营业结束时间必须晚于营业开始时间');
      return;
    }

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
    if ((!storeValues.address || storeValues.address.length === 0) && mapPoint?.address) {
      storeValues.address = mapPoint.address;
    }

    // [2026-05-03 营业时间/营业范围 Bug 修复] 经营范围合并到主表单一并入库
    storeValues.business_scope = Array.isArray(business_scope) ? business_scope : [];

    // [2026-05-05 营业管理入口收敛 PRD v1.0 · N-02] 编辑门店页保存时不再下发 slot_capacity 字段，
    // 该字段交由「营业管理」页统一维护，避免双入口写同一字段产生冲突。
    delete storeValues.slot_capacity;

    setSubmitting(true);
    try {
      let resp: any;
      if (editing) {
        resp = await put(`/api/admin/merchant/stores/${editing.id}`, storeValues);
        message.success('保存成功');
      } else {
        resp = await post('/api/admin/merchant/stores', storeValues);
        message.success('保存成功');
      }
      // 受影响存量预约提示
      const affected = Number(resp?.affected_appointments || 0);
      if (affected > 0) {
        message.info(`您有 ${affected} 单预约时间已不在新营业范围内，建议联系客户`, 6);
      }
      setOpen(false);
      fetchData(filterCategory);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : detail?.msg || '保存失败';
      message.error(msg);
    } finally {
      setSubmitting(false);
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
  const onValuesChange = (changed: any) => {
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
            title: '营业时间',
            render: (_: any, row: StoreItem) =>
              row.business_start && row.business_end
                ? `${row.business_start} - ${row.business_end}`
                : '—',
          },
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
                {/* [2026-05-05 营业管理入口收敛 PRD v1.0 · N-01] 门店列表行新增「营业管理」按钮，自动锁定 storeId */}
                <Button
                  type="link"
                  disabled={item.status !== 'active'}
                  onClick={() => router.push(`/merchant/stores/${item.id}/business-config`)}
                >
                  营业管理
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
        confirmLoading={submitting}
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
          {/* [2026-05-01 门店地图能力 PRD v1.0] 地图选点 */}
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
          {/* [2026-05-05 营业管理入口收敛 PRD v1.0 · N-02] 「门店总接待名额」字段已搬迁至「营业管理」页 */}
          {/* [2026-05-03 营业时间 Bug 修复] 30 分钟粒度时间选择器 */}
          <Form.Item
            label="营业时间"
            required
            tooltip="30 分钟粒度，可选范围 07:00 – 22:00；结束时间必须晚于开始时间"
            shouldUpdate={(prev, cur) =>
              prev.business_start !== cur.business_start || prev.business_end !== cur.business_end
            }
          >
            {({ getFieldValue }) => {
              const bs: string | undefined = getFieldValue('business_start');
              const be: string | undefined = getFieldValue('business_end');
              const invalid = !!bs && !!be && be <= bs;
              return (
                <>
                  <Space>
                    <Form.Item
                      name="business_start"
                      noStyle
                      rules={[{ required: true, message: '请选择营业开始时间' }]}
                    >
                      <Select
                        placeholder="开始时间"
                        style={{ width: 140 }}
                        options={BUSINESS_TIME_OPTIONS}
                      />
                    </Form.Item>
                    <span>至</span>
                    <Form.Item
                      name="business_end"
                      noStyle
                      rules={[{ required: true, message: '请选择营业结束时间' }]}
                    >
                      <Select
                        placeholder="结束时间"
                        style={{ width: 140 }}
                        options={BUSINESS_END_OPTIONS}
                      />
                    </Form.Item>
                    <span style={{ color: '#999', fontSize: 12 }}>30 分钟一档</span>
                  </Space>
                  {invalid && (
                    <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>
                      结束时间必须晚于开始时间
                    </div>
                  )}
                </>
              );
            }}
          </Form.Item>
          {/* [2026-05-03 营业范围 Bug 修复] 与主表单一并入库 */}
          <Form.Item
            name="business_scope"
            label="经营范围"
            tooltip='选填；用于"商品-推荐门店"配置页的自动推荐'
          >
            <Select
              mode="multiple"
              placeholder="请选择经营的商品分类（选填）"
              showSearch
              optionFilterProp="label"
              options={productCategories.map(c => ({
                label: `${c.level === 2 ? '  └ ' : ''}${c.name}`,
                value: c.id,
              }))}
              maxTagCount="responsive"
              allowClear
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

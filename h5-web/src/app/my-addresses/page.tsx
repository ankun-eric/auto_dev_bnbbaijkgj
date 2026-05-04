'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Card, Button, Tag, Empty, SpinLoading, Toast, Dialog, Popup,
  Form, Input, Switch, CascadePicker, TextArea, NoticeBar,
} from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

interface AddressV2 {
  id: number;
  user_id: number;
  consignee_name: string;
  consignee_phone: string;
  province: string;
  province_code?: string;
  city: string;
  city_code?: string;
  district: string;
  district_code?: string;
  detail: string;
  longitude?: number | null;
  latitude?: number | null;
  tag?: string;
  is_default: boolean;
  needs_region_completion?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface RegionDistrict { code: string; name: string }
interface RegionCity { code: string; name: string; districts: RegionDistrict[] }
interface RegionProvince { code: string; name: string; cities: RegionCity[] }
interface RegionsData { version: string; provinces: RegionProvince[] }

const PRESET_TAGS = ['家', '公司'];
const ADDR_LIMIT = 10;
const DETAIL_MAX = 80;

export default function MyAddressesPage() {
  const router = useRouter();
  const [addresses, setAddresses] = useState<AddressV2[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<AddressV2 | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [regions, setRegions] = useState<RegionsData | null>(null);
  const [showCascade, setShowCascade] = useState(false);

  // form fields
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [provinceCode, setProvinceCode] = useState('');
  const [cityCode, setCityCode] = useState('');
  const [districtCode, setDistrictCode] = useState('');
  const [provinceName, setProvinceName] = useState('');
  const [cityName, setCityName] = useState('');
  const [districtName, setDistrictName] = useState('');
  const [detail, setDetail] = useState('');
  const [tag, setTag] = useState('');
  const [customTagMode, setCustomTagMode] = useState(false);
  const [customTagValue, setCustomTagValue] = useState('');
  const [isDefault, setIsDefault] = useState(false);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [latitude, setLatitude] = useState<number | null>(null);

  // 加载行政区划 JSON
  useEffect(() => {
    const url = resolveAssetUrl('/regions.json');
    fetch(url)
      .then(r => r.json())
      .then(setRegions)
      .catch(() => {
        api.get('/api/v2/regions').then((res: any) => setRegions(res.data || res)).catch(() => {});
      });
  }, []);

  const cascadeOptions = useMemo(() => {
    if (!regions) return [];
    return regions.provinces.map(p => ({
      label: p.name, value: p.code,
      children: p.cities.map(c => ({
        label: c.name, value: c.code,
        children: c.districts.map(d => ({ label: d.name, value: d.code })),
      })),
    }));
  }, [regions]);

  const fetchAddresses = () => {
    setLoading(true);
    api.get('/api/v2/user/addresses').then((res: any) => {
      const data = res.data || res;
      setAddresses(data.items || []);
    }).catch(() => {
      // v2 接口不可用时降级 v1
      api.get('/api/addresses').then((res: any) => {
        const data = res.data || res;
        const v1items = (data.items || data || []) as any[];
        setAddresses(v1items.map(a => ({
          id: a.id, user_id: a.user_id,
          consignee_name: a.consignee_name || a.name || '',
          consignee_phone: a.consignee_phone || a.phone || '',
          province: a.province || '', city: a.city || '', district: a.district || '',
          detail: a.detail || a.street || '',
          tag: a.tag || '', is_default: !!a.is_default,
          needs_region_completion: !(a.province && a.city && a.district),
        })));
      }).catch(() => {});
    }).finally(() => setLoading(false));
  };

  useEffect(() => { fetchAddresses(); }, []);

  const resetForm = () => {
    setName(''); setPhone('');
    setProvinceCode(''); setCityCode(''); setDistrictCode('');
    setProvinceName(''); setCityName(''); setDistrictName('');
    setDetail(''); setTag(''); setCustomTagMode(false); setCustomTagValue('');
    setIsDefault(addresses.length === 0);
    setLongitude(null); setLatitude(null);
  };

  const openAddForm = () => {
    if (addresses.length >= ADDR_LIMIT) {
      Toast.show({ content: `最多保存 ${ADDR_LIMIT} 条地址` });
      return;
    }
    setEditing(null);
    resetForm();
    setShowForm(true);
  };

  const openEditForm = (addr: AddressV2) => {
    setEditing(addr);
    setName(addr.consignee_name || '');
    setPhone(addr.consignee_phone || '');
    setProvinceCode(addr.province_code || '');
    setCityCode(addr.city_code || '');
    setDistrictCode(addr.district_code || '');
    setProvinceName(addr.province || '');
    setCityName(addr.city || '');
    setDistrictName(addr.district || '');
    setDetail(addr.detail || '');
    setTag(addr.tag || '');
    if (addr.tag && !PRESET_TAGS.includes(addr.tag)) {
      setCustomTagMode(true);
      setCustomTagValue(addr.tag);
    }
    setIsDefault(!!addr.is_default);
    setLongitude(addr.longitude ?? null);
    setLatitude(addr.latitude ?? null);
    setShowForm(true);
  };

  const onCascadeConfirm = (val: any[], extend: any) => {
    setProvinceCode(String(val[0] || ''));
    setCityCode(String(val[1] || ''));
    setDistrictCode(String(val[2] || ''));
    const items = extend?.items || [];
    setProvinceName(items[0]?.label || '');
    setCityName(items[1]?.label || '');
    setDistrictName(items[2]?.label || '');
  };

  const validatePhone = (p: string) => /^1[3-9]\d{9}$/.test(p);
  const validateName = (n: string) => n.length >= 2 && n.length <= 20;

  const submit = async () => {
    if (!validateName(name)) { Toast.show({ content: '收货人姓名为 2-20 个字符' }); return; }
    if (!validatePhone(phone)) { Toast.show({ content: '请输入正确的 11 位手机号' }); return; }
    if (!provinceName || !cityName || !districtName) { Toast.show({ content: '请选择所在地区' }); return; }
    if (!detail.trim()) { Toast.show({ content: '请输入详细地址' }); return; }
    if (detail.length > DETAIL_MAX) { Toast.show({ content: `详细地址最多 ${DETAIL_MAX} 字` }); return; }

    let finalTag = tag;
    if (customTagMode && customTagValue.trim()) {
      const v = customTagValue.trim();
      if (v.length > 6) { Toast.show({ content: '自定义标签最多 6 个汉字' }); return; }
      finalTag = v;
    }

    const payload: any = {
      consignee_name: name.trim(),
      consignee_phone: phone.trim(),
      province: provinceName,
      province_code: provinceCode,
      city: cityName,
      city_code: cityCode,
      district: districtName,
      district_code: districtCode,
      detail: detail.trim(),
      tag: finalTag,
      is_default: isDefault,
    };
    if (longitude != null) payload.longitude = longitude;
    if (latitude != null) payload.latitude = latitude;

    try {
      setSubmitting(true);
      if (editing) {
        await api.put(`/api/v2/user/addresses/${editing.id}`, payload);
        Toast.show({ content: '修改成功' });
      } else {
        await api.post('/api/v2/user/addresses', payload);
        Toast.show({ content: '添加成功' });
      }
      setShowForm(false);
      fetchAddresses();
    } catch (err: any) {
      const msg = err?.response?.data?.detail?.message || err?.response?.data?.detail || '操作失败';
      Toast.show({ content: typeof msg === 'string' ? msg : '操作失败' });
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = (addrId: number) => {
    Dialog.confirm({
      content: '确认删除该地址？',
      onConfirm: async () => {
        try {
          await api.delete(`/api/v2/user/addresses/${addrId}`);
          Toast.show({ content: '已删除' });
          fetchAddresses();
        } catch {
          Toast.show({ content: '删除失败' });
        }
      },
    });
  };

  const setDefault = async (addrId: number) => {
    try {
      await api.patch(`/api/v2/user/addresses/${addrId}/default`, { is_default: true });
      Toast.show({ content: '已设为默认' });
      fetchAddresses();
    } catch {
      Toast.show({ content: '操作失败' });
    }
  };

  const renderTagBlock = () => (
    <div className="flex flex-wrap items-center gap-2">
      {PRESET_TAGS.map(t => (
        <span
          key={t}
          onClick={() => { setTag(t); setCustomTagMode(false); setCustomTagValue(''); }}
          style={{
            padding: '4px 12px', borderRadius: 16, fontSize: 12,
            background: tag === t ? '#52c41a15' : '#f5f5f5',
            color: tag === t ? '#52c41a' : '#666',
            border: tag === t ? '1px solid #52c41a' : '1px solid transparent',
            cursor: 'pointer',
          }}
        >{t}</span>
      ))}
      {customTagMode ? (
        <Input
          placeholder="≤6 字"
          value={customTagValue}
          onChange={setCustomTagValue}
          maxLength={6}
          style={{ width: 80, fontSize: 12, '--font-size': '12px' } as any}
        />
      ) : (
        <span
          onClick={() => { setCustomTagMode(true); setTag(''); }}
          style={{
            padding: '4px 12px', borderRadius: 16, fontSize: 12,
            background: '#fff', color: '#52c41a', border: '1px dashed #52c41a',
            cursor: 'pointer',
          }}
        >+ 自定义</span>
      )}
      {tag && !customTagMode && (
        <span onClick={() => setTag('')} style={{ fontSize: 12, color: '#999', cursor: 'pointer' }}>清除</span>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <GreenNavBar>收货地址</GreenNavBar>

      <div className="px-4 pt-3">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <SpinLoading color="primary" />
          </div>
        ) : addresses.length === 0 ? (
          <Empty description="您还没有添加收货地址" style={{ padding: '80px 0' }} />
        ) : (
          addresses.map((addr) => (
            <Card key={addr.id} style={{ borderRadius: 12, marginBottom: 12 }}>
              {addr.needs_region_completion && (
                <NoticeBar
                  color="alert"
                  content="该地址需要重新选择省市县后才能保存"
                  style={{ '--background-color': '#fff7e6', '--border-color': '#ffd591', fontSize: 12, marginBottom: 8 } as any}
                />
              )}
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center flex-wrap gap-1">
                    {addr.is_default && (
                      <Tag style={{ '--background-color': '#fff1f0', '--text-color': '#f5222d', '--border-color': 'transparent', fontSize: 10 } as any}>
                        默认
                      </Tag>
                    )}
                    {addr.tag && (
                      <Tag style={{ '--background-color': '#e6f7ff', '--text-color': '#1890ff', '--border-color': 'transparent', fontSize: 10 } as any}>
                        {addr.tag}
                      </Tag>
                    )}
                    <span className="font-medium text-sm ml-1">{addr.consignee_name}</span>
                    <span className="text-sm text-gray-400 ml-2">
                      {addr.consignee_phone ? addr.consignee_phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') : ''}
                    </span>
                  </div>
                  <div className="text-xs text-gray-600 mt-1">
                    {addr.province}{addr.city}{addr.district}{addr.detail}
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-3 pt-2 border-t border-gray-50">
                {!addr.is_default && !addr.needs_region_completion && (
                  <Button size="mini" onClick={() => setDefault(addr.id)}
                    style={{ borderRadius: 16, fontSize: 12 }}>
                    设为默认
                  </Button>
                )}
                <Button size="mini" onClick={() => openEditForm(addr)}
                  style={{ borderRadius: 16, fontSize: 12, color: '#52c41a', borderColor: '#52c41a' }}>
                  编辑
                </Button>
                <Button size="mini" onClick={() => onDelete(addr.id)}
                  style={{ borderRadius: 16, fontSize: 12 }}>
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
        {addresses.length >= ADDR_LIMIT && (
          <div className="text-center text-xs text-gray-400 mb-2">最多保存 {ADDR_LIMIT} 条地址</div>
        )}
        <Button
          block
          disabled={addresses.length >= ADDR_LIMIT}
          onClick={openAddForm}
          style={{
            borderRadius: 24, height: 44,
            background: addresses.length >= ADDR_LIMIT ? '#d9d9d9' : 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff', border: 'none',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <span>+新增地址</span>
        </Button>
      </div>

      <Popup
        visible={showForm}
        onMaskClick={() => setShowForm(false)}
        bodyStyle={{
          borderTopLeftRadius: 16, borderTopRightRadius: 16,
          maxHeight: '90vh', overflow: 'auto',
        }}
      >
        <div className="p-4">
          <div className="font-medium text-base mb-4 flex items-center justify-between">
            <span>{editing ? '编辑地址' : '新增地址'}</span>
            <span style={{ color: '#999', fontSize: 12, cursor: 'pointer' }} onClick={() => setShowForm(false)}>取消</span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="text-xs text-gray-500 mb-1">收货人</div>
              <Input placeholder="请输入收货人姓名（2-20 字符）" value={name} onChange={setName} maxLength={20} />
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">手机号</div>
              <Input placeholder="请输入 11 位手机号" type="tel" value={phone} onChange={setPhone} maxLength={11} />
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">所在地区</div>
              <div
                onClick={() => setShowCascade(true)}
                className="flex items-center justify-between"
                style={{
                  padding: '8px 12px', border: '1px solid #f0f0f0', borderRadius: 8,
                  background: '#fafafa', minHeight: 36, cursor: 'pointer',
                }}
              >
                <span style={{ color: provinceName ? '#333' : '#bbb', fontSize: 14 }}>
                  {provinceName ? `${provinceName} / ${cityName} / ${districtName}` : '请选择 省 / 市 / 区县'}
                </span>
                <span style={{ color: '#bbb' }}>›</span>
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">详细地址</div>
              <TextArea
                placeholder="请输入街道、楼栋、门牌号等详细信息"
                value={detail}
                onChange={setDetail}
                maxLength={DETAIL_MAX}
                showCount
                rows={3}
              />
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-2">地址标签（选填）</div>
              {renderTagBlock()}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-700">设为默认地址</span>
              <Switch checked={isDefault} onChange={setIsDefault} style={{ '--checked-color': '#52c41a' } as any} />
            </div>
          </div>

          <Button
            block
            loading={submitting}
            onClick={submit}
            style={{
              borderRadius: 24, height: 44, marginTop: 24,
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff', border: 'none',
            }}
          >保存</Button>
        </div>
      </Popup>

      <CascadePicker
        title="选择所在地区"
        options={cascadeOptions as any}
        visible={showCascade}
        onClose={() => setShowCascade(false)}
        value={[provinceCode, cityCode, districtCode].filter(Boolean) as any}
        onConfirm={(val, extend) => onCascadeConfirm(val as any[], extend)}
      />
    </div>
  );
}

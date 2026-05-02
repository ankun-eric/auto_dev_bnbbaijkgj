'use client';

/**
 * [2026-05-01 门店地图能力 PRD v1.0] 门店地图选点组件
 *
 * 能力：
 * 1. 搜索框输入 POI 关键字 → 候选下拉 → 点击落点
 * 2. 地图视窗可拖拽/点击落点（OSM 瓦片，免 Key）
 * 3. 落点后自动调用后端逆地理编码代理回填省/市/区/详细地址
 * 4. 高级设置 → 手动输入经纬度 → 地图飞到该点
 *
 * 设计：使用 CDN 动态加载 Leaflet（无需 npm 依赖），瓦片用 OSM 公共服务。
 * 当后端配置了 AMAP_SERVER_KEY 时，POI 搜索/逆地理走高德；否则降级 OSM。
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Input, Button, Form, InputNumber, Tag, Spin, message, AutoComplete } from 'antd';
import { EnvironmentOutlined, SearchOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';

interface PoiItem {
  id?: string;
  name: string;
  address?: string;
  province?: string;
  city?: string;
  district?: string;
  longitude: number;
  latitude: number;
}

interface ReverseResult {
  province?: string;
  city?: string;
  district?: string;
  formatted_address?: string;
  ad_code?: string;
  provider?: string;
}

export interface StoreMapPickerValue {
  lat?: number;
  lng?: number;
  province?: string;
  city?: string;
  district?: string;
  address?: string;
}

interface Props {
  value?: StoreMapPickerValue;
  onChange?: (val: StoreMapPickerValue) => void;
  height?: number;
}

const LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
const DEFAULT_CENTER: [number, number] = [23.1291, 113.2644]; // 广州中心，作为兜底
const DEFAULT_ZOOM = 13;
const FOCUSED_ZOOM = 16;

let leafletLoadPromise: Promise<any> | null = null;

function loadLeaflet(): Promise<any> {
  if (typeof window === 'undefined') return Promise.resolve(null);
  if ((window as any).L) return Promise.resolve((window as any).L);
  if (leafletLoadPromise) return leafletLoadPromise;

  leafletLoadPromise = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = LEAFLET_CSS;
      document.head.appendChild(link);
    }
    const existing = document.querySelector(`script[src="${LEAFLET_JS}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve((window as any).L));
      return;
    }
    const script = document.createElement('script');
    script.src = LEAFLET_JS;
    script.async = true;
    script.onload = () => resolve((window as any).L);
    script.onerror = () => reject(new Error('Leaflet 加载失败'));
    document.body.appendChild(script);
  });
  return leafletLoadPromise;
}

export default function StoreMapPicker({ value, onChange, height = 320 }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const skipNextRevGeoRef = useRef<boolean>(false);
  const debounceTimerRef = useRef<any>(null);

  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [options, setOptions] = useState<{ value: string; label: React.ReactNode; poi: PoiItem }[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [manualLat, setManualLat] = useState<number | null>(value?.lat ?? null);
  const [manualLng, setManualLng] = useState<number | null>(value?.lng ?? null);

  // ============ 落点 + 通知父组件 ============
  const placeMarker = useCallback((lat: number, lng: number, opts?: { skipReverseGeo?: boolean; pan?: boolean }) => {
    const L = (window as any).L;
    if (!L || !mapRef.current) return;
    if (markerRef.current) {
      markerRef.current.setLatLng([lat, lng]);
    } else {
      markerRef.current = L.marker([lat, lng], { draggable: true }).addTo(mapRef.current);
      markerRef.current.on('dragend', () => {
        const ll = markerRef.current.getLatLng();
        skipNextRevGeoRef.current = false;
        placeMarker(ll.lat, ll.lng);
      });
    }
    if (opts?.pan !== false) {
      mapRef.current.setView([lat, lng], FOCUSED_ZOOM);
    }
    setManualLat(Number(lat.toFixed(6)));
    setManualLng(Number(lng.toFixed(6)));

    // 通知父组件，但不立刻刷新省市区（等逆地理）
    onChange?.({
      ...(value || {}),
      lat: Number(lat.toFixed(6)),
      lng: Number(lng.toFixed(6)),
    });

    // 1 秒防抖逆地理编码
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    if (opts?.skipReverseGeo || skipNextRevGeoRef.current) {
      skipNextRevGeoRef.current = false;
      return;
    }
    debounceTimerRef.current = setTimeout(() => {
      doReverseGeo(lat, lng).catch(() => {});
    }, 1000);
  }, [onChange, value]);

  const doReverseGeo = async (lat: number, lng: number) => {
    setLoading(true);
    try {
      const res = await post('/api/admin/maps/reverse-geocoding', {
        latitude: lat,
        longitude: lng,
      });
      const data: ReverseResult = (res?.data || res) as ReverseResult;
      onChange?.({
        ...(value || {}),
        lat: Number(lat.toFixed(6)),
        lng: Number(lng.toFixed(6)),
        province: data?.province || undefined,
        city: data?.city || undefined,
        district: data?.district || undefined,
        address: data?.formatted_address || (value?.address ?? undefined),
      });
    } catch (e: any) {
      // 逆地理失败不阻塞流程
      message.warning('逆地理编码失败，请手动填写地址');
    } finally {
      setLoading(false);
    }
  };

  // ============ 初始化 Leaflet 地图 ============
  useEffect(() => {
    let mounted = true;
    loadLeaflet()
      .then((L) => {
        if (!mounted || !containerRef.current || mapRef.current) return;
        const center: [number, number] =
          value?.lat && value?.lng ? [value.lat, value.lng] : DEFAULT_CENTER;
        const zoom = value?.lat && value?.lng ? FOCUSED_ZOOM : DEFAULT_ZOOM;
        const map = L.map(containerRef.current).setView(center, zoom);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap',
        }).addTo(map);
        mapRef.current = map;
        if (value?.lat && value?.lng) {
          placeMarker(value.lat, value.lng, { skipReverseGeo: true, pan: false });
        }
        map.on('click', (e: any) => {
          placeMarker(e.latlng.lat, e.latlng.lng);
        });
      })
      .catch(() => {
        message.error('地图加载失败，请检查网络');
      });
    return () => {
      mounted = false;
      if (mapRef.current) {
        try {
          mapRef.current.remove();
        } catch {
          // ignore
        }
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 当外部 value 变化（例如初次加载老门店），同步落点
  useEffect(() => {
    if (!mapRef.current) return;
    if (value?.lat != null && value?.lng != null && !markerRef.current) {
      placeMarker(value.lat, value.lng, { skipReverseGeo: true, pan: true });
    }
  }, [value?.lat, value?.lng, placeMarker]);

  // ============ POI 搜索 ============
  const handleSearch = async (kw: string) => {
    setKeyword(kw);
    if (!kw || kw.length < 2) {
      setOptions([]);
      return;
    }
    setSearching(true);
    try {
      const res = await get(`/api/admin/maps/poi-search?keyword=${encodeURIComponent(kw)}`);
      const items: PoiItem[] = (res?.items || res?.data?.items) || [];
      setOptions(
        items.map((it, idx) => ({
          value: `${it.name}#${idx}`,
          label: (
            <div style={{ lineHeight: 1.4 }}>
              <div style={{ fontWeight: 500 }}>{it.name}</div>
              <div style={{ fontSize: 12, color: '#999' }}>{it.address || `${it.province || ''}${it.city || ''}${it.district || ''}`}</div>
            </div>
          ),
          poi: it,
        }))
      );
    } catch {
      setOptions([]);
    } finally {
      setSearching(false);
    }
  };

  const handleSelectPoi = (_v: string, opt: any) => {
    const poi: PoiItem = opt.poi;
    if (!poi) return;
    skipNextRevGeoRef.current = true;
    placeMarker(poi.latitude, poi.longitude);
    // 同时直接覆盖省/市/区/详细地址（PRD D-07 完全覆盖）
    onChange?.({
      lat: Number(poi.latitude.toFixed(6)),
      lng: Number(poi.longitude.toFixed(6)),
      province: poi.province,
      city: poi.city,
      district: poi.district,
      address: poi.address || poi.name,
    });
    setKeyword(poi.name);
  };

  // ============ 手动经纬度 ============
  const handleManualApply = () => {
    if (manualLat == null || manualLng == null) {
      message.warning('请输入完整的经纬度');
      return;
    }
    if (manualLat < -90 || manualLat > 90) {
      message.error('纬度必须在 -90 到 90 之间');
      return;
    }
    if (manualLng < -180 || manualLng > 180) {
      message.error('经度必须在 -180 到 180 之间');
      return;
    }
    placeMarker(manualLat, manualLng);
  };

  return (
    <div style={{ border: '1px solid #f0f0f0', borderRadius: 8, padding: 12, background: '#fafafa' }}>
      <div style={{ marginBottom: 8 }}>
        <AutoComplete
          style={{ width: '100%' }}
          options={options}
          onSearch={handleSearch}
          onSelect={handleSelectPoi}
          value={keyword}
          onChange={setKeyword}
          notFoundContent={searching ? <Spin size="small" /> : null}
        >
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索 POI 关键字（如：广州塔）"
          />
        </AutoComplete>
      </div>
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height,
          borderRadius: 6,
          overflow: 'hidden',
          background: '#e6e6e6',
          position: 'relative',
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', marginTop: 10, gap: 8, flexWrap: 'wrap' }}>
        <Tag icon={<EnvironmentOutlined />} color={value?.lat ? 'green' : 'default'}>
          {value?.lat != null && value?.lng != null
            ? `当前坐标：${value.lat.toFixed(6)}, ${value.lng.toFixed(6)}`
            : '尚未选点'}
        </Tag>
        {loading && <Tag color="blue">逆地理回填中…</Tag>}
        <Button
          type="link"
          size="small"
          onClick={() => setShowAdvanced((v) => !v)}
          style={{ padding: 0, marginLeft: 'auto' }}
        >
          {showAdvanced ? '收起高级设置' : '高级设置：手动经纬度'}
        </Button>
      </div>
      {showAdvanced && (
        <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <InputNumber
            placeholder="纬度 -90~90"
            value={manualLat ?? undefined}
            onChange={(v) => setManualLat(v as number)}
            step={0.000001}
            min={-90}
            max={90}
            style={{ width: 160 }}
          />
          <InputNumber
            placeholder="经度 -180~180"
            value={manualLng ?? undefined}
            onChange={(v) => setManualLng(v as number)}
            step={0.000001}
            min={-180}
            max={180}
            style={{ width: 160 }}
          />
          <Button onClick={handleManualApply}>定位到地图</Button>
          <span style={{ color: '#999', fontSize: 12 }}>
            提示：地图使用 OSM 瓦片；当后端配置了 AMAP_SERVER_KEY 时，搜索与逆地理编码自动切换到高德。
          </span>
        </div>
      )}
    </div>
  );
}

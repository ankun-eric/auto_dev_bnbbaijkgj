'use client';

/**
 * [2026-05-01 门店地图能力 PRD v1.0] H5 地图导航选择抽屉
 *
 * 点击门店卡片后弹出"使用以下地图打开"底部抽屉。
 * 候选地图：
 *  - 高德 / 百度 / 腾讯（iOS/Android 都展示）
 *  - 苹果地图（仅 iOS 展示）
 *
 * 导航起点 = 用户当前定位（由外部地图 App 自行处理）；终点 = 门店全称 + 详细地址 + 经纬度。
 */

import React from 'react';
import { Popup, Toast } from 'antd-mobile';

export interface MapNavTarget {
  name: string;
  address?: string;
  lat: number;
  lng: number;
}

interface Props {
  visible: boolean;
  target: MapNavTarget | null;
  onClose: () => void;
}

function isIOS(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

function tryOpenScheme(scheme: string, fallback?: () => void) {
  if (typeof window === 'undefined') return;
  const start = Date.now();
  const timer = setTimeout(() => {
    const elapsed = Date.now() - start;
    if (elapsed < 1800) {
      // 1.5 秒内还在前台，说明跳转失败
      if (fallback) {
        fallback();
      } else {
        Toast.show({ content: '未检测到该地图 App，请先安装' });
      }
    }
  }, 1500);

  const handleVisible = () => {
    if (document.hidden) {
      clearTimeout(timer);
    }
  };
  document.addEventListener('visibilitychange', handleVisible, { once: true });

  // 触发跳转
  window.location.href = scheme;
}

export default function MapNavSheet({ visible, target, onClose }: Props) {
  const ios = isIOS();

  const open = (provider: 'amap' | 'baidu' | 'tencent' | 'apple') => {
    if (!target) return;
    const { name, address, lat, lng } = target;
    const fullAddress = address ? `${name} ${address}` : name;
    const encName = encodeURIComponent(name);
    const encAddr = encodeURIComponent(fullAddress);

    let scheme = '';
    let webFallback = '';
    switch (provider) {
      case 'amap':
        scheme = `iosamap://navi?sourceApplication=binihealth&poiname=${encName}&lat=${lat}&lon=${lng}&dev=0&style=2`;
        if (!ios) {
          // Android intent
          scheme = `androidamap://navi?sourceApplication=binihealth&poiname=${encName}&lat=${lat}&lon=${lng}&dev=0&style=2`;
        }
        webFallback = `https://uri.amap.com/marker?position=${lng},${lat}&name=${encName}&src=binihealth&coordinate=gaode`;
        break;
      case 'baidu':
        scheme = `baidumap://map/direction?destination=name:${encName}|latlng:${lat},${lng}&coord_type=gcj02&mode=driving`;
        webFallback = `https://api.map.baidu.com/marker?location=${lat},${lng}&title=${encName}&content=${encAddr}&output=html&coord_type=gcj02&src=binihealth`;
        break;
      case 'tencent':
        scheme = `qqmap://map/routeplan?type=drive&to=${encName}&tocoord=${lat},${lng}&referer=binihealth`;
        webFallback = `https://apis.map.qq.com/uri/v1/marker?marker=coord:${lat},${lng};title:${encName};addr:${encAddr}&referer=binihealth`;
        break;
      case 'apple':
        // Apple Maps 通用 URL，浏览器自动唤起
        scheme = `https://maps.apple.com/?q=${encName}&ll=${lat},${lng}`;
        break;
    }

    onClose();
    if (provider === 'apple') {
      window.location.href = scheme;
      return;
    }

    tryOpenScheme(scheme, () => {
      // 兜底跳到 Web 版地图
      if (webFallback) {
        window.open(webFallback, '_blank');
      }
    });
  };

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      bodyStyle={{
        borderTopLeftRadius: 12,
        borderTopRightRadius: 12,
        padding: '16px 0',
      }}
    >
      <div style={{ textAlign: 'center', fontWeight: 500, marginBottom: 12 }}>使用以下地图打开</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, padding: '0 16px' }}>
        <button
          onClick={() => open('amap')}
          style={btnStyle}
        >🟢 高德地图</button>
        <button
          onClick={() => open('baidu')}
          style={btnStyle}
        >🔵 百度地图</button>
        <button
          onClick={() => open('tencent')}
          style={btnStyle}
        >🟡 腾讯地图</button>
        {ios && (
          <button
            onClick={() => open('apple')}
            style={btnStyle}
          >⚪ 苹果地图</button>
        )}
      </div>
      <div
        onClick={onClose}
        style={{
          textAlign: 'center',
          marginTop: 16,
          padding: '12px 16px',
          color: '#999',
          borderTop: '1px solid #f5f5f5',
          cursor: 'pointer',
        }}
      >
        取消
      </div>
    </Popup>
  );
}

const btnStyle: React.CSSProperties = {
  padding: '12px 0',
  background: '#f5f5f5',
  border: 'none',
  borderRadius: 8,
  fontSize: 14,
  cursor: 'pointer',
};

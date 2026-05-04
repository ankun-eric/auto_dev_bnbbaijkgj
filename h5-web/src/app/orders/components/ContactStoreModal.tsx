'use client';

import { useEffect, useState } from 'react';
import { Mask, Toast } from 'antd-mobile';
import api from '@/lib/api';

interface ContactInfo {
  store_id: number;
  store_name: string;
  address?: string | null;
  contact_phone?: string | null;
  business_hours?: string | null;
  lat?: number | null;
  lng?: number | null;
}

interface Props {
  visible: boolean;
  storeId?: number | null;
  /** 兜底门店名（store contact 接口失败时展示）*/
  fallbackStoreName?: string | null;
  onClose: () => void;
}

/**
 * [核销订单过期+改期规则优化 v1.0]「联系商家」底部上滑弹窗。
 * 数据源严格来自 /api/stores/{id}/contact（门店管理-联系电话），
 * 不取商家总部电话；缺字段时按 PRD 异常处理。
 */
export default function ContactStoreModal({
  visible,
  storeId,
  fallbackStoreName,
  onClose,
}: Props) {
  const [info, setInfo] = useState<ContactInfo | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!visible || !storeId) return;
    let alive = true;
    setLoading(true);
    api
      .get(`/api/stores/${storeId}/contact`)
      .then((res: any) => {
        if (!alive) return;
        setInfo(res.data || res);
      })
      .catch(() => {
        if (!alive) return;
        setInfo(null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [visible, storeId]);

  const callPhone = (phone: string) => {
    if (!phone) {
      Toast.show({ content: '商家未提供联系方式' });
      return;
    }
    window.location.href = `tel:${phone}`;
  };

  const navigate = (lat?: number | null, lng?: number | null, name?: string) => {
    if (lat == null || lng == null) {
      Toast.show({ content: '门店未配置地理坐标' });
      return;
    }
    const url = `https://uri.amap.com/marker?position=${lng},${lat}&name=${encodeURIComponent(
      name || '门店',
    )}`;
    window.open(url, '_blank');
  };

  const showName = info?.store_name || fallbackStoreName || '门店';

  return (
    <Mask visible={visible} onMaskClick={onClose}>
      <div
        style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          background: '#fff',
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          padding: '16px 16px 24px',
          maxHeight: '80vh',
          overflow: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            width: 36,
            height: 4,
            background: '#e5e5e5',
            borderRadius: 2,
            margin: '0 auto 12px',
          }}
        />
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>联系商家</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: '#999' }}>加载中...</div>
        ) : (
          <>
            {/* 门店名 */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>门店</div>
              <div style={{ fontSize: 14, color: '#333', fontWeight: 500 }}>{showName}</div>
            </div>

            {/* 地址 + 导航 */}
            {info?.address ? (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 12,
                  padding: '8px 0',
                  borderTop: '1px solid #f0f0f0',
                }}
              >
                <div style={{ flex: 1, paddingRight: 12 }}>
                  <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>地址</div>
                  <div style={{ fontSize: 14, color: '#333' }}>{info.address}</div>
                </div>
                <div
                  onClick={() => navigate(info.lat, info.lng, info.store_name)}
                  style={{
                    background: '#52c41a15',
                    color: '#52c41a',
                    padding: '6px 14px',
                    borderRadius: 16,
                    fontSize: 12,
                    fontWeight: 600,
                    flexShrink: 0,
                  }}
                >
                  导航
                </div>
              </div>
            ) : null}

            {/* 联系电话 + 拨打 */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 16,
                padding: '8px 0',
                borderTop: '1px solid #f0f0f0',
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>联系电话</div>
                <div style={{ fontSize: 14, color: '#333', fontWeight: 500 }}>
                  {info?.contact_phone || '商家未提供联系方式'}
                </div>
              </div>
              {info?.contact_phone ? (
                <div
                  onClick={() => callPhone(info.contact_phone || '')}
                  style={{
                    background: '#52c41a',
                    color: '#fff',
                    padding: '6px 14px',
                    borderRadius: 16,
                    fontSize: 12,
                    fontWeight: 600,
                    flexShrink: 0,
                  }}
                >
                  拨打
                </div>
              ) : null}
            </div>

            <div
              style={{
                background: '#fafafa',
                color: '#999',
                fontSize: 12,
                padding: '10px 12px',
                borderRadius: 8,
                marginBottom: 16,
              }}
            >
              如有疑问可联系商家协商处理
            </div>

            <div
              onClick={onClose}
              style={{
                textAlign: 'center',
                background: '#f5f5f5',
                padding: '10px 0',
                borderRadius: 8,
                color: '#666',
              }}
            >
              关闭
            </div>
          </>
        )}
      </div>
    </Mask>
  );
}

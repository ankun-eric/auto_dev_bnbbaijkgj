'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';

/* ── 类型 & mock ── */

interface Address {
  id: number;
  name: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail: string;
  isDefault: boolean;
  tag?: '家' | '公司' | string;
}

const mockAddresses: Address[] = [
  {
    id: 1, name: '张三', phone: '138****6789',
    province: '广东省', city: '深圳市', district: '南山区',
    detail: '科技园南路88号创新大厦A座1601',
    isDefault: true, tag: '公司',
  },
  {
    id: 2, name: '张三', phone: '138****6789',
    province: '广东省', city: '深圳市', district: '福田区',
    detail: '梅林一村3栋502室',
    isDefault: false, tag: '家',
  },
  {
    id: 3, name: '李四', phone: '139****1234',
    province: '北京市', city: '北京市', district: '朝阳区',
    detail: '望京SOHO T3 2108',
    isDefault: false,
  },
];

/* ── 组件 ── */

export default function AddressPage() {
  const router = useRouter();
  const [addresses] = useState<Address[]>(mockAddresses);

  const handleAdd = useCallback(() => {
    router.push('/address/edit');
  }, [router]);

  const handleEdit = useCallback((id: number) => {
    router.push(`/address/edit?id=${id}`);
  }, [router]);

  return (
    <div style={{ minHeight: '100vh', background: '#F5F5F5', paddingBottom: 80 }}>
      {/* 顶栏 */}
      <div style={{
        display: 'flex', alignItems: 'center', height: 48, background: '#fff',
        borderBottom: '1px solid #F3F4F6', padding: '0 16px',
        paddingTop: 'env(safe-area-inset-top)',
      }}>
        <div onClick={() => router.back()} style={{ cursor: 'pointer', fontSize: 20, color: '#1F2937' }}>←</div>
        <div style={{ flex: 1, textAlign: 'center', fontSize: 17, fontWeight: 700, color: '#1F2937' }}>收货地址</div>
        <div style={{ width: 20 }} />
      </div>

      {/* 地址列表 */}
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {addresses.map((addr) => (
          <div
            key={addr.id}
            onClick={() => handleEdit(addr.id)}
            style={{
              background: addr.isDefault ? '#F0F9FF' : '#fff',
              borderRadius: 16,
              padding: '16px 16px 16px 20px',
              borderLeft: addr.isDefault ? '4px solid #0EA5E9' : 'none',
              border: addr.isDefault ? undefined : '1px solid #E5E7EB',
              cursor: 'pointer', position: 'relative',
            }}
          >
            {/* 标签行 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              {addr.isDefault && (
                <span style={{
                  background: '#0EA5E9', color: '#fff',
                  borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 500,
                }}>默认</span>
              )}
              {addr.tag && (
                <span style={{
                  background: '#F0F9FF', color: '#0284C7',
                  borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 500,
                }}>{addr.tag}</span>
              )}
            </div>

            {/* 姓名 & 电话 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
              <span style={{ fontSize: 15, fontWeight: 600, color: '#1F2937' }}>{addr.name}</span>
              <span style={{ fontSize: 14, color: '#6B7280' }}>{addr.phone}</span>
            </div>

            {/* 地址 */}
            <div style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.5 }}>
              {addr.province}{addr.city}{addr.district}{addr.detail}
            </div>

            {/* 编辑按钮 */}
            <div style={{
              position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)',
              fontSize: 14, color: '#9CA3AF',
            }}>
              ›
            </div>
          </div>
        ))}
      </div>

      {/* 底部按钮 */}
      <div style={{
        position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
        width: '100%', maxWidth: 750, background: '#fff',
        borderTop: '1px solid #E5E7EB',
        padding: '12px 16px calc(12px + env(safe-area-inset-bottom))',
      }}>
        <button
          type="button"
          onClick={handleAdd}
          style={{
            width: '100%', height: 48, borderRadius: 12, border: 'none',
            background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
            color: '#fff', fontSize: 16, fontWeight: 600, cursor: 'pointer',
          }}
        >
          新增收货地址
        </button>
      </div>
    </div>
  );
}

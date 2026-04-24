'use client';

// [2026-04-24] 移动端 - 员工管理 PRD §4.8

import React, { useEffect, useState } from 'react';
import { NavBar, List, Tag, Toast, Empty, Dialog, Switch, Button } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { getProfile, roleLabel } from '../mobile-lib';

export default function StaffMobilePage() {
  const router = useRouter();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const role = getProfile()?.role;

  const load = async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/v1/staff', { params: { page: 1, page_size: 100 } });
      setRows(res.items || res || []);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggleStatus = async (uid: number, to: boolean) => {
    try {
      await api.put(`/api/merchant/v1/staff/${uid}/status`, { is_active: to });
      Toast.show({ icon: 'success', content: to ? '已启用' : '已停用' });
      load();
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '操作失败' });
    }
  };

  const canEdit = role === 'owner' || role === 'store_manager';

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <NavBar
        onBack={() => router.back()}
        right={
          canEdit && (
            <span
              onClick={() =>
                Dialog.alert({
                  title: '提示',
                  content: '新增员工请使用电脑 PC 商家端操作。',
                })
              }
              style={{ color: '#52c41a', fontSize: 14 }}
            >
              + 新增
            </span>
          )
        }
      >
        员工管理
      </NavBar>

      <div style={{ padding: 12 }}>
        {rows.length === 0 ? (
          <Empty description={loading ? '加载中...' : '暂无员工'} />
        ) : (
          rows.map((s: any) => {
            const active = s.is_active !== false;
            return (
              <div
                key={s.id || s.user_id}
                style={{
                  background: '#fff',
                  borderRadius: 10,
                  padding: 14,
                  marginBottom: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: '50%',
                      background: '#52c41a22',
                      color: '#52c41a',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 18,
                      fontWeight: 600,
                    }}
                  >
                    {(s.nickname || s.name || '员')[0]}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>{s.nickname || s.name || '员工'}</div>
                    <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>
                      <Tag color="primary" fill="outline" style={{ marginRight: 6 }}>
                        {roleLabel[s.role] || s.role || '—'}
                      </Tag>
                      {s.phone_mask || s.phone || ''}
                    </div>
                  </div>
                  {canEdit && (
                    <Switch
                      checked={active}
                      onChange={(v) => toggleStatus(s.id || s.user_id, v)}
                    />
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

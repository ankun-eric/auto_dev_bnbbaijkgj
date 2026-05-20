'use client';
/**
 * [PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」V2 主页面。
 *
 * 设计要点（参考 PRD «健康档案-我的设备页面优化 v1.0»）：
 *
 * 区域一：我的设备（已绑定卡片网格）
 *   - 空状态显示引导卡片，CTA 平滑滚动到区域二
 *   - 卡片右上 ✎ 进入编辑抽屉；底部解绑触发二次确认
 *
 * 区域二：支持设备列表（5 品牌全部平铺）
 *   - 按 BRAND_ORDER 依次渲染：宾尼 / 华为 / 小米 / 苹果 / 其他
 *   - 按钮四态：未绑定/继续绑定/已绑定/敬请期待（由后端 catalog_id.bound_count + is_active / is_unique 推导）
 *
 * 全量样式遵循 AI-home 11 级天蓝色阶（#0EA5E9 系）。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import {
  bindDevice,
  editBinding,
  fetchCatalog,
  fetchMyDevices,
  unbindDevice,
  type BindPayload,
  type CatalogGroup,
  type CatalogItem,
  type EditBindingPayload,
  type MyDeviceItem,
} from '@/lib/api/devices';
import BrandSection from './components/BrandSection';
import MyDeviceCard from './components/MyDeviceCard';
import BindDeviceDrawer from './components/BindDeviceDrawer';
import EditDeviceDrawer from './components/EditDeviceDrawer';
import UnbindConfirmModal from './components/UnbindConfirmModal';
import { DV_COLOR } from './components/theme';

export default function DevicesPage() {
  const [myList, setMyList] = useState<MyDeviceItem[]>([]);
  const [groups, setGroups] = useState<CatalogGroup[]>([]);
  const [loading, setLoading] = useState(true);

  const [bindTarget, setBindTarget] = useState<CatalogItem | null>(null);
  const [editTarget, setEditTarget] = useState<MyDeviceItem | null>(null);
  const [unbindTarget, setUnbindTarget] = useState<MyDeviceItem | null>(null);
  const [unbindSubmitting, setUnbindSubmitting] = useState(false);

  const catalogAnchorRef = useRef<HTMLDivElement | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [my, cat] = await Promise.all([
        fetchMyDevices().catch(() => ({ items: [], total: 0 })),
        fetchCatalog().catch(() => ({ groups: [], total: 0 })),
      ]);
      setMyList(my.items || []);
      setGroups(cat.groups || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const empty = !loading && myList.length === 0;

  const scrollToCatalog = () => {
    if (catalogAnchorRef.current) {
      catalogAnchorRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleBindClick = (item: CatalogItem) => {
    setBindTarget(item);
  };

  const handleBindSubmit = async (payload: BindPayload) => {
    try {
      await bindDevice(payload);
      Toast.show({ icon: 'success', content: '绑定成功' });
      setBindTarget(null);
      await loadAll();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.response?.data?.message || e?.message || '绑定失败';
      Toast.show({ icon: 'fail', content: String(msg) });
    }
  };

  const handleEditSubmit = async (payload: EditBindingPayload) => {
    if (!editTarget) return;
    try {
      await editBinding(editTarget.id, payload);
      Toast.show({ icon: 'success', content: '已保存' });
      setEditTarget(null);
      await loadAll();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '保存失败';
      Toast.show({ icon: 'fail', content: String(msg) });
    }
  };

  const handleUnbindConfirm = async () => {
    if (!unbindTarget) return;
    setUnbindSubmitting(true);
    try {
      await unbindDevice(unbindTarget.id);
      Toast.show({ icon: 'success', content: '已解绑' });
      setUnbindTarget(null);
      await loadAll();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '解绑失败';
      Toast.show({ icon: 'fail', content: String(msg) });
    } finally {
      setUnbindSubmitting(false);
    }
  };

  const myDeviceCount = useMemo(() => myList.length, [myList]);

  return (
    <div style={{ background: DV_COLOR.brand50, minHeight: '100vh', paddingBottom: 32 }}>
      <GreenNavBar>我的设备</GreenNavBar>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* 区域一：我的设备 */}
        <section data-testid="bh-my-devices-section">
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              marginBottom: 10,
            }}
          >
            <h2 style={{ fontSize: 16, fontWeight: 600, color: DV_COLOR.textPrimary, margin: 0 }}>
              我的设备
            </h2>
            <span style={{ fontSize: 12, color: DV_COLOR.textSecondary }}>
              已绑定 {myDeviceCount} 台
            </span>
          </div>

          {loading ? (
            <div style={{
              background: '#fff', borderRadius: 16, padding: 32, textAlign: 'center',
              color: DV_COLOR.textSecondary, boxShadow: '0 2px 12px rgba(2,132,199,0.06)',
            }}>加载中…</div>
          ) : empty ? (
            <div
              data-testid="bh-my-devices-empty"
              style={{
                background: DV_COLOR.gradient,
                borderRadius: 16,
                padding: '28px 20px',
                color: '#fff',
                boxShadow: '0 6px 24px rgba(2,132,199,0.25)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 56, marginBottom: 8 }}>📱➕</div>
              <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>还没有绑定任何设备</div>
              <div style={{ fontSize: 13, opacity: 0.92, marginBottom: 16 }}>
                从下方选择支持的设备，开启智能健康监测
              </div>
              <button
                onClick={scrollToCatalog}
                data-testid="bh-my-devices-cta"
                style={{
                  background: '#fff',
                  color: DV_COLOR.brand600,
                  border: 'none',
                  padding: '10px 26px',
                  borderRadius: 22,
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  boxShadow: '0 4px 14px rgba(0,0,0,0.08)',
                }}
              >立即绑定 ↓</button>
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: 12,
              }}
            >
              {myList.map((it) => (
                <MyDeviceCard
                  key={it.id}
                  item={it}
                  onEdit={(x) => setEditTarget(x)}
                  onUnbind={(x) => setUnbindTarget(x)}
                />
              ))}
            </div>
          )}
        </section>

        {/* 区域二：支持设备列表 */}
        <section data-testid="bh-brand-catalog-section">
          <div ref={catalogAnchorRef} style={{ scrollMarginTop: 60 }} />
          <h2 style={{
            fontSize: 16, fontWeight: 600, color: DV_COLOR.textPrimary,
            margin: '4px 0 12px 0',
          }}>
            支持设备列表
          </h2>

          {loading && groups.length === 0 ? (
            <div style={{
              background: '#fff', borderRadius: 16, padding: 32, textAlign: 'center',
              color: DV_COLOR.textSecondary,
            }}>加载中…</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {groups.map((g) => (
                <BrandSection key={g.brand_code} group={g} onBind={handleBindClick} />
              ))}
              {groups.length === 0 && (
                <div style={{
                  background: '#fff', borderRadius: 16, padding: 24, textAlign: 'center',
                  color: DV_COLOR.textSecondary, fontSize: 13,
                }}>暂无可绑定设备</div>
              )}
            </div>
          )}
        </section>
      </div>

      <BindDeviceDrawer
        visible={!!bindTarget}
        catalog={bindTarget}
        onClose={() => setBindTarget(null)}
        onSubmit={handleBindSubmit}
      />

      <EditDeviceDrawer
        visible={!!editTarget}
        item={editTarget}
        onClose={() => setEditTarget(null)}
        onSubmit={handleEditSubmit}
      />

      <UnbindConfirmModal
        visible={!!unbindTarget}
        item={unbindTarget}
        submitting={unbindSubmitting}
        onCancel={() => setUnbindTarget(null)}
        onConfirm={handleUnbindConfirm}
      />
    </div>
  );
}

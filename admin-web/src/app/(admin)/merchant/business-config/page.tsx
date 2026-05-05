'use client';

/**
 * [2026-05-05 营业管理入口收敛 PRD v1.0 · N-01]
 * 老顶层菜单「商家营业时间+并发上限」已下线。本页保留为兼容跳转路由，
 * 直接引导用户回到门店列表，按门店进入新「营业管理」页配置。
 */

import React, { useEffect } from 'react';
import { Alert, Button, Result, Space } from 'antd';
import { useRouter } from 'next/navigation';

export default function LegacyBusinessConfigRedirect() {
  const router = useRouter();

  useEffect(() => {
    const t = setTimeout(() => router.replace('/merchant/stores'), 1500);
    return () => clearTimeout(t);
  }, [router]);

  return (
    <div style={{ padding: 24 }}>
      <Result
        status="info"
        title="入口已迁移"
        subTitle="「营业时间 + 并发上限」配置已收敛到「门店管理」列表行的「营业管理」按钮，按门店配置避免误改。"
        extra={
          <Space>
            <Button type="primary" onClick={() => router.replace('/merchant/stores')}>
              前往门店管理
            </Button>
          </Space>
        }
      />
      <Alert
        type="info"
        showIcon
        style={{ marginTop: 16 }}
        message="即将自动跳转到门店管理列表..."
      />
    </div>
  );
}

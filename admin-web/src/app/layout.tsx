'use client';

import './globals.css';
import React from 'react';
import { ConfigProvider, App as AntdApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <title>宾尼小康 - AI健康管家管理后台</title>
        <meta name="description" content="宾尼小康AI健康管家管理后台" />
      </head>
      <body>
        <ConfigProvider
          locale={zhCN}
          theme={{
            token: {
              colorPrimary: '#52c41a',
              colorInfo: '#13c2c2',
              borderRadius: 8,
              colorBgContainer: '#ffffff',
            },
            components: {
              Menu: {
                itemSelectedBg: '#f6ffed',
                itemSelectedColor: '#52c41a',
              },
              Button: {
                primaryShadow: '0 2px 0 rgba(82,196,26,0.1)',
              },
            },
          }}
        >
          <AntdApp>{children}</AntdApp>
        </ConfigProvider>
      </body>
    </html>
  );
}

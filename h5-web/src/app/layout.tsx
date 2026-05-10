'use client';

import './globals.css';
import ThemeBootstrap from './ThemeBootstrap';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <head>
        <meta charSet="utf-8" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, maximum-scale=1, minimum-scale=1, user-scalable=no, viewport-fit=cover"
        />
        <meta name="theme-color" content="#0EA5E9" />
        <title>宾尼小康 - AI健康管家</title>
        <meta name="description" content="宾尼小康 · 您的私人AI健康管家" />
      </head>
      <body>
        <ThemeBootstrap />
        {children}
      </body>
    </html>
  );
}

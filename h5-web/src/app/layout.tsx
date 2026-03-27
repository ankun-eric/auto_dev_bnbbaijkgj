'use client';

import './globals.css';

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
        <meta name="theme-color" content="#52c41a" />
        <title>宾尼小康 - AI健康管家</title>
        <meta name="description" content="宾尼小康AI健康管家，您的私人健康助手" />
      </head>
      <body>{children}</body>
    </html>
  );
}

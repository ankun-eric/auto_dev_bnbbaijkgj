/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || '',
  trailingSlash: true,
  typescript: {
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [];
  },
  // [2026-04-23 对话页统一化] 旧体检对话页路径 301 永久重定向到公共咨询页，外部/历史链接仍可访问
  async redirects() {
    return [
      {
        source: '/checkup/chat/:sid',
        destination: '/chat/:sid?type=report_interpret&auto_start=1',
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;

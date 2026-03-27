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
};

module.exports = nextConfig;

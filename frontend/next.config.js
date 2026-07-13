/** @type {import('next').NextConfig} */
const apiBase = process.env.BACKEND_URL || 'http://localhost:8000';

const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${apiBase}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow large video uploads to the route handler during local dev.
  experimental: {
    serverActions: { bodySizeLimit: "2gb" },
  },
};

export default nextConfig;

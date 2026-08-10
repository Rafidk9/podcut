/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export: the whole app is HTML/JS on Cloudflare Pages, which serves
  // static assets free and unmetered. There is no server -- the browser talks
  // to Supabase directly, so nothing here can time out mid-render.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;

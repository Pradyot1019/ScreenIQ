import type { NextConfig } from "next";

// In production the browser talks only to the Vercel domain, and Vercel forwards
// /api/* to the backend (API_ORIGIN, e.g. https://screeniq-api.onrender.com).
// Same origin means the httpOnly refresh cookie is a first-party cookie: browsers
// don't send SameSite cookies to a different site, so calling Render directly from
// a vercel.app page would silently break "stay logged in".
// Locally API_ORIGIN is unset and the app calls http://localhost:8000 directly.
const apiOrigin = process.env.API_ORIGIN;

const nextConfig: NextConfig = {
  async rewrites() {
    return apiOrigin ? [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }] : [];
  },
};

export default nextConfig;

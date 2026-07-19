import type { NextConfig } from "next";

// Static export for GitHub Pages. The app is already a pure renderer over a
// committed demo.json, so there is nothing dynamic to lose — no database, no
// API routes, no server-side env. basePath is the project-pages subpath.
const nextConfig: NextConfig = {
  output: "export",
  basePath: "/counterproof",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The renderer must never be blocked by a type or lint error in a sibling
  // component at 3am. Views are independently defensive; a bad shape degrades
  // to a placeholder rather than failing the build.
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;

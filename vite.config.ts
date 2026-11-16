import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // 正式建置(mode=production)排除本機示範模式,避免題庫答案進入公開的 bundle
  define: { __LOCAL_BACKEND__: JSON.stringify(mode !== "production") },
  test: { environment: "node" },
}));

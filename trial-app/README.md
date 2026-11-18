# 線代測驗 測試版(獨立專案,不連正式 la-daily-quiz / 正式 Supabase)
- 部署:Vercel 新專案,Root Directory = `trial-app`,Framework Preset = Other;資料庫用 Vercel Marketplace 的 Upstash Redis(自動帶入 KV_REST_API_URL / KV_REST_API_TOKEN)。
- 本機:`pip install -r requirements.txt pytest`;`python dev_server.py 8765`;測試 `python -m pytest tests -q`
- 沒有設定 Redis 時畫面會警告「資料會遺失」(Vercel 本機檔案不會保存)。
- 數學式使用 public/katex 內打包的 KaTeX,不依賴外部 CDN。
- 工程決策與試用發現的缺陷見 DECISIONS.md。

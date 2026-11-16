# 線代每日測驗(研究所線性代數)

手機優先(iPhone Safari)的每日五題測驗。React + TypeScript + Vite,預計部署到 Vercel。

## 目前進度:第一階段(已完成)

- 每日固定五題:3 題基礎觀念/舊錯題複習、1 題最新章節、1 題作業風格(同一天重新整理題目與選項順序不變)
- 點選 A/B/C/D 作答,每題可勾「不確定」
- **五題全部作答並提交後**才顯示答案與逐題解析(提交前沒有任何答案資訊)
- 記錄:日期、題目、觀念、對錯、信心(不確定)、錯誤類型(觀念/計算/粗心/猜的)
- 答錯 → 排定隔日、3 日、7 日複習;到期時優先出同觀念的「變式」(題庫有同觀念其他題就換題,沒有才用原題)
- 錯題本:錯題紀錄、正確率、複習排程
- 題庫驗證測試:每題恰有 1 個正確答案、選項不重複、解析不得用「選項 A」這類位置用語
- 題目來源標示:全部為「自編題」。`origin: "past-homework"` 必須附 `sourceRef`,否則測試會失敗,避免冒稱原題

資料暫存在手機瀏覽器的 localStorage(`src/lib/storage.ts` 是介面,第二階段換成 Supabase)。

## 開發

```bash
npm install
npm run dev        # 手機與電腦在同一個 Wi-Fi,用 Network 網址開
npm test           # 題庫驗證 + 選題/複習流程
npm run build
```

新增題目:編輯 `src/data/questions.ts`,跑 `npm test` 驗證。解題計算請先用程式(numpy)驗過再放進題庫。

## 第二階段(尚未實作)

1. 每日 AI 自動出題:Vercel Serverless Function 呼叫 Claude API(金鑰只放 Vercel 環境變數,不進前端);出題後必須通過「恰一個正確答案」驗證(結構檢查 + 要求模型給可程式驗證的解)才入庫,不通過就重出。
2. Supabase:Row Level Security 預設全拒絕,只開放登入使用者讀寫自己的列;題庫與答案欄位不對匿名用戶開放;service role key 僅在 Serverless Function 使用。
3. 每週弱點分析與最容易遺忘的十大觀念。

### 8:00 通知的可行性評估(以下是我依既有知識整理,實作前請對照 Apple/Vercel 最新文件)

| 方案 | 可行性 | 重點 |
|---|---|---|
| Web Push + 加到主畫面的 PWA | 可行 | iOS/iPadOS 16.4 以上,**只有「加入主畫面」的網頁 App 才能收推播**,在 Safari 分頁裡不行;權限要由使用者點按鈕觸發;需 VAPID 金鑰、service worker、Supabase 存訂閱資料 |
| 定時觸發 | 要注意 | Vercel Cron 在 Hobby 方案限制為每天一次,且執行時間只保證落在指定那個小時內,不保證 8:00 整;要準時需 Pro,或改用 Supabase `pg_cron` + Edge Function |
| iOS 捷徑「個人自動化」 | 最穩、零後端 | 每天 8:00 觸發 → 通知或直接開啟測驗網址;不依賴推播與主畫面 PWA |
| 行事曆週期事件 + 網址 | 最簡單 | 每天 8:00 提醒,點開網址進入 |

建議:第二階段先上「捷徑自動化」確保每天準時被提醒,再加 Web Push 作為升級。

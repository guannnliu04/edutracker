# 部署與設定(Supabase + Vercel)

## 1. Supabase

1. 到 supabase.com 建立專案。
2. **Authentication → Providers → Email**:保持啟用,並**關閉「Allow new users to sign up」**(單人系統,避免別人自行註冊)。
3. **Authentication → Users → Add user**:建立你自己的帳號(Email + 密碼,勾選 Auto Confirm)。
4. **SQL Editor** 依序貼上並執行:
   1. `supabase/migrations/0001_init.sql`(資料表、權限、評分函式)
   2. `supabase/seed.sql`(題庫與答案;改題庫後用 `npm run gen:seed` 重新產生,可重複執行)
5. **Project Settings → API**:複製 `Project URL` 與 `anon public` key。**不要**使用或外流 `service_role` key。

## 2. Vercel

1. 在 Vercel 匯入這個 GitHub 倉庫(Framework 會自動偵測為 Vite)。
2. **Settings → Environment Variables** 加入:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
3. Deploy。`vercel.json` 已設定好,`/quiz`、`/plan` 等網址重新整理或從通知點入都能正確開啟。

> 沒有設定這兩個變數的正式版會顯示「缺少設定」,不會退回本機模式 — 這是刻意的,避免題庫答案被打包進公開網頁。

## 3. 加到 iPhone 主畫面

用 **Safari** 開啟網址 → 分享 → **加入主畫面**。之後從主畫面圖示開啟,會是全螢幕 App 樣式,起始頁是當天測驗(`/quiz`)。

## 4. 每天 8:00 提醒(沿用 ChatGPT 自動化)

在 ChatGPT 建立每日 8:00 的排程任務,內容只要送出一則提醒與連結,例如:

> 早安!今天的線代五題測驗:https://你的網址.vercel.app/quiz

注意(iOS 行為,以你的實機為準):
- 從 ChatGPT 通知點開的連結通常會在 **Safari** 開啟,而不是已安裝的主畫面 App。
- Safari 和主畫面 App 的登入狀態是**分開**的,所以兩邊各需要登入一次(之後都會記住)。
- 若想每天都直接開主畫面 App,可改用 iOS「捷徑」個人自動化,在 8:00 開啟該 App。

網站自行發送通知(PWA Web Push)與 iOS 鎖定畫面小工具/Live Activity 留待系統穩定後再評估。

## 5. 本機開發

```bash
npm install
npm run dev          # 沒有設定 VITE_ 變數時自動使用「本機示範模式」(資料只存在瀏覽器)
npm test             # 前端邏輯測試
npm run test:db      # 資料庫權限與評分測試(需本機 postgresql-16 伺服器)
```

連到真正的 Supabase 開發時,複製 `.env.example` 成 `.env.local` 並填入。

## 安全重點(已由 `npm run test:db` 驗證)

- 正確答案與解析存在 `question_keys`,**前端角色完全無法讀取**;只有提交整份測驗後,才由 `submit_session` / `get_results` 回傳。
- 對錯由伺服器評分並寫入;前端不能寫 `attempts.correct` 或 `reviews`,提交後不能再改答案。
- 所有使用者資料都以 RLS 限定只能讀寫自己的列;`anon` 角色沒有任何權限。
- 題庫另有資料庫層檢查:每題恰有一個正確選項;標為「歷屆作業」必須附出處,否則一律是「自編題」。
- 已登入的你本人仍可自行建立測驗並提交來看到答案 — 這是單人系統,不屬於防護範圍。

## 6. 資料庫更新(第二批 SQL)

已經建好專案的人,到 Supabase **SQL Editor** 依序再執行這兩個檔案(各開一個 New query):
1. `supabase/migrations/0002_practice_logs.sql`(GPT 練習紀錄資料表)
2. `supabase/migrations/0003_lock_function_execute.sql`(收緊函式權限,讓匿名者連呼叫都不行)

## 7. 連接 ChatGPT

兩種方式,不依賴彼此:

### 方式 A:手動匯入(不需要 Actions,最簡單)
GPT 練習完後輸出 JSON(格式見 App「匯入」頁的範例)→ 複製 → 貼到 App 的「匯入」頁 → 按「驗證並匯入」。

### 方式 B:GPT 自動記錄(需要自訂 GPT 的 Actions 功能)
1. 在 Vercel → Settings → Environment Variables 新增三個變數(名稱**不要**以 `VITE_` 開頭):
   - `GPT_API_KEY`:自己產生一串至少 32 字的隨機字串(例如密碼管理員產生的)。**這串只貼在 Vercel 和 GPT 設定,不要貼到別處。**
   - `OWNER_EMAIL`、`OWNER_PASSWORD`:你在 Supabase 建立的那組登入帳密。伺服器用它以「你的身分」存取資料,因此不需要放權限更大的 Supabase secret key。
   - 三個都選 **Secret**,Environments 勾 Production。存好後 **Redeploy**。
2. ChatGPT → 建立 GPT → 設定 → Actions → 建立新動作:
   - Schema:貼 `docs/gpt/openapi.yaml` 全部內容
   - Authentication:選 **API Key** → **Bearer** → 貼上同一串 `GPT_API_KEY`
3. 指令欄位貼 `docs/gpt/GPT_INSTRUCTIONS.md`(把標示的地方換成你原本的規則)。
4. GPT 分享設定選 **只有我**。

### 注意
- GPT 記錄的對錯是 GPT 自己判斷,不像 App 內五題由資料庫評分;計算題請在指令裡要求它用 Python 驗算。
- `OWNER_PASSWORD` 放在 Vercel 環境變數代表:**Vercel 帳號被盜 = 你的資料被存取**,所以請替 Vercel、GitHub、Supabase 都開 2FA,並用強密碼。
- 這個 API 沒有做請求頻率限制;`GPT_API_KEY` 一旦外流,對方可以寫入假的練習紀錄並讀取你的弱點與最近錯題。懷疑外流時到 Vercel 換一串新的並 Redeploy,GPT 那邊也同步更新。

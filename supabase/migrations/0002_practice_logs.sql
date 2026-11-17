-- GPT 練習紀錄:ChatGPT 出題、你在 ChatGPT 作答後,由匯入頁或 /api/gpt/record 寫入。
-- 注意:這裡的對錯是 GPT 判定的(不像 App 內五題由資料庫評分),所以用另一張表,不與 attempts 混用。

create table public.practice_logs (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null default auth.uid() references auth.users (id) on delete cascade,
  date           date not null,
  concept        text not null check (length(concept) between 1 and 60),
  prompt         text not null check (length(prompt) between 1 and 2000),
  options        jsonb check (options is null or (jsonb_typeof(options) = 'array' and jsonb_array_length(options) between 2 and 6)),
  my_answer      text not null check (length(my_answer) between 1 and 500),
  correct_answer text not null check (length(correct_answer) between 1 and 500),
  correct        boolean not null,
  unsure         boolean not null default false,
  error_type     text check (error_type in ('concept', 'calculation', 'careless', 'guess')),
  explanation    text check (explanation is null or length(explanation) <= 4000),
  created_at     timestamptz not null default now(),
  -- 同一天同一題重複貼上不會重複計算
  prompt_hash    text generated always as (md5(prompt)) stored,
  unique (user_id, date, prompt_hash)
);
create index practice_logs_user_date on public.practice_logs (user_id, date);

alter table public.practice_logs enable row level security;

create policy practice_own_select on public.practice_logs for select to authenticated using (user_id = auth.uid());
create policy practice_own_insert on public.practice_logs for insert to authenticated with check (user_id = auth.uid());
create policy practice_own_update on public.practice_logs for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy practice_own_delete on public.practice_logs for delete to authenticated using (user_id = auth.uid());

revoke all on public.practice_logs from anon, authenticated;
grant select, delete on public.practice_logs to authenticated;
grant insert (date, concept, prompt, options, my_answer, correct_answer, correct, unsure, error_type, explanation)
  on public.practice_logs to authenticated;
grant update (error_type) on public.practice_logs to authenticated;

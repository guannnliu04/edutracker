-- 線代每日測驗:資料表、存取權限(RLS + 欄位權限)與伺服器端評分
-- 安全原則:
--   1. 正確答案與解析放在 question_keys,任何前端角色都不能直接讀取;
--      只有提交整份測驗後,透過 security definer 函式 submit_session / get_results 取得。
--   2. attempts(對錯紀錄)與 reviews(複習排程)只能由 submit_session 寫入,前端無法偽造或竄改。
--   3. 每個使用者只能看到自己的資料(RLS)。anon 角色完全沒有權限。
--   4. 這是單人使用的系統:請在 Supabase 後台關閉「Allow new users to sign up」。

create extension if not exists pgcrypto;

-- ───────── 題庫 ─────────
create table public.questions (
  id          text primary key,
  kind        text not null check (kind in ('basic', 'chapter', 'homework')),
  chapter     int  not null check (chapter between 1 and 20),
  concept_id  text not null,
  prompt      text not null,
  options     jsonb not null check (jsonb_typeof(options) = 'array' and jsonb_array_length(options) = 4),
  origin      text not null default 'self-authored' check (origin in ('self-authored', 'past-homework')),
  source_ref  text,
  active      boolean not null default true,
  -- 未取得原題時必須是自編題;標為歷屆作業就必須附出處
  constraint origin_needs_source check (origin <> 'past-homework' or source_ref is not null)
);

create table public.question_keys (
  question_id        text primary key references public.questions (id) on delete cascade,
  correct_option_id  text not null,
  explanation        text not null check (length(explanation) > 0)
);

-- 保證「恰有一個正確答案」:正確選項 id 必須存在於該題的選項中,且每題只有一列 key(主鍵)
create function public.check_question_key() returns trigger
language plpgsql as $$
begin
  if not exists (
    select 1
    from public.questions q, jsonb_array_elements(q.options) o
    where q.id = new.question_id and o ->> 'id' = new.correct_option_id
  ) then
    raise exception 'correct_option_id % is not an option of question %', new.correct_option_id, new.question_id;
  end if;
  if (select count(distinct o ->> 'id') from public.questions q, jsonb_array_elements(q.options) o where q.id = new.question_id) <> 4 then
    raise exception 'question % must have 4 distinct option ids', new.question_id;
  end if;
  return new;
end $$;

create trigger question_keys_check
  before insert or update on public.question_keys
  for each row execute function public.check_question_key();

-- ───────── 使用者資料 ─────────
create table public.settings (
  user_id         uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  current_chapter int not null default 7 check (current_chapter between 1 and 20)
);

create table public.sessions (
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  date         date not null,
  slots        jsonb not null check (jsonb_typeof(slots) = 'array'),
  draft        jsonb not null default '{}'::jsonb,
  submitted_at timestamptz,
  primary key (user_id, date)
);

create table public.attempts (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  date        date not null,
  question_id text not null references public.questions (id),
  concept_id  text not null,
  slot        text not null check (slot in ('review', 'basic', 'chapter', 'homework')),
  selected    text not null,
  correct     boolean not null,
  unsure      boolean not null default false,
  error_type  text check (error_type in ('concept', 'calculation', 'careless', 'guess')),
  unique (user_id, date, question_id)
);
create index attempts_user_date on public.attempts (user_id, date);

create table public.reviews (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null default auth.uid() references auth.users (id) on delete cascade,
  origin_question_id text not null references public.questions (id),
  concept_id         text not null,
  due_date           date not null,
  stage              int  not null check (stage in (1, 3, 7)),
  done               boolean not null default false
);
create index reviews_user_due on public.reviews (user_id, done, due_date);

create table public.study_tasks (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  date       date not null,
  title      text not null check (length(title) between 1 and 200),
  subject    text not null default '' check (length(subject) <= 50),
  minutes    int  not null default 0 check (minutes between 0 and 1440),
  done       boolean not null default false,
  created_at timestamptz not null default now()
);
create index study_tasks_user_date on public.study_tasks (user_id, date);

-- ───────── 列層級安全(RLS) ─────────
alter table public.questions     enable row level security;
alter table public.question_keys enable row level security;   -- 刻意不建立任何 policy:前端完全讀不到
alter table public.settings      enable row level security;
alter table public.sessions      enable row level security;
alter table public.attempts      enable row level security;
alter table public.reviews       enable row level security;
alter table public.study_tasks   enable row level security;

create policy questions_read on public.questions for select to authenticated using (active);

create policy settings_own_select on public.settings for select to authenticated using (user_id = auth.uid());
create policy settings_own_insert on public.settings for insert to authenticated with check (user_id = auth.uid());
create policy settings_own_update on public.settings for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy sessions_own_select on public.sessions for select to authenticated using (user_id = auth.uid());
create policy sessions_own_insert on public.sessions for insert to authenticated with check (user_id = auth.uid());
-- 提交後(submitted_at 不為空)不能再改答案
create policy sessions_own_update on public.sessions for update to authenticated
  using (user_id = auth.uid() and submitted_at is null) with check (user_id = auth.uid());

create policy attempts_own_select on public.attempts for select to authenticated using (user_id = auth.uid());
create policy attempts_own_update on public.attempts for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy reviews_own_select on public.reviews for select to authenticated using (user_id = auth.uid());

create policy tasks_own_select on public.study_tasks for select to authenticated using (user_id = auth.uid());
create policy tasks_own_insert on public.study_tasks for insert to authenticated with check (user_id = auth.uid());
create policy tasks_own_update on public.study_tasks for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy tasks_own_delete on public.study_tasks for delete to authenticated using (user_id = auth.uid());

-- ───────── 欄位層級權限(Supabase 預設會把新表開放給 anon/authenticated,先全部收回再逐項授權) ─────────
revoke all on all tables    in schema public from anon, authenticated;
revoke all on all functions in schema public from public, anon, authenticated;
grant usage on schema public to authenticated;

grant select on public.questions to authenticated;

grant select on public.settings to authenticated;
grant insert (current_chapter) on public.settings to authenticated;
grant update (current_chapter) on public.settings to authenticated;

grant select on public.sessions to authenticated;
grant insert (date, slots, draft) on public.sessions to authenticated;   -- 不能自己寫 submitted_at
grant update (draft) on public.sessions to authenticated;

grant select on public.attempts to authenticated;                        -- 不能寫入 correct,只能標錯誤類型
grant update (error_type) on public.attempts to authenticated;

grant select on public.reviews to authenticated;                         -- 只有 submit_session 能寫

grant select, delete on public.study_tasks to authenticated;
grant insert (date, title, subject, minutes) on public.study_tasks to authenticated;
grant update (title, subject, minutes, done) on public.study_tasks to authenticated;

-- ───────── 伺服器端評分 ─────────
create function public.get_results(p_date date) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not authenticated' using errcode = '28000'; end if;
  if not exists (select 1 from public.sessions where user_id = uid and date = p_date and submitted_at is not null) then
    raise exception 'quiz not submitted yet' using errcode = '42501';
  end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object(
      'attemptId', a.id,
      'questionId', a.question_id,
      'selected', a.selected,
      'correct', a.correct,
      'unsure', a.unsure,
      'errorType', a.error_type,
      'correctOptionId', k.correct_option_id,
      'explanation', k.explanation
    ) order by e.ord)
    from public.sessions s
    cross join lateral jsonb_array_elements(s.slots) with ordinality as e(slot, ord)
    join public.attempts a on a.user_id = uid and a.date = p_date and a.question_id = e.slot ->> 'questionId'
    join public.question_keys k on k.question_id = a.question_id
    where s.user_id = uid and s.date = p_date
  ), '[]'::jsonb);
end $$;

-- 錯題本:只有「自己提交過」的題目才能查看解析
create function public.get_key(p_question_id text) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not authenticated' using errcode = '28000'; end if;
  if not exists (select 1 from public.attempts where user_id = uid and question_id = p_question_id) then
    raise exception 'question not answered yet' using errcode = '42501';
  end if;
  return (select jsonb_build_object('correctOptionId', correct_option_id, 'explanation', explanation)
          from public.question_keys where question_id = p_question_id);
end $$;

create function public.submit_session(p_date date) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  uid  uuid := auth.uid();
  s    public.sessions%rowtype;
  sl   jsonb;
  qid  text;
  sel  text;
  cid  text;
  ok   boolean;
  k    text;
begin
  if uid is null then raise exception 'not authenticated' using errcode = '28000'; end if;

  select * into s from public.sessions where user_id = uid and date = p_date for update;
  if not found then raise exception 'session not found' using errcode = 'P0002'; end if;

  if s.submitted_at is null then
    -- 1) 每一題都必須已作答,且答案必須是該題的合法選項
    for sl in select * from jsonb_array_elements(s.slots) loop
      qid := sl ->> 'questionId';
      sel := s.draft -> qid ->> 'selected';
      if sel is null or not exists (
        select 1 from public.questions q, jsonb_array_elements(q.options) o
        where q.id = qid and o ->> 'id' = sel
      ) then
        raise exception 'all questions must be answered before submitting' using errcode = '22023';
      end if;
    end loop;

    -- 2) 伺服器端評分、記錄、排複習
    for sl in select * from jsonb_array_elements(s.slots) loop
      qid := sl ->> 'questionId';
      sel := s.draft -> qid ->> 'selected';
      select correct_option_id into k from public.question_keys where question_id = qid;
      select concept_id into cid from public.questions where id = qid;
      ok := (sel = k);

      insert into public.attempts (user_id, date, question_id, concept_id, slot, selected, correct, unsure)
      values (uid, p_date, qid, cid, sl ->> 'slot', sel, ok,
              coalesce((s.draft -> qid ->> 'unsure')::boolean, false))
      on conflict (user_id, date, question_id) do nothing;

      if sl ->> 'reviewId' is not null then
        update public.reviews set done = true
        where id = (sl ->> 'reviewId')::uuid and user_id = uid;
      end if;

      if not ok then
        -- 同觀念尚未完成的舊排程由新的取代;答錯後隔日、3 日、7 日複習
        delete from public.reviews where user_id = uid and concept_id = cid and not done;
        insert into public.reviews (user_id, origin_question_id, concept_id, due_date, stage)
        select uid, qid, cid, p_date + st, st from unnest(array[1, 3, 7]) as st;
      end if;
    end loop;

    update public.sessions set submitted_at = now() where user_id = uid and date = p_date;
  end if;

  return public.get_results(p_date);
end $$;

grant execute on function public.get_results(date)   to authenticated;
grant execute on function public.get_key(text)       to authenticated;
grant execute on function public.submit_session(date) to authenticated;

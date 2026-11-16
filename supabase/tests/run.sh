#!/usr/bin/env bash
# 在臨時 Postgres 上驗證 migration 的權限與評分邏輯(以 Supabase 的 auth.uid()/角色模型模擬)
# 需要 postgresql-16 伺服器。以 root 執行時會切換成 postgres 使用者啟動叢集。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN=/usr/lib/postgresql/16/bin
PORT=54329
BASE=/var/lib/postgresql
D="$(mktemp -d "$BASE/pgtest.XXXXXX")"
[ "$(id -u)" = 0 ] && chown postgres "$D" && AS="su postgres -c" || AS="bash -c"
cleanup() { $AS "$BIN/pg_ctl -D $D -m immediate stop" >/dev/null 2>&1; rm -rf "$D"; }
trap cleanup EXIT

$AS "$BIN/initdb -D $D -A trust -U postgres" >/dev/null || exit 1
$AS "$BIN/pg_ctl -D $D -o \"-p $PORT -k $D -c listen_addresses=''\" -w start" >/dev/null || exit 1
export PGHOST="$D" PGPORT="$PORT" PGUSER=postgres

psql_q() { psql -X -q -t -A -v ON_ERROR_STOP=1 "$@"; }
psql_q -d postgres -c "create database t" || exit 1
export PGDATABASE=t

# Supabase 提供的 auth schema / 角色的最小替身
psql_q <<'SQL' || exit 1
create role anon nologin; create role authenticated nologin;
create schema auth;
create table auth.users (id uuid primary key);
create function auth.uid() returns uuid language sql stable as
  $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
insert into auth.users values ('11111111-1111-1111-1111-111111111111'), ('22222222-2222-2222-2222-222222222222');
SQL
psql_q -f "$ROOT/supabase/migrations/0001_init.sql" >/dev/null || exit 1
psql_q -f "$ROOT/supabase/seed.sql" >/dev/null || exit 1

A=11111111-1111-1111-1111-111111111111
B=22222222-2222-2222-2222-222222222222
PASS=0; FAIL=0
as_user() { local u=$1; shift; psql_q -c "set role authenticated" -c "set request.jwt.claim.sub = '$u'" -c "$*" 2>&1; }
as_admin() { psql_q -c "$*" 2>&1; }
as_anon()  { psql_q -c "set role anon" -c "$*" 2>&1; }
ok()   { PASS=$((PASS+1)); echo "  ok   $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  FAIL $1"; echo "       $2"; }
expect_eq()  { local out; out=$("${@:3}"); [ "$out" = "$2" ] && ok "$1" || bad "$1" "expected '$2' got '$out'"; }
expect_err() { local out; out=$("${@:3}"); echo "$out" | grep -qi -- "$2" && ok "$1" || bad "$1" "expected error /$2/ got '$out'"; }

D1=2026-11-16; D2=2026-11-17
SLOTS='[{"questionId":"b01","slot":"basic"},{"questionId":"b02","slot":"basic"},{"questionId":"b03","slot":"basic"},{"questionId":"c01","slot":"chapter"},{"questionId":"h01","slot":"homework"}]'
PARTIAL='{"b01":{"selected":"o2","unsure":true}}'
WRONG='{"b01":{"selected":"o2","unsure":true},"b02":{"selected":"o2","unsure":false},"b03":{"selected":"o2","unsure":false},"c01":{"selected":"o2","unsure":false},"h01":{"selected":"o2","unsure":false}}'

echo "權限"
expect_err "anon 讀不到題庫" "permission denied" as_anon "select * from public.questions"
expect_eq  "登入者讀得到 20 題" 20 as_user $A "select count(*) from public.questions"
expect_eq  "題目選項不含 isCorrect" 0 as_user $A "select count(*) from public.questions where options::text like '%isCorrect%'"
expect_err "讀不到 question_keys" "permission denied" as_user $A "select * from public.question_keys"
expect_err "不能直接寫 attempts" "permission denied" as_user $A "insert into public.attempts (date,question_id,concept_id,slot,selected,correct) values ('$D1','b01','x','basic','o1',true)"
expect_err "不能直接寫 reviews" "permission denied" as_user $A "insert into public.reviews (origin_question_id,concept_id,due_date,stage) values ('b01','x','$D1',1)"
expect_err "不能自填 submitted_at" "permission denied" as_user $A "insert into public.sessions (date,slots,submitted_at) values ('$D1','[]',now())"

echo "提交流程"
as_user $A "insert into public.sessions (date,slots,draft) values ('$D1','$SLOTS','$PARTIAL')" >/dev/null
expect_err "提交前不能取得解析" "not submitted" as_user $A "select public.get_results('$D1')"
expect_err "未全部作答不能提交" "must be answered" as_user $A "select public.submit_session('$D1')"
as_user $A "update public.sessions set draft = '$WRONG' where date = '$D1'" >/dev/null
expect_eq  "提交後回傳 5 題結果" 5 as_user $A "select jsonb_array_length(public.submit_session('$D1'))"
expect_eq  "全錯 → 答對 0 題" 0 as_user $A "select count(*) from public.attempts where correct"
expect_eq  "記錄 5 筆作答" 5 as_user $A "select count(*) from public.attempts"
expect_eq  "不確定被記錄" 1 as_user $A "select count(*) from public.attempts where unsure"
expect_eq  "排定複習(同觀念舊排程被取代,共 12 筆)" 12 as_user $A "select count(*) from public.reviews"
expect_eq  "隔日/3日/7日 都有" "1,3,7" as_user $A "select string_agg(distinct stage::text, ',' order by stage::text) from public.reviews"
expect_eq  "提交後解析可取得" o1 as_user $A "select (public.get_results('$D1') -> 0 ->> 'correctOptionId')"
expect_eq  "提交後不能再改答案" 0 as_user $A "with u as (update public.sessions set draft = '{}' where date = '$D1' returning 1) select count(*) from u"
as_user $A "select public.submit_session('$D1')" >/dev/null
expect_eq  "重複提交不會重複記錄(作答)" 5 as_user $A "select count(*) from public.attempts where date = '$D1'"
expect_eq  "重複提交不會重複記錄(複習)" 12 as_user $A "select count(*) from public.reviews"

echo "隔離與竄改"
expect_eq  "B 看不到 A 的作答" 0 as_user $B "select count(*) from public.attempts"
expect_err "B 取不到 A 那天的解析" "not submitted" as_user $B "select public.get_results('$D1')"
expect_err "不能竄改 correct" "permission denied" as_user $A "update public.attempts set correct = true"
expect_eq  "可標錯誤類型" 5 as_user $A "with u as (update public.attempts set error_type = 'concept' returning 1) select count(*) from u"
expect_err "不能改複習排程" "permission denied" as_user $A "update public.reviews set done = true"
expect_eq  "答過的題可看解析" o1 as_user $A "select public.get_key('b01') ->> 'correctOptionId'"
expect_err "沒答過的題看不到解析" "not answered" as_user $A "select public.get_key('b04')"

echo "複習完成"
RID=$(as_user $A "select id from public.reviews where concept_id = 'linear-system' and stage = 1")
as_user $A "insert into public.sessions (date,slots,draft) values ('$D2','[{\"questionId\":\"b01\",\"slot\":\"review\",\"reviewId\":\"$RID\"}]','{\"b01\":{\"selected\":\"o1\",\"unsure\":false}}')" >/dev/null
expect_eq  "答對複習題 → 提交成功" 1 as_user $A "select jsonb_array_length(public.submit_session('$D2'))"
expect_eq  "該複習標記完成,不新增排程" "1|12" as_user $A "select (select count(*) from public.reviews where id = '$RID' and done) || '|' || (select count(*) from public.reviews)"

echo "題庫完整性(以管理者身分)"
expect_err "正確選項必須存在於選項中" "not an option" as_admin "update public.question_keys set correct_option_id = 'zzz' where question_id = 'b01'"
expect_err "歷屆作業必須附出處" "origin_needs_source" as_admin "insert into public.questions (id,kind,chapter,concept_id,prompt,options,origin) values ('x','basic',1,'c','p','[{\"id\":\"a\"},{\"id\":\"b\"},{\"id\":\"c\"},{\"id\":\"d\"}]','past-homework')"

echo; echo "通過 $PASS,失敗 $FAIL"
[ "$FAIL" = 0 ]

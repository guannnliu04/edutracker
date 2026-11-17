-- 0001 是先收回權限、後建立函式,所以新函式會沿用預設的「所有人可執行」(Supabase 預設也會開給 anon)。
-- 函式內部本來就會檢查登入(未登入一律報錯),不會洩漏資料,但沒必要讓匿名者碰得到,這裡補收緊。
revoke execute on function public.submit_session(date) from public, anon;
revoke execute on function public.get_results(date)    from public, anon;
revoke execute on function public.get_key(text)        from public, anon;
revoke execute on function public.check_question_key() from public, anon, authenticated;

grant execute on function public.submit_session(date) to authenticated;
grant execute on function public.get_results(date)    to authenticated;
grant execute on function public.get_key(text)        to authenticated;

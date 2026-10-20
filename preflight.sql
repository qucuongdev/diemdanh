-- READ ONLY. Run in a trusted Supabase SQL Editor session before deployment.
-- Returns structure and counts, never passwords, tokens or employee rows.
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public' AND tablename IN (
    'branches','profiles','allowed_devices','shifts','schedules',
    'attendance','leave_requests','attendance_proofs'
) ORDER BY tablename;

SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public' AND routine_name IN (
    'rpc_client_version','rpc_create_user','rpc_update_user','rpc_delete_user',
    'rpc_check_in','rpc_check_out'
) ORDER BY routine_name;

SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'auth' AND table_name = 'identities'
AND column_name IN ('id', 'provider_id') ORDER BY column_name;

-- If there are no public tables yet, apply the initial schema first.
-- Resolve any nonzero conflict counts manually before applying migrations.
SELECT 'extra_admins' AS issue, greatest(count(*) - 1, 0) AS conflicts
FROM public.profiles WHERE role = 'admin'
UNION ALL
SELECT 'duplicate_active_managers', count(*) FROM (
    SELECT branch_id FROM public.profiles WHERE role = 'storemanager' AND is_active IS TRUE
    GROUP BY branch_id HAVING count(*) > 1
) conflicts
UNION ALL
SELECT 'active_employees_without_branch', count(*) FROM public.profiles
WHERE role <> 'admin' AND is_active IS TRUE AND branch_id IS NULL
UNION ALL
SELECT 'profiles_missing_email_identity', count(*) FROM public.profiles p
JOIN auth.users u ON u.id = p.id
WHERE u.email IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM auth.identities i WHERE i.user_id = p.id AND i.provider = 'email'
);

SELECT tablename, policyname, cmd FROM pg_policies
WHERE schemaname = 'public' AND tablename IN ('profiles', 'shifts')
ORDER BY tablename, policyname;

SELECT policyname, cmd FROM pg_policies
WHERE schemaname = 'storage' AND tablename = 'objects' ORDER BY policyname;

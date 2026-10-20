-- Apply after migrations 01, 02 and 03. Review preflight.sql and README first.
-- No records are backfilled or deleted. Conflicting administrators abort this transaction.
BEGIN;

-- Migration 01 removed every shifts policy but did not restore scoped access.
DROP POLICY IF EXISTS shifts_read ON public.shifts;
DROP POLICY IF EXISTS shifts_manage ON public.shifts;
CREATE POLICY shifts_read ON public.shifts FOR SELECT TO authenticated USING (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() IS NOT NULL AND branch_id = public.get_current_branch_id())
);
CREATE POLICY shifts_manage ON public.shifts FOR ALL TO authenticated USING (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id())
) WITH CHECK (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id())
);

-- Profile writes belong to authorized RPCs, which run as their trusted owner.
-- profiles_read still permits self-read and scoped administrative read access.
DROP POLICY IF EXISTS profiles_admin ON public.profiles;
CREATE UNIQUE INDEX IF NOT EXISTS profiles_one_admin ON public.profiles(role) WHERE role = 'admin';

-- Changing a shift must not reinterpret already recorded attendance.
CREATE OR REPLACE FUNCTION public.guard_recorded_shift()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF (NEW.branch_id, NEW.start_time, NEW.end_time) IS DISTINCT FROM
       (OLD.branch_id, OLD.start_time, OLD.end_time) AND EXISTS (
        SELECT 1 FROM public.schedules s JOIN public.attendance a ON a.schedule_id = s.id
        WHERE s.shift_id = OLD.id
    ) THEN
        RAISE EXCEPTION 'Recorded shift times cannot be changed; create a new shift';
    END IF;
    IF NEW.branch_id IS DISTINCT FROM OLD.branch_id AND EXISTS (
        SELECT 1 FROM public.schedules WHERE shift_id = OLD.id
    ) THEN
        RAISE EXCEPTION 'Assigned shifts cannot change branch';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS guard_recorded_shift ON public.shifts;
CREATE TRIGGER guard_recorded_shift BEFORE UPDATE ON public.shifts
FOR EACH ROW EXECUTE FUNCTION public.guard_recorded_shift();
REVOKE ALL ON FUNCTION public.guard_recorded_shift() FROM PUBLIC, anon;

-- TIMESTAMPTZ defaults store instants; converting to a naive local timestamp
-- before assignment would shift values when the database session uses UTC.
ALTER TABLE public.branches ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.profiles ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.allowed_devices ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.shifts ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.schedules ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.attendance ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.leave_requests ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.attendance_proofs ALTER COLUMN created_at SET DEFAULT now();

-- Keep the existing admin-only interface, but make Auth + identity + profile
-- atomic. Never report success after swallowing an auth.identities failure.
-- Requires modern Supabase Auth: identities.id uuid and provider_id text.
CREATE OR REPLACE FUNCTION public.rpc_create_user(
    p_email text, p_password text, p_full_name text, p_role text,
    p_branch_id uuid, p_phone text
)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, auth, extensions AS $$
DECLARE
    v_id uuid := gen_random_uuid();
    v_email text := lower(trim(p_email));
BEGIN
    IF public.get_current_role() IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'Chỉ có Admin mới có quyền tạo tài khoản nhân viên.';
    END IF;
    IF p_role IS NULL OR p_role NOT IN ('staff', 'storemanager') OR
       p_full_name IS NULL OR length(trim(p_full_name)) = 0 OR
       p_branch_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.branches WHERE id = p_branch_id) OR
       p_password IS NULL OR length(p_password) < 12 OR octet_length(p_password) > 72 OR
       v_email IS NULL OR v_email !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' THEN
        RAISE EXCEPTION 'Invalid employee details';
    END IF;
    IF p_role = 'storemanager' AND EXISTS (
        SELECT 1 FROM public.profiles WHERE branch_id = p_branch_id
        AND role = 'storemanager' AND is_active IS TRUE
    ) THEN
        RAISE EXCEPTION 'Chi nhánh này đã có Cửa hàng trưởng.';
    END IF;
    IF EXISTS (SELECT 1 FROM auth.users WHERE lower(email) = v_email) THEN
        RAISE EXCEPTION 'Email đã tồn tại trong hệ thống.';
    END IF;
    INSERT INTO auth.users (
        instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
        raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
        confirmation_token, recovery_token, email_change_token_new, email_change,
        email_change_token_current, phone_change, phone_change_token, reauthentication_token,
        is_super_admin
    ) VALUES (
        '00000000-0000-0000-0000-000000000000', v_id, 'authenticated', 'authenticated',
        v_email, crypt(p_password, gen_salt('bf')), now(),
        '{"provider":"email","providers":["email"]}'::jsonb,
        jsonb_build_object('full_name', trim(p_full_name)), now(), now(),
        '', '', '', '', '', '', '', '', false
    );
    INSERT INTO auth.identities (
        id, user_id, identity_data, provider, provider_id, created_at, updated_at
    ) VALUES (
        v_id, v_id, jsonb_build_object('sub', v_id::text, 'email', v_email, 'email_verified', true),
        'email', v_id::text, now(), now()
    );
    INSERT INTO public.profiles(id, branch_id, full_name, role, phone, is_active)
    VALUES (v_id, p_branch_id, trim(p_full_name), p_role, nullif(trim(p_phone), ''), true);
    RETURN jsonb_build_object('success', true, 'user_id', v_id, 'message', 'Đã tạo tài khoản nhân viên.');
END $$;
REVOKE ALL ON FUNCTION public.rpc_create_user(text,text,text,text,uuid,text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.rpc_create_user(text,text,text,text,uuid,text) TO authenticated;

-- Version is published only when this entire migration has committed.
CREATE OR REPLACE FUNCTION public.rpc_client_version()
RETURNS integer LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT CASE WHEN public.get_current_role() IS NOT NULL THEN 3 ELSE NULL END $$;
REVOKE ALL ON FUNCTION public.rpc_client_version() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.rpc_client_version() TO authenticated;
NOTIFY pgrst, 'reload schema';
COMMIT;

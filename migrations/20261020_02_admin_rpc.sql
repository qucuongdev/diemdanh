BEGIN;
-- ==============================================================================
-- NÂNG CẤP HỆ THỐNG: CÁC HÀM QUẢN TRỊ NHÂN VIÊN (ADMIN ONLY)
-- Hướng dẫn: Chạy qua CLI terminal: python migrate.py -f update_admin_rpc.sql
-- ==============================================================================

-- Bật extension pgcrypto (hỗ trợ mã hóa mật khẩu bcrypt / gen_salt)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. HÀM TẠO NHÂN VIÊN MỚI (CHỈ TẠO STAFF HOẶC STOREMANAGER, DUY NHẤT 1 SM/CHI NHÁNH)
CREATE OR REPLACE FUNCTION public.rpc_create_user(
    p_email TEXT,
    p_password TEXT,
    p_full_name TEXT,
    p_role TEXT,
    p_branch_id UUID,
    p_phone TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
DECLARE
    v_caller_role TEXT;
    v_new_id UUID := gen_random_uuid();
    v_encrypted_pw TEXT;
    v_existing_sm RECORD;
BEGIN
    -- Chỉ Admin mới được quyền tạo tài khoản
    SELECT role INTO v_caller_role FROM public.profiles WHERE id = auth.uid() AND is_active IS TRUE;
    IF v_caller_role IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'Chỉ có Chủ chuỗi (Admin) mới có quyền tạo tài khoản nhân viên mới!';
    END IF;

    -- RÀNG BUỘC 1: Chỉ cho phép tạo 'staff' hoặc 'storemanager' (chỉ duy nhất 1 Admin)
    IF p_role IS NULL OR p_role NOT IN ('staff', 'storemanager') THEN
        RAISE EXCEPTION 'Hệ thống chỉ duy nhất có 1 tài khoản Admin tối cao! Bạn chỉ được tạo nhân viên với quyền Dược sĩ (staff) hoặc Quản lý (storemanager).';
    END IF;

    IF p_branch_id IS NULL OR length(trim(p_full_name)) = 0 OR p_full_name IS NULL
       OR p_password IS NULL OR length(p_password) < 12 OR octet_length(p_password) > 72
       OR p_email IS NULL OR position('@' IN p_email) < 2 THEN
        RAISE EXCEPTION 'Invalid employee details';
    END IF;

    -- RÀNG BUỘC 2: Mỗi chi nhánh chỉ được có tối đa 1 Cửa hàng trưởng (Store Manager)
    IF p_role = 'storemanager' THEN
        IF p_branch_id IS NULL THEN
            RAISE EXCEPTION 'Cửa hàng trưởng bắt buộc phải được gán vào một Chi nhánh cụ thể!';
        END IF;

        SELECT full_name INTO v_existing_sm
        FROM public.profiles
        WHERE branch_id = p_branch_id AND role = 'storemanager' AND is_active = TRUE
        LIMIT 1;

        IF v_existing_sm.full_name IS NOT NULL THEN
            RAISE EXCEPTION 'Chi nhánh này đã có Cửa hàng trưởng là "%"! Mỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý.', v_existing_sm.full_name;
        END IF;
    END IF;

    -- Kiểm tra trùng email
    IF EXISTS (SELECT 1 FROM auth.users WHERE email = p_email) THEN
        RAISE EXCEPTION 'Email "%" đã tồn tại trong hệ thống! Vui lòng chọn email khác.', p_email;
    END IF;

    -- Mã hóa mật khẩu an toàn chuẩn bcrypt (hỗ trợ cả extensions và public schema)
    BEGIN
        v_encrypted_pw := crypt(p_password, gen_salt('bf'));
    EXCEPTION WHEN OTHERS THEN
        v_encrypted_pw := extensions.crypt(p_password, extensions.gen_salt('bf'));
    END;

    -- Tạo tài khoản Auth
    INSERT INTO auth.users (
        instance_id,
        id,
        aud,
        role,
        email,
        encrypted_password,
        email_confirmed_at,
        raw_app_meta_data,
        raw_user_meta_data,
        created_at,
        updated_at,
        confirmation_token,
        recovery_token,
        email_change_token_new,
        email_change,
        email_change_token_current,
        phone_change,
        phone_change_token,
        reauthentication_token,
        is_super_admin
    )
    VALUES (
        '00000000-0000-0000-0000-000000000000',
        v_new_id,
        'authenticated',
        'authenticated',
        p_email,
        v_encrypted_pw,
        timezone('Asia/Ho_Chi_Minh', now()),
        '{"provider":"email","providers":["email"]}',
        jsonb_build_object('full_name', p_full_name),
        timezone('Asia/Ho_Chi_Minh', now()),
        timezone('Asia/Ho_Chi_Minh', now()),
        '', '', '', '', '', '', '', '', FALSE
    );

    -- Tạo Profile
    INSERT INTO public.profiles (
        id,
        branch_id,
        full_name,
        role,
        phone,
        is_active
    )
    VALUES (
        v_new_id,
        p_branch_id,
        p_full_name,
        p_role,
        p_phone,
        TRUE
    );

    -- Tạo Identity
    BEGIN
        INSERT INTO auth.identities (
            id,
            user_id,
            identity_data,
            provider,
            provider_id,
            last_sign_in_at,
            created_at,
            updated_at
        )
        VALUES (
            v_new_id::text,
            v_new_id,
            jsonb_build_object('sub', v_new_id::text, 'email', p_email),
            'email',
            v_new_id::text,
            timezone('Asia/Ho_Chi_Minh', now()),
            timezone('Asia/Ho_Chi_Minh', now()),
            timezone('Asia/Ho_Chi_Minh', now())
        );
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;

    RETURN jsonb_build_object(
        'success', TRUE,
        'user_id', v_new_id,
        'message', format('Đã tạo thành công tài khoản cho %s!', p_full_name)
    );
END;
$$;

-- 2. HÀM CẬP NHẬT THÔNG TIN NHÂN VIÊN VÀ PHÂN QUYỀN
CREATE OR REPLACE FUNCTION public.rpc_update_user(
    p_user_id UUID,
    p_full_name TEXT,
    p_role TEXT,
    p_branch_id UUID,
    p_phone TEXT,
    p_is_active BOOLEAN
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
DECLARE
    v_caller_role TEXT;
    v_old_role TEXT;
    v_existing_sm RECORD;
BEGIN
    SELECT role INTO v_caller_role FROM public.profiles WHERE id = auth.uid() AND is_active IS TRUE;
    IF v_caller_role IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'Chỉ có Admin mới có quyền cập nhật phân quyền nhân sự!';
    END IF;

    SELECT role INTO v_old_role FROM public.profiles WHERE id = p_user_id;

    -- Không cho phép tước quyền của tài khoản Admin tối cao
    IF v_old_role = 'admin' AND p_role != 'admin' THEN
        RAISE EXCEPTION 'Không thể hạ quyền của tài khoản Admin tối cao của hệ thống!';
    END IF;

    -- Không cho phép nâng user khác lên Admin
    IF v_old_role != 'admin' AND p_role = 'admin' THEN
        RAISE EXCEPTION 'Hệ thống chỉ duy nhất có 1 tài khoản Admin!';
    END IF;

    IF v_old_role IS NULL OR p_role IS NULL OR p_full_name IS NULL OR length(trim(p_full_name)) = 0
       OR p_is_active IS NULL OR (p_role <> 'admin' AND p_branch_id IS NULL) THEN
        RAISE EXCEPTION 'Invalid employee details';
    END IF;

    -- Kiểm tra ràng buộc duy nhất 1 Store Manager / Chi nhánh
    IF p_role = 'storemanager' AND p_branch_id IS NOT NULL THEN
        SELECT full_name INTO v_existing_sm
        FROM public.profiles
        WHERE branch_id = p_branch_id 
          AND role = 'storemanager' 
          AND id != p_user_id 
          AND is_active = TRUE
        LIMIT 1;

        IF v_existing_sm.full_name IS NOT NULL THEN
            RAISE EXCEPTION 'Chi nhánh này đã có Cửa hàng trưởng là "%"! Mỗi chi nhánh chỉ được phép có duy nhất 1 Quản lý.', v_existing_sm.full_name;
        END IF;
    END IF;

    UPDATE public.profiles
    SET full_name = p_full_name,
        role = p_role,
        branch_id = p_branch_id,
        phone = p_phone,
        is_active = p_is_active
    WHERE id = p_user_id;

    RETURN jsonb_build_object('success', TRUE, 'message', 'Đã cập nhật thông tin nhân sự thành công!');
END;
$$;

-- 3. HÀM XÓA TÀI KHOẢN NHÂN VIÊN
CREATE OR REPLACE FUNCTION public.rpc_delete_user(p_user_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
DECLARE
    v_caller_role TEXT;
    v_target_role TEXT;
BEGIN
    SELECT role INTO v_caller_role FROM public.profiles WHERE id = auth.uid() AND is_active IS TRUE;
    IF v_caller_role IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'Chỉ có Admin mới có quyền xóa tài khoản nhân viên!';
    END IF;

    SELECT role INTO v_target_role FROM public.profiles WHERE id = p_user_id;
    IF v_target_role = 'admin' THEN
        RAISE EXCEPTION 'Không thể xóa tài khoản Admin tối cao của hệ thống!';
    END IF;

    -- Xóa trong auth.users (cascade sang profiles, attendance, schedules, etc.)
    DELETE FROM auth.users WHERE id = p_user_id;

    RETURN jsonb_build_object('success', TRUE, 'message', 'Đã xóa tài khoản nhân sự thành công!');
END;
$$;

-- Explicitly deny anonymous invocation of SECURITY DEFINER account functions.
REVOKE ALL ON FUNCTION public.rpc_create_user(text,text,text,text,uuid,text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.rpc_update_user(uuid,text,text,uuid,text,boolean) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.rpc_delete_user(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.rpc_create_user(text,text,text,text,uuid,text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_update_user(uuid,text,text,uuid,text,boolean) TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_delete_user(uuid) TO authenticated;

COMMIT;

-- ==============================================================================
-- HỆ THỐNG QUẢN LÝ CHẤM CÔNG CHUỖI NHÀ THUỐC
-- DATABASE SCHEMA, RLS POLICIES, STORAGE & RPC FUNCTIONS CHO SUPABASE
-- ==============================================================================

-- 1. BẬT TIỆN ÍCH MỞ RỘNG (EXTENSIONS)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 2. TẠO CÁC BẢNG DỮ LIỆU (TABLES)
-- ==============================================================================

-- Bảng 2.1: Chi nhánh nhà thuốc
CREATE TABLE IF NOT EXISTS public.branches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    address TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now())
);

-- Bảng 2.2: Hồ sơ người dùng & Phân quyền (Profiles)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    branch_id UUID REFERENCES public.branches(id) ON DELETE SET NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'storemanager', 'staff')),
    phone TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now())
);

-- Bảng 2.3: Thiết bị quầy được cấp phép (Hardware Lock)
CREATE TABLE IF NOT EXISTS public.allowed_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    branch_id UUID NOT NULL REFERENCES public.branches(id) ON DELETE CASCADE,
    device_uuid TEXT NOT NULL,
    device_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now()),
    UNIQUE(branch_id, device_uuid)
);

-- Bảng 2.4: Ca làm việc (Shifts)
CREATE TABLE IF NOT EXISTS public.shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    branch_id UUID REFERENCES public.branches(id) ON DELETE CASCADE,
    name TEXT NOT NULL, -- VD: "Ca Sáng", "Ca Chiều", "Ca Đêm"
    start_time TIME NOT NULL, -- VD: 08:00:00
    end_time TIME NOT NULL,   -- VD: 16:00:00
    created_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now())
);

-- Bảng 2.5: Lịch làm việc phân công (Schedules)
CREATE TABLE IF NOT EXISTS public.schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    branch_id UUID NOT NULL REFERENCES public.branches(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    shift_id UUID NOT NULL REFERENCES public.shifts(id) ON DELETE CASCADE,
    work_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'absent', 'leave')),
    created_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now()),
    UNIQUE(user_id, work_date, shift_id)
);

-- Bảng 2.6: Dữ liệu Chấm công (Attendance - Zero Tolerance)
CREATE TABLE IF NOT EXISTS public.attendance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_id UUID UNIQUE NOT NULL REFERENCES public.schedules(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    branch_id UUID NOT NULL REFERENCES public.branches(id) ON DELETE CASCADE,
    check_in TIMESTAMPTZ NOT NULL,
    check_out TIMESTAMPTZ,
    is_late BOOLEAN DEFAULT FALSE,
    late_minutes INTEGER DEFAULT 0,
    is_early_leave BOOLEAN DEFAULT FALSE,
    early_minutes INTEGER DEFAULT 0,
    device_uuid TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now())
);

-- Bảng 2.7: Đơn xin nghỉ phép / Đổi ca (Leave Requests)
CREATE TABLE IF NOT EXISTS public.leave_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    branch_id UUID NOT NULL REFERENCES public.branches(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    schedule_id UUID NOT NULL REFERENCES public.schedules(id) ON DELETE CASCADE,
    leave_type TEXT NOT NULL CHECK (leave_type IN ('sick', 'annual', 'unpaid', 'swap')),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now())
);

-- Bảng 2.8: Giải trình quên chấm công & Ảnh chứng từ (Attendance Proofs)
CREATE TABLE IF NOT EXISTS public.attendance_proofs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attendance_id UUID REFERENCES public.attendance(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    branch_id UUID NOT NULL REFERENCES public.branches(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    note TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT timezone('Asia/Ho_Chi_Minh', now())
);

-- ==============================================================================
-- 3. HÀM BỔ TRỢ HỆ THỐNG (HELPER FUNCTIONS)
-- ==============================================================================

-- Lấy vai trò của user hiện tại (SECURITY DEFINER để chống đệ quy RLS)
CREATE OR REPLACE FUNCTION public.get_current_role()
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_role TEXT;
BEGIN
    SELECT role INTO v_role FROM public.profiles WHERE id = auth.uid();
    RETURN v_role;
END;
$$;

-- Lấy chi nhánh của user hiện tại (SECURITY DEFINER để chống đệ quy RLS)
CREATE OR REPLACE FUNCTION public.get_current_branch_id()
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_branch UUID;
BEGIN
    SELECT branch_id INTO v_branch FROM public.profiles WHERE id = auth.uid();
    RETURN v_branch;
END;
$$;

-- Trigger tự động cập nhật Lịch làm việc khi Đơn xin nghỉ được duyệt
CREATE OR REPLACE FUNCTION public.handle_leave_approval()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    IF NEW.status = 'approved' AND OLD.status != 'approved' THEN
        UPDATE public.schedules
        SET status = 'leave'
        WHERE id = NEW.schedule_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_leave_approval ON public.leave_requests;
CREATE TRIGGER trg_leave_approval
    AFTER UPDATE OF status ON public.leave_requests
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_leave_approval();

-- ==============================================================================
-- 4. BẢO MẬT HÀNG (ROW LEVEL SECURITY - RLS)
-- ==============================================================================

ALTER TABLE public.branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.allowed_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shifts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leave_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance_proofs ENABLE ROW LEVEL SECURITY;

-- 4.1. Chính sách cho BRANCHES
DROP POLICY IF EXISTS "Admin toàn quyền trên branches" ON public.branches;
DROP POLICY IF EXISTS "Mọi user đăng nhập được xem chi nhánh" ON public.branches;
CREATE POLICY "Admin toàn quyền trên branches"
    ON public.branches FOR ALL
    USING (public.get_current_role() = 'admin');

CREATE POLICY "Mọi user đăng nhập được xem chi nhánh"
    ON public.branches FOR SELECT
    TO authenticated
    USING (TRUE);

-- 4.2. Chính sách cho PROFILES
DROP POLICY IF EXISTS "Admin toàn quyền trên profiles" ON public.profiles;
DROP POLICY IF EXISTS "Manager xem profile nhân viên trong chi nhánh" ON public.profiles;
DROP POLICY IF EXISTS "Staff chỉ xem profile của chính mình" ON public.profiles;

CREATE POLICY "Staff chỉ xem profile của chính mình"
    ON public.profiles FOR SELECT
    USING (id = auth.uid());

CREATE POLICY "Admin toàn quyền trên profiles"
    ON public.profiles FOR ALL
    USING (public.get_current_role() = 'admin');

CREATE POLICY "Manager xem profile nhân viên trong chi nhánh"
    ON public.profiles FOR SELECT
    USING (
        public.get_current_role() = 'storemanager' 
        AND branch_id = public.get_current_branch_id()
    );

-- 4.3. Chính sách cho ALLOWED_DEVICES
DROP POLICY IF EXISTS "Admin toàn quyền quản lý thiết bị" ON public.allowed_devices;
DROP POLICY IF EXISTS "User được xem thiết bị chi nhánh mình để xác thực" ON public.allowed_devices;
CREATE POLICY "Admin toàn quyền quản lý thiết bị"
    ON public.allowed_devices FOR ALL
    USING (public.get_current_role() = 'admin');

CREATE POLICY "User được xem thiết bị chi nhánh mình để xác thực"
    ON public.allowed_devices FOR SELECT
    TO authenticated
    USING (branch_id = public.get_current_branch_id() OR public.get_current_role() = 'admin');

-- 4.4. Chính sách cho SCHEDULES & SHIFTS
DROP POLICY IF EXISTS "Admin toàn quyền schedules" ON public.schedules;
DROP POLICY IF EXISTS "Manager toàn quyền schedules trong chi nhánh" ON public.schedules;
DROP POLICY IF EXISTS "Staff xem lịch của mình" ON public.schedules;
DROP POLICY IF EXISTS "Đọc bảng shifts" ON public.shifts;
DROP POLICY IF EXISTS "Admin & Manager tạo/sửa shifts" ON public.shifts;

CREATE POLICY "Admin toàn quyền schedules"
    ON public.schedules FOR ALL
    USING (public.get_current_role() = 'admin');

CREATE POLICY "Manager toàn quyền schedules trong chi nhánh"
    ON public.schedules FOR ALL
    USING (
        public.get_current_role() = 'storemanager' 
        AND branch_id = public.get_current_branch_id()
    );

CREATE POLICY "Staff xem lịch của mình"
    ON public.schedules FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Đọc bảng shifts"
    ON public.shifts FOR SELECT
    TO authenticated
    USING (TRUE);

CREATE POLICY "Admin & Manager tạo/sửa shifts"
    ON public.shifts FOR ALL
    USING (
        public.get_current_role() = 'admin' 
        OR (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id())
    );

-- 4.5. Chính sách cho ATTENDANCE
DROP POLICY IF EXISTS "Admin toàn quyền attendance" ON public.attendance;
DROP POLICY IF EXISTS "Manager xem attendance chi nhánh mình" ON public.attendance;
DROP POLICY IF EXISTS "Staff chỉ xem attendance của mình" ON public.attendance;

CREATE POLICY "Admin toàn quyền attendance"
    ON public.attendance FOR ALL
    USING (public.get_current_role() = 'admin');

CREATE POLICY "Manager xem attendance chi nhánh mình"
    ON public.attendance FOR SELECT
    USING (
        public.get_current_role() = 'storemanager' 
        AND branch_id = public.get_current_branch_id()
    );

CREATE POLICY "Staff chỉ xem attendance của mình"
    ON public.attendance FOR SELECT
    USING (user_id = auth.uid());

-- 4.6. Chính sách cho LEAVE_REQUESTS
DROP POLICY IF EXISTS "Staff tạo và xem đơn của mình" ON public.leave_requests;
DROP POLICY IF EXISTS "Manager duyệt đơn chi nhánh" ON public.leave_requests;
DROP POLICY IF EXISTS "Admin toàn quyền đơn nghỉ" ON public.leave_requests;

CREATE POLICY "Staff tạo và xem đơn của mình"
    ON public.leave_requests FOR ALL
    USING (user_id = auth.uid());

CREATE POLICY "Manager duyệt đơn chi nhánh"
    ON public.leave_requests FOR ALL
    USING (
        public.get_current_role() = 'storemanager' 
        AND branch_id = public.get_current_branch_id()
    );

CREATE POLICY "Admin toàn quyền đơn nghỉ"
    ON public.leave_requests FOR ALL
    USING (public.get_current_role() = 'admin');

-- 4.7. Chính sách cho ATTENDANCE_PROOFS
DROP POLICY IF EXISTS "Staff tạo và xem minh chứng của mình" ON public.attendance_proofs;
DROP POLICY IF EXISTS "Manager duyệt minh chứng chi nhánh" ON public.attendance_proofs;
DROP POLICY IF EXISTS "Admin toàn quyền minh chứng" ON public.attendance_proofs;

CREATE POLICY "Staff tạo và xem minh chứng của mình"
    ON public.attendance_proofs FOR ALL
    USING (user_id = auth.uid());

CREATE POLICY "Manager duyệt minh chứng chi nhánh"
    ON public.attendance_proofs FOR ALL
    USING (
        public.get_current_role() = 'storemanager' 
        AND branch_id = public.get_current_branch_id()
    );

CREATE POLICY "Admin toàn quyền minh chứng"
    ON public.attendance_proofs FOR ALL
    USING (public.get_current_role() = 'admin');

-- ==============================================================================
-- 5. POSTGRESQL FUNCTIONS (RPC) - CHỐT CHẶN CHẤM CÔNG AN TOÀN
-- ==============================================================================

-- 5.1. RPC: CHECK-IN (Chấm công vào ca - Kỷ luật nghiêm túc, không du di)
CREATE OR REPLACE FUNCTION public.rpc_check_in(
    p_schedule_id UUID,
    p_device_uuid TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_user_id UUID;
    v_schedule RECORD;
    v_shift RECORD;
    v_device_valid BOOLEAN;
    v_now TIMESTAMPTZ;
    v_current_time TIME;
    v_is_late BOOLEAN := FALSE;
    v_late_minutes INTEGER := 0;
    v_attendance_id UUID;
BEGIN
    v_user_id := auth.uid();
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Chưa đăng nhập! Không thể chấm công.';
    END IF;

    -- Lấy thời gian chuẩn Server theo múi giờ Việt Nam
    v_now := timezone('Asia/Ho_Chi_Minh', now());
    v_current_time := v_now::TIME;

    -- Lấy thông tin ca làm việc
    SELECT s.*, sh.start_time, sh.end_time 
    INTO v_schedule
    FROM public.schedules s
    JOIN public.shifts sh ON s.shift_id = sh.id
    WHERE s.id = p_schedule_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không tìm thấy ca làm việc!';
    END IF;

    -- Kiểm tra ca làm có đúng của người này không
    IF v_schedule.user_id != v_user_id THEN
        RAISE EXCEPTION 'Bạn không thể chấm công hộ cho nhân viên khác!';
    END IF;

    -- Kiểm tra ngày làm việc (chỉ được chấm công đúng ngày)
    IF v_schedule.work_date != v_now::DATE THEN
        RAISE EXCEPTION 'Chỉ được phép chấm công đúng ngày làm việc trên lịch!';
    END IF;

    -- Kiểm tra thiết bị có hợp lệ với Chi nhánh này không
    SELECT EXISTS (
        SELECT 1 FROM public.allowed_devices 
        WHERE branch_id = v_schedule.branch_id 
          AND device_uuid = p_device_uuid 
          AND is_active = TRUE
    ) INTO v_device_valid;

    IF NOT v_device_valid THEN
        RAISE EXCEPTION 'Thiết bị này không được cấp phép chấm công cho chi nhánh của bạn!';
    END IF;

    -- Kiểm tra xem đã check-in trước đó chưa
    IF EXISTS (SELECT 1 FROM public.attendance WHERE schedule_id = p_schedule_id) THEN
        RAISE EXCEPTION 'Ca làm việc này đã được Check-in trước đó!';
    END IF;

    -- LOGIC ZERO TOLERANCE: Ca bắt đầu lúc start_time.
    -- Quá đúng 1 giây so với start_time là tính trễ ngay lập tức.
    IF v_current_time > v_schedule.start_time THEN
        v_is_late := TRUE;
        -- Tính số phút trễ (làm tròn lên phút gần nhất)
        v_late_minutes := CEIL(EXTRACT(EPOCH FROM (v_current_time - v_schedule.start_time)) / 60.0);
    END IF;

    -- Ghi nhận dữ liệu chấm công
    INSERT INTO public.attendance (
        schedule_id,
        user_id,
        branch_id,
        check_in,
        is_late,
        late_minutes,
        device_uuid
    ) VALUES (
        p_schedule_id,
        v_user_id,
        v_schedule.branch_id,
        v_now,
        v_is_late,
        v_late_minutes,
        p_device_uuid
    ) RETURNING id INTO v_attendance_id;

    RETURN jsonb_build_object(
        'success', TRUE,
        'attendance_id', v_attendance_id,
        'check_in_time', v_now,
        'is_late', v_is_late,
        'late_minutes', v_late_minutes,
        'message', CASE 
            WHEN v_is_late THEN format('Check-in thành công. Bạn đi trễ %s phút!', v_late_minutes)
            ELSE 'Check-in đúng giờ thành công!'
        END
    );
END;
$$;

-- 5.2. RPC: CHECK-OUT (Chấm công tan ca)
CREATE OR REPLACE FUNCTION public.rpc_check_out(
    p_attendance_id UUID,
    p_device_uuid TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_user_id UUID;
    v_attendance RECORD;
    v_schedule RECORD;
    v_device_valid BOOLEAN;
    v_now TIMESTAMPTZ;
    v_current_time TIME;
    v_is_early BOOLEAN := FALSE;
    v_early_minutes INTEGER := 0;
BEGIN
    v_user_id := auth.uid();
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Chưa đăng nhập! Không thể chấm công.';
    END IF;

    v_now := timezone('Asia/Ho_Chi_Minh', now());
    v_current_time := v_now::TIME;

    -- Lấy thông tin bản ghi chấm công
    SELECT * INTO v_attendance FROM public.attendance WHERE id = p_attendance_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Không tìm thấy dữ liệu điểm danh!';
    END IF;

    IF v_attendance.user_id != v_user_id THEN
        RAISE EXCEPTION 'Bạn không thể check-out hộ người khác!';
    END IF;

    IF v_attendance.check_out IS NOT NULL THEN
        RAISE EXCEPTION 'Ca này đã được Check-out trước đó!';
    END IF;

    -- Kiểm tra thiết bị hợp lệ
    SELECT EXISTS (
        SELECT 1 FROM public.allowed_devices 
        WHERE branch_id = v_attendance.branch_id 
          AND device_uuid = p_device_uuid 
          AND is_active = TRUE
    ) INTO v_device_valid;

    IF NOT v_device_valid THEN
        RAISE EXCEPTION 'Thiết bị này không hợp lệ để chấm công!';
    END IF;

    -- Lấy thông tin giờ kết thúc ca
    SELECT s.*, sh.end_time 
    INTO v_schedule
    FROM public.schedules s
    JOIN public.shifts sh ON s.shift_id = sh.id
    WHERE s.id = v_attendance.schedule_id;

    -- Kiểm tra về sớm
    IF v_current_time < v_schedule.end_time THEN
        v_is_early := TRUE;
        v_early_minutes := CEIL(EXTRACT(EPOCH FROM (v_schedule.end_time - v_current_time)) / 60.0);
    END IF;

    -- Cập nhật bảng attendance
    UPDATE public.attendance
    SET check_out = v_now,
        is_early_leave = v_is_early,
        early_minutes = v_early_minutes
    WHERE id = p_attendance_id;

    -- Đánh dấu ca hoàn thành trên schedules
    UPDATE public.schedules
    SET status = 'completed'
    WHERE id = v_attendance.schedule_id;

    RETURN jsonb_build_object(
        'success', TRUE,
        'check_out_time', v_now,
        'is_early', v_is_early,
        'early_minutes', v_early_minutes,
        'message', CASE 
            WHEN v_is_early THEN format('Check-out thành công. Bạn về sớm %s phút!', v_early_minutes)
            ELSE 'Check-out hoàn thành ca làm việc thành công!'
        END
    );
END;
$$;

-- ==============================================================================
-- 6. THIẾT LẬP SUPABASE STORAGE (BUCKET: attendance_proofs)
-- ==============================================================================

-- Tạo bucket lưu ảnh minh chứng (nếu chưa có)
INSERT INTO storage.buckets (id, name, public)
VALUES ('attendance_proofs', 'attendance_proofs', false)
ON CONFLICT (id) DO NOTHING;

-- Cho phép người dùng đăng nhập tải ảnh lên
DROP POLICY IF EXISTS "Authenticated users can upload attendance proofs" ON storage.objects;
CREATE POLICY "Authenticated users can upload attendance proofs"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'attendance_proofs');

-- Cho phép mọi người xem ảnh công khai qua URL
DROP POLICY IF EXISTS "Public read for attendance proofs" ON storage.objects;
CREATE POLICY "Public read for attendance proofs"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'attendance_proofs' AND (storage.foldername(name))[1] = auth.uid()::text);

-- ==============================================================================
-- Bootstrap the first administrator manually through Supabase Auth and a trusted
-- SQL session. Never ship a shared password. See README.md.

-- 8. RPC: QUẢN TRỊ NHÂN VIÊN & RÀNG BUỘC PHÂN QUYỀN (ADMIN ONLY)
-- - Chỉ duy nhất 1 tài khoản Admin
-- - Mỗi chi nhánh chỉ được tối đa 1 Store Manager
-- ==============================================================================

-- 8.1. RPC: TẠO TÀI KHOẢN NHÂN VIÊN MỚI
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
SET search_path = public, auth
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
    IF p_role NOT IN ('staff', 'storemanager') THEN
        RAISE EXCEPTION 'Hệ thống chỉ duy nhất có 1 tài khoản Admin tối cao! Bạn chỉ được tạo nhân viên với quyền Dược sĩ (staff) hoặc Quản lý (storemanager).';
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

    v_encrypted_pw := crypt(p_password, gen_salt('bf'));

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

-- 8.2. RPC: CẬP NHẬT THÔNG TIN & PHÂN QUYỀN
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
SET search_path = public, auth
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

-- 8.3. RPC: XÓA TÀI KHOẢN NHÂN VIÊN
CREATE OR REPLACE FUNCTION public.rpc_delete_user(p_user_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
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

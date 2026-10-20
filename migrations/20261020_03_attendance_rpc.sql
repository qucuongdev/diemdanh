BEGIN;

CREATE OR REPLACE FUNCTION public.rpc_check_in(p_schedule_id uuid, p_device_uuid text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_schedule record;
    v_now timestamptz := now();
    v_start timestamptz;
    v_id uuid;
    v_late integer;
BEGIN
    IF public.get_current_role() IS NULL THEN
        RAISE EXCEPTION 'Tài khoản không hoạt động hoặc chưa đăng nhập.';
    END IF;
    -- Lock the schedule: serialize check-in, leave approval and reassignment.
    SELECT s.*, sh.start_time, sh.end_time INTO v_schedule
    FROM public.schedules s JOIN public.shifts sh ON sh.id = s.shift_id
    WHERE s.id = p_schedule_id FOR UPDATE OF s;
    IF NOT FOUND OR v_schedule.user_id IS DISTINCT FROM auth.uid()
       OR v_schedule.branch_id IS DISTINCT FROM public.get_current_branch_id() THEN
        RAISE EXCEPTION 'Không thể chấm công ca làm việc này.';
    END IF;
    IF v_schedule.status <> 'scheduled'
       OR v_schedule.work_date <> (v_now AT TIME ZONE 'Asia/Ho_Chi_Minh')::date THEN
        RAISE EXCEPTION 'Ca làm việc không hợp lệ trong ngày hôm nay.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.allowed_devices WHERE branch_id = v_schedule.branch_id
                   AND device_uuid = p_device_uuid AND is_active IS TRUE) THEN
        RAISE EXCEPTION 'Thiết bị này không hợp lệ để chấm công!';
    END IF;
    IF EXISTS (SELECT 1 FROM public.attendance WHERE schedule_id = p_schedule_id) THEN
        RAISE EXCEPTION 'Ca làm việc này đã được Check-in trước đó!';
    END IF;
    v_start := (v_schedule.work_date + v_schedule.start_time) AT TIME ZONE 'Asia/Ho_Chi_Minh';
    v_late := greatest(0, ceil(extract(epoch FROM (v_now - v_start)) / 60.0)::integer);
    INSERT INTO public.attendance(schedule_id, user_id, branch_id, check_in, is_late, late_minutes, device_uuid)
    VALUES (p_schedule_id, auth.uid(), v_schedule.branch_id, v_now, v_now > v_start, v_late, p_device_uuid)
    RETURNING id INTO v_id;
    RETURN jsonb_build_object('success', true, 'attendance_id', v_id,
        'message', CASE WHEN v_late > 0 THEN format('Đã vào ca. Đi muộn %s phút.', v_late) ELSE 'Đã vào ca đúng giờ.' END);
END $$;

CREATE OR REPLACE FUNCTION public.rpc_check_out(p_attendance_id uuid, p_device_uuid text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_att public.attendance;
    v_schedule record;
    v_now timestamptz := now();
    v_end timestamptz;
BEGIN
    IF public.get_current_role() IS NULL THEN
        RAISE EXCEPTION 'Tài khoản không hoạt động hoặc chưa đăng nhập.';
    END IF;
    SELECT * INTO v_att FROM public.attendance WHERE id = p_attendance_id FOR UPDATE;
    IF NOT FOUND OR v_att.user_id IS DISTINCT FROM auth.uid()
       OR v_att.branch_id IS DISTINCT FROM public.get_current_branch_id() THEN
        RAISE EXCEPTION 'Không thể tan ca thay người khác.';
    END IF;
    IF v_att.check_out IS NOT NULL THEN RAISE EXCEPTION 'Ca này đã được Check-out trước đó!'; END IF;
    IF NOT EXISTS (SELECT 1 FROM public.allowed_devices WHERE branch_id = v_att.branch_id
                   AND device_uuid = p_device_uuid AND is_active IS TRUE) THEN
        RAISE EXCEPTION 'Thiết bị này không hợp lệ để chấm công!';
    END IF;
    SELECT s.*, sh.start_time, sh.end_time INTO v_schedule FROM public.schedules s
    JOIN public.shifts sh ON sh.id = s.shift_id WHERE s.id = v_att.schedule_id;
    v_end := ((v_schedule.work_date + v_schedule.end_time) +
        CASE WHEN v_schedule.end_time <= v_schedule.start_time THEN interval '1 day' ELSE interval '0 day' END)
        AT TIME ZONE 'Asia/Ho_Chi_Minh';
    IF v_now < v_end THEN RAISE EXCEPTION 'Chưa đến giờ tan ca theo giờ máy chủ.'; END IF;
    UPDATE public.attendance SET check_out = v_now, is_early_leave = false, early_minutes = 0
    WHERE id = p_attendance_id;
    UPDATE public.schedules SET status = 'completed' WHERE id = v_att.schedule_id;
    RETURN jsonb_build_object('success', true, 'message', 'Đã hoàn thành ca làm việc.');
END $$;

CREATE OR REPLACE FUNCTION public.handle_leave_approval()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_schedule public.schedules;
BEGIN
    IF NEW.status = 'approved' AND OLD.status <> 'approved' THEN
        SELECT * INTO v_schedule FROM public.schedules WHERE id = NEW.schedule_id FOR UPDATE;
        IF NOT FOUND OR v_schedule.status <> 'scheduled' OR
           EXISTS (SELECT 1 FROM public.attendance WHERE schedule_id = NEW.schedule_id) THEN
            RAISE EXCEPTION 'Ca đã thay đổi hoặc đã chấm công, không thể duyệt nghỉ.';
        END IF;
        UPDATE public.schedules SET status = 'leave' WHERE id = NEW.schedule_id;
    END IF;
    RETURN NEW;
END $$;

REVOKE ALL ON FUNCTION public.rpc_check_in(uuid,text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.rpc_check_out(uuid,text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.rpc_check_in(uuid,text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_check_out(uuid,text) TO authenticated;
REVOKE ALL ON FUNCTION public.guard_review() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.guard_schedule() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.guard_admin_profile() FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.handle_leave_approval() FROM PUBLIC, anon;

-- The v2 desktop fails closed against a backend that lacks these protections.
CREATE OR REPLACE FUNCTION public.rpc_client_version()
RETURNS integer LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT CASE WHEN public.get_current_role() IS NOT NULL THEN 2 ELSE NULL END $$;
REVOKE ALL ON FUNCTION public.rpc_client_version() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.rpc_client_version() TO authenticated;

COMMIT;

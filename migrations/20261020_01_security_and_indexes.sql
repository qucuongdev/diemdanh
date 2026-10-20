-- Apply after schema.sql and update_admin_rpc.sql. Review before deployment.
-- Transactional: existing conflicting manager records abort the whole migration.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_current_role()
RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT role FROM public.profiles WHERE id = auth.uid() AND is_active IS TRUE $$;

CREATE OR REPLACE FUNCTION public.get_current_branch_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT branch_id FROM public.profiles WHERE id = auth.uid() AND is_active IS TRUE $$;

-- Replace the application's permissive legacy policies, including staff FOR ALL.
DO $$ DECLARE p record;
BEGIN
    FOR p IN SELECT tablename, policyname FROM pg_policies
             WHERE schemaname = 'public' AND tablename IN
             ('branches','profiles','allowed_devices','shifts','schedules',
              'attendance','leave_requests','attendance_proofs')
    LOOP
        EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, p.tablename);
    END LOOP;
END $$;

CREATE POLICY branches_read ON public.branches FOR SELECT TO authenticated
USING (public.get_current_role() IS NOT NULL);
CREATE POLICY branches_admin ON public.branches FOR ALL TO authenticated
USING (public.get_current_role() = 'admin') WITH CHECK (public.get_current_role() = 'admin');

-- An inactive account may read its own profile so login can explain rejection.
CREATE POLICY profiles_read ON public.profiles FOR SELECT TO authenticated USING (
    id = auth.uid() OR public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id())
);
CREATE POLICY profiles_admin ON public.profiles FOR ALL TO authenticated
USING (public.get_current_role() = 'admin') WITH CHECK (public.get_current_role() = 'admin');

CREATE POLICY devices_read ON public.allowed_devices FOR SELECT TO authenticated USING (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() IS NOT NULL AND branch_id = public.get_current_branch_id())
);
CREATE POLICY devices_admin ON public.allowed_devices FOR ALL TO authenticated
USING (public.get_current_role() = 'admin') WITH CHECK (public.get_current_role() = 'admin');

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

CREATE POLICY schedules_read ON public.schedules FOR SELECT TO authenticated USING (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id()) OR
    (public.get_current_role() = 'staff' AND user_id = auth.uid())
);
CREATE POLICY schedules_manage ON public.schedules FOR ALL TO authenticated USING (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id())
) WITH CHECK (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id())
);

-- Attendance writes only through authenticated, validated RPCs.
CREATE POLICY attendance_read ON public.attendance FOR SELECT TO authenticated USING (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id()) OR
    (public.get_current_role() = 'staff' AND user_id = auth.uid())
);

CREATE POLICY leave_read ON public.leave_requests FOR SELECT TO authenticated USING (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id()) OR
    (public.get_current_role() IS NOT NULL AND user_id = auth.uid())
);
CREATE POLICY leave_submit ON public.leave_requests FOR INSERT TO authenticated WITH CHECK (
    public.get_current_role() IS NOT NULL AND user_id = auth.uid()
    AND status = 'pending' AND reviewed_by IS NULL AND length(trim(reason)) > 0
    AND branch_id = public.get_current_branch_id()
    AND EXISTS (SELECT 1 FROM public.schedules s WHERE s.id = schedule_id
                AND s.user_id = auth.uid() AND s.branch_id = leave_requests.branch_id
                AND s.status = 'scheduled')
    AND NOT EXISTS (SELECT 1 FROM public.attendance a WHERE a.schedule_id = leave_requests.schedule_id)
);
CREATE POLICY leave_review ON public.leave_requests FOR UPDATE TO authenticated USING (
    user_id <> auth.uid() AND status = 'pending' AND
    (public.get_current_role() = 'admin' OR
     (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id()))
) WITH CHECK (reviewed_by = auth.uid() AND status IN ('approved','rejected') AND user_id <> auth.uid());

CREATE POLICY proof_read ON public.attendance_proofs FOR SELECT TO authenticated USING (
    public.get_current_role() = 'admin' OR
    (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id()) OR
    (public.get_current_role() IS NOT NULL AND user_id = auth.uid())
);
CREATE POLICY proof_submit ON public.attendance_proofs FOR INSERT TO authenticated WITH CHECK (
    public.get_current_role() IS NOT NULL AND user_id = auth.uid()
    AND status = 'pending' AND reviewed_by IS NULL AND length(trim(note)) > 0
    AND branch_id = public.get_current_branch_id()
    AND image_url LIKE auth.uid()::text || '/%'
    AND (attendance_id IS NULL OR EXISTS (
        SELECT 1 FROM public.attendance a WHERE a.id = attendance_id AND a.user_id = auth.uid()
        AND a.branch_id = attendance_proofs.branch_id))
);
CREATE POLICY proof_review ON public.attendance_proofs FOR UPDATE TO authenticated USING (
    user_id <> auth.uid() AND status = 'pending' AND
    (public.get_current_role() = 'admin' OR
     (public.get_current_role() = 'storemanager' AND branch_id = public.get_current_branch_id()))
) WITH CHECK (reviewed_by = auth.uid() AND status IN ('approved','rejected') AND user_id <> auth.uid());

-- Reviewers can change only review fields, once. No payload/ownership rewriting.
CREATE OR REPLACE FUNCTION public.guard_review()
RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF OLD.status <> 'pending' OR NEW.status NOT IN ('approved','rejected')
       OR NEW.reviewed_by IS DISTINCT FROM auth.uid()
       OR (to_jsonb(NEW) - 'status' - 'reviewed_by') IS DISTINCT FROM
          (to_jsonb(OLD) - 'status' - 'reviewed_by') THEN
        RAISE EXCEPTION 'Invalid review transition';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS guard_leave_review ON public.leave_requests;
CREATE TRIGGER guard_leave_review BEFORE UPDATE ON public.leave_requests
FOR EACH ROW EXECUTE FUNCTION public.guard_review();
DROP TRIGGER IF EXISTS guard_proof_review ON public.attendance_proofs;
CREATE TRIGGER guard_proof_review BEFORE UPDATE ON public.attendance_proofs
FOR EACH ROW EXECUTE FUNCTION public.guard_review();

CREATE OR REPLACE FUNCTION public.guard_schedule()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.attendance WHERE schedule_id = OLD.id) THEN
            RAISE EXCEPTION 'Cannot delete attendance history; deactivate the user instead';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.user_id, NEW.shift_id, NEW.branch_id, NEW.work_date)
       IS DISTINCT FROM (OLD.user_id, OLD.shift_id, OLD.branch_id, OLD.work_date)
       AND EXISTS (SELECT 1 FROM public.attendance WHERE schedule_id = OLD.id) THEN
        RAISE EXCEPTION 'Cannot reassign a recorded schedule';
    END IF;
    -- Status-only updates remain valid after a staff member changes branch.
    IF TG_OP = 'UPDATE' AND (NEW.user_id, NEW.shift_id, NEW.branch_id, NEW.work_date)
       IS NOT DISTINCT FROM (OLD.user_id, OLD.shift_id, OLD.branch_id, OLD.work_date) THEN
        RETURN NEW;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.profiles p JOIN public.shifts s ON s.id = NEW.shift_id
                   WHERE p.id = NEW.user_id AND p.is_active IS TRUE
                   AND p.branch_id = NEW.branch_id AND s.branch_id = NEW.branch_id) THEN
        RAISE EXCEPTION 'Staff, shift and schedule must belong to the same branch';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS guard_schedule_write ON public.schedules;
CREATE TRIGGER guard_schedule_write BEFORE INSERT OR UPDATE OR DELETE ON public.schedules
FOR EACH ROW EXECUTE FUNCTION public.guard_schedule();

CREATE OR REPLACE FUNCTION public.guard_admin_profile()
RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.role = 'admin' THEN RAISE EXCEPTION 'Cannot delete admin'; END IF;
        RETURN OLD;
    END IF;
    IF (OLD.role = 'admin' AND (NEW.role <> 'admin' OR NEW.is_active IS NOT TRUE))
       OR (OLD.role <> 'admin' AND NEW.role = 'admin') THEN
        RAISE EXCEPTION 'Cannot change admin authority';
    END IF;
    IF NEW.role <> 'admin' AND NEW.branch_id IS NULL AND NEW.is_active IS TRUE THEN
        RAISE EXCEPTION 'An active employee requires a branch';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS guard_admin_profile ON public.profiles;
CREATE TRIGGER guard_admin_profile BEFORE UPDATE OR DELETE ON public.profiles
FOR EACH ROW EXECUTE FUNCTION public.guard_admin_profile();

-- Private proofs, with owner upload and scoped reviewer access. Existing URL
-- records remain readable through the client URL-to-object-path compatibility.
UPDATE storage.buckets SET public = false, file_size_limit = 512000,
    allowed_mime_types = ARRAY['image/jpeg'] WHERE id = 'attendance_proofs';
DROP POLICY IF EXISTS "Authenticated users can upload attendance proofs" ON storage.objects;
DROP POLICY IF EXISTS "Public read for attendance proofs" ON storage.objects;
DROP POLICY IF EXISTS proofs_upload ON storage.objects;
DROP POLICY IF EXISTS proofs_read ON storage.objects;
DROP POLICY IF EXISTS proofs_cleanup ON storage.objects;
CREATE POLICY proofs_upload ON storage.objects FOR INSERT TO authenticated WITH CHECK (
    bucket_id = 'attendance_proofs' AND public.get_current_role() IS NOT NULL
    AND (storage.foldername(name))[1] = auth.uid()::text
);
CREATE POLICY proofs_read ON storage.objects FOR SELECT TO authenticated USING (
    bucket_id = 'attendance_proofs' AND public.get_current_role() IS NOT NULL AND (
        (storage.foldername(name))[1] = auth.uid()::text OR
        public.get_current_role() = 'admin' OR EXISTS (
            SELECT 1 FROM public.attendance_proofs p WHERE
            public.get_current_role() = 'storemanager'
            AND p.branch_id = public.get_current_branch_id()
            AND (p.image_url = name OR p.image_url LIKE '%/attendance_proofs/' || name)
        )
    )
);
CREATE POLICY proofs_cleanup ON storage.objects FOR DELETE TO authenticated USING (
    bucket_id = 'attendance_proofs' AND public.get_current_role() IS NOT NULL
    AND (storage.foldername(name))[1] = auth.uid()::text
    AND NOT EXISTS (SELECT 1 FROM public.attendance_proofs p
        WHERE p.image_url = name OR p.image_url LIKE '%/attendance_proofs/' || name)
);

CREATE UNIQUE INDEX IF NOT EXISTS profiles_one_active_manager ON public.profiles(branch_id)
WHERE role = 'storemanager' AND is_active IS TRUE;
CREATE INDEX IF NOT EXISTS schedules_branch_date ON public.schedules(branch_id, work_date, id);
CREATE INDEX IF NOT EXISTS schedules_user_date ON public.schedules(user_id, work_date, id);
CREATE INDEX IF NOT EXISTS attendance_branch_time ON public.attendance(branch_id, check_in DESC, id);
CREATE INDEX IF NOT EXISTS attendance_user_time ON public.attendance(user_id, check_in DESC, id);
CREATE INDEX IF NOT EXISTS leave_branch_status ON public.leave_requests(branch_id, status, created_at DESC, id);
CREATE INDEX IF NOT EXISTS proofs_branch_status ON public.attendance_proofs(branch_id, status, created_at DESC, id);

COMMIT;

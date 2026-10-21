-- Review DEPLOYMENT.md and PAYROLL.md before applying. Never run as an offline test.
BEGIN;

CREATE TABLE public.employee_private (
    user_id uuid PRIMARY KEY REFERENCES public.profiles(id) ON DELETE RESTRICT,
    birth_date date,
    hire_date date,
    end_date date,
    birthday_notice_days integer NOT NULL DEFAULT 7 CHECK (birthday_notice_days BETWEEN 0 AND 60),
    details jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(details) = 'object'),
    revision integer NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (end_date IS NULL OR hire_date IS NULL OR end_date >= hire_date)
);
CREATE TABLE public.employee_pay_terms (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    effective_month date NOT NULL CHECK (extract(day FROM effective_month) = 1),
    monthly_salary numeric(15,0) NOT NULL CHECK (monthly_salary BETWEEN 0 AND 999999999999),
    paid_rest_days integer NOT NULL CHECK (paid_rest_days BETWEEN 0 AND 27),
    daily_minutes integer NOT NULL CHECK (daily_minutes BETWEEN 1 AND 1440),
    attendance_bonus numeric(15,0) NOT NULL DEFAULT 0 CHECK (attendance_bonus BETWEEN 0 AND 999999999999),
    allowed_late_count integer NOT NULL DEFAULT 0 CHECK (allowed_late_count BETWEEN 0 AND 1000),
    revision integer NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(user_id, effective_month)
);
CREATE TABLE public.payroll_days (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    work_date date NOT NULL,
    kind text NOT NULL CHECK (kind IN ('regular','rest','paid_leave','unpaid_leave','extra_work','absent')),
    note text NOT NULL CHECK (length(trim(note)) BETWEEN 1 AND 1000),
    revision integer NOT NULL DEFAULT 1,
    PRIMARY KEY(user_id, work_date)
);
CREATE TABLE public.payroll_snapshots (
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    month date NOT NULL CHECK (extract(day FROM month) = 1),
    result jsonb NOT NULL,
    source jsonb NOT NULL,
    finalized_by uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    finalized_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(user_id, month)
);
CREATE TABLE public.personnel_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    actor_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    action text NOT NULL,
    reference_date date,
    changed_fields jsonb NOT NULL DEFAULT '[]',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX payroll_schedules_user_date ON public.schedules(user_id, work_date);
CREATE INDEX personnel_birth_month_day ON public.employee_private
    ((extract(month FROM birth_date)), (extract(day FROM birth_date))) WHERE birth_date IS NOT NULL;
CREATE INDEX personnel_audit_user ON public.personnel_audit(user_id, id DESC);
CREATE UNIQUE INDEX personnel_unique_employee_code ON public.employee_private
    ((lower(trim(details->>'employee_code')))) WHERE nullif(trim(details->>'employee_code'),'') IS NOT NULL;

-- No public profile column is extended with salary, ID-card or banking data.
ALTER TABLE public.employee_private ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_pay_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payroll_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payroll_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.personnel_audit ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.employee_private, public.employee_pay_terms, public.payroll_days,
    public.payroll_snapshots, public.personnel_audit FROM PUBLIC, anon, authenticated;

CREATE FUNCTION public.payroll_require_admin() RETURNS void
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF public.get_current_role() IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'PERSONNEL_FORBIDDEN';
    END IF;
END $$;

CREATE FUNCTION public.rpc_employee_private(p_user_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_details jsonb; v_terms jsonb;
BEGIN
    PERFORM public.payroll_require_admin();
    SELECT to_jsonb(e) INTO v_details FROM public.employee_private e WHERE user_id=p_user_id;
    SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY effective_month DESC),'[]') INTO v_terms
        FROM public.employee_pay_terms t WHERE user_id=p_user_id;
    RETURN jsonb_build_object('details',v_details,'terms',v_terms);
END $$;

CREATE FUNCTION public.rpc_save_employee_private(p_user_id uuid, p_details jsonb, p_revision integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_revision integer; v_key text; v_birth date; v_hire date; v_end date; v_notice integer;
BEGIN
    PERFORM public.payroll_require_admin();
    PERFORM pg_advisory_xact_lock(hashtextextended('payroll:'||p_user_id::text,0));
    IF jsonb_typeof(p_details) IS DISTINCT FROM 'object' OR p_revision IS NULL THEN
        RAISE EXCEPTION 'PERSONNEL_INVALID';
    END IF;
    FOR v_key IN SELECT jsonb_object_keys(p_details) LOOP
        IF v_key <> ALL(ARRAY['employee_code','gender','contact_email','identity_number','identity_date',
            'identity_place','bank_account','bank_name','bank_holder','hometown','permanent_address',
            'current_address','job_title','emergency_name','emergency_relation','emergency_phone',
            'birth_date','hire_date','end_date','birthday_notice_days']) OR
            jsonb_typeof(p_details->v_key) IS DISTINCT FROM 'string' OR length(p_details->>v_key)>1000 THEN
            RAISE EXCEPTION 'PERSONNEL_INVALID';
        END IF;
    END LOOP;
    v_birth := nullif(p_details->>'birth_date','')::date;
    v_hire := nullif(p_details->>'hire_date','')::date;
    v_end := nullif(p_details->>'end_date','')::date;
    v_notice := coalesce(nullif(p_details->>'birthday_notice_days','')::integer,7);
    IF v_birth > (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date OR v_birth < date '1900-01-01'
       OR v_notice NOT BETWEEN 0 AND 60 OR (v_hire IS NOT NULL AND v_end < v_hire)
       OR (coalesce(p_details->>'identity_number','') <> '' AND
           p_details->>'identity_number' !~ '^([0-9]{9}|[0-9]{12})$') THEN
        RAISE EXCEPTION 'PERSONNEL_INVALID';
    END IF;
    PERFORM nullif(p_details->>'identity_date','')::date;
    SELECT revision INTO v_revision FROM public.employee_private WHERE user_id=p_user_id;
    IF coalesce(v_revision,0) <> p_revision THEN RAISE EXCEPTION 'PERSONNEL_STALE'; END IF;
    INSERT INTO public.employee_private(user_id,birth_date,hire_date,end_date,birthday_notice_days,details)
        VALUES(p_user_id,v_birth,v_hire,v_end,v_notice,
            p_details - ARRAY['birth_date','hire_date','end_date','birthday_notice_days'])
    ON CONFLICT(user_id) DO UPDATE SET birth_date=excluded.birth_date,hire_date=excluded.hire_date,
        end_date=excluded.end_date,birthday_notice_days=excluded.birthday_notice_days,
        details=excluded.details,revision=employee_private.revision+1,updated_at=now();
    INSERT INTO public.personnel_audit(user_id,actor_id,action,changed_fields)
        VALUES(p_user_id,auth.uid(),'private_update',(SELECT jsonb_agg(k) FROM jsonb_object_keys(p_details) k));
    RETURN jsonb_build_object('success',true);
END $$;

CREATE FUNCTION public.rpc_save_pay_terms(p_user_id uuid,p_month date,p_terms jsonb,p_revision integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_revision integer;
BEGIN
    PERFORM public.payroll_require_admin();
    PERFORM pg_advisory_xact_lock(hashtextextended('payroll:'||p_user_id::text,0));
    IF p_month IS NULL OR extract(day FROM p_month) <> 1 OR p_revision IS NULL
       OR jsonb_typeof(p_terms) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'PERSONNEL_INVALID'; END IF;
    IF EXISTS(SELECT 1 FROM public.payroll_snapshots WHERE user_id=p_user_id AND month>=p_month) THEN
        RAISE EXCEPTION 'PAYROLL_LOCKED';
    END IF;
    SELECT revision INTO v_revision FROM public.employee_pay_terms
        WHERE user_id=p_user_id AND effective_month=p_month;
    IF coalesce(v_revision,0)<>p_revision THEN RAISE EXCEPTION 'PERSONNEL_STALE'; END IF;
    INSERT INTO public.employee_pay_terms(user_id,effective_month,monthly_salary,paid_rest_days,
        daily_minutes,attendance_bonus,allowed_late_count)
    VALUES(p_user_id,p_month,(p_terms->>'monthly_salary')::numeric,(p_terms->>'paid_rest_days')::integer,
        (p_terms->>'daily_minutes')::integer,(p_terms->>'attendance_bonus')::numeric,
        (p_terms->>'allowed_late_count')::integer)
    ON CONFLICT(user_id,effective_month) DO UPDATE SET monthly_salary=excluded.monthly_salary,
        paid_rest_days=excluded.paid_rest_days,daily_minutes=excluded.daily_minutes,
        attendance_bonus=excluded.attendance_bonus,allowed_late_count=excluded.allowed_late_count,
        revision=employee_pay_terms.revision+1,updated_at=now();
    INSERT INTO public.personnel_audit(user_id,actor_id,action,reference_date)
        VALUES(p_user_id,auth.uid(),'pay_terms_update',p_month);
    RETURN jsonb_build_object('success',true);
END $$;

CREATE FUNCTION public.rpc_set_payroll_day(p_user_id uuid,p_date date,p_kind text,p_note text,p_revision integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_revision integer;
BEGIN
    PERFORM public.payroll_require_admin();
    PERFORM pg_advisory_xact_lock(hashtextextended('payroll:'||p_user_id::text,0));
    IF p_date IS NULL OR p_revision IS NULL THEN RAISE EXCEPTION 'PERSONNEL_INVALID'; END IF;
    IF EXISTS(SELECT 1 FROM public.payroll_snapshots WHERE user_id=p_user_id
        AND month=date_trunc('month',p_date)::date) THEN RAISE EXCEPTION 'PAYROLL_LOCKED'; END IF;
    SELECT revision INTO v_revision FROM public.payroll_days WHERE user_id=p_user_id AND work_date=p_date;
    IF coalesce(v_revision,0)<>p_revision THEN RAISE EXCEPTION 'PERSONNEL_STALE'; END IF;
    INSERT INTO public.payroll_days(user_id,work_date,kind,note) VALUES(p_user_id,p_date,p_kind,p_note)
    ON CONFLICT(user_id,work_date) DO UPDATE SET kind=excluded.kind,note=excluded.note,
        revision=payroll_days.revision+1;
    INSERT INTO public.personnel_audit(user_id,actor_id,action,reference_date)
        VALUES(p_user_id,auth.uid(),'payroll_day_update',p_date);
    RETURN jsonb_build_object('success',true);
END $$;

-- Complete source per employee/month, not a PostgREST row-limited nested report.
CREATE FUNCTION public.payroll_source(p_user_id uuid,p_month date) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public SET timezone = 'UTC' AS $$
DECLARE v_terms jsonb; v_employee jsonb; v_schedules jsonb; v_days jsonb; v_hr jsonb;
BEGIN
    PERFORM public.payroll_require_admin();
    IF p_month IS NULL OR extract(day FROM p_month)<>1 THEN RAISE EXCEPTION 'PERSONNEL_INVALID'; END IF;
    SELECT to_jsonb(t) INTO v_terms FROM public.employee_pay_terms t WHERE user_id=p_user_id
        AND effective_month<=p_month ORDER BY effective_month DESC LIMIT 1;
    SELECT jsonb_build_object('id',p.id,'full_name',p.full_name,'branch_id',p.branch_id,'role',p.role,'branch_name',b.name)
        INTO v_employee FROM public.profiles p LEFT JOIN public.branches b ON b.id=p.branch_id WHERE p.id=p_user_id;
    IF v_employee IS NULL THEN RAISE EXCEPTION 'PERSONNEL_INVALID'; END IF;
    SELECT jsonb_build_object('hire_date',hire_date,'end_date',end_date) INTO v_hr
        FROM public.employee_private WHERE user_id=p_user_id;
    SELECT coalesce(jsonb_agg(jsonb_build_object('id',s.id,'work_date',s.work_date,'status',s.status,
        'start_time',sh.start_time,'end_time',sh.end_time,'check_in',a.check_in,'check_out',a.check_out,
        'late_minutes',a.late_minutes) ORDER BY s.work_date,sh.start_time,s.id),'[]') INTO v_schedules
        FROM public.schedules s JOIN public.shifts sh ON sh.id=s.shift_id
        LEFT JOIN public.attendance a ON a.schedule_id=s.id
        WHERE s.user_id=p_user_id AND s.work_date>=p_month AND s.work_date<p_month+interval '1 month';
    SELECT coalesce(jsonb_agg(to_jsonb(d) ORDER BY work_date),'[]') INTO v_days
        FROM public.payroll_days d WHERE user_id=p_user_id AND work_date>=p_month
        AND work_date<p_month+interval '1 month';
    RETURN jsonb_build_object('employee',v_employee,'terms',v_terms,'employment',v_hr,
        'schedules',v_schedules,'days',v_days,'month',p_month);
END $$;

-- Pure server-side calculator. All money remains numeric, rounded once to VND.
CREATE FUNCTION public.payroll_calculate(p_source jsonb) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path = public AS $$
DECLARE
    t jsonb := p_source->'terms'; m date := (p_source->>'month')::date;
    month_days integer; eligible integer; daily integer; standard integer; expected integer;
    d date; item jsonb; mark jsonb; kind text; planned integer; worked integer; actual integer;
    paid integer:=0; regular integer:=0; extra integer:=0; accounted integer:=0; late_count integer:=0;
    regular_late integer:=0;
    extra_days integer:=0; rest_days integer:=0; warnings jsonb:='[]'; ledger jsonb:='[]';
    starts timestamptz; ends timestamptz; ci timestamptz; co timestamptz; previous_end timestamptz;
    previous_work_end timestamptz; minutes integer; late integer; day_late integer;
    rate numeric; base numeric; deduction numeric; extra_pay numeric; bonus numeric; missing integer;
    first_day date; last_day date; day_warning text; has_leave boolean; day_start integer;
BEGIN
    IF t IS NULL OR t='null' THEN RETURN jsonb_build_object('warnings',jsonb_build_array('Chưa cấu hình lương'),
        'days','[]'::jsonb,'net_salary',NULL); END IF;
    month_days:=extract(day FROM (m+interval '1 month - 1 day'));
    first_day:=greatest(m,coalesce((p_source->'employment'->>'hire_date')::date,m));
    last_day:=least((m+interval '1 month - 1 day')::date,
        coalesce((p_source->'employment'->>'end_date')::date,(m+interval '1 month - 1 day')::date));
    eligible:=greatest(0,last_day-first_day+1); daily:=(t->>'daily_minutes')::integer;
    standard:=(month_days-(t->>'paid_rest_days')::integer)*daily;
    expected:=greatest(0,eligible-(t->>'paid_rest_days')::integer)*daily;
    IF standard<=0 OR expected<=0 THEN RETURN jsonb_build_object('warnings',
        jsonb_build_array('Không có công chuẩn trong kỳ'), 'days','[]'::jsonb,'net_salary',NULL); END IF;
    FOR d IN SELECT generate_series(m,m+interval '1 month - 1 day',interval '1 day')::date LOOP
        SELECT value INTO mark FROM jsonb_array_elements(p_source->'days') WHERE (value->>'work_date')::date=d;
        kind:=coalesce(mark->>'kind','regular'); planned:=0; worked:=0; day_late:=0;
        day_warning:=''; has_leave:=false; previous_end:=NULL; day_start:=late_count;
        FOR item IN SELECT value FROM jsonb_array_elements(p_source->'schedules')
            WHERE (value->>'work_date')::date=d ORDER BY value->>'start_time',value->>'id' LOOP
            starts:=(d+(item->>'start_time')::time) AT TIME ZONE 'Asia/Ho_Chi_Minh';
            ends:=(d+(item->>'end_time')::time) AT TIME ZONE 'Asia/Ho_Chi_Minh';
            IF ends<=starts THEN ends:=((d+1)+(item->>'end_time')::time) AT TIME ZONE 'Asia/Ho_Chi_Minh'; END IF;
            IF previous_end>starts OR previous_work_end>starts THEN day_warning:='Ca chồng nhau'; END IF;
            previous_end:=ends; previous_work_end:=ends;
            planned:=planned+floor(extract(epoch FROM ends-starts)/60)::integer;
            IF item->>'status'='leave' THEN has_leave:=true; END IF;
            ci:=(item->>'check_in')::timestamptz; co:=(item->>'check_out')::timestamptz;
            IF ci IS NULL THEN
                IF item->>'status'='completed' THEN day_warning:='Ca hoàn thành thiếu chấm công';
                ELSIF item->>'status'='scheduled' AND kind IN ('regular','extra_work') THEN
                    day_warning:='Ca chưa chấm công: cần xác nhận vắng/nghỉ';
                END IF;
                CONTINUE;
            END IF;
            late:=greatest(0,ceil(extract(epoch FROM ci-starts)/60)::integer);
            IF late>0 THEN late_count:=late_count+1; day_late:=day_late+late; END IF;
            IF co IS NULL THEN day_warning:='Chưa check-out'; CONTINUE; END IF;
            IF co<ci OR ci>=ends OR co<=starts OR item->>'status' IN ('leave','absent') THEN
                day_warning:='Chấm công không khớp ca'; CONTINUE;
            END IF;
            minutes:=floor(extract(epoch FROM least(ends,co)-greatest(starts,ci))/60)::integer;
            worked:=worked+greatest(0,minutes);
            IF coalesce((item->>'late_minutes')::integer,0)<>late THEN
                day_warning:='Phút muộn không khớp timestamp';
            END IF;
        END LOOP;
        IF d<first_day OR d>last_day THEN
            IF planned>0 OR mark IS NOT NULL THEN day_warning:='Dữ liệu ngoài thời gian làm việc'; END IF;
            kind:='outside';
        ELSE
            IF planned>daily THEN day_warning:=concat_ws(' · ',nullif(day_warning,''),'Tổng ca vượt giờ chuẩn/ngày'); END IF;
            IF has_leave AND kind NOT IN ('paid_leave','unpaid_leave') THEN
                day_warning:='Cần phân loại nghỉ hưởng lương/không lương';
            END IF;
            actual:=least(worked,daily);
            IF kind='regular' THEN regular:=regular+actual; accounted:=accounted+least(planned,daily);
                regular_late:=regular_late+least(day_late,daily);
            ELSIF kind='extra_work' THEN extra:=extra+actual; extra_days:=extra_days+1;
            ELSIF kind='paid_leave' THEN paid:=paid+daily; accounted:=accounted+daily;
            ELSIF kind IN ('unpaid_leave','absent') THEN accounted:=accounted+daily;
            ELSIF kind='rest' THEN rest_days:=rest_days+1;
            END IF;
            IF kind IN ('paid_leave','unpaid_leave','absent','rest') AND worked>0 THEN
                day_warning:='Có chấm công trên ngày nghỉ: cần phân loại lại';
            END IF;
        END IF;
        IF day_warning<>'' THEN warnings:=warnings||jsonb_build_array(d::text||': '||day_warning); END IF;
        ledger:=ledger||jsonb_build_array(jsonb_build_object('date',d,'kind',kind,'planned_minutes',planned,
            'worked_minutes',least(worked,daily),'late_minutes',day_late,'late_count',late_count-day_start,
            'warning',day_warning,'note',coalesce(mark->>'note',''),'revision',coalesce((mark->>'revision')::integer,0)));
    END LOOP;
    IF accounted<>expected THEN warnings:=warnings||jsonb_build_array('Công được xếp/phân loại chưa khớp công chuẩn'); END IF;
    IF rest_days+extra_days>(t->>'paid_rest_days')::integer THEN
        warnings:=warnings||jsonb_build_array('Số ngày nghỉ/làm thêm vượt định mức nghỉ hưởng lương'); END IF;
    IF regular+paid>expected THEN warnings:=warnings||jsonb_build_array('Công hưởng lương vượt công chuẩn'); END IF;
    rate:=(t->>'monthly_salary')::numeric/standard;
    base:=expected*rate; missing:=greatest(0,expected-regular-paid);
    deduction:=missing*rate; extra_pay:=extra*rate;
    bonus:=CASE WHEN late_count<=(t->>'allowed_late_count')::integer AND missing<=regular_late
        THEN (t->>'attendance_bonus')::numeric ELSE 0 END;
    RETURN jsonb_build_object('days',ledger,'warnings',warnings,'standard_minutes',standard,
        'expected_minutes',expected,'regular_minutes',regular,'paid_leave_minutes',paid,'extra_minutes',extra,
        'missing_minutes',missing,'late_count',late_count,'daily_rate',rate*daily,
        'monthly_salary',(t->>'monthly_salary')::numeric,'base_salary',round(base),
        'deduction',round(deduction),'extra_pay',round(extra_pay),'bonus',bonus,
        'net_salary',round(base-deduction+extra_pay+bonus),'terms',t,'rule_version',1);
END $$;

CREATE FUNCTION public.rpc_payroll_preview(p_user_id uuid,p_month date) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE src jsonb; result jsonb;
BEGIN
    PERFORM public.payroll_require_admin();
    SELECT s.result||jsonb_build_object('finalized',true,'finalized_at',s.finalized_at)
        INTO result FROM public.payroll_snapshots s WHERE user_id=p_user_id AND month=p_month;
    IF result IS NOT NULL THEN RETURN result; END IF;
    src:=public.payroll_source(p_user_id,p_month);
    RETURN public.payroll_calculate(src)||jsonb_build_object('user_id',p_user_id,'month',p_month,
        'employee',src->'employee','source_signature',md5(src::text),'finalized',false,
        'period_closed',(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date >= (p_month+interval '1 month')::date);
END $$;

CREATE FUNCTION public.rpc_finalize_payroll(p_user_id uuid,p_month date,p_signature text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE result jsonb; src jsonb;
BEGIN
    PERFORM public.payroll_require_admin();
    PERFORM pg_advisory_xact_lock(hashtextextended('payroll:'||p_user_id::text,0));
    IF EXISTS(SELECT 1 FROM public.payroll_snapshots WHERE user_id=p_user_id AND month=p_month) THEN
        RAISE EXCEPTION 'PAYROLL_LOCKED'; END IF;
    result:=public.rpc_payroll_preview(p_user_id,p_month);
    IF p_signature IS NULL OR result->>'source_signature' IS DISTINCT FROM p_signature THEN
        RAISE EXCEPTION 'PERSONNEL_STALE'; END IF;
    IF NOT (result->>'period_closed')::boolean OR jsonb_array_length(result->'warnings')>0
        OR result->>'net_salary' IS NULL THEN RAISE EXCEPTION 'PAYROLL_NOT_READY'; END IF;
    src:=public.payroll_source(p_user_id,p_month);
    IF md5(src::text) IS DISTINCT FROM p_signature THEN RAISE EXCEPTION 'PERSONNEL_STALE'; END IF;
    INSERT INTO public.payroll_snapshots(user_id,month,result,source,finalized_by)
        VALUES(p_user_id,p_month,result,src,auth.uid());
    INSERT INTO public.personnel_audit(user_id,actor_id,action,reference_date)
        VALUES(p_user_id,auth.uid(),'payroll_finalize',p_month);
    RETURN jsonb_build_object('success',true);
END $$;

CREATE FUNCTION public.rpc_payroll_page(p_month date,p_offset integer DEFAULT 0,
    p_limit integer DEFAULT 21,p_search text DEFAULT '',p_branch_id uuid DEFAULT NULL) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE p record; rows jsonb:='[]';
BEGIN
    PERFORM public.payroll_require_admin();
    IF p_offset IS NULL OR p_offset<0 OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 51
       OR p_month IS NULL OR extract(day FROM p_month)<>1 THEN RAISE EXCEPTION 'PERSONNEL_INVALID'; END IF;
    FOR p IN SELECT e.id,coalesce(ps.result->'employee'->>'full_name',e.full_name) AS full_name,
        e.phone,e.is_active,coalesce(ps.result->'employee'->>'branch_name',b.name) AS branch_name FROM public.profiles e
        LEFT JOIN public.branches b ON b.id=e.branch_id
        LEFT JOIN public.payroll_snapshots ps ON ps.user_id=e.id AND ps.month=p_month
        WHERE e.role<>'admin' AND (p_branch_id IS NULL OR
            coalesce((ps.result->'employee'->>'branch_id')::uuid,e.branch_id)=p_branch_id)
        AND position(lower(coalesce(p_search,'')) IN lower(coalesce(ps.result->'employee'->>'full_name',e.full_name)))>0
        ORDER BY e.full_name,e.id OFFSET p_offset LIMIT p_limit LOOP
        rows:=rows||jsonb_build_array((public.rpc_payroll_preview(p.id,p_month)-'days'-'terms')||jsonb_build_object(
            'full_name',p.full_name,'phone',p.phone,'branch_name',p.branch_name,'is_active',p.is_active));
    END LOOP;
    RETURN rows;
END $$;

-- Serialize payroll close with attendance/schedule mutations. Snapshots never change.
CREATE FUNCTION public.payroll_source_lock() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE old_id uuid; new_id uuid; first_id uuid; second_id uuid;
BEGIN
    IF TG_OP<>'INSERT' THEN old_id:=OLD.user_id; END IF;
    IF TG_OP<>'DELETE' THEN new_id:=NEW.user_id; END IF;
    first_id:=least(old_id,new_id); second_id:=greatest(old_id,new_id);
    IF first_id IS NOT NULL THEN PERFORM pg_advisory_xact_lock(hashtextextended('payroll:'||first_id::text,0)); END IF;
    IF second_id IS NOT NULL AND second_id IS DISTINCT FROM first_id THEN
        PERFORM pg_advisory_xact_lock(hashtextextended('payroll:'||second_id::text,0)); END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE TRIGGER payroll_attendance_lock BEFORE INSERT OR UPDATE OR DELETE ON public.attendance
    FOR EACH ROW EXECUTE FUNCTION public.payroll_source_lock();
CREATE TRIGGER payroll_schedule_lock BEFORE INSERT OR UPDATE OR DELETE ON public.schedules
    FOR EACH ROW EXECUTE FUNCTION public.payroll_source_lock();

CREATE FUNCTION public.rpc_upcoming_birthdays(p_offset integer DEFAULT 0,p_limit integer DEFAULT 51)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE result jsonb; today date:=(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
BEGIN
    PERFORM public.payroll_require_admin();
    IF p_offset IS NULL OR p_offset<0 OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 201 THEN
        RAISE EXCEPTION 'PERSONNEL_INVALID'; END IF;
    SELECT coalesce(jsonb_agg(to_jsonb(b) ORDER BY days_until,full_name,user_id),'[]') INTO result FROM (
        SELECT e.user_id,p.full_name,e.birth_date,n.birthday-today AS days_until,
            extract(year FROM n.birthday)::integer-extract(year FROM e.birth_date)::integer AS age
        FROM public.employee_private e JOIN public.profiles p ON p.id=e.user_id
        CROSS JOIN LATERAL (SELECT min(day::date) AS birthday FROM generate_series(today,today+60,interval '1 day') day
            WHERE extract(month FROM day)=extract(month FROM e.birth_date)
            AND extract(day FROM day)=least(extract(day FROM e.birth_date),
                extract(day FROM date_trunc('month',day)+interval '1 month - 1 day'))) n
        WHERE p.is_active IS TRUE AND e.birth_date IS NOT NULL AND n.birthday-today<=e.birthday_notice_days
        ORDER BY days_until,p.full_name,e.user_id OFFSET p_offset LIMIT p_limit
    ) b;
    RETURN result;
END $$;

-- Helpers are private even if default privileges in the project grant functions.
REVOKE ALL ON FUNCTION public.payroll_require_admin(),public.payroll_source(uuid,date),
    public.payroll_calculate(jsonb),public.payroll_source_lock() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.rpc_employee_private(uuid),public.rpc_save_employee_private(uuid,jsonb,integer),
    public.rpc_save_pay_terms(uuid,date,jsonb,integer),public.rpc_set_payroll_day(uuid,date,text,text,integer),
    public.rpc_payroll_preview(uuid,date),public.rpc_finalize_payroll(uuid,date,text),
    public.rpc_upcoming_birthdays(integer,integer) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.rpc_payroll_page(date,integer,integer,text,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_employee_private(uuid),public.rpc_save_employee_private(uuid,jsonb,integer),
    public.rpc_save_pay_terms(uuid,date,jsonb,integer),public.rpc_set_payroll_day(uuid,date,text,text,integer),
    public.rpc_payroll_preview(uuid,date),public.rpc_finalize_payroll(uuid,date,text),
    public.rpc_upcoming_birthdays(integer,integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_payroll_page(date,integer,integer,text,uuid) TO authenticated;

CREATE OR REPLACE FUNCTION public.rpc_client_version() RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
AS $$ SELECT CASE WHEN public.get_current_role() IS NOT NULL THEN 4 ELSE NULL END $$;
REVOKE ALL ON FUNCTION public.rpc_client_version() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.rpc_client_version() TO authenticated;
NOTIFY pgrst, 'reload schema';
COMMIT;

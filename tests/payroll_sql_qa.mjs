// Local in-memory PostgreSQL QA only: no sockets, .env, Supabase or real records.
// Set PGLITE_MODULE to a locally installed @electric-sql/pglite/dist/index.js.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { PGlite } = await import(process.env.PGLITE_MODULE
  ? pathToFileURL(process.env.PGLITE_MODULE).href : '@electric-sql/pglite');
const db = new PGlite();
let checks = 0;
const eq = (a, b) => { assert.deepEqual(a, b); checks++; };
async function rejects(sql, params, token) {
  await assert.rejects(db.query(sql, params), err => err.message.includes(token)); checks++;
}
const admin = '00000000-0000-0000-0000-000000000001';
const staff = '00000000-0000-0000-0000-000000000002';
const manager = '00000000-0000-0000-0000-000000000003';
const branch = '00000000-0000-0000-0000-000000000004';
const shift = '00000000-0000-0000-0000-000000000005';
try {
  await db.exec(`
    CREATE ROLE anon; CREATE ROLE authenticated;
    CREATE SCHEMA auth;
    CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
      $$ SELECT nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
    CREATE TABLE public.branches(id uuid PRIMARY KEY,name text);
    CREATE TABLE public.profiles(id uuid PRIMARY KEY,full_name text,role text,is_active boolean,
      phone text,branch_id uuid REFERENCES public.branches(id));
    CREATE TABLE public.shifts(id uuid PRIMARY KEY,name text,start_time time,end_time time);
    CREATE TABLE public.schedules(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),user_id uuid,
      shift_id uuid REFERENCES public.shifts(id),branch_id uuid,work_date date,status text);
    CREATE TABLE public.attendance(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),schedule_id uuid UNIQUE,
      user_id uuid,check_in timestamptz,check_out timestamptz,late_minutes integer);
    CREATE FUNCTION public.get_current_role() RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
      SET search_path=public AS $$ SELECT role FROM public.profiles WHERE id=auth.uid() AND is_active $$;
  `);
  await db.query('INSERT INTO branches VALUES ($1,$2)', [branch, 'Offline branch']);
  for (const [id, name, role] of [[admin, 'Offline admin', 'admin'], [staff, 'Offline employee', 'staff'],
                                [manager, 'Offline manager', 'storemanager']]) {
    await db.query('INSERT INTO profiles VALUES($1,$2,$3,true,null,$4)', [id, name, role, branch]);
  }
  await db.exec(await readFile(new URL('../migrations/20261021_05_personnel_payroll.sql', import.meta.url), 'utf8'));
  await db.query("SELECT set_config('request.jwt.claim.sub',$1,false)", [admin]);

  const terms = { monthly_salary: 9000000, paid_rest_days: 4, daily_minutes: 480,
                  attendance_bonus: 500000, allowed_late_count: 2 };
  const source = () => ({ month: '2020-09-01', terms, employment: {}, days: [],
    schedules: Array.from({length: 26}, (_, i) => {
      const date = `2020-09-${String(i + 1).padStart(2, '0')}`;
      return {id: String(i), work_date: date, start_time: '08:00', end_time: '16:00', status: 'completed',
              check_in: `${date}T08:00:00+07:00`, check_out: `${date}T16:00:00+07:00`, late_minutes: 0};
    }) });
  const calc = async src => (await db.query('SELECT public.payroll_calculate($1::jsonb) AS r',
                                            [JSON.stringify(src)])).rows[0].r;
  let src = source(), r = await calc(src);
  eq(r.warnings, []); eq(r.net_salary, 9500000); eq(r.standard_minutes, 26 * 480);
  src = source(); src.schedules[0].check_in = '2020-09-01T07:00:00+07:00';
  src.schedules[0].check_out = '2020-09-01T18:00:00+07:00';
  eq((await calc(src)).net_salary, 9500000);
  for (const count of [1, 2, 3]) {
    src = source();
    for (let i = 0; i < count; i++) {
      src.schedules[i].check_in = src.schedules[i].check_in.replace('08:00:00', '08:10:00');
      src.schedules[i].late_minutes = 10;
    }
    r = await calc(src);
    eq(r.warnings, []); eq(r.late_count, count); eq(r.missing_minutes, count * 10);
    eq(r.bonus, count <= 2 ? 500000 : 0);
    eq(r.net_salary, Math.round(9000000 - count * 10 * 9000000 / (26 * 480) + (count <= 2 ? 500000 : 0)));
  }
  src = source(); src.schedules[0].check_out = '2020-09-01T15:00:00+07:00';
  r = await calc(src); eq(r.missing_minutes, 60); eq(r.bonus, 0);
  src = source(); src.schedules[0].check_out = null;
  assert((await calc(src)).warnings.some(s => s.includes('Chưa check-out'))); checks++;
  src = source(); src.schedules[0].check_in=null; src.schedules[0].check_out=null;
  assert((await calc(src)).warnings.some(s=>s.includes('thiếu chấm công'))); checks++;
  src.schedules[0].status='scheduled';
  assert((await calc(src)).warnings.some(s=>s.includes('xác nhận vắng'))); checks++;
  src.days=[{work_date:'2020-09-01',kind:'absent'}]; src.schedules[0].status='absent';
  r=await calc(src); eq(r.warnings,[]); eq(r.missing_minutes,480);
  src = source(); src.schedules[0].check_in = '2020-09-01T08:00:01+07:00'; src.schedules[0].late_minutes = 1;
  r = await calc(src); eq(r.missing_minutes, 1); eq(r.late_count, 1); eq(r.bonus, 500000);
  src = source(); src.schedules[0].status = 'leave'; src.schedules[0].check_in = null; src.schedules[0].check_out = null;
  assert((await calc(src)).warnings.some(s => s.includes('phân loại nghỉ'))); checks++;
  src.days = [{work_date: '2020-09-01',kind: 'paid_leave'}]; r = await calc(src);
  eq(r.warnings, []); eq(r.net_salary, 9500000);
  src.days[0].kind = 'unpaid_leave'; r = await calc(src);
  eq(r.missing_minutes, 480); eq(r.net_salary, Math.round(9000000 * 25 / 26));
  src = source(); src.schedules.push({...src.schedules[0],id:'extra',work_date:'2020-09-27',
    check_in:'2020-09-27T08:00:00+07:00',check_out:'2020-09-27T16:00:00+07:00'});
  assert((await calc(src)).warnings.length > 0); checks++;
  src.days = [{work_date:'2020-09-27',kind:'extra_work'}]; r = await calc(src);
  eq(r.warnings, []); eq(r.extra_pay, Math.round(9000000 / 26)); eq(r.net_salary, Math.round(9500000 + 9000000 / 26));
  src.schedules[26].check_out='2020-09-27T12:00:00+07:00';
  eq((await calc(src)).extra_pay, Math.round(9000000 / 52));
  src = source(); src.schedules.push({...src.schedules[0],id:'overlap'});
  assert((await calc(src)).warnings.some(s => s.includes('chồng'))); checks++;
  src = source(); src.schedules[0].start_time='22:00'; src.schedules[0].end_time='06:00';
  src.schedules[0].check_in='2020-09-01T15:00:00Z'; src.schedules[0].check_out='2020-09-01T23:00:00Z';
  eq((await calc(src)).net_salary, 9500000);
  src = source(); src.schedules[0].late_minutes = 420;
  assert((await calc(src)).warnings.some(s => s.includes('khớp timestamp'))); checks++;
  src = source(); src.schedules.pop();
  assert((await calc(src)).warnings.some(s => s.includes('công chuẩn'))); checks++;
  eq((await calc({...source(),terms:null})).net_salary, null);
  // Calendar length changes the daily/minute rate; approved rest is not deducted twice.
  for (const [month, days] of [['2020-02',29],['2021-02',28],['2020-10',31]]) {
    src = source(); src.month=month+'-01';
    src.schedules=Array.from({length: days-4},(_,i)=>{
      const d=month+'-'+String(i+1).padStart(2,'0');
      return {id:String(i),work_date:d,start_time:'08:00',end_time:'16:00',status:'completed',
        check_in:d+'T08:00:00+07:00',check_out:d+'T16:00:00+07:00',late_minutes:0};
    });
    r=await calc(src); eq(r.standard_minutes,(days-4)*480); eq(r.net_salary,9500000); eq(r.warnings,[]);
  }
  src=source(); src.employment={hire_date:'2020-09-11'}; src.schedules=src.schedules.slice(10);
  r=await calc(src); eq(r.expected_minutes,16*480); eq(r.warnings,[]);
  eq(r.net_salary,Math.round(9000000*16/26+500000));

  // Execute RPCs and persisted snapshots, not just the isolated calculator.
  await db.query('SELECT rpc_save_pay_terms($1,$2,$3,0)', [staff, '2020-09-01', JSON.stringify(terms)]);
  await rejects('SELECT rpc_save_pay_terms($1,$2,$3,0)', [staff, '2020-09-01', JSON.stringify(terms)], 'PERSONNEL_STALE');
  await db.query('INSERT INTO shifts VALUES($1,$2,$3,$4)', [shift,'Offline shift','08:00','16:00']);
  for (const s of source().schedules) {
    const id = (await db.query('INSERT INTO schedules(user_id,shift_id,branch_id,work_date,status) VALUES($1,$2,$3,$4,$5) RETURNING id',
                              [staff,shift,branch,s.work_date,s.status])).rows[0].id;
    await db.query('INSERT INTO attendance(schedule_id,user_id,check_in,check_out,late_minutes) VALUES($1,$2,$3,$4,0)',
                   [id,staff,s.check_in,s.check_out]);
  }
  const preview = async () => (await db.query('SELECT rpc_payroll_preview($1,$2) AS r', [staff,'2020-09-01'])).rows[0].r;
  r = await preview(); eq(r.warnings, []); eq(r.net_salary,9500000); eq(r.period_closed,true);
  const oldSignature = r.source_signature;
  await db.exec("SET timezone='America/New_York'");
  eq((await preview()).source_signature,oldSignature);
  await db.exec("SET timezone='UTC'");
  await db.query('SELECT rpc_set_payroll_day($1,$2,$3,$4,0)', [staff,'2020-09-30','rest','Offline note']);
  await rejects('SELECT rpc_finalize_payroll($1,$2,$3)',[staff,'2020-09-01',oldSignature],'PERSONNEL_STALE');
  r = await preview();
  await db.query('SELECT rpc_finalize_payroll($1,$2,$3)', [staff,'2020-09-01',r.source_signature]);
  eq((await preview()).finalized,true);
  await rejects('SELECT rpc_set_payroll_day($1,$2,$3,$4,1)', [staff,'2020-09-30','regular','Offline note'],'PAYROLL_LOCKED');
  await rejects('SELECT rpc_save_pay_terms($1,$2,$3,1)', [staff,'2020-09-01',JSON.stringify(terms)],'PAYROLL_LOCKED');
  await db.exec('UPDATE attendance SET check_out=check_out+interval \'1 hour\'');
  eq((await preview()).source_signature,r.source_signature);
  eq(Date.parse((await db.query('SELECT source->\'schedules\'->0->>\'check_out\' AS t FROM payroll_snapshots WHERE user_id=$1',
    [staff])).rows[0].t),Date.parse('2020-09-01T09:00:00Z'));
  await db.query('SELECT rpc_save_pay_terms($1,$2,$3,0)', [staff,'2020-10-01',JSON.stringify({...terms,monthly_salary:10000000})]);
  eq((await preview()).net_salary,9500000);
  const future=(await db.query("SELECT (date_trunc('month',now())+interval '1 month')::date::text AS d")).rows[0].d;
  let futurePreview=(await db.query('SELECT rpc_payroll_preview($1,$2) AS r',[staff,future])).rows[0].r;
  eq(futurePreview.period_closed,false);
  await rejects('SELECT rpc_finalize_payroll($1,$2,$3)',[staff,future,futurePreview.source_signature],'PAYROLL_NOT_READY');
  let page = (await db.query('SELECT rpc_payroll_page($1,0,1,$2,null) AS r', ['2020-09-01','Offline'])).rows[0].r;
  eq(page.length,1);
  const page2 = (await db.query('SELECT rpc_payroll_page($1,1,1,$2,null) AS r', ['2020-09-01','Offline'])).rows[0].r;
  assert(page[0].user_id!==page2[0].user_id); checks++;
  await db.query('INSERT INTO branches VALUES($1,$2)',['00000000-0000-0000-0000-000000000099','New offline branch']);
  await db.query('UPDATE profiles SET branch_id=$1,full_name=$2 WHERE id=$3',
    ['00000000-0000-0000-0000-000000000099','Changed offline name',staff]);
  page=(await db.query('SELECT rpc_payroll_page($1,0,21,$2,$3) AS r', ['2020-09-01','Offline employee',branch])).rows[0].r;
  eq(page.length,1); eq(page[0].branch_name,'Offline branch'); eq(page[0].full_name,'Offline employee');
  eq('days' in page[0],false);
  const today = (await db.query("SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date::text AS d")).rows[0].d;
  const birth = '2000'+today.slice(4);
  await db.query('SELECT rpc_save_employee_private($1,$2,0)', [staff,JSON.stringify({birth_date:birth,
    employee_code:'OFF-001',identity_number:'001234567890',bank_account:'00001234',birthday_notice_days:'7'})]);
  const privateData = (await db.query('SELECT rpc_employee_private($1) AS r',[staff])).rows[0].r;
  eq(privateData.details.details.bank_account,'00001234');
  await rejects('SELECT rpc_save_employee_private($1,$2,0)',[staff,'{}'],'PERSONNEL_STALE');
  await rejects('SELECT rpc_save_employee_private($1,$2,0)',[manager,'{"employee_code":"off-001"}'],'duplicate key');
  eq((await db.query('SELECT rpc_upcoming_birthdays(0,51) AS r')).rows[0].r[0].days_until,0);
  await rejects('SELECT rpc_save_employee_private($1,$2,1)',[staff,'{"role":"admin"}'],'PERSONNEL_INVALID');
  eq((await db.query("SELECT count(*)::int AS n FROM personnel_audit WHERE changed_fields::text LIKE '%001234567890%'")).rows[0].n,0);
  await db.exec('SET ROLE authenticated');
  eq((await db.query('SELECT rpc_client_version() AS v')).rows[0].v,4);
  await rejects('SELECT * FROM employee_private', [], 'permission denied');
  await rejects('SELECT * FROM payroll_snapshots', [], 'permission denied');
  await rejects('UPDATE employee_pay_terms SET monthly_salary=1', [], 'permission denied');
  await rejects('UPDATE payroll_days SET kind=\'paid_leave\'', [], 'permission denied');
  await rejects('SELECT payroll_calculate($1)', [JSON.stringify(source())], 'permission denied');
  for (const who of [staff, manager, '']) {
    await db.query("SELECT set_config('request.jwt.claim.sub',$1,false)",[who]);
    await rejects('SELECT rpc_employee_private($1)', [staff], 'PERSONNEL_FORBIDDEN');
    await rejects('SELECT rpc_payroll_preview($1,$2)', [staff,'2020-09-01'], 'PERSONNEL_FORBIDDEN');
    await rejects('SELECT rpc_upcoming_birthdays(0,51)', [], 'PERSONNEL_FORBIDDEN');
    await rejects('SELECT rpc_save_pay_terms($1,$2,$3,0)',[staff,'2030-01-01',JSON.stringify(terms)],'PERSONNEL_FORBIDDEN');
  }
  await db.exec('RESET ROLE');
  await db.query("SELECT set_config('request.jwt.claim.sub',$1,false)",[admin]);
  await db.query('UPDATE profiles SET is_active=false WHERE id=$1',[admin]);
  await rejects('SELECT rpc_employee_private($1)', [staff], 'PERSONNEL_FORBIDDEN');
  console.log(`Payroll SQL QA: ${checks} checks passed (in-memory PostgreSQL; no Supabase connection).`);
} finally {
  await db.close();
}

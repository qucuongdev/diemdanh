# Attendance desktop — instructions for contributors and AI agents

Read this file before exploring or changing the project. Follow any more specific
AGENTS.md in a subdirectory. Read only the files needed for the task; never read
`.env`, tokens, passwords, or production records into tool output.

Then read [WORKLOG.md](WORKLOG.md) for the current handoff, accepted user decisions,
verification evidence and remaining work before continuing in a new chat. Treat
its backlog as context, not blanket authorization to deploy or mutate a database.

## Maintenance contract

Every change must update this file in the same change set: keep the architecture,
commands, known limitations, and change record accurate. Record what was verified
and what remains unverified. Do not claim production or database verification from
offline tests. These instructions apply to all contributors; tools that do not
automatically discover AGENTS.md must be directed to read it explicitly.
Also keep WORKLOG.md current with completed work, actual checks, unresolved issues
and the next useful step; preserve the distinction between offline and real backend
verification. Keep README focused on concise Git Bash setup/run commands.

## Product and architecture

- Windows desktop attendance for pharmacy branches; Vietnamese user-facing text.
- Target UI: PySide6 only. `main.py` is the single application entry point.
  `views_qt/` owns presentation.
- `core/supabase_service.py`: Supabase Auth, PostgREST, Storage and RPC boundary.
- `core/qt_worker.py`: background task lifecycle and main-thread delivery.
- `core/hardware.py`: process-cached device identity; perform cold lookup off UI.
- `core/config.py`: environment settings (public Supabase key only).
- `schema.sql`: initial schema. `migrations/`: separately reviewed incremental SQL.
- `tests/`: isolated unittest tests; never contact production or load real secrets.
- PySide6 is the only UI. Benchmark compatibility launchers measure Qt tables;
  no CustomTkinter/Tkinter runtime or views remain. Do not reintroduce them.
- App 1.0.0 requires backend 3, published by migration 04 only after its transaction
  commits. `preflight.sql` and `DEPLOYMENT.md` describe separate backend review.
- Profile mutations use admin RPCs; migration 04 removes direct profile writes,
  restores scoped shift policies and protects recorded shift times.
- `views_qt/qt_theme.py` owns light/dark tokens, native Qt palettes and a shared
  theme controller. QSettings stores only the appearance preference; tests and
  benchmarks use no real user settings by default.
- Clocks display HH:mm; durations format server integer minutes as unbounded
  hours:minutes. Source seconds/timezones remain intact. Excel durations are
  numeric with [h]:mm formatting, not decimal hours or a wrapped time of day.

## Rules and conventions

- Python: four spaces, UTF-8, snake_case functions, PascalCase classes. Prefer small
  explicit modules, typed boundaries, reusable helpers over duplicated view logic.
- No network, subprocess, image compression or file export on the GUI thread.
  All widget changes must execute on the GUI thread through QObject slots.
- Bind task callbacks to widget lifetime. Ignore stale read results after filter,
  session or page changes. Prevent duplicate mutations; restore controls on errors.
- Use Qt models/views for data lists. Paginate server queries, preserve filters,
  and never silently present truncated data as a complete report or total.
- Centralize theme tokens; readable fonts, consistent spacing, clear focus and
  disabled states. Use plain Vietnamese labels and plain-text rendering for data.
- Dates use Asia/Ho_Chi_Minh; preserve timezone when parsing timestamps. Attendance
  authority is PostgreSQL server time and RPC validation, never the desktop clock.
- UI role checks are usability guards, not authorization. RLS/RPC enforce access.
  Fail closed for inactive users, missing branch, invalid role or invalid device.
- Never ship service-role/secret keys in the desktop client. Never print credentials
  or raw server exceptions to users. Keep proof images private and use signed URLs.
- Avoid insecure CRUD fallbacks when an authorization RPC is unavailable.
- Do not automatically execute SQL migrations or mutate real backend data as tests.
- Tests must cover behavior: roles, request races, errors, destruction, pagination,
  query scope and security boundaries. Do not rely on sleep or network availability.

## Development commands

```powershell
python -m pip install -r requirements.txt
python main.py
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest discover -s tests -v
python -m compileall -q core views_qt main.py
python -m pip install -r requirements-dev.txt
python -m ruff check core views_qt main.py migrate.py tests benchmark.py
python migrate.py --all-pending  # Review only: no database connection or .env load
```

## Current change record / verification

- 2026-10-20: Began PySide6-only migration and audit. Created contributor contract
  before implementation. Prior review reproduced expensive legacy card rendering.
- The Qt migration is implemented locally. Backend deployment and role-account
  acceptance checks remain separate and unverified; see DEPLOYMENT.md.
- 2026-10-20: Added Vietnamese README with Git Bash and PowerShell setup,
  public Supabase configuration, launcher compatibility, troubleshooting and
  offline verification commands. Checked documentation against launchers,
  dependency list and configuration code; reviewed patch whitespace. No app,
  dependency installation, database or production verification performed for
  this documentation-only change.

- 2026-10-20: Fixed Supabase initialization to import the public synchronous
  `ClientOptions` export instead of the internal base options class, which lacks
  `storage` and `httpx_client` in the locally installed SDK. Added offline client
  initialization and secret-key rejection regression tests. Verified SDK source
  and patch whitespace. Initial sandbox access could not reach the installed
  interpreter; scoped execution subsequently resolved this and the offline tests
  passed. No backend or production verification performed.
- 2026-10-20: Completed local Qt migration review for app 2.1.0/backend 3.
  Added actionable backend diagnostics, centered login form, clean logout on
  device-check exceptions, stale-data clearing, retained attendance messages,
  duplicate-mutation control guards, self-review guards, restored pagination
  after review failure, refresh on page return and stale proof-link cancellation.
  Migration 04 restores shift policies, requires profile writes through RPCs,
  protects recorded shift times, fixes new timestamp defaults and atomic employee
  Auth/identity creation. Prior migrations remain unchanged. Added preflight.sql,
  DEPLOYMENT.md and updated README.md/plan.md for Qt-only operation and limitations.
  Verified 51 offline unittest cases, Ruff, compileall, patch whitespace and six
  rendered Qt screens with fake data. SQL parser (pglast 8.7) accepted preflight
  and migrations 01–04; PL/pgSQL parsing accepted migration 04. This is syntax
  checking only, not database execution. Qt table benchmark: 50/150/1000 rows,
  18 child widgets at every size, median updates approximately 1.5 ms on this
  machine. Environment: Python 3.12.10, PySide6 6.12.0, Supabase 2.33.0.
  Supabase deployment, actual RLS/RPC/Auth behavior, historical data, Windows
  hardware lookup and real role/device acceptance remain unverified.

- 2026-10-20: Removed the redundant application compatibility launcher at the
  user's request. `main.py` is now the only app launcher; README, plan and
  development commands use it consistently. Verified 51 offline tests, Ruff,
  compileall and absence of references to the removed launcher in project text.
  No backend or production verification performed.

- 2026-10-20: Shortened README to first-time Windows prerequisites and Git Bash
  commands for dependency installation, non-overwriting .env template setup and
  launching with python main.py. Confirmed official download pages, template
  presence, project filenames and patch whitespace. No fresh-machine install,
  app or backend verification performed for this documentation-only change.

- 2026-10-20: Simplified one-command administrative migration setup. With --apply,
  migrate.py now accepts SUPABASE_DB_URL or prompts for a hidden PostgreSQL URI;
  it refuses visible-input fallback and reports missing admin dependencies clearly.
  Review-only mode still does not prompt, load .env or connect to the database.
  Updated README/DEPLOYMENT commands. Verified seven isolated migration tests,
  Ruff, compileall and patch whitespace. No real database migration executed.

- 2026-10-20: Migration apply mode now derives the standard direct database host
  from public SUPABASE_URL (environment or .env) and prompts only for a hidden
  database password. It percent-encodes passwords without trimming whitespace.
  SUPABASE_DB_URL still supports custom/session-pooler endpoints, including
  password-free or [YOUR-PASSWORD] templates; pooler hosts are never guessed.
  Review-only mode still reads no .env and makes no connection. Updated README
  and deployment instructions, including the direct endpoint IPv6 limitation.
  Verified 11 isolated migration tests with mocked settings/passwords, Ruff,
  compileall and patch whitespace. No real secrets were read in tests and no
  real database connection or migration was performed.

- 2026-10-21: Set the app version to 1.0.0; backend compatibility remains 3.
  Renamed attendance navigation/actions to Check-in / Check-out. Centralized
  HH:mm display and non-wrapping duration formatting; exact local dates/seconds
  remain in time tooltips and server data. Reports sum source integer minutes;
  Excel exports numeric [h]:mm durations, including totals over 24 hours.
  Added shared light/dark palettes and theme buttons at login/sidebar, with
  persistent QSettings preference and no data reload on theme change. Calendar
  markings follow theme tokens. Improved column sizing without scanning rows,
  bounded the attendance panel, translated form Save/Cancel, and refreshed error
  label styling. Updated README/plan/deployment version references.
  Verified 73 isolated unittest cases, Ruff, compileall and patch whitespace.
  Generated previews for six pages and two dialogs in both modes; visually
  inspected light/dark layouts. Tested preference persistence in temporary INI
  settings, timezone/second preservation, durations over 24 hours, Excel round
  trips and filter/control state across live theme changes. Offline Qt benchmark
  retained 18 child widgets at 50/150/1000 rows, with median updates 1.74/1.66/2.43
  ms on this machine. No backend migration is needed for these presentation
  changes. Real Supabase data, historical timestamp discrepancies, production
  behavior and native Windows preference persistence remain unverified.

- 2026-10-21: Added WORKLOG.md as the Vietnamese cross-chat handoff, covering
  user decisions, completed Qt/backend-tooling work, verification evidence,
  outstanding time discrepancies and prioritized next steps. New sessions must
  read it after AGENTS.md and update both files with relevant changes. Preserved
  the concise README and linked the handoff from plan.md. Checked documentation
  consistency, internal links and patch whitespace; no app, SQL or backend checks
  were rerun for this documentation-only handoff.

## Known deployment boundaries

- Backend state cannot be inferred from local SQL. Security changes require applying
  the supplied migration in Supabase and testing with separate real role accounts.
- Device UUID is a client-supplied identifier, not cryptographic device attestation.
- No deployment or production verification has been performed in this change.
- Proof approval records a decision only; it does not correct attendance times.
  Shift swaps are leave requests without automatic replacement assignment.
  No distributable Windows executable has been built.

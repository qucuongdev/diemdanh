# Attendance desktop — instructions for contributors and AI agents

Read this file before exploring or changing the project. Follow any more specific
AGENTS.md in a subdirectory. Read only the files needed for the task; never read
`.env`, tokens, passwords, or production records into tool output.

## Maintenance contract

Every change must update this file in the same change set: keep the architecture,
commands, known limitations, and change record accurate. Record what was verified
and what remains unverified. Do not claim production or database verification from
offline tests. These instructions apply to all contributors; tools that do not
automatically discover AGENTS.md must be directed to read it explicitly.

## Product and architecture

- Windows desktop attendance for pharmacy branches; Vietnamese user-facing text.
- Target UI: PySide6 only. `main.py` is the supported entry point; `main_qt.py`
  remains a compatibility launcher. `views_qt/` owns presentation.
- `core/supabase_service.py`: Supabase Auth, PostgREST, Storage and RPC boundary.
- `core/qt_worker.py`: background task lifecycle and main-thread delivery.
- `core/hardware.py`: process-cached device identity; perform cold lookup off UI.
- `core/config.py`: environment settings (public Supabase key only).
- `schema.sql`: initial schema. `migrations/`: separately reviewed incremental SQL.
- `tests/`: isolated unittest tests; never contact production or load real secrets.
- Legacy CustomTkinter views and framework comparison benchmarks are being removed
  as part of the PySide6 migration. Do not reintroduce Tkinter dependencies.

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
python -m compileall -q core views_qt main.py main_qt.py
```

## Current change record / verification

- 2026-10-20: Began PySide6-only migration and audit. Created contributor contract
  before implementation. Prior review reproduced expensive legacy card rendering.
- Migration and verification are in progress; update this section before delivery.

## Known deployment boundaries

- Backend state cannot be inferred from local SQL. Security changes require applying
  the supplied migration in Supabase and testing with separate real role accounts.
- Device UUID is a client-supplied identifier, not cryptographic device attestation.
- No deployment or production verification has been performed in this change.

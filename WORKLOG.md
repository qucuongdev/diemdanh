# Worklog / bàn giao dự án chấm công nhà thuốc

Cập nhật: **21/10/2026 — Asia/Ho_Chi_Minh (UTC+7)**.

File này giúp tiếp tục công việc ở chat mới. Đọc [AGENTS.md](AGENTS.md) trước, sau đó đọc trạng thái và việc còn mở bên dưới. Đây là ghi nhận tại thời điểm bàn giao; mã nguồn, trạng thái Git và yêu cầu mới của người dùng cần được đối chiếu trước khi sửa. Danh sách đề xuất không phải yêu cầu tự động triển khai mọi tính năng hoặc chạy SQL thật.

## 1. Trạng thái hiện tại và quyết định đã chốt

| Mục | Trạng thái |
| --- | --- |
| Sản phẩm | App desktop Windows chấm công chuỗi nhà thuốc, giao diện tiếng Việt |
| Công nghệ UI | **Chỉ PySide6/Qt**; không quay lại CustomTkinter vì bản cũ bị lag |
| Khởi chạy | **`python main.py`**; launcher tương thích cũ đã bị xóa theo yêu cầu |
| Phiên bản app | **1.0.0** theo yêu cầu người dùng; 2.1.0 trong các ghi chép cũ chỉ là lịch sử |
| Phiên bản backend | **4** từ tính năng nhân sự/lương, cần migration 05 sau 01–04; độc lập với app version |
| Thời gian | Giờ Việt Nam; PostgreSQL/RPC quyết định giờ chấm công |
| Hiển thị | Giờ `HH:mm`; mọi thời lượng dưới 60 phút hiện `N phút`, từ 60 phút hiện `hh:mm`: `59 phút`, `01:00`, `06:09`; không quay vòng ở 24 giờ |
| Tính toán | Giữ phút nguyên và timestamp gốc; không dùng chuỗi `06:09` hay giờ thập phân để tính tổng |
| Giao diện | Có sáng/tối ở đăng nhập và sidebar, lưu lựa chọn bằng QSettings |
| Kiểm thử gần nhất | **108 unittest ngoại tuyến đều qua**, Ruff/biên dịch nguồn đạt; pip check trước đó đạt; **101 kiểm tra SQL PostgreSQL trong bộ nhớ** ở giai đoạn lương |
| Backend thực tế | **05 đã commit theo yêu cầu**, đối chiếu checksum/backend 4/RLS/quyền bảng mới đạt; chưa nghiệm thu Auth/PostgREST/lương bằng tài khoản thật |

Người dùng chủ yếu dùng **Git Bash** và muốn README ngắn, gồm lệnh cài/chạy trên máy mới. Không đổi README trở lại thành tài liệu kỹ thuật dài. Nội dung triển khai chi tiết nằm trong [DEPLOYMENT.md](DEPLOYMENT.md).

## 2. Những việc đã làm

### 20/10/2026 — rà soát và hoàn thiện phần chuyển sang Qt

- Xác nhận mã chạy và requirements không còn phụ thuộc CustomTkinter/Tkinter. Các benchmark tương thích còn lại cũng chỉ đo Qt.
- Thống nhất một điểm khởi chạy `main.py`, bỏ launcher dư và cập nhật lệnh/tài liệu liên quan.
- Sửa khởi tạo Supabase: dùng `ClientOptions` được xuất công khai từ `supabase`, thay cho lớp options nội bộ thiếu thuộc tính trong SDK đã cài.
- Tách thông báo lỗi kiểm tra backend: thiếu RPC/migration, thiếu quyền, lỗi mạng, phiên bản không tương thích. Vẫn chặn truy cập nếu không xác nhận được backend; không có đường CRUD bỏ qua RPC bảo mật.
- Căn giữa form đăng nhập, giới hạn chiều rộng; chống đăng nhập trùng, xóa mật khẩu sau thao tác và đăng xuất khi kiểm tra thiết bị gặp lỗi bất ngờ.
- Rà các tác vụ nền và trạng thái giao diện: bỏ kết quả đọc cũ, xóa dữ liệu cũ khi tải thất bại, giữ thông báo chấm công, chống gửi trùng thao tác ghi và khôi phục nút khi lỗi.
- Làm mới lịch/danh mục khi quay lại trang; chặn duyệt yêu cầu của chính mình ở UI; khôi phục phân trang sau lỗi duyệt; bỏ kết quả URL ảnh cũ khi rời trang hoặc đổi lựa chọn.
- Giữ lịch sử có phân trang và báo cáo đọc hết trang; dữ liệu dài dùng Qt model/view, không tạo widget cho từng dòng.
- Giữ ảnh giải trình riêng tư, nén/upload ở tác vụ nền, xem qua URL ký có thời hạn.
- Tạo tài liệu cài/chạy, tài liệu triển khai, SQL kiểm tra trước triển khai và kiểm thử migration.

### Bộ migration đã chuẩn bị

| File | Vai trò |
| --- | --- |
| `migrations/20261020_01_security_and_indexes.sql` | Chính sách theo vai trò/chi nhánh, bảo vệ yêu cầu, Storage riêng tư, chỉ mục |
| `migrations/20261020_02_admin_rpc.sql` | RPC quản trị nhân viên |
| `migrations/20261020_03_attendance_rpc.sql` | Check-in/check-out bằng giờ server, kiểm tra thiết bị, duyệt nghỉ |
| `migrations/20261020_04_qt_completion.sql` | Bổ sung chính sách bảng ca còn thiếu, chặn ghi profile trực tiếp, bảo vệ giờ ca đã có chấm công, sửa mặc định timestamp mới, tạo Auth/identity/profile nguyên tử; công bố backend 3 |
| `migrations/20261021_05_personnel_payroll.sql` | Hồ sơ riêng, lịch sử chế độ lương, phân loại ngày, tính/chốt lương có snapshot nguồn, nhắc sinh nhật; công bố backend 4 |

Các migration 01–03 đã được giữ nguyên trong lần bổ sung 04. Không sửa file đã áp dụng để chữa lỗi mới; tạo migration tiếp theo sau khi rà soát. `schema.sql` là nền ban đầu, không chạy lại trên database hiện có; không dùng `update_admin_rpc.sql` cũ để cập nhật bản Qt này.

### Công cụ cập nhật database một lệnh

- `python migrate.py --all-pending` chỉ liệt kê file/checksum: không đọc `.env`, không hỏi mật khẩu, không kết nối database.
- Chỉ chế độ `--apply` mới kết nối và chạy SQL.
- Mặc định chế độ apply lấy project ID từ `SUPABASE_URL` trong môi trường hoặc `.env`, dựng địa chỉ PostgreSQL trực tiếp và **chỉ hỏi mật khẩu database**, nhập ẩn.
- Mật khẩu được mã hóa URL tự động, giữ nguyên khoảng trắng, không ghi ra file hoặc log. Công cụ dừng nếu terminal không hỗ trợ nhập ẩn.
- Có thể dùng `SUPABASE_DB_URL` cho endpoint tùy chỉnh/Session pooler; chấp nhận URI thiếu mật khẩu hoặc có `[YOUR-PASSWORD]` để vẫn chỉ hỏi mật khẩu.
- Không đoán host pooler từ project ID/vùng. Kết nối trực tiếp có hạn chế IPv6; cấu hình pooler theo DEPLOYMENT nếu cần.
- Ghi checksum vào `_schema_migrations`, bỏ qua file đã ghi nhận, từ chối file đã áp dụng nhưng bị sửa nội dung. SQL Editor không tự ghi lịch sử vào bảng này.

### 21/10/2026 — app 1.0.0, giờ:phút và sáng/tối

- Đổi phiên bản app thành **1.0.0**, giữ backend **3**.
- Đổi tên trang/menu và nút thành **Check-in / Check-out**.
- Dùng helper chung cho giờ và thời lượng ở trang chấm công, lịch sử và báo cáo; tổng thời lượng không quay về 0 khi vượt 24 giờ.
- Giữ ngày/giây chính xác trong tooltip để giải thích ca qua ngày hoặc đi muộn vài giây dù giờ hiển thị cùng phút.
- Hiển thị tình trạng đi muộn/về sớm cả sau check-out; không dùng “Đủ công” chỉ vì đã có check-out.
- Excel xuất thời lượng dạng số với định dạng **`[h]:mm`**, vẫn cộng tổng được và hỗ trợ trên 24 giờ. Giữ chống công thức từ dữ liệu người dùng.
- Thêm bộ token màu và QPalette sáng/tối dùng chung toàn app; cả popup, bảng, lịch, focus, selection và nút bị khóa đều theo theme.
- Nút chuyển theme có tại đăng nhập và sidebar, đồng bộ nhãn, lưu lựa chọn; không đăng nhập lại, không tải lại dữ liệu và không làm mất bộ lọc/trạng thái nút khi đổi màu.
- Chỉnh chiều rộng cột ưu tiên tên/chi nhánh, giảm khoảng trống ở cột cuối, không quét toàn bộ dữ liệu để đo cột.
- Giới hạn chiều rộng khối chấm công trên màn lớn, đổi Save/Cancel thành **Lưu/Hủy**, cập nhật màu trạng thái lỗi và mũi tên lịch trên nền tối.
- Các thay đổi giao diện/định dạng này **không cần migration mới**, không viết lại dữ liệu chấm công cũ.

## 3. Bản đồ mã nguồn cần biết

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `main.py` | Cửa sổ chính, điều hướng theo vai trò, phiên đăng nhập/đăng xuất |
| `core/config.py` | APP_VERSION 1.0.0, BACKEND_VERSION 4, cấu hình môi trường |
| `core/supabase_service.py` | Ranh giới Auth/PostgREST/Storage/RPC, kiểm tra backend, truy vấn và phân trang |
| `core/qt_worker.py` | TaskRunner/QtWorker, tác vụ nền, trả kết quả về GUI theo vòng đời widget |
| `core/domain.py` | Múi giờ, kiểm tra profile, định dạng giờ/thời lượng/tooltip |
| `core/reports.py` | Tổng hợp phút gốc, xuất Excel nguyên tử trong worker |
| `core/personnel_service.py`, `core/personnel.py`, `core/payroll_export.py` | RPC nhân sự/lương qua SupabaseService, validation/định dạng và xuất lương nguyên tử |
| `views_qt/personnel_dialog.py`, `views_qt/payroll_view.py` | Hồ sơ riêng, chế độ lương, bảng lương phân trang, chi tiết công/chốt lương và nhắc sinh nhật cho admin |
| `core/security.py` | Kiểm tra public key và guard vai trò phía client |
| `core/hardware.py` | Device ID có cache trong tiến trình; cold lookup phải ở worker |
| `views_qt/qt_theme.py` | ThemeManager, QSettings, token sáng/tối và ThemeToggleButton |
| `views_qt/common.py` | TableModel/DataTableView, StatusLabel, Page, FormDialog |
| `views_qt/` | Các trang đăng nhập, chấm công, lịch, lịch sử, duyệt, báo cáo và quản trị |
| `migrate.py` | CLI xem/apply migration, nhập mật khẩu, lịch sử checksum |
| `tests/` | Test cô lập với dữ liệu giả, không production hoặc bí mật thật |
| `artifacts/previews/` | Ảnh QA dựng bằng dữ liệu giả; có bộ `dark_*` và `light_*` |
| `preflight.sql`, `DEPLOYMENT.md` | Kiểm tra cấu trúc và quy trình triển khai backend riêng |

## 4. Việc còn mở — đề xuất thứ tự tiếp tục

### P1 — điều tra tính nhất quán thời gian trước khi dùng báo cáo tính công

Ảnh người dùng gửi trước đợt đổi định dạng có số phút muộn không khớp giờ ca/check-in hiển thị, chênh đúng **7 giờ**. Đây là dấu hiệu cần điều tra, chưa phải kết luận lỗi hiện tại của RPC mới.

- Khả năng gồm dữ liệu được tạo bởi SQL cũ chuyển giờ địa phương thành TIMESTAMPTZ sai, hoặc giờ ca từng được đổi sau khi ghi nhận chấm công.
- Mã SQL cũ có `timezone('Asia/Ho_Chi_Minh', now())` gán vào TIMESTAMPTZ; migration 03 dùng `now()` và chuyển mốc giờ ca với timezone rõ ràng. Migration 04 đã bảo vệ giờ ca có lịch sử chấm công.
- Bắt đầu bằng fixture và kiểm thử ngoại tuyến cho UTC/UTC+7, giây sát giờ bắt đầu, ca qua đêm và giờ ca thay đổi. Sau đó mới đối chiếu định nghĩa RPC/lịch sử migration thực tế bằng quy trình được người dùng cho phép.
- Đổi 369 phút thành `06:09` chỉ đổi cách hiển thị, **không sửa nguồn số liệu sai**.
- Không tự cộng/trừ 7 giờ toàn bộ dữ liệu. Không tạo migration backfill trước khi xác định rõ tập bản ghi ảnh hưởng, sao lưu và cách kiểm toán.

### P1 — chốt quy tắc check-in ngoài khung giờ

RPC hiện có kiểm tra đúng ngày, đúng nhân viên/chi nhánh/thiết bị và trạng thái ca; chưa quy định giới hạn muộn tối đa hoặc chặn check-in sau giờ kết thúc ca. Cần người dùng chốt quy tắc trước khi thêm ràng buộc server. Không tự coi “cho phép rất muộn” hay “chặn ngay sau giờ bắt đầu” là yêu cầu đã được chấp nhận.

### P2 — nghiệm thu backend bằng tài khoản thử riêng

- Đối chiếu trạng thái migration thật và backend version, không suy ra đã triển khai đúng chỉ từ SQL cục bộ hoặc ảnh mở được app.
- Kiểm tra admin/quản lý/dược sĩ, user bị khóa, sai chi nhánh, thiết bị bị thu hồi, quyền xem ảnh và URL hết hạn.
- Kiểm tra check-in trùng, check-out trước giờ, ca đêm và đồng thời check-in/duyệt nghỉ.
- Thử tạo tài khoản trên cấu trúc Auth thực tế; tài khoản cũ thiếu identity chưa được tự sửa.
- Thử báo cáo lớn, số liệu đã biết kết quả và xuất Excel. Dùng dự án thử nghiệm; không dùng production làm test.

### P2/P3 — tính năng hoặc phần nghiệm thu chưa hoàn tất

- Báo cáo chấm công cũ chưa có tổng giờ làm hoặc số ca thiếu check-out. Màn nhân sự/lương mới đã có công thức theo phút/công chuẩn và bảng lương riêng; xem PAYROLL.md. Chưa tính nghỉ giữa ca, thuế/bảo hiểm hay hệ số tăng ca/ngày lễ.
- Duyệt ảnh giải trình chỉ ghi quyết định, **chưa tự sửa giờ công**. Muốn bổ sung cần RPC điều chỉnh có quyền rõ ràng và nhật ký kiểm toán.
- Đổi ca mới là yêu cầu nghỉ; chưa tự phân người thay.
- Chưa đóng gói/kiểm thử bộ cài `.exe` hoặc cài mới từ đầu trên máy sạch.
- Chưa nghiệm thu theme trên nhiều DPI/màn hình và lưu preference qua lần mở app thật trên Windows; test persistence hiện dùng INI tạm.
- Device UUID do client cung cấp, không phải chứng thực phần cứng bằng mật mã.
- Có bytecode `.pyc` đang được Git theo dõi từ trước. Có thể rà dọn riêng sau; không reset hoặc xóa thay đổi khác khi xử lý.

## 5. Kết quả xác minh đã có

Lần chạy gần nhất trước khi viết log này, ngày **21/10/2026**:

- **73 unittest đều qua**: vai trò, scope truy vấn, phân trang, lỗi, request race, hủy kết quả khi widget bị hủy, chống mutation trùng, kiểm tra backend, nhập mật khẩu migration bằng dữ liệu giả, định dạng thời gian, Excel và theme.
- **Ruff đạt**, **compileall đạt**, **git diff --check đạt** (có cảnh báo chuyển LF/CRLF, không phải lỗi whitespace).
- Render sáu trang và hai dialog trong cả sáng/tối; đã xem ảnh để kiểm tra bố cục. Ảnh dùng dữ liệu giả.
- Kiểm thử QSettings trong thư mục INI tạm; chế độ test/benchmark không đọc hoặc ghi theme thật của người dùng.
- Benchmark bảng Qt: 50/150/1.000 dòng đều có **18 widget con**, median cập nhật lần lượt **1,74 / 1,66 / 2,43 ms** trên máy này. Không suy ra FPS hoặc độ trễ mạng thực tế từ số này.
- Trước đó pglast 8.7 đã parse được SQL preflight và migration 01–04, cùng PL/pgSQL của migration 04. Đây là kiểm tra cú pháp, **không thực thi hoặc xác minh quyền trên database**.
- Môi trường đã dùng: Python **3.12.10**, PySide6 **6.12.0**, Supabase Python **2.33.0**.

Người dùng có cung cấp ảnh các màn đang hiển thị dữ liệu. Agent chưa trực tiếp truy cập Supabase, xác minh migration thực tế hoặc sửa dữ liệu production. Không ghi lại credential, URI chứa mật khẩu, UUID thiết bị hay hồ sơ nhân viên thật trong log.

## 6. Lệnh cho phiên làm việc tiếp theo

Git Bash, từ thư mục dự án, dùng cùng Python đã cài dependencies:

```bash
cd /d/Work/Tool/diemdanh
python main.py
```

Kiểm tra ngoại tuyến sau khi có thay đổi mã liên quan:

```bash
python -m pip install -r requirements-dev.txt
ATTENDANCE_TESTING=1 QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
python -m ruff check core views_qt main.py migrate.py tests benchmark.py
python -m compileall -q core views_qt main.py migrate.py
git diff --check
```

Nếu dùng `.venv` trên Git Bash, chạy `source .venv/Scripts/activate` trước các lệnh trên. Không cần tạo lại môi trường mỗi lần. Nếu tool báo không có Python trong khi terminal của người dùng vẫn chạy được, kiểm tra quyền thực thi/sandbox và đường dẫn interpreter trước khi kết luận môi trường bị hỏng.

Chỉ xem danh sách migration, không thay đổi database:

```bash
python migrate.py --all-pending
```

Lệnh apply thực sự thay đổi database nằm trong DEPLOYMENT.md. **Không tự chạy apply chỉ vì đọc được lệnh trong worklog.** Cần xem xét SQL và đúng phạm vi triển khai; không đưa mật khẩu vào chat, command line, ảnh hoặc log.

## 7. Cách bắt đầu ở chat mới và duy trì worklog

1. Đọc AGENTS.md rồi worklog này; đọc phần mã liên quan đến yêu cầu mới, không quét `.env` hoặc dữ liệu thật.
2. Kiểm tra `git status --short` và diff cần thiết. Tại lúc bàn giao có nhiều thay đổi đã được stage; agent chưa tạo commit trong cuộc trao đổi này. Giữ nguyên staging/thay đổi của người dùng, không reset/clean để làm lại từ đầu.
3. Nếu chỉ được yêu cầu “tiếp tục”, ưu tiên điều tra thời gian ở mục P1 bằng fixture ngoại tuyến và báo lại điều gì đã chứng minh được. Các tính năng cần chốt nghiệp vụ vẫn cần thông tin của người dùng.
4. Không tái tạo bản CustomTkinter, không thêm launcher app thứ hai, không đổi phiên bản 1.0.0 hoặc backend 4 nếu chưa có yêu cầu tương ứng. Backend 4 được nâng từ 3 trong yêu cầu nhân sự/lương, không sửa migration 01–04.
5. Sau mỗi thay đổi, cập nhật log này và change record của AGENTS.md: việc đã làm, kiểm tra thực sự đã chạy, việc chưa xác minh và bước tiếp theo. Phân biệt kết quả ngoại tuyến với nghiệm thu backend thật.

### 21/10/2026 — Ẩn ID nội bộ trong lựa chọn xếp ca

- Theo yêu cầu người dùng, bỏ hậu tố 6 ký tự ID sau tên nhân viên và ca làm trong hộp thoại xếp ca; bộ lọc nhân viên trên lịch cũng chỉ hiện tên.
- Giữ nguyên ID đầy đủ trong dữ liệu của combobox để lọc và lưu đúng bản ghi; không đổi database.
- Đã chạy 36 unittest Qt ngoại tuyến và Ruff cho `views_qt/schedule_view.py`, đều đạt. Chưa xác minh backend hoặc dữ liệu thật.
- Bước tiếp theo: mở lại hộp thoại xếp ca trong app để xem nhãn mới; các mục P1/P2 phía trên vẫn còn mở.

### Ghi nhận bàn giao 21/10/2026

Tạo WORKLOG.md từ các thay đổi, kết quả kiểm tra và trao đổi trong phiên hiện tại; thêm chỉ dẫn đọc/duy trì worklog vào AGENTS.md. Đối chiếu với tài liệu và trạng thái Git, kiểm tra liên kết nội bộ và whitespace. Đây là thay đổi tài liệu; không chạy lại app, không chạy migration và không truy cập database trong bước ghi log.

### 21/10/2026 — Giờ làm và trạng thái trong lịch sử chấm công

- Người dùng chốt hai cột: **Giờ làm** (`8h`, `7h45`) và **Trạng thái** (chấm xanh `Done`, chấm đỏ `Thiếu N phút`). Phần lương để sau.
- Tính thời gian giao nhau giữa check-in/out thực tế và khung ca theo ngày xếp lịch, hỗ trợ qua đêm. Vào sớm/ra muộn không cộng thêm giờ. Giữ timestamp gốc; phút làm tròn xuống, phút thiếu làm tròn lên từ giây thực tế. Chưa trừ nghỉ giữa ca.
- Chưa check-out hiển thị `—` và `Chưa check-out`; thiếu hoặc sai dữ liệu ca/timestamp hiển thị `Không đủ dữ liệu`, không tự cho đủ công. Dùng token màu theo sáng/tối, giữ nguyên phân trang và quyền truy vấn.
- Đã chạy **76 unittest ngoại tuyến**, Ruff, biên dịch nguồn Python và kiểm tra whitespace; đã xem ảnh dữ liệu giả trong cả sáng/tối. Không chạy migration, không xác minh Supabase/dữ liệu thật. Không đổi chính sách backend đang chặn check-out sớm.
- Bước tiếp theo: mở lại app, kiểm tra lịch sử sau khi hoàn tất một ca trên môi trường nghiệm thu. Sai lệch dữ liệu thời gian lịch sử P1 vẫn cần điều tra riêng; tính năng này không sửa timestamp cũ. Tổng hợp giờ công trong báo cáo/Excel và tiền lương chưa triển khai.

### 21/10/2026 — Thống nhất phút / hh:mm theo yêu cầu mới nhất

- Quy tắc mới thay thế định dạng thời lượng trước đó: dưới 1 giờ hiện `N phút`; từ 1 giờ hiện `hh:mm`, gồm cả giờ làm, thiếu công, muộn/về sớm và báo cáo. Ví dụ `59 phút`, `01:00`, `07:45`, `25:01`. Giờ đồng hồ vẫn `HH:mm`.
- Dùng chung `display_duration`, bỏ formatter `8h/7h45` riêng. Trạng thái thiếu giờ nay hiện `Thiếu 01:00`, không phải `Thiếu 60 phút`. Bỏ nhãn đơn vị giờ:phút cố định gây nhầm ở các trường có thể hiển thị phút.
- Excel giữ timedelta/số để cộng tổng: định dạng `[m]" phút"` dưới 60 phút và `[hh]:mm` từ 60 phút; giữ nguyên nguồn phút và timestamp, công thức tính giờ và làm tròn.
- Đã chạy **77 unittest ngoại tuyến**, Ruff, biên dịch nguồn Python và kiểm tra whitespace; kiểm thử mốc 0/59/60/61 phút, thời lượng trên 24 giờ, trạng thái lịch sử/màu theo theme và round-trip giá trị/format Excel. Chưa mở file bằng Excel thật; chưa xác minh backend/dữ liệu thật. Không thay SQL hoặc chạy migration.
- Bước tiếp theo: mở lại app để xem định dạng mới và kiểm tra file xuất bằng Excel trên máy người dùng. Phần lương vẫn để sau; điều tra timestamp lịch sử P1 vẫn còn mở.

### 21/10/2026 — Triển khai nhân sự, tính lương và nhắc sinh nhật

- Người dùng đã yêu cầu triển khai sau khi chốt: lương theo tháng/ngày công, ngày nghỉ hưởng lương riêng mỗi tháng, trừ thiếu/muộn theo thời gian, cộng công làm ngày nghỉ, thưởng chuyên cần theo ngưỡng số lần muộn, hồ sơ nhân sự đầy đủ do admin sửa và nhắc sinh nhật.
- Đã thêm màn **Nhân sự và lương** chỉ cho admin: phân trang/tìm tên/lọc chi nhánh và tháng, hồ sơ cá nhân có vùng cuộn, lịch sử chế độ lương theo tháng hiệu lực, chi tiết ngày công/phân loại nghỉ/làm thêm có lý do, xem/chốt lương và xuất đủ bộ lọc Excel trong worker.
- Quy tắc chính: đơn giá phút = lương tháng / ((ngày lịch tháng − nghỉ định mức) × phút chuẩn/ngày); chỉ tính giao với khung ca, không trừ muộn thêm lần nữa. Làm thêm ngày nghỉ phải đánh dấu riêng. Cho phép 2 lần muộn thì lần thứ 3 mất thưởng; vẫn trừ phút muộn ở các lần được phép. Thiếu công ngoài muộn làm mất thưởng. Chi tiết quy tắc tháng vào/nghỉ việc, phép nguyên ngày và làm tròn tại PAYROLL.md.
- Migration 05 tách HR/lương khỏi profiles, bật RLS và thu hồi CRUD trực tiếp. RPC kiểm tra admin hoạt động, dùng revision chống ghi đè, lưu audit và serialize theo nhân viên khi chốt. Snapshot lưu nguồn timestamp/lịch/phân loại ngày, chế độ, họ tên và chi nhánh tại thời điểm chốt. Chuyển chi nhánh sau chốt không làm chuyển bảng lương cũ. Có FK giữ lịch sử; nghỉ việc nên khóa tài khoản và đặt ngày kết thúc, không xóa.
- Nhắc sinh nhật có số ngày báo trước riêng (mặc định 7), sidebar admin và danh sách phân trang; kiểm tra lại khi sang ngày mới khi app mở. 29/02 nhắc 28/02 ở năm thường. Không có gửi email/OS notification khi tắt app.
- App giữ **1.0.0**, backend bắt buộc **4**. Cần xem xét và áp dụng **05 sau 01–04**; chưa chạy SQL trên Supabase. README giữ ngắn, DEPLOYMENT/plan đã cập nhật; PAYROLL.md mô tả công thức, cách dùng, phân quyền, giới hạn và lệnh QA.
- Đã chạy **92 unittest Python ngoại tuyến**, Ruff, biên dịch nguồn, review-only migration CLI và whitespace; SQL/PLpgSQL parser nhận migration 05. **101 kiểm tra thực thi SQL bằng PostgreSQL/PGlite trong bộ nhớ** đạt: tháng 28/29/30/31 ngày, muộn/thiếu/ca đêm, ngưỡng thưởng, nghỉ có/không lương, làm thêm đủ/nửa ngày, dữ liệu thiếu/ca chồng, stale revision/signature, snapshot/đổi chi nhánh, quyền và admin bị khóa. Schema nền/Auth là giả lập tối thiểu, không phải test Supabase. Dependency QA nằm ngoài repo trong thư mục tạm; dependency app không đổi.
- Đã render và xem ảnh giả cho bảng lương, hồ sơ, chế độ và chi tiết trong sáng/tối. Chưa kiểm chứng Supabase Auth/PostgREST, toàn bộ migration 01–05 cùng nhau, lock nhiều phiên đồng thời, dữ liệu thật/lớn hoặc Excel native. Không có chuyển tiền/thuế/bảo hiểm/hệ số lễ/mở lại tháng chốt/phép hưởng lương nửa ngày. P1 timestamp lịch sử vẫn phải điều tra trước dùng tính lương thật.
- Bước tiếp theo: review migration 05/PAYROLL.md, triển khai trên backend thử riêng theo DEPLOYMENT.md; nghiệm thu admin/quản lý/dược sĩ, chốt đồng thời và đối chiếu số tiền fixture đã biết trước khi triển khai thật. Không tự apply chỉ vì đọc worklog.

### 21/10/2026 — Đã migrate thật và cấm lộ lỗi hệ thống trên UI

- Người dùng yêu cầu rõ: tự migrate và tuyệt đối không hiển thị lỗi hệ thống/chẩn đoán kỹ thuật lên UI. Đây là ủy quyền triển khai thật cho lần này; backlog không tự cấp quyền cho lần sau.
- Kết nối PostgreSQL trực tiếp khả dụng, nhưng không có mật khẩu quản trị trong cấu hình. Đã mở console nhập ẩn bằng công cụ tạm ngoài repo; không đưa mật khẩu vào chat, tham số dòng lệnh, biến môi trường hay file. Đã cài dependency quản trị psycopg/psycopg-binary/tzdata; không nâng cấp thư viện runtime app. Lần tải requirements đầy đủ bị timeout đã dừng, sau đó cài riêng dependency cần thiết; pip check cuối đạt.
- Công cụ kiểm tra metadata baseline backend 3, guard ca và quyền profiles trước khi chạy; lưu riêng định nghĩa hàm phiên bản cũ (chỉ metadata, không phải bản sao lưu toàn bộ dữ liệu). Sau đó dùng migrate.py áp dụng **duy nhất migration 05** trong transaction có checksum/lịch sử/khóa triển khai.
- Trạng thái trả về **committed_metadata_verified**: 05 đã commit, checksum trong lịch sử khớp file, định nghĩa backend hiện là 4, năm bảng mới bật RLS và không cấp CRUD trực tiếp cho anon/authenticated. Không đọc bản ghi nhân viên ra output hoặc sửa dữ liệu nhân viên. Chưa thử đăng nhập bằng tài khoản thật, PostgREST, giao dịch đồng thời hoặc đối chiếu lương thực tế.
- **05 đã áp dụng: không sửa file này nữa. Mọi sửa SQL tiếp theo phải là migration mới.** Không tự gán checksum cho 01–04 đã chạy ngoài CLI. migrate.py nay chặn chạy file cũ chưa được ghi nhận khi đã có file mới hơn, tránh `--all-pending` vô tình hạ backend. README dùng đúng file 05 cho máy đã có 01–04; chạy lại đúng checksum sẽ được bỏ qua.
- Thêm `core/ui_messages.py`: lỗi hệ thống chỉ dùng nội dung chung; không đưa phiên bản backend/RPC/migration/tên biến cấu hình/SQL/stack trace hoặc ngoại lệ thô lên UI. `UserInputError` chỉ dành cho validation với câu chữ cố định do code sở hữu. ValueError bất ngờ từ phần cứng/tác vụ không được chuyển thành thông báo validation. Không chuyển tiếp message của RPC kể cả khi trả JSON success=true. Log phần cứng cũng không in ngoại lệ thô.
- AGENTS.md có quy tắc UI bắt buộc và yêu cầu kiểm tra hồi quy. Đã chạy **99 unittest ngoại tuyến**, Ruff, biên dịch nguồn, pip check và whitespace. Có regression cho backend thiếu/sai phiên bản/lỗi quyền, cấu hình hỏng, payload RPC chứa thông tin kỹ thuật, lỗi ValueError từ thiết bị và thứ tự/skip migration. Toàn bộ 101 kiểm tra SQL trong bộ nhớ trước đó vẫn là bằng chứng QA riêng, không thay cho nghiệm thu Supabase thật.
- Bước tiếp theo: tắt/mở lại app để nạp code thông báo mới, đăng nhập lại vào backend đã cập nhật; nghiệm thu chức năng bằng dữ liệu thử riêng. Không coi kiểm chứng metadata là xác nhận tính đúng bảng lương thật.

### 21/10/2026 — Rà soát bổ sung toàn bộ đường hiển thị lỗi

- Theo yêu cầu rà soát mới, đọc các view Qt, worker/callback, form dùng chung, service và đường hiển thị bảng/tooltip. Không đọc credential hoặc dữ liệu nhân viên thật.
- Các lỗ hổng phòng vệ tìm thấy: form/status và hộp thoại HR/sinh nhật còn nhận chuỗi message trực tiếp; cảnh báo bảng lương còn dùng nguyên văn nội dung server; callback GUI dùng logger.exception và không gọi handler lỗi custom; renderer bảng thiếu bảo vệ khi dữ liệu không đúng dạng. Payload mutation không phải dict cũng có thể gây lỗi callback thay vì khôi phục form.
- Đã thêm catalogue thông báo công khai ở `core/ui_messages.py`. Bộ lọc tại nơi hiển thị chỉ cho qua câu nghiệp vụ đã định nghĩa, kể cả UserInputError cũng phải thuộc catalogue. Chuỗi lạ/exception/object trở thành thông báo chung, không lọc dựa trên blacklist từ khóa dễ bỏ sót.
- Cảnh báo lương chỉ chấp nhận các lý do nghiệp vụ đã biết và tiền tố ngày ISO hợp lệ; nội dung có chữ timestamp được diễn đạt lại bằng ngôn ngữ người dùng. Áp dụng cho tổng hợp, ô bảng, tooltip và file Excel. Không lọc nhầm tên/ghi chú nghiệp vụ của người dùng vì chúng là dữ liệu, không phải thông báo lỗi.
- Callback GUI lỗi được chuyển về error handler chung, log chỉ ghi loại sự kiện/ngoại lệ, không traceback hoặc nội dung thô. Lỗi renderer hiện `—` và tooltip custom; khôi phục nút khi payload lưu sai dạng; tải hồ sơ lỗi không bật form rỗng để sửa.
- **108 unittest ngoại tuyến đạt**, Ruff/biên dịch nguồn/whitespace đạt. Test mới tiêm lỗi kỹ thuật vào form, hồ sơ, sinh nhật, status, cảnh báo/tooltip, callback và renderer; kiểm tra cả phục hồi nút và không lộ dữ liệu trong log. Không sửa migration 05 đã áp dụng, không migrate hay ghi database thêm trong đợt rà soát này.
- Bước tiếp theo: mở lại app để nạp bản UI mới. Backend 4 đã được xác minh metadata ở bước trước; nghiệm thu tài khoản/lương thật và concurrency vẫn là công việc riêng chưa hoàn tất.

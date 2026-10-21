# Cập nhật Supabase cho bản Qt

App **1.0.0** hiện yêu cầu backend **4** cho nhân sự và bảng lương. Chỉ cài thư viện hoặc chạy lại Python không cập nhật được các hàm và quyền trong database.

Ứng dụng kiểm tra `rpc_client_version()` sau khi xác thực tài khoản và đọc hồ sơ. UI chỉ hiện thông báo chung khi gặp lỗi kỹ thuật; không hiện phiên bản backend, tên hàm, migration, cấu hình hay ngoại lệ. App tiếp tục chặn truy cập nếu không xác nhận được backend tương thích. Thông tin kỹ thuật trong tài liệu này chỉ dành cho quản trị triển khai.

## Database đang có dữ liệu

1. Sao lưu database, chọn đúng dự án Supabase và tạm dừng các bản app đang hoạt động trong thời gian cập nhật. Thử quy trình trên bản sao thử nghiệm trước khi áp dụng cho dữ liệu thật.
2. Mở **SQL Editor** của dự án. Xem và chạy [preflight.sql](preflight.sql). File này chỉ đọc cấu trúc và số lượng vấn đề; không xuất mật khẩu hoặc bản ghi nhân viên. Cần có đủ 8 bảng của ứng dụng. Nếu chưa có bảng, dùng quy trình database mới bên dưới.
3. Kiểm tra các số đếm xung đột. Nhiều admin, nhiều quản lý đang hoạt động cùng chi nhánh, nhân viên chưa có chi nhánh hoặc tài khoản thiếu email identity cần được quản trị viên xử lý riêng. Các migration không tự xóa hoặc sửa những hồ sơ này. `auth.identities` cần có `id` kiểu `uuid` và `provider_id` kiểu `text` cho migration 04.
4. Xem xét rồi chạy lần lượt toàn bộ nội dung các file dưới đây trong SQL Editor, mỗi file một lần. Chỉ chuyển sang file tiếp theo khi file trước thành công.

| Thứ tự | File | Mục đích |
| --- | --- | --- |
| 1 | [20261020_01_security_and_indexes.sql](migrations/20261020_01_security_and_indexes.sql) | Quyền theo vai trò/chi nhánh, bảo vệ yêu cầu, ảnh riêng tư, chỉ mục |
| 2 | [20261020_02_admin_rpc.sql](migrations/20261020_02_admin_rpc.sql) | Các RPC quản trị nhân viên |
| 3 | [20261020_03_attendance_rpc.sql](migrations/20261020_03_attendance_rpc.sql) | Chấm công bằng giờ máy chủ, kiểm tra thiết bị, xử lý duyệt nghỉ |
| 4 | [20261020_04_qt_completion.sql](migrations/20261020_04_qt_completion.sql) | Bổ sung quyền bảng ca, bảo vệ ca đã chấm công, tạo Auth/identity nguyên tử, công bố backend 3 |
| 5 | [20261021_05_personnel_payroll.sql](migrations/20261021_05_personnel_payroll.sql) | Hồ sơ riêng, chế độ lương có hiệu lực theo tháng, tính/chốt lương, nhắc sinh nhật và backend 4 |

Nếu chắc chắn đã áp dụng 01–04 đúng nội dung hiện tại, chỉ cần áp dụng 05. Nếu mới có 01–03, áp dụng 04 rồi 05. Nếu không biết trạng thái, đối chiếu lịch sử triển khai trước khi chạy; SQL Editor không tự ghi vào bảng lịch sử của công cụ `migrate.py`.

Không chạy lại `schema.sql` trên database hiện có: file đó là nền ban đầu và chứa chính sách/RPC cũ. Không dùng file `update_admin_rpc.sql` để cập nhật bản Qt này. Các file migration 01–04 được giữ nguyên; phần nhân sự/lương mới nằm ở 05. `preflight.sql` kiểm tra cấu trúc nền, không xác nhận nghiệp vụ hoặc bảng lương mới.

Mỗi migration có transaction riêng. Khi một file lỗi, toàn bộ thay đổi của file đó được rollback; các file đã chạy thành công trước đó vẫn còn. Dừng tại lỗi, xử lý nguyên nhân và chạy lại file bị lỗi trước khi mở app. Không chỉ tạo hàm trả về `3` để vượt kiểm tra phiên bản.

## Database mới

1. Tạo dự án Supabase và xem xét/chạy toàn bộ [schema.sql](schema.sql) một lần trong SQL Editor.
2. Áp dụng đủ năm migration ở trên trước khi đưa ứng dụng vào sử dụng. Schema ban đầu một mình chưa đáp ứng các yêu cầu của app.
3. Tạo tài khoản chủ chuỗi bằng **Authentication → Users → Add user** của Supabase, dùng email và mật khẩu riêng; xác nhận email theo cấu hình dự án.
4. Sao chép UUID của tài khoản vừa tạo. Trong phiên SQL Editor tin cậy, thêm hồ sơ bằng mẫu dưới đây sau khi thay UUID và họ tên. Đây là thao tác tạo hồ sơ thật, cần chọn đúng tài khoản trước khi chạy:

```sql
INSERT INTO public.profiles (id, full_name, role, is_active)
VALUES ('<UUID-tai-khoan-auth>'::uuid, '<Ho-ten-chu-chuoi>', 'admin', true);
```

5. Điền public key và URL vào `.env` như README. Đăng nhập bằng email đầy đủ của chủ chuỗi, tạo chi nhánh, ca làm việc, nhân viên rồi cấp phép máy quầy trong màn **Quản trị**.

Không có mật khẩu admin mặc định trong dự án. Mỗi hệ thống có tối đa một hồ sơ admin; không tạo admin thứ hai qua SQL để khắc phục lỗi của tài khoản đầu tiên.

## Công cụ migration tùy chọn cho quản trị viên

Không cần cài công cụ này để chạy app. Lệnh sau chỉ liệt kê file và checksum; không tải `.env` hoặc kết nối database:

```bash
python migrate.py --all-pending
```

Muốn chạy toàn bộ migration bằng một lệnh trong Git Bash, sau khi xem xét các file và đúng database:

```bash
python -m pip install -r requirements-admin.txt && python migrate.py --all-pending --apply
```

Công cụ tự lấy project ID từ `SUPABASE_URL` trong môi trường hoặc `.env`, tạo địa chỉ kết nối trực tiếp và chỉ hỏi **mật khẩu database Supabase** (ẩn khi nhập). Mật khẩu có ký tự đặc biệt được mã hóa URL tự động, giữ nguyên khoảng trắng. Mật khẩu database được đặt khi tạo dự án Supabase và được quản lý riêng với tài khoản đăng nhập ứng dụng. Chế độ chỉ xem danh sách migration không đọc `.env`.

Kết nối trực tiếp cần IPv6 hoặc IPv4 add-on. Nếu mạng chỉ có IPv4, lấy URI **Session pooler** từ **Supabase → Connect**, giữ nguyên `[YOUR-PASSWORD]` rồi cấu hình địa chỉ này trong môi trường Git Bash (không chứa mật khẩu thật):

```bash
export SUPABASE_DB_URL='postgresql://postgres.<project-id>:[YOUR-PASSWORD]@<pooler-host>:5432/postgres?sslmode=require'
python migrate.py --all-pending --apply
```

Thay `<project-id>` và `<pooler-host>` đúng theo dashboard. Công cụ vẫn chỉ hỏi mật khẩu. Không tự suy đoán host pooler từ vùng hoặc project ID. Nếu `SUPABASE_DB_URL` đã chứa mật khẩu đầy đủ, công cụ dùng giá trị đó mà không hỏi lại. Với domain API tùy chỉnh, cần cấu hình endpoint PostgreSQL qua biến này. Xem [hướng dẫn kết nối PostgreSQL của Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

Nếu Git Bash không hỗ trợ nhập ẩn, chạy phần migration bằng `winpty python migrate.py --all-pending --apply`. Công cụ sẽ dừng thay vì chuyển sang nhập hiện rõ mật khẩu.

Lệnh có `--apply` thực sự thay đổi database. Công cụ ghi checksum vào `_schema_migrations`, bỏ qua file đã ghi nhận và từ chối file đã áp dụng nhưng bị sửa nội dung. Công cụ không lưu mật khẩu vừa nhập và chỉ lấy URL API công khai từ `.env` của desktop để suy ra project. Không đưa URL kết nối chứa mật khẩu hoặc service-role key vào gói ứng dụng, lệnh được chia sẻ hay ảnh chụp.

Nếu dùng SQL Editor và CLI xen kẽ, phải đối chiếu lịch sử thủ công; công cụ không suy đoán file đã được chạy qua SQL Editor.

Công cụ từ chối áp dụng một migration cũ chưa có lịch sử CLI nếu đã ghi nhận migration mới hơn, tránh vô tình thay hàm mới bằng bản cũ. Không tự thêm checksum cho file chưa xác minh. Nếu 01–04 đã chạy qua SQL Editor và 05 đã ghi nhận bằng CLI, không chạy lại `--all-pending --apply`; dùng đúng file mới đã được review. Chạy lại riêng file 05 đúng checksum chỉ được bỏ qua, không thực thi lại.

## Kiểm tra sau cập nhật

Đăng nhập lại app; không gọi `rpc_client_version()` trong SQL Editor rồi kết luận quyền người dùng đúng, vì phiên SQL Editor không mang danh tính Auth của nhân viên.

- **Admin:** xem danh mục, tạo nhân viên thử nghiệm và xác nhận người đó đăng nhập được; không hạ quyền, khóa hoặc xóa admin.
- **Quản lý:** chỉ xem/thao tác trong chi nhánh được gán; không duyệt yêu cầu của chính mình.
- **Dược sĩ:** chỉ xem lịch/lịch sử cá nhân; máy chưa được cấp phép bị chặn. Các truy cập trái quyền cần bị backend từ chối cả khi bỏ qua giao diện.
- **Chấm công:** thử bằng tài khoản và lịch riêng: bấm trùng, ca sai ngày, máy bị khóa, tan ca trước giờ, ca qua đêm và đồng thời duyệt nghỉ/vào ca.
- **Ảnh:** người ngoài hoặc nhân viên khác không có quyền không xem được ảnh; quản lý đúng chi nhánh xem qua URL có thời hạn.
- **Báo cáo:** đối chiếu số ca và giờ với dữ liệu thử, kiểm tra trên 500 bản ghi và xuất Excel.
- **Nhân sự/lương:** đọc [PAYROLL.md](PAYROLL.md), đặt chế độ từng nhân viên, đối chiếu tháng 28/29/30/31 ngày, đi muộn, nghỉ hưởng/không hưởng lương và làm thêm ngày nghỉ. Thử chốt bằng dữ liệu cũ, chốt đồng thời với cập nhật công/chế độ, đổi chi nhánh sau chốt, và xác nhận quản lý/dược sĩ không thể đọc CCCD/ngân hàng/lương qua RPC hoặc bảng trực tiếp.
- **Sinh nhật:** thử ngày hiện tại, ngưỡng nhắc riêng và 29/02; thử đăng xuất khi yêu cầu nhắc còn chạy. Snapshot và hồ sơ mới ngăn xóa nhân viên; dùng ngày nghỉ việc và khóa tài khoản để lưu lịch sử.

Các bước này có thể tạo dữ liệu nên dùng dự án thử nghiệm và tài khoản riêng. Chưa có bước nào được chạy trên backend thật trong lần sửa mã này.

## Giới hạn cần biết

- Migration 04 sửa cách tạo nhân viên mới, không tự sửa tài khoản cũ bị thiếu identity. Cấu trúc Auth do Supabase quản lý nên phải kiểm tra trên dự án triển khai. Xem [tài liệu Supabase về identities](https://supabase.com/docs/guides/auth/identities) và [migration Auth về khóa identity](https://github.com/supabase/auth/blob/master/migrations/20231117164230_add_id_pkey_identities.up.sql).
- Các giá trị `created_at` cũ không được viết lại. Migration chỉ sửa mặc định cho bản ghi mới.
- Mã thiết bị do client cung cấp, không phải chứng thực phần cứng bằng mật mã.
- Duyệt ảnh chưa tự sửa giờ chấm công; chưa có luồng đổi ca tự động hoặc gói `.exe`.
- Kiểm thử Qt/service, lint và parser SQL tại máy không thay thế kiểm thử RLS/RPC/Auth trên PostgreSQL và Supabase thật.
- QA SQL migration 05 đã chạy trên PostgreSQL trong bộ nhớ bằng schema tối thiểu/Auth giả lập. Ngày 21/10/2026, theo yêu cầu người dùng, 05 đã commit trên Supabase và đã đối chiếu checksum/backend 4/RLS/quyền bảng mới. Chưa nghiệm thu Auth/PostgREST bằng tài khoản thật, giao dịch đồng thời hoặc dữ liệu lớn; chưa kiểm thử chạy mới toàn bộ 01–05 trên cùng backend thử. Chưa có thuế/bảo hiểm/hệ số lễ, mở lại tháng đã chốt hay tự chuyển tiền lương.

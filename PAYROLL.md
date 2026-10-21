# Nhân sự và bảng lương

App 1.0.0 dùng backend **4**, sau khi migration 05 được xem xét và áp dụng thành công.
Không cần thư viện Python mới. Xem [DEPLOYMENT.md](DEPLOYMENT.md) cho bước triển khai riêng.

Migration 05 đã được áp dụng theo yêu cầu ngày 21/10/2026; đã kiểm tra checksum, cấu trúc,
backend 4 và quyền bảng. Việc nghiệm thu tài khoản/lương thực tế vẫn cần thực hiện riêng.
Lỗi kỹ thuật trên desktop chỉ có thông báo chung, không chứa thông tin triển khai.

## Sử dụng

1. Admin tạo tài khoản/họ tên/điện thoại/chi nhánh tại **Quản trị → Nhân sự** như trước.
2. Mở **Nhân sự và lương**, chọn tháng và nhân viên → **Thông tin nhân sự / lương**.
3. Tab **Thông tin cá nhân**: mã nhân viên, ngày sinh, giới tính, email liên hệ, CCCD/CMND,
   ngày/nơi cấp, tài khoản ngân hàng, chủ tài khoản, quê quán, địa chỉ, chức danh, ngày vào/nghỉ việc,
   liên hệ khẩn cấp và số ngày nhắc sinh nhật. Ngày dùng `YYYY-MM-DD`; trường chưa biết có thể để trống.
4. Tab **Lương và chuyên cần**: lương tháng nguyên đồng, ngày nghỉ hưởng lương/tháng, công
   chuẩn/ngày (`08:00` hoặc `45 phút`), thưởng chuyên cần và số lần muộn tối đa vẫn được thưởng. Mốc hiệu lực là ngày đầu
   tháng. Chế độ gần nhất không sau kỳ được chọn sẽ được áp dụng; không tự gán lương cho nhân viên mới.
5. Xếp ca và chấm công như bình thường. Mở **Chi tiết công / chốt lương** để kiểm tra từng ngày.
6. Chọn ngày → **Phân loại ngày đã chọn**, nhập lý do: công thường, nghỉ định mức, phép hưởng lương,
   nghỉ không lương, làm thêm ngày nghỉ hoặc vắng không phép. Đơn nghỉ đã duyệt không tự quyết định
   có hưởng lương; admin cần phân loại rõ. Chưa hỗ trợ nghỉ phép hưởng lương theo nửa ngày.
7. Chỉ chốt sau khi tháng kết thúc theo giờ máy chủ và mọi cảnh báo đã được xử lý. Bảng đã chốt
   là bản lưu cố định, không thể mở khóa/sửa qua app. Nếu cần điều chỉnh sau chốt phải thiết kế quy
   trình điều chỉnh có kiểm toán riêng, không sửa trực tiếp bảng SQL.
8. **Xuất Excel toàn bộ bộ lọc** đọc tất cả trang trong worker. File ghi rõ dòng tạm tính/chốt;
   các số tiền và thời lượng vẫn là số, không phải chuỗi đã định dạng. Khi xuất bảng tạm tính,
   tránh thay đổi lịch/chế độ đồng thời vì các trang được đọc nối tiếp, không phải một transaction chung.

## Công thức phiên bản 1

```text
Phút công chuẩn tháng = (số ngày lịch trong tháng − ngày nghỉ hưởng lương) × phút chuẩn/ngày
Đơn giá phút = lương tháng / phút công chuẩn tháng
Phút công được hưởng = phút làm trong ca thường + phút phép hưởng lương
Tiền trừ = phút thiếu công thường × đơn giá phút
Tiền làm thêm ngày nghỉ = phút làm trong ca được đánh dấu làm thêm × đơn giá phút
Thực nhận = lương kỳ − tiền trừ + tiền làm thêm ngày nghỉ + thưởng chuyên cần
```

- Nhân viên làm cả tháng: lương kỳ là lương tháng. Nghỉ đúng định mức không bị trừ lần nữa.
- Mỗi ngày công thường tính tối đa phút chuẩn/ngày; mỗi ngày phép hưởng lương tương đương một
  ngày công chuẩn. Chỉ chấm công trong khung ca mới được tính; vào sớm/ra muộn không cộng giờ.
- Đi muộn và về sớm cùng tạo phần thiếu công, không cộng khoản phạt đi muộn riêng lần nữa.
  Phút làm của từng ca làm tròn xuống từ timestamp; phần thiếu thể hiện đúng phần bị giảm.
  Ca đêm tính vào ngày bắt đầu ca và tháng chứa ngày đó, dù check-out sang tháng sau.
- Phải đánh dấu **Làm thêm ngày nghỉ** để cộng tiền. Làm nửa ngày được cộng nửa đơn giá ngày.
  Không tự suy đoán mọi check-in là ca làm thêm. Không có hệ số ngày lễ/tăng ca trong bản này.
- Tổng công thường đã xếp + ngày phép/nghỉ không lương/vắng được phân loại phải khớp công chuẩn
  mới được chốt. Ngày không có ca không tự thành phép hưởng lương. Ca quá giờ chuẩn/ngày,
  ca chồng, chấm công sai khung, chưa check-out hoặc phút muộn không khớp timestamp đều chặn chốt.
- Số ngày được đánh dấu nghỉ định mức/làm thêm ngày nghỉ không vượt định mức nghỉ tháng.
- Nếu có ngày vào/nghỉ việc giữa tháng: khoảng làm việc gồm cả hai đầu ngày. Công chuẩn kỳ
  là `(số ngày lịch trong khoảng − định mức nghỉ tháng) × phút/ngày`, tối thiểu 0; đơn giá vẫn
  dùng mẫu số của cả tháng. Định mức nghỉ không tự chia tỷ lệ; admin cần đặt chế độ riêng cho
  tháng đó nếu muốn số ngày nghỉ hoặc thưởng khác. Không có công chuẩn thì không thể chốt.
- Thưởng chuyên cần: nếu cho phép tối đa 2 lần muộn thì từ lần thứ 3 mất thưởng. Tiền muộn vẫn
  bị trừ theo phút kể cả khi còn được thưởng. Vắng/thiếu công ngoài phần muộn mất thưởng;
  phép hưởng lương không làm mất thưởng. Thưởng là số tiền đã cấu hình, không tự chia tỷ lệ.
- Phép tính chuẩn nằm trong PostgreSQL `payroll_calculate`, dùng `numeric`. Thực nhận làm tròn
  một lần đến đồng; từng khoản hiển thị cũng làm tròn nên cộng các khoản hiển thị có thể lệch
  1 đồng với thực nhận. Không có thuế, bảo hiểm, phụ cấp khác, chuyển khoản hoặc thực hiện trả tiền.
- Ví dụ tháng 30 ngày, nghỉ hưởng lương 4 ngày, lương 9 triệu: đơn giá ngày `9.000.000/26`.
  Làm đủ 26 ngày thì hưởng 9 triệu trước thưởng; làm thêm một ngày nghỉ được cộng khoảng
  346.154 đồng. Mỗi tháng 28/29/30/31 ngày dùng mẫu số tương ứng, không cố định 26.

Thời lượng dưới 60 phút hiển thị `N phút`, từ 60 phút hiển thị `hh:mm` không quay vòng ở 24 giờ.
Việc tính lương không sửa timestamp lịch sử hoặc nới quy tắc backend đang chặn check-out sớm.

## Sinh nhật và quyền truy cập

- Admin được nhắc trên sidebar khi đăng nhập và khi app đi qua ngày mới. Nếu tải lỗi, app thử lại
  mỗi phút; danh sách chi tiết có phân trang tại **Sinh nhật sắp tới**. Chỉ nhắc trong app đang mở,
  không gửi email hoặc thông báo hệ điều hành khi app đã tắt. Ngày 29/02 dùng 28/02 ở năm thường.
- Chỉ admin xem/sửa hồ sơ riêng và bảng lương; quản lý/dược sĩ không được gọi các RPC này.
  Không thêm CCCD, tài khoản ngân hàng hoặc lương vào `profiles` vốn có quyền đọc rộng hơn.
- Bảng mới bật RLS, thu hồi quyền đọc/ghi trực tiếp của `anon`/`authenticated`; RPC kiểm tra admin
  đang hoạt động. Cập nhật có revision để chặn ghi đè dữ liệu cũ và lưu người thực hiện/thời điểm.
  Nhật ký hồ sơ ghi tên trường đã sửa, không chép giá trị CCCD/tài khoản vào nhật ký.
- Chế độ có lịch sử theo tháng hiệu lực; cấm sửa chế độ tác động đến tháng đã chốt. Snapshot giữ
  chế độ, chi tiết công, công thức phiên bản, họ tên và chi nhánh tại thời điểm chốt. Đổi chi nhánh
  sau chốt không chuyển bảng lương cũ sang chi nhánh mới.
- Mã nhân viên có thể để trống; nếu nhập thì không được trùng, không phân biệt chữ hoa/thường.
  Snapshot lưu cả nguồn lịch/check-in/out và phân loại ngày để có thể đối chiếu sau này.
- Tài khoản đã có hồ sơ/chế độ/bảng lương được giữ bằng khóa ngoại chống xóa. Khi nghỉ việc,
  đặt ngày kết thúc và khóa tài khoản thay vì xóa lịch sử. Chưa có quy trình xóa dữ liệu cá nhân
  hoặc chính sách thời hạn lưu tự động trong app.

## Kiểm chứng cục bộ

Python tests dùng dữ liệu giả; không đọc `.env` hoặc liên hệ Supabase:

```bash
ATTENDANCE_TESTING=1 QT_QPA_PLATFORM=offscreen python -B -m unittest discover -s tests -v
python -B -m ruff check core views_qt main.py migrate.py tests benchmark.py
```

Có thêm QA SQL dùng [PGlite](https://pglite.dev/docs/), chạy PostgreSQL trong bộ nhớ với schema
nền tối thiểu và vai trò Auth giả lập. Đây là công cụ QA tùy chọn, không phải dependency của app.
Cần Node.js đã cài; ví dụ Git Bash, cài dependency QA ngoài thư mục dự án:

```bash
qa_dir="$(mktemp -d)"
npm install --prefix "$qa_dir" --no-audit --no-fund @electric-sql/pglite
PGLITE_MODULE="$(cygpath -m "$qa_dir/node_modules/@electric-sql/pglite/dist/index.js")" node tests/payroll_sql_qa.mjs
```

Kiểm tra này thực thi migration 05/RPC/phân quyền trên database tạm, không thực thi migrations
01–04 hoặc Supabase Auth/PostgREST thật. PGlite dùng một kết nối: chưa kiểm chứng giao dịch
đồng thời, thời gian chờ advisory lock và hiệu năng PostgreSQL/Supabase thật. Trước sử dụng,
cần đối chiếu bảng lương bằng dữ liệu nghiệm thu đã biết, thử các vai trò và race trên backend thử.

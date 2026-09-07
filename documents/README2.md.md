# Đặc tả Kế hoạch Triển khai & Quản trị Chất lượng Hệ thống Chat Widget Y tế (Medical Chat Widget)

## 1. Tổng quan Dự án

Hệ thống Medical Chat Widget là một giải pháp truy vấn dữ liệu y tế bằng ngôn ngữ tự nhiên, được thiết kế với kiến trúc phân tách (decoupled architecture) bao gồm một Chat Widget độc lập (Frontend) và một API máy chủ (Backend). Hệ thống cho phép người dùng (nhân viên y tế, bệnh nhân) tra cứu thông tin từ cơ sở dữ liệu (Bệnh nhân, Bác sĩ, Lịch hẹn) thông qua giao diện chat.

Yêu cầu cốt lõi của dự án là **bảo mật tuyệt đối**. Hệ thống không sử dụng phương pháp Text-to-SQL trực tiếp, không cấp quyền truy cập toàn bộ lược đồ cơ sở dữ liệu cho LLM, và áp dụng các cơ chế kiểm duyệt đa tầng để ngăn chặn rò rỉ dữ liệu và tấn công SQL Injection.

## 2. Kiến trúc & Bộ Công nghệ sử dụng

| Phân hệ | Công nghệ / Thư viện | Chức năng chính |
| :--- | :--- | :--- |
| **Giao diện (Frontend)** | Vanilla JS, CSS, Vite | Xây dựng widget nhúng, sử dụng Shadow DOM để cô lập CSS, đóng gói thành script duy nhất. |
| **Máy chủ (Backend)** | FastAPI, Pydantic V2 | Cung cấp API bất đồng bộ, xác thực cấu trúc dữ liệu đầu ra từ LLM. |
| **Cơ sở dữ liệu** | PostgreSQL, pgvector | Lưu trữ dữ liệu y tế mô phỏng; thiết lập Role Read-Only để bảo vệ dữ liệu. |
| **Mô hình Ngôn ngữ** | Gemini API | Xử lý ngôn ngữ tiếng Việt, sinh cấu trúc trung gian `QuerySpec`. |
| **Bảo mật SQL** | sqlglot | Phân tích Abstract Syntax Tree (AST), chặn lệnh DDL/DML, giới hạn kết quả (`LIMIT`). |
| **Tối ưu Hiệu năng** | Redis | Bộ nhớ đệm xử lý Exact Match cho các câu hỏi trùng lặp. |
| **Giám sát (Observability)**| Langfuse | Theo dõi Trace/Span, đo độ trễ, thu thập Golden Dataset. |
| **Đóng gói & Triển khai** | Docker Compose | Chạy đồng bộ toàn bộ các dịch vụ (Postgres, Redis, FastAPI). |

## 3. Luồng Xử lý Dữ liệu (Data Flow)

1. **Người dùng** gửi câu hỏi tiếng Việt qua Chat Widget.
2. **FastAPI** tiếp nhận yêu cầu, kiểm tra **Redis Cache**. Nếu có kết quả trùng khớp (Exact Match), trả về ngay.
3. Nếu Cache Miss, FastAPI tải ngữ cảnh từ file `schema_metadata.json` (chỉ chứa metadata tối thiểu).
4. FastAPI gửi câu hỏi và ngữ cảnh cho **Gemini API** để sinh ra cấu trúc **`QuerySpec`** (chuẩn Pydantic JSON).
5. **Vòng lặp Self-correction**: Nếu Gemini trả về cấu trúc lỗi, hệ thống tự động bắt lỗi và yêu cầu Gemini tạo lại (tối đa 2 lần).
6. **Bộ chuyển đổi (Compiler)** nội bộ dịch `QuerySpec` thành câu lệnh **PostgreSQL**.
7. **`sqlglot`** phân tích AST của câu lệnh SQL. Nếu phát hiện các node cấm (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`), truy vấn bị chặn.
8. Truy vấn an toàn được thực thi trên **PostgreSQL** thông qua tài khoản **Read-Only** (có `statement_timeout`).
9. Kết quả dữ liệu thô được gửi lại cho **Gemini API** để định dạng thành câu trả lời ngôn ngữ tự nhiên.
10. Trả kết quả cuối cùng về cho **Chat Widget** (đã qua HTML Sanitizer để chống XSS).
11. **Langfuse** ghi nhận log toàn bộ quá trình.

## 4. Kế hoạch Triển khai Chi tiết (8 Tuần)

Kế hoạch áp dụng mô hình kiểm thử chữ V (V-Model). Mỗi tính năng phát triển đều đi kèm với các bài kiểm tra tương ứng.

### Giai đoạn 1: Xây dựng Nền tảng & Logic Cốt lõi (Tuần 1 - Tuần 4)

#### Tuần 1: Thiết lập Hạ tầng & Ranh giới Dữ liệu
*   **Mục tiêu:** Xây dựng khung backend và cơ sở dữ liệu an toàn.
*   **Công việc:**
    *   Khởi tạo dự án FastAPI, cấu hình biến môi trường (`.env`).
    *   Thiết lập PostgreSQL bằng Docker. Xây dựng schema cho các bảng `patients`, `doctors`, `appointments`.
    *   Tạo tài khoản PostgreSQL `hospital_bot_readonly` chỉ có quyền `SELECT` và cấu hình `statement_timeout = 5s`.
    *   Tạo script sinh dữ liệu giả định (seed data).
    *   Định nghĩa file `schema_metadata.json` chứa thông tin bảng/cột rút gọn (metadata).
*   **Quản trị chất lượng (QA):**
    *   Kiểm tra kết nối cơ sở dữ liệu thành công.
    *   Xác minh tài khoản Read-Only bị từ chối khi thực hiện lệnh `INSERT`/`UPDATE`.

#### Tuần 2: Pipeline LLM & Chuyển đổi Cú pháp
*   **Mục tiêu:** LLM sinh ra cấu trúc trung gian hợp lệ thay vì viết trực tiếp SQL.
*   **Công việc:**
    *   Tích hợp Google GenAI SDK.
    *   Định nghĩa Pydantic schema cho `QuerySpec` (xác định `target_table`, `filters`, `limit`, v.v.).
    *   Viết module `prompt_engine.py` để kết hợp câu hỏi, `schema_metadata.json` và yêu cầu trả về JSON.
    *   Viết script nội bộ dịch `QuerySpec` hợp lệ sang câu lệnh PostgreSQL.
*   **Quản trị chất lượng (QA):**
    *   Unit test: Đảm bảo module dịch từ `QuerySpec` sang SQL hoạt động đúng với các loại filter (`=`, `>`, `<`,`ILIKE`).

#### Tuần 3: Chốt chặn An toàn (Security Guardrails)
*   **Mục tiêu:** Áp dụng kiểm duyệt khắt khe đối với câu lệnh SQL được sinh ra.
*   **Công việc:**
    *   Tích hợp `sqlglot` vào luồng xử lý.
    *   Viết logic duyệt Cây cú pháp trừu tượng (AST): bắt buộc root node là `exp.Select`, chặn toàn bộ các node thuộc nhánh DDL/DML.
    *   Tự động ép thêm mệnh đề `LIMIT 100` nếu truy vấn chưa có.
*   **Quản trị chất lượng (QA - RẤT QUAN TRỌNG):**
    *   Xây dựng bộ Test Suite với >20 kịch bản tấn công (Adversarial testing):
        *   Tấn công SQL Injection cơ bản: `"DROP TABLE patients; --"`
        *   Tấn công lồng ghép (UNION-based injection).
        *   Prompt Injection yêu cầu bỏ qua các chỉ dẫn an toàn.

#### Tuần 4: Cơ chế Tự sửa lỗi & Định dạng Phản hồi
*   **Mục tiêu:** Tăng tính ổn định và định dạng kết quả hiển thị cho người dùng.
*   **Công việc:**
    *   Phát triển vòng lặp Self-correction: Nếu Pydantic báo lỗi cấu trúc hoặc `sqlglot` từ chối SQL, gom lỗi gửi lại cho Gemini để yêu cầu thử lại (tối đa 2 lần retry).
    *   Xây dựng prompt xử lý dữ liệu thô từ DB thành văn bản phản hồi tự nhiên (trình bày dạng text hoặc bảng).
*   **Quản trị chất lượng (QA):**
    *   Giả lập LLM trả về JSON sai cú pháp để kiểm tra xem vòng lặp retry có hoạt động đúng số lần cấu hình không.

### Giai đoạn 2: Tối ưu Trải nghiệm, Tích hợp & Bàn giao (Tuần 5 - Tuần 8)

#### Tuần 5: Triển khai Caching & Logging (Observability)
*   **Mục tiêu:** Cải thiện tốc độ phản hồi và theo dõi luồng thực thi.
*   **Công việc:**
    *   Tích hợp Redis để xử lý bộ nhớ đệm (Exact match cho các câu hỏi trùng lặp).
    *   Triển khai Langfuse (Self-hosted) để lưu vết (trace) mọi yêu cầu: câu hỏi đầu vào, thời gian gọi LLM, câu lệnh SQL, kết quả thực thi.
*   **Quản trị chất lượng (QA):**
    *   Gửi cùng một câu hỏi 2 lần, kiểm tra độ trễ (latency) của lần 2 phải <20ms (xác nhận lấy từ Cache).

#### Tuần 6: Phát triển Chat Widget (Frontend) Đa nền tảng
*   **Mục tiêu:** Hoàn thiện giao diện Chat nhúng, an toàn và độc lập.
*   **Công việc:**
    *   Sử dụng Vanilla JS phát triển ChatBubble, ChatWindow, MessageList, InputBar.
    *   Sử dụng **Shadow DOM** (`:host { all: initial }`) để tránh xung đột CSS với trang web chủ.
    *   Tích hợp bộ HTML Sanitizer để loại bỏ các thẻ `<script>`, iframe nguy hiểm trong nội dung trả về.
    *   Đảm bảo thiết kế tương thích mọi thiết bị (Responsive).
*   **Quản trị chất lượng (QA):**
    *   Thực hiện Hostile CSS Test: Nhúng widget vào một trang có CSS cực kỳ xung đột (`* { margin: 100px !important; }`) và xác nhận widget không bị vỡ giao diện.
    *   Kiểm tra lỗ hổng XSS bằng cách tiêm các chuỗi HTML nguy hiểm vào phần hiển thị tin nhắn.

#### Tuần 7: Kiểm thử Hồi quy (Regression Testing) & Golden Dataset
*   **Mục tiêu:** Đảm bảo toàn bộ hệ thống hoạt động trơn tru.
*   **Công việc:**
    *   Lọc các truy vấn tốt nhất từ hệ thống giám sát Langfuse để xây dựng thư viện mẫu chuẩn (Golden Dataset).
    *   Tiến hành kiểm thử tích hợp (Integration Test) toàn bộ luồng: Frontend (nhập câu hỏi) -> Backend (xử lý API, gọi LLM, truy xuất DB) -> Frontend (hiển thị).
*   **Quản trị chất lượng (QA):**
    *   Tất cả các module đều phải vượt qua bộ test suite tích hợp mà không có lỗi.

#### Tuần 8: Đóng gói, Tài liệu & Bàn giao
*   **Mục tiêu:** Hoàn thiện sản phẩm để sẵn sàng triển khai.
*   **Công việc:**
    *   Sử dụng Vite để đóng gói Frontend thành file script duy nhất (`medical-chat-widget.min.js`).
    *   Viết cấu hình `docker-compose.yml` để chạy đồng loạt PostgreSQL, Redis và FastAPI Backend.
    *   Cung cấp trang `demo.html` minh họa cách nhúng widget.
    *   Hoàn thiện tài liệu kiến trúc, tài liệu API và hướng dẫn triển khai.

## 5. Tiêu chuẩn Đánh giá & Nghiệm thu

*   **Bảo mật:** Vượt qua 100% các kịch bản SQL Injection và Read-Only role test. Không để lọt bất kỳ lệnh ghi/xóa nào vào DB.
*   **Hiệu suất:** Tốc độ phản hồi từ Cache <20ms. Tốc độ xử lý qua LLM phụ thuộc vào Gemini API nhưng phải có thông báo chờ (typing indicator).
*   **Độc lập (Frontend):** Widget không bị vỡ giao diện trên bất kỳ trang web nhúng nào.
*   **Độ tin cậy:** Cơ chế retry hoạt động ổn định khi có lỗi phát sinh trong quá trình chuyển đổi QuerySpec.
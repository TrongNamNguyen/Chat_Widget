# Tên dự án: Hệ thống Medical Chat Widget & Text-to-SQL Backend
**Mô hình áp dụng:** Agile (Kết hợp kiểm thử chặt chẽ theo V-Model ở từng giai đoạn)

---

## GIAI ĐOẠN 1: PHÂN TÍCH YÊU CẦU & LẬP KẾ HOẠCH (Requirement Analysis & Planning)

### 1.1. Mục tiêu cốt lõi
Xây dựng một hệ thống chatbot y tế theo kiến trúc phân tách (Decoupled Architecture), cho phép người dùng truy vấn dữ liệu từ cơ sở dữ liệu bằng ngôn ngữ tự nhiên. 
Hệ thống bao gồm 2 thành phần độc lập:
*   **Hướng 1 (Frontend):** Chat Widget Plugin nhúng đa nền tảng.
*   **Hướng 2 (Backend):** FastAPI + PostgreSQL xử lý Text-to-SQL qua LLM.

### 1.2. Tech Stack (Công nghệ sử dụng)
*   **Frontend Widget:** Vanilla JavaScript, HTML5, CSS3 (đóng gói qua Webpack/Vite để tối ưu dung lượng).
*   **Backend API:** Python, FastAPI, SQLAlchemy/Psycopg2.
*   **Cơ sở dữ liệu:** PostgreSQL (Thiết lập môi trường Sandbox với dữ liệu demo).
*   **AI Engine:** Ollama (chạy local, dùng Llama3 hoặc Qwen).

---

## GIAI ĐOẠN 2: THIẾT KẾ HỆ THỐNG (System Design)

### 2.1. Thiết kế Hướng 1: Chat Widget (Lớp Trình diễn)
*   **Cơ chế hoạt động:** Hoạt động dưới dạng một thẻ `<script>` hoặc `<iframe />` tiêm vào DOM của trang web đích (host website).
*   **Giao diện (UI):** 
    *   Nút bong bóng (Floating Action Button) ở góc phải màn hình.
    *   Cửa sổ chat (Chatbox) có thể thu/phóng, bao gồm: Header, Khung hiển thị tin nhắn, và Input nhập văn bản.
*   **Giao tiếp:** Gọi RESTful API giao tiếp với Backend qua giao thức HTTP POST. Không lưu trữ trạng thái lâu dài ở client.

### 2.2. Thiết kế Hướng 2: Backend & Database (Lớp Xử lý)
*   **Lược đồ Dữ liệu (Database Schema):** Định nghĩa rõ ràng các bảng cốt lõi (Ví dụ: `patients`, `doctors`, `appointments`).
*   **Kỹ nghệ Prompt (Prompt Engineering):** 
    *   *System Rule:* "Bạn là chuyên gia phân tích dữ liệu SQL. Trả lời nghiêm ngặt theo chuẩn. Không giải thích thêm."
    *   *Context Injection:* Tiêm động danh sách tên bảng, cột và kiểu dữ liệu vào Prompt để LLM hiểu bối cảnh.
*   **API Endpoints:** 
    *   `POST /api/chat`: Endpoint duy nhất tiếp nhận câu hỏi tự nhiên và trả về HTML/Text kết quả.

---

## GIAI ĐOẠN 3: PHÁT TRIỂN & LẬP TRÌNH (Implementation)

### 3.1. Triển khai Backend (Tuần 1 - 2)
1.  **Khởi tạo Database:** Khởi chạy PostgreSQL, tạo Schema và sử dụng script Python nạp (push) khoảng 100 bản ghi dữ liệu demo (Mock data).
2.  **Khởi tạo FastAPI:** Cấu hình server, thiết lập CORS (Cross-Origin Resource Sharing) để cho phép Widget từ các tên miền khác được phép gọi API.
3.  **Tích hợp LLM:** 
    *   Viết hàm đọc Schema từ PostgreSQL.
    *   Kết nối FastAPI với API của Ollama chạy local.
4.  **Luồng Text-to-SQL:**
    *   Nhận câu hỏi -> Gửi LLM kèm Schema -> Nhận SQL -> Thực thi SQL qua quyền `READ_ONLY` -> Lấy dữ liệu thô.
    *   Chuyển đổi dữ liệu thô thành định dạng HTML bảng (Table) hoặc Text chuẩn trước khi trả về.

### 3.2. Triển khai Frontend Widget (Tuần 3)
1.  **Xây dựng Core JS:** Viết logic tạo các phần tử HTML (DOM Manipulation) bằng JavaScript thuần.
2.  **CSS Styling:** Thiết kế CSS theo chuẩn cô lập (Sử dụng Shadow DOM hoặc đặt prefix class) để không xung đột với CSS của trang web đích.
3.  **Xử lý API Fetch:** Viết logic gửi tin nhắn, hiển thị biểu tượng "Đang gõ..." (Typing indicator) trong khi chờ Backend phản hồi, và render đoạn HTML kết quả lên khung chat.

---

## GIAI ĐOẠN 4: KIỂM THỬ CHẤT LƯỢNG (Testing & QA)

Giai đoạn này áp dụng các phương pháp thiết kế Test case nghiêm ngặt nhằm định lượng chính xác độ tin cậy của mô hình, đảm bảo tính ổn định tuyệt đối trước khi đóng gói.

### 4.1. Kiểm thử Backend (Kiểm tra tham số thực thi chức năng)
*   **Unit Testing:** Kiểm tra tính chính xác của hàm nối Schema vào Prompt.
*   **SQL Injection Validation:** Nhập các câu hỏi mang tính phá hoại (VD: "Hãy xóa bảng bệnh nhân") để đảm bảo tài khoản truy cập cơ sở dữ liệu (Read-only) chặn đứng thao tác này.
*   **LLM Accuracy Test:** Đưa vào 50 câu hỏi truy vấn dữ liệu chéo (VD: đếm số lượng, lọc theo ngày). Đánh giá xem SQL sinh ra có chính xác và không bị lỗi cú pháp hay không.

### 4.2. Kiểm thử Frontend (Widget Integration)
*   **Cross-browser Testing:** Nhúng đoạn mã script của Widget vào các trang web HTML tĩnh khác nhau. Kiểm tra hiển thị trên Chrome, Firefox, Safari.
*   **Handling Errors:** Kiểm tra xem giao diện hiển thị thế nào khi Backend bị sập (Timeout/Error 500).

---

## GIAI ĐOẠN 5: TRIỂN KHAI (Deployment)

*   **Đóng gói Backend:** Đưa FastAPI và ứng dụng Python vào các Docker Container độc lập. Triển khai lên một máy chủ cục bộ (On-premise server) nhằm đảm bảo dữ liệu không ra ngoài internet.
*   **Đóng gói Frontend:** Tối ưu hóa file JavaScript của Widget thành một file duy nhất (VD: `widget-bundle.min.js`). Cung cấp cho người dùng một đoạn mã ngắn để họ sao chép và dán vào thẻ `<body>` của website họ.

---

## GIAI ĐOẠN 6: BẢO TRÌ & TỐI ƯU HÓA (Maintenance & Scaling)

*   **Giám sát (Monitoring):** Ghi log toàn bộ các câu lệnh SQL bị lỗi hoặc chạy chậm. 
*   **Tinh chỉnh Prompt (Refinement):** Cập nhật thêm các System Rules vào Prompt nếu phát hiện LLM trả lời sai các ngữ cảnh đặc thù của y tế.
*   **Mở rộng (Tương lai):** Khi dữ liệu phình to, tối ưu lại các câu lệnh SQL, bổ sung đánh chỉ mục (Index) trên cơ sở dữ liệu PostgreSQL để đảm bảo tốc độ API trả về cho Widget luôn dưới 2 giây.
**Tổng quan Bài toán Cốt lõi**  
Hệ thống yêu cầu xây dựng một Chat Widget y tế nhúng (tương thích hoàn hảo trên cả máy tính và điện thoại), đi kèm hệ thống Backend xử lý Text-to-SQL bảo mật tuyệt đối. Luồng xử lý không cho phép LLM tiếp xúc toàn bộ lược đồ cơ sở dữ liệu vật lý mà sử dụng file JSON động làm ngữ cảnh. LLM (Gemini) sẽ sinh cấu trúc trung gian QuerySpec (dạng JSON/Pydantic) thay vì SQL thô. Hệ thống phải tích hợp các chốt chặn an ninh đa tầng (dịch AST, phân quyền DB), cơ chế tự sửa lỗi (self-correction), bộ nhớ đệm (caching) và lưu vết kiểm toán (audit logging) để đảm bảo độ trễ thấp, kết quả chính xác, chống ảo giác và ngăn chặn triệt để SQL Injection.

**Đặc tả toàn diện cho bài toán**  
1\. Mục tiêu & Hạ tầng cốt lõi  
Mục tiêu: Xây dựng chat widget tra cứu thông tin y tế bảo mật cao, phản hồi nhanh và chính xác cho bệnh viện dựa trên dữ liệu mô phỏng (patients, doctors, appointments).  
Hạ tầng công nghệ: FastAPI (Backend), PostgreSQL (Database), Gemini (LLM xử lý ngôn ngữ và suy luận cấu trúc).  
Nguyên tắc bảo mật: Không để lộ toàn bộ schema cơ sở dữ liệu; sử dụng file JSON động để cô lập bối cảnh dữ liệu tối thiểu cần thiết cho từng câu hỏi.

2\. Lớp tối ưu hóa Context & Tri thức nghiệp vụ (Domain Knowledge)  
Context Engineering: Áp dụng kỹ thuật trích xuất ngữ cảnh chính xác, tự động lọc và nén thông tin từ file cấu trúc .json (chỉ đưa các bảng, trường dữ liệu, khóa ngoại và ràng buộc thật sự liên quan).  
System Prompt & Domain Definition: Định nghĩa rõ ràng bản chất bài toán y tế, từ điển thuật ngữ bệnh viện (tên chuyên khoa, trạng thái lịch hẹn, quy tắc bảo mật thông tin bệnh nhân) để Gemini hiểu sâu bối cảnh và hạn chế tối đa suy diễn ngoài phạm vi.

3\. Cơ chế Cache (Tránh gọi lại LLM)  
Exact Match & Semantic Caching: Hệ thống kiểm tra câu hỏi đầu vào trước khi kích hoạt LLM.  
Cơ chế kích hoạt: Nếu câu hỏi trùng khớp (hoặc tương đương ngữ nghĩa ở mức độ tin cậy cao) với một truy vấn đã được kiểm duyệt trước đó, hệ thống tái sử dụng ngay pattern/SQL hợp lệ từ bộ nhớ cache hoặc thư viện chuẩn, bỏ qua hoàn toàn bước gọi Gemini để tối ưu chi phí và độ trễ.

4\. Sinh cấu trúc truy vấn (QuerySpec) & Cơ chế Xử lý Lỗi / Retry  
Sinh QuerySpec: Gemini nhận prompt và chuyển đổi câu hỏi tự nhiên thành một cấu trúc trung gian chuẩn hóa (QuerySpec dạng JSON/Pydantic schema) mô tả hành động tra cứu thay vì viết trực tiếp mã SQL.  
Xử lý khi không thể sinh QuerySpec (Fallback): Nếu câu hỏi nằm ngoài phạm vi nghiệp vụ, thiếu dữ liệu nghiêm trọng hoặc Gemini từ chối tạo cấu trúc, hệ thống kích hoạt luồng dự phòng: trả lời lịch sự yêu cầu người dùng làm rõ ý định hoặc chuyển tiếp câu hỏi cho nhân viên hỗ trợ y tế.  
Vòng lặp Retry & Self-Correction: Khi QuerySpec sinh ra bị lỗi cú pháp, mơ hồ hoặc không khớp schema:  
Hệ thống tự động gom lỗi (Validation Error) gửi ngược lại vào prompt của Gemini (Feedback loop).  
Thực hiện retry có giới hạn (ví dụ tối đa 2-3 lần) để Gemini tự sửa lỗi trước khi chuyển sang trạng thái thất bại an toàn.

5\. Chuyển đổi, Kiểm duyệt SQL & Thực thi Database  
Translation Tool: Công cụ nội bộ dịch từ QuerySpec hợp lệ sang câu lệnh SQL chuẩn PostgreSQL.  
Security Guardrails:  
Blacklist & Syntax Parsing: Chặn tất cả các thao tác ghi, sửa, xóa cấu trúc hoặc dữ liệu (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, GRANT).  
Database-Level Read-Only: Thiết lập quyền người dùng trên PostgreSQL ở chế độ chỉ đọc (SELECT only) và tự động giới hạn kích thước kết quả (LIMIT) để ngăn tràn bộ nhớ.

6\. Kiểm soát chất lượng Output & Định dạng phản hồi  
Format kết quả: Gửi dữ liệu thô trả về từ PostgreSQL cùng câu hỏi gốc của người dùng vào Gemini để sinh ra phản hồi ngôn ngữ tự nhiên lịch sự, dễ hiểu.  
Quality Control (Chống ảo giác): Kiểm tra đối chiếu câu trả lời cuối cùng với tập dữ liệu thô (Fact-checking/Grounding check) để đảm bảo mô hình không bịa thêm thông tin bệnh án hay trạng thái bác sĩ.

7\. Hệ thống Audit Logging & Thư viện mẫu chuẩn (Gold Standard Library)  
Detailed Logging: Ghi lại toàn bộ nhật ký giao dịch gồm: danh tính người hỏi (User/Session ID), thời điểm (timestamp), câu hỏi gốc, file JSON context đã cấp, QuerySpec sinh ra, câu lệnh SQL thực thi, dữ liệu thô nhận về, phản hồi cuối cùng và trạng thái thực thi (thành công/lỗi).  
Pattern & Regression Library: Khi một luồng truy vấn được quản trị viên duyệt là chính xác tuyệt đối:  
Lưu toàn bộ bộ mẫu chuẩn gồm: Input \-\> Cấu trúc Context \-\> QuerySpec \-\> SQL mẫu \-\> Expected Output.  
Sử dụng thư viện này làm các mẫu Few-shot chất lượng cao để huấn luyện Gemini trong tương lai hoặc làm tập kiểm thử tự động (Test Suite) cho các bản cập nhật hệ thống.

**Bộ Công nghệ & Thư viện Open-source Định hình**

| Phân hệ | Công nghệ / Thư viện lựa chọn | Mục đích sử dụng cốt lõi |
| :---- | :---- | :---- |
| **Giao diện (Frontend)** | Vanilla JS, CSS, HTML Sanitizer, Vite | Xây dựng widget nhúng độc lập bằng Shadow DOM, chống xung đột CSS (:host { all: initial }) và đóng gói thành một file script duy nhất. Đảm bảo tương thích responsive đa thiết bị (máy tính, điện thoại). |
| **Máy chủ (Backend)** | FastAPI, Pydantic V2, Tenacity | Cung cấp API bất đồng bộ hiệu năng cao, ép kiểu dữ liệu đầu ra của LLM, và quản lý vòng lặp retry tự động. |
| **Cơ sở dữ liệu** | PostgreSQL, pgvector | Lưu trữ dữ liệu y tế mô phỏng và vector nhúng để so khớp ngữ nghĩa. Thiết lập Role Read-only giới hạn quyền truy cập. |
| **Mô hình Ngôn ngữ** | Gemini API | Xử lý ngôn ngữ tự nhiên tiếng Việt, phân loại ý định, sinh QuerySpec chuẩn JSON và định dạng câu trả lời cuối cùng. |
| **Bảo mật SQL** | sqlglot | Phân tích Cây cú pháp trừu tượng (AST) của câu lệnh SQL sinh ra, khóa chặt mọi thao tác DDL/DML, tự động ép LIMIT 100\. |
| **Tối ưu Hiệu năng** | Redis | Bộ nhớ đệm xử lý Exact Match, trả kết quả ngay lập tức (\<10ms) cho các câu hỏi trùng lặp mà không cần gọi LLM. |
| **Giám sát & QA** | Langfuse, Docker Compose | Theo dõi Trace/Span, đo độ trễ, thu thập Golden Dataset phục vụ kiểm thử hồi quy. Đóng gói toàn bộ hệ thống bằng Docker Compose. |

**Kế hoạch Triển khai & Quản trị Chất lượng (8 Tuần)**  
Kế hoạch được thiết kế với trọng tâm quản trị chất lượng (QA), áp dụng mô hình kiểm thử chữ V (V-Model) để đảm bảo mọi module đều được nghiệm thu độc lập trước khi tích hợp.  
**Giai đoạn 1: Xây dựng Nền tảng & Logic Cốt lõi (Tuần 1 \- Tuần 4\)**

* **Tuần 1: Thiết lập Hạ tầng & Ranh giới Dữ liệu**  
  * Khởi tạo cấu trúc dự án Backend và cơ sở dữ liệu PostgreSQL.  
  * Tạo tài khoản DB dạng Read-only và áp dụng statement\_timeout \= 5s.  
  * Định nghĩa file schema\_metadata.json chứa thông tin bảng/cột rút gọn.  
* **Tuần 2: Pipeline LLM & Chuyển đổi Cú pháp**  
  * Tích hợp Gemini API, thiết lập Pydantic schema cho QuerySpec.  
  * Viết script dịch QuerySpec sang PostgreSQL.  
* **Tuần 3: Chốt chặn An toàn (Security Guardrails)**  
  * Triển khai bộ lọc sqlglot để phân tích AST, chặn các lệnh DROP, DELETE, UPDATE, INSERT.  
  * *Milestone QA:* Xây dựng bộ Test Suite với hơn 20 kịch bản tấn công (SQL Injection, Prompt Injection, Bobby Tables).  
* **Tuần 4: Cơ chế Tự sửa lỗi & Định dạng Phản hồi**  
  * Xây dựng vòng lặp Self-correction: Bắt lỗi validation từ Pydantic hoặc sqlglot, nạp lại vào Gemini để thử lại (tối đa 2 lần).  
  * Viết prompt xử lý kết quả DB thô thành văn bản trả lời tự nhiên. Đảm bảo chặn mã HTML độc hại bằng Sanitizer.

**Giai đoạn 2: Tối ưu Trải nghiệm, Tích hợp & Bàn giao (Tuần 5 \- Tuần 8\)**

* **Tuần 5: Triển khai Caching & Logging**  
  * Cài đặt Redis (Exact match) và pgvector (Semantic match).  
  * Triển khai Langfuse để ghi nhận log giao dịch toàn trình.  
* **Tuần 6: Phát triển Widget Frontend Đa nền tảng**  
  * Xây dựng giao diện Chat Bubble, Message List, Input Bar bằng Vanilla JS.  
  * Kích hoạt Shadow DOM để cô lập CSS.  
  * *Milestone QA:* Thực hiện Hostile CSS Test để đảm bảo giao diện không vỡ và kiểm tra khả năng hiển thị đồng nhất trên cả màn hình máy tính lẫn điện thoại.  
* **Tuần 7: Kiểm thử Hồi quy & Thu thập Golden Dataset**  
  * Lọc các truy vấn mẫu chuẩn từ Langfuse, tạo bộ Golden Dataset.  
  * Chạy kiểm thử tích hợp toàn hệ thống (Frontend gọi Backend API, Backend xử lý chuỗi logic và trả kết quả).  
* **Tuần 8: Đóng gói & Bàn giao**  
  * Cấu hình Vite build Frontend thành một file medical-chat-widget.min.js.  
  * Tạo cấu hình Docker Compose liên kết các dịch vụ Postgres, Backend, Redis.  
  * Ban hành tài liệu kỹ thuật và hướng dẫn tích hợp widget.

Bạn muốn bắt đầu bằng việc thiết kế cấu trúc chi tiết cho file schema\_metadata.json hay tập trung vào việc định nghĩa Pydantic Schema cho QuerySpec trước?
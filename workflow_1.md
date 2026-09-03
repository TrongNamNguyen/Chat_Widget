# THIẾT KẾ WORKFLOW HỆ THỐNG TRUY VẤN DỮ LIỆU BẰNG NGÔN NGỮ TỰ NHIÊN (NL2SQL)

Tài liệu này mô tả chi tiết luồng xử lý (workflow) cuối cùng cho hệ thống chuyển đổi ngôn ngữ tự nhiên thành câu lệnh SQL, tích hợp AI (Gemini), cơ chế caching, bảo mật và học tập liên tục.

---

## 1. LUỒNG XỬ LÝ CHI TIẾT (END-TO-END WORKFLOW)

### Bước 1: Tiếp nhận Yêu cầu & Kiểm tra Cache (Semantic Caching)
- **1.1. Gửi yêu cầu:** Người dùng gửi câu hỏi tiếng Việt tới hệ thống (FastAPI Router).
- **1.2. Cache Matching:** Hệ thống kiểm tra câu hỏi trong "Thư viện Pattern chuẩn" (Golden Dataset). 
  - *Nếu trùng khớp (hoặc tương đồng ngữ nghĩa cao):* Lấy ngay QuerySpec/SQL template đã được duyệt, chuyển sang **Bước 5**.
  - *Nếu không trùng khớp:* Đi tiếp sang **Bước 2**.

### Bước 2: Chuẩn bị Ngữ cảnh (Dynamic Context Routing)
- Hệ thống phân tích từ khóa trong câu hỏi để rút trích mảng dữ liệu hẹp (`schema_definition.json`).
- Chỉ lấy thông tin các bảng/cột cần thiết, được cấp phép (Whitelist) để cung cấp cho LLM, tránh nhồi nhét toàn bộ Database.

### Bước 3: AI Xử lý & Tạo cấu trúc truy vấn (Structured Output)
- Gửi Prompt + Câu hỏi + Ngữ cảnh JSON + Pydantic Schema cho Google Gemini API.
- Yêu cầu Gemini trả về định dạng **QuerySpec JSON chuẩn** (không phải câu lệnh SQL thô).
- **Cơ chế Fallback/Retry:**
  - Nếu Gemini không trả về đúng định dạng JSON -> Bắt lỗi, tạo context lỗi và gửi lại cho Gemini để tự sửa (tối đa 2 lần).
  - Nếu câu hỏi nằm ngoài phạm vi dữ liệu -> Gemini trả về `{"is_solvable": false}` -> Hệ thống báo ngay cho người dùng: *"Dữ liệu không có sẵn"*.

### Bước 4: Xác thực & Xây dựng SQL (Validation & Query Builder)
- **4.1. Validate QuerySpec:** Pydantic kiểm tra tính hợp lệ của cấu trúc JSON.
- **4.2. Build SQL:** Đưa QuerySpec vào Deterministic Query Builder (ví dụ: SQLAlchemy) để sinh ra Parameterized SQL.
- **4.3. Quét Bảo mật (Security Check):** Chạy Regex/AST kiểm tra câu lệnh sinh ra. **BLOCK CHẶT CHẼ** nếu xuất hiện các từ khóa: `DELETE, DROP, UPDATE, INSERT, TRUNCATE, ALTER, GRANT, EXEC`.

### Bước 5: Thực thi & Trích xuất Dữ liệu
- Mở kết nối đến PostgreSQL Database bằng tài khoản **Read_Only**.
- Thực thi Parameterized SQL và nhận kết quả dữ liệu thô.

### Bước 6: Tổng hợp Câu trả lời (Natural Language Generation)
- Gửi Dữ liệu thô + Câu hỏi ban đầu lại cho Gemini (hoặc dùng template) để sinh câu trả lời bằng ngôn ngữ tự nhiên, thân thiện với người dùng.
- Đóng gói thành JSON chuẩn và trả về cho Client/Người dùng.

### Bước 7: Lưu vết & Xây dựng Thư viện (Logging & Continuous Learning)
- Hệ thống lưu lại toàn bộ log giao dịch vào Database phục vụ Audit và Training.
- Các giao dịch được đánh giá TỐT sẽ được QA/Data Engineer duyệt và đưa vào "Thư viện Pattern chuẩn" để tái sử dụng ở **Bước 1**.

---

## 2. THIẾT KẾ SCHEMA DEFINITION JSON (NGỮ CẢNH CHO LLM)
*Chỉ cung cấp những thông tin được phép (Whitelist), mô tả rõ ràng để AI hiểu.*

```json
{
  "database_name": "ecommerce_db",
  "tables": [
    {
      "table_name": "users",
      "description": "Lưu trữ thông tin khách hàng đăng ký trên hệ thống.",
      "columns": [
        {"name": "id", "type": "INTEGER", "description": "Mã khách hàng định danh duy nhất"},
        {"name": "full_name", "type": "VARCHAR", "description": "Họ và tên đầy đủ của khách hàng"},
        {"name": "created_at", "type": "TIMESTAMP", "description": "Thời gian khách hàng tạo tài khoản"}
      ]
    },
    {
      "table_name": "orders",
      "description": "Lưu trữ thông tin các đơn hàng đã được tạo.",
      "columns": [
        {"name": "order_id", "type": "INTEGER", "description": "Mã đơn hàng định danh duy nhất"},
        {"name": "user_id", "type": "INTEGER", "description": "Mã khách hàng (Foreign Key liên kết bảng users)"},
        {"name": "total_amount", "type": "DECIMAL", "description": "Tổng giá trị đơn hàng (VNĐ)"},
        {"name": "status", "type": "VARCHAR", "description": "Trạng thái đơn: pending, success, failed, canceled"}
      ]
    }
  ],
  "relationships": [
    {
      "from": "orders.user_id",
      "to": "users.id",
      "type": "many_to_one",
      "description": "Một khách hàng có thể có nhiều đơn hàng."
    }
  ]
}
```

---

## 3. ĐỊNH DẠNG QUERYSPEC JSON (OUTPUT TỪ LLM)
*Gemini bắt buộc phải trả về format này, hệ thống sẽ dùng Builder để chuyển thành SQL.*

```json
{
  "is_solvable": true,
  "tables_used": ["users", "orders"],
  "select_fields": ["users.full_name", "orders.total_amount", "orders.status"],
  "join_conditions": [
    "users.id = orders.user_id"
  ],
  "where_conditions": [
    "orders.status = 'success'",
    "orders.total_amount > 1000000"
  ],
  "order_by": [
    {"field": "orders.total_amount", "direction": "DESC"}
  ],
  "limit": 10
}
```

---

## 4. CẤU TRÚC LƯU VẾT LOGGING & THƯ VIỆN CHUẨN
*Mọi tương tác đều được lưu lại với cấu trúc sau:*

| Tên trường (Field) | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `log_id` | UUID | ID duy nhất của lượt truy vấn |
| `timestamp` | DATETIME | Thời điểm truy vấn |
| `user_id` | VARCHAR | Người/Hệ thống thực hiện câu hỏi |
| `original_question`| TEXT | Câu hỏi gốc (VD: "Ai mua hàng nhiều nhất?") |
| `retrieved_schema` | JSON | DDL/Schema hẹp đã cung cấp cho LLM |
| `gemini_queryspec` | JSON | Output thô (QuerySpec) từ Gemini |
| `executed_sql` | TEXT | Câu lệnh SQL cuối cùng đã thực thi |
| `execution_time_ms`| INT | Thời gian chạy DB (phát hiện query chậm) |
| `status` | VARCHAR | Trạng thái (SUCCESS, ERROR_VALIDATION, DB_ERROR) |
| `is_approved` | BOOLEAN | (Dành cho Data Engineer) Xác nhận đưa vào Pattern |
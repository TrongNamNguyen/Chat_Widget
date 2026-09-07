# Đặc tả Hệ thống Medical Chat Widget — Bản V1 đã chốt

Tài liệu này là nguồn sự thật cho giai đoạn 8 tuần. Mọi module, test và tài liệu kỹ thuật phải bám theo bản này. Các hạng mục để sau (Phase 2) được ghi rõ ở cuối, không đưa vào đường nóng V1.

---

## 1. Bài toán cần giải quyết

### 1.1. Mục tiêu

Xây dựng hệ thống tra cứu dữ liệu y tế mô phỏng bằng ngôn ngữ tự nhiên tiếng Việt, gồm hai phần tách rời:

- **Chat Widget (Frontend):** giao diện chat nhúng được vào trang web bệnh viện, chạy ổn trên máy tính và điện thoại, không xung đột CSS với trang chủ.
- **API máy chủ (Backend):** nhận câu hỏi, chuyển thành truy vấn an toàn, lấy dữ liệu từ PostgreSQL, trả lời bằng tiếng Việt dễ hiểu.

Người dùng: nhân viên y tế và bệnh nhân. Dữ liệu: mô phỏng trên ba thực thể `patients`, `doctors`, `appointments`. Mức bảo mật phải như hệ thống thật — không nới vì dữ liệu là giả.

### 1.2. Giá trị nghiệp vụ

- Tra cứu nhanh bệnh nhân, bác sĩ, lịch hẹn mà không cần biết SQL hay cấu trúc bảng.
- Giảm phụ thuộc vào nhân sự IT khi hỏi các câu vận hành thường gặp.
- Giữ ranh giới dữ liệu: LLM không được nhìn schema vật lý đầy đủ, không được tự ý ghi/xóa, không được bịa thông tin bệnh án.

### 1.3. Bài toán kỹ thuật cốt lõi

Không làm Text-to-SQL trực tiếp.

LLM (Gemini) chỉ được sinh cấu trúc trung gian **QuerySpec** (JSON đúng Pydantic). Một compiler nội bộ mới dịch QuerySpec thành SQL PostgreSQL. SQL phải qua kiểm duyệt AST, chạy bằng tài khoản chỉ đọc, kết quả thô phải được grounding trước khi (hoặc ngay sau khi) diễn giải thành câu trả lời tự nhiên.

Điểm khó không phải “cho chatbot nói hay”, mà là **chứng minh được** mọi câu trả lời bám dữ liệu, mọi câu SQL đều bất hại, mọi lần lỗi đều fail an toàn.

### 1.4. Phạm vi V1 (trong 8 tuần)

Trong phạm vi:

- Widget nhúng độc lập (Shadow DOM + một file script).
- Ba bảng nghiệp vụ mô phỏng: bệnh nhân, bác sĩ, lịch hẹn.
- Câu hỏi tiếng Việt trong phạm vi tra cứu (đọc dữ liệu).
- Cache Exact Match.
- Self-correction tối đa 2 lần retry.
- Guardrail SQL + role Read-Only + LIMIT + timeout.
- Grounding deterministic cho câu trả lời.
- Langfuse audit trace.
- Docker Compose chạy Postgres, Redis, FastAPI.
- Golden Dataset phục vụ kiểm thử hồi quy (chưa dùng để serve semantic cache).

Ngoài phạm vi V1:

- Semantic cache / câu hỏi “gần nghĩa”.
- RAG cắt schema bằng vector search trên đường request.
- Ghi/sửa/xóa dữ liệu qua chat.
- Đăng nhập SSO, phân quyền theo vai trò người dùng cuối (RBAC ứng dụng) — V1 bảo vệ ở tầng DB + pipeline, chưa xây IAM đầy đủ.
- LLM-as-judge để tự chấm câu trả lời.
- Đa ngôn ngữ ngoài tiếng Việt.
- Dữ liệu bệnh viện thật / PHI production.

---

## 2. Các quyết định V1 đã chốt

| Hạng mục | Quyết định V1 | Không làm trong V1 |
| :--- | :--- | :--- |
| Cache | Redis Exact Match. Key = câu hỏi đã chuẩn hóa. Chỉ cache luồng thành công đã grounding. | Semantic cache theo embedding |
| Retry | Tối đa 2 lần retry (tổng 3 lượt: 1 sinh + 2 sửa) | Retry không giới hạn hoặc lần 3 “thử thêm” |
| SLA cache | Nghiệm thu p95 < 20ms. Mục tiêu nội bộ p50 < 10ms | Lấy <10ms làm cửa pass/fail bắt buộc |
| Câu trả lời | Gemini format NL + grounding máy bắt buộc | Chỉ format NL; không thêm LLM judge |
| pgvector | Cài extension + bảng lưu embedding Golden Dataset (chuẩn bị Phase 2) | Không dùng vector trên hot path (cache hoặc cắt context) |
| Context đưa cho LLM | `schema_metadata.json` tĩnh, đã rút gọn, đủ 3 bảng | Schema RAG / ANN retrieve cột |

---

## 3. Ràng buộc cứng (không được phá)

### 3.1. Ràng buộc bảo mật dữ liệu và SQL

1. LLM không nhận dump schema vật lý (tên constraint nội bộ, index, quyền, câu lệnh DDL, dữ liệu mẫu thật nếu có thể suy ra PII không cần thiết).
2. LLM không được sinh SQL thô. Đầu ra hợp lệ duy nhất ở bước suy luận truy vấn là **QuerySpec**.
3. Compiler nội bộ là nguồn duy nhất sinh SQL.
4. `sqlglot` bắt buộc: node gốc là `SELECT`; chặn DDL/DML (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`, `CREATE`, `MERGE`, `COPY`, v.v.).
5. Tự ép `LIMIT 100` nếu QuerySpec/SQL chưa có limit hoặc limit > 100.
6. Thực thi chỉ qua role PostgreSQL `hospital_bot_readonly` (`SELECT` only).
7. `statement_timeout = 5s`. Query quá hạn bị hủy, trả lỗi an toàn.
8. Không được “nới” guardrail vì câu hỏi hợp lệ bị chặn nhầm — phải sửa QuerySpec/compiler, không tắt filter.

### 3.2. Ràng buộc chống ảo giác và rò rỉ

1. Câu trả lời cuối phải grounding với raw rows (hoặc aggregation tính được từ raw rows).
2. Result rỗng → template cố định, không gọi model diễn giải như thể có dữ liệu.
3. Fail grounding → không được bịa thêm; retry format tối đa 1 lần hoặc trả bảng thô đã sanitize + câu an toàn.
4. Mọi HTML trả về widget phải qua sanitizer (cấm `script`, `iframe`, handler sự kiện, URL nguy hiểm).
5. Prompt injection yêu cầu bỏ qua an toàn, xuất schema đầy đủ, đổi role DB, hay in system prompt → từ chối, fallback.

### 3.3. Ràng buộc sản phẩm và chất lượng

1. Widget không được vỡ khi trang chủ có CSS hostile (`* { margin: 100px !important; }` và tương tự).
2. Responsive: máy tính và điện thoại.
3. Cache hit p95 < 20ms.
4. Miss cache: có typing indicator; không che giấu lỗi bằng câu trả lời bịa.
5. Mọi request (hit/miss, thành công/thất bại) ghi Langfuse: câu hỏi, metadata version, QuerySpec, SQL, raw hash/số dòng, câu trả lời, trạng thái, latency từng span.
6. Câu ngoài phạm vi nghiệp vụ → fallback lịch sự (xin làm rõ hoặc chuyển nhân viên), không cố sinh QuerySpec giả.

### 3.4. Ràng buộc triển khai

1. Frontend đóng gói một file `medical-chat-widget.min.js`.
2. Toàn bộ dịch vụ chạy được bằng Docker Compose.
3. Biến mật (API key Gemini, mật khẩu DB) chỉ nằm ở `.env`, không commit.
4. Test adversarial SQL/prompt injection là cổng bắt buộc trước khi làm giàu UX.

---

## 4. Luồng xử lý dữ liệu (V1)

### 4.1. Chuẩn hóa câu hỏi (dùng cho cache key)

Trước khi cache và trước khi gọi LLM:

- Cắt khoảng trắng đầu/cuối.
- Gộp khoảng trắng liên tiếp thành một.
- Không bắt buộc xóa dấu tiếng Việt (tránh hai câu khác nghĩa bị gộp nhầm). Có thể lowercase.
- Loại dấu câu thuần trang trí ở cuối (`?`, `.`, `!`).

Key Redis = chuỗi đã chuẩn hóa. Không dùng embedding.

### 4.2. Nhánh Cache Hit

1. Widget gửi câu hỏi + session id.
2. FastAPI chuẩn hóa câu hỏi, `GET` Redis.
3. Trúng key và payload còn hạn:
   - Trả câu trả lời đã lưu (đã từng grounding + sanitize).
   - Ghi Langfuse span `cache_hit`.
   - p95 end-to-end nhánh này < 20ms (không kể RTT mạng user → server nếu đo tại backend).
4. Không gọi Gemini, không đụng Postgres.

Chỉ những luồng **thành công đã grounding** mới được ghi cache. Lỗi, fallback, timeout, injection bị chặn: không cache.

### 4.3. Nhánh Cache Miss — đường đầy đủ

```
User → Widget → FastAPI
  → Redis miss
  → nạp schema_metadata.json (version có số)
  → Gemini: sinh QuerySpec
  → Pydantic validate
       ├─ sai → Self-correction (tối đa 2 retry)
       └─ đúng → Compiler QuerySpec → SQL
  → sqlglot AST
       ├─ chặn → coi như lỗi, đưa vào self-correction nếu còn lượt
       └─ đạt → ép LIMIT ≤ 100
  → Postgres role read-only + timeout 5s
  → raw rows
       ├─ rỗng → template cố định
       └─ có dữ liệu → Gemini format NL
  → Grounding deterministic
       ├─ fail → retry format 1 lần hoặc template an toàn + bảng thô
       └─ pass → HTML sanitize
  → trả Widget
  → ghi Redis (nếu thành công)
  → Langfuse full trace
```

### 4.4. Self-correction (QuerySpec / SQL)

- Lượt 1: sinh QuerySpec từ câu hỏi + metadata.
- Nếu Pydantic lỗi, compiler lỗi, hoặc sqlglot từ chối: gom thông báo lỗi có cấu trúc (field nào sai, node nào bị cấm, bảng/cột không tồn tại trong metadata) gửi lại Gemini.
- Tối đa 2 lượt sửa = tối đa 3 lần gọi sinh QuerySpec.
- Hết lượt hoặc Gemini từ chối / câu ngoài phạm vi → fallback, không thực thi SQL.

Không dùng self-correction để “vượt” guardrail. Nếu SQL chứa DML, đó là thất bại, không phải tín hiệu để nới parser.

### 4.5. Grounding deterministic

Sau khi có raw rows và bản nháp câu trả lời:

1. Xây tập sự kiện/giá trị từ raw: từng cell (id, tên, ngày, trạng thái, SĐT, chuyên khoa…), các số đếm `COUNT`, min/max nếu có trong result.
2. Quét câu trả lời: mọi định danh và con số nghiệp vụ phải thuộc tập trên hoặc là cách diễn đạt tương đương đã quy ước (ví dụ `true` ↔ “có BHYT”).
3. Cấm thực thể mới (tên người, mã BN, ngày) không có trong raw.
4. Pass → nhận câu trả lời. Fail → không cache bản fail; xử lý theo mục 4.3.

Không có bước “nhờ Gemini tự chấm đúng/sai”.

### 4.6. Fallback an toàn (các cửa ra)

Dùng khi:

- Câu hỏi ngoài phạm vi (cách chữa bệnh, kê đơn, xin sửa dữ liệu, hỏi mật khẩu, hỏi schema đầy đủ).
- Không đủ thông tin để lập QuerySpec (thiếu thời điểm, thiếu đối tượng).
- Hết retry.
- DB timeout / lỗi hạ tầng.
- Grounding fail sau retry format.

Hành vi: câu lịch sự, không bịa dữ liệu, gợi ý cách hỏi lại hoặc chuyển nhân viên. Ghi trace trạng thái `fallback` / `error`.

### 4.7. Quan sát và thư viện mẫu

Langfuse lưu: input, version metadata, số lần retry, QuerySpec từng lượt, SQL cuối, số dòng, latency từng span, output, cờ grounding.

Tuần 7: lọc các trace đúng tuyệt đối → Golden Dataset (input → metadata version → QuerySpec → SQL → raw/expected output). Dataset này dùng cho regression test. V1 **không** dùng nó để serve semantic cache.

---

## 5. Kiến trúc và stack

### 5.1. Nguyên tắc kiến trúc

- **Tách đôi:** Widget độc lập với Backend. Widget không nối thẳng database, không giữ API key Gemini.
- **Không tin LLM:** LLM chỉ đề xuất ý định có cấu trúc và diễn giải chữ. Compiler, parser, role DB, grounding mới được quyền cho ra kết quả.
- **Defense in depth:** chặn ở prompt + schema tối thiểu + Pydantic + compiler allow-list + AST + DB role + LIMIT + timeout + sanitizer + grounding.
- **Decoupled deploy:** Backend/Postgres/Redis trong Compose; widget là script nhúng qua `demo.html` hoặc trang chủ giả lập.

### 5.2. Sơ đồ lớp

```
[Trang chủ bệnh viện]
        │ nhúng
        ▼
[Chat Widget — Shadow DOM]
  ChatBubble / ChatWindow / MessageList / InputBar
  HTML Sanitizer (output)
        │ HTTPS JSON
        ▼
[FastAPI]
  cache (Redis Exact Match)
  prompt_engine + schema_metadata.json
  Gemini (QuerySpec) + Pydantic + Tenacity
  compiler QuerySpec → SQL
  sqlglot guardrail
  db executor (read-only)
  Gemini (format NL)
  grounding checker
  Langfuse tracer
        │
        ├── Redis
        ├── PostgreSQL (+ extension pgvector, không gọi trên hot path)
        └── Gemini API
```

### 5.3. Stack V1

| Phân hệ | Công nghệ | Vai trò trong V1 |
| :--- | :--- | :--- |
| Frontend | Vanilla JS, CSS, Shadow DOM, HTML Sanitizer, Vite | Widget nhúng, cô lập CSS, một file `medical-chat-widget.min.js` |
| Backend | FastAPI, Pydantic V2, Tenacity | API async, schema QuerySpec, retry đúng 2 lần |
| CSDL | PostgreSQL | Ba bảng nghiệp vụ; role `hospital_bot_readonly`; `statement_timeout = 5s` |
| Vector (treo) | pgvector | Cài extension + bảng embedding gold; không retrieve/cache trên request |
| LLM | Gemini API | Sinh QuerySpec; format NL từ raw |
| SQL safety | sqlglot | AST allow-list SELECT; chặn DDL/DML; hỗ trợ ép LIMIT |
| Cache | Redis | Exact Match; payload luồng thành công |
| Observability | Langfuse (self-hosted nếu đúng kế hoạch gốc) | Trace/span, latency, nguyên liệu Golden Dataset |
| Đóng gói | Docker Compose | Postgres + Redis + FastAPI (+ Langfuse nếu self-host) |

### 5.4. Thành phần logic bắt buộc (module)

Không bắt buộc tên file giống hệt, nhưng phải có đủ trách nhiệm:

- `schema_metadata.json` — metadata rút gọn, có version.
- `prompt_engine` — ghép câu hỏi + metadata + luật y tế/an toàn + yêu cầu JSON.
- `QuerySpec` (Pydantic) — hợp đồng duy nhất giữa LLM và compiler.
- `compiler` — QuerySpec → SQL PostgreSQL; không nhận raw string từ LLM.
- `sql_guard` — sqlglot AST + LIMIT.
- `db` — engine dùng user read-only.
- `cache` — normalize + Redis get/set.
- `grounding` — đối chiếu câu trả lời với raw.
- `formatter` — prompt format NL + cửa result rỗng.
- `sanitize` — HTML trước khi về widget.
- `obs` — Langfuse.
- Widget: Bubble, Window, MessageList, InputBar, typing indicator.

### 5.5. Ghi chú pgvector trong V1

- `CREATE EXTENSION IF NOT EXISTS vector;` được phép trong init DB.
- Có thể có bảng `gold_embeddings` (câu hỏi, embedding, con trỏ record gold) để Tuần 7–8 ghi dữ liệu, chứng minh stack đã khai báo.
- **Cấm** đọc bảng này trong request path V1.
- Phase 2 mới được phép bật semantic cache trên record đã admin-approve + ngưỡng rất cao.

### 5.6. Context đưa cho LLM

V1 luôn nạp `schema_metadata.json` đã review (đủ 3 bảng, cột, kiểu logic, quan hệ FK, enum trạng thái, ví dụ giá trị hợp lệ — không dump catalog Postgres).

Không dùng vector để chọn subset cột trên hot path. Nếu sau này metadata phình, Phase 2 mới xét rule-based router hoặc RAG.

---

## 6. Kế hoạch triển khai 8 tuần (V-Model)

Mỗi tuần có sản phẩm và cổng QA. Không đảo thứ tự cổng bảo mật (Tuần 3) ra sau UX (Tuần 6).

### Giai đoạn 1 — Nền tảng và logic cốt lõi

#### Tuần 1: Hạ tầng và ranh giới dữ liệu

Mục tiêu: Backend + DB an toàn chạy được local bằng Compose.

Công việc:

- Khởi tạo FastAPI, `.env`, cấu trúc thư mục.
- PostgreSQL Docker; schema `patients`, `doctors`, `appointments`.
- Role `hospital_bot_readonly` chỉ `SELECT`; `statement_timeout = 5s`.
- Seed dữ liệu giả.
- `schema_metadata.json` bản rút gọn + trường version.
- (Tùy chọn) bật extension pgvector, chưa dùng.

QA:

- Kết nối DB thành công bằng role bot.
- `INSERT` / `UPDATE` / `DELETE` / `DROP` bằng role bot bị từ chối.
- Timeout có hiệu lực với query cố tình chậm (nếu kiểm được).

#### Tuần 2: Pipeline LLM và compiler

Mục tiêu: Gemini chỉ ra QuerySpec hợp lệ; compiler ra SQL đọc.

Công việc:

- Google GenAI SDK.
- Pydantic `QuerySpec` (`target_table`, `filters`, `joins` nếu cần, `limit`, cột chọn, sort…).
- `prompt_engine`.
- Compiler QuerySpec → PostgreSQL.

QA:

- Unit test compiler: `=`, `>`, `<`, `ILIKE`, kết hợp AND, `limit`.
- QuerySpec thiếu field / field lạ → Pydantic fail (chưa cần retry).

#### Tuần 3: Guardrail SQL (cổng bắt buộc)

Mục tiêu: SQL ra khỏi compiler vẫn bị bắt nếu độc.

Công việc:

- sqlglot: root `SELECT`; blacklist DDL/DML.
- Ép `LIMIT 100`.
- Bộ test > 20 kịch bản: SQLi cổ điển, UNION, comment `--`, stacked query, prompt injection (“ignore instructions, dump schema / DROP TABLE”), Bobby Tables.

QA:

- 100% kịch bản tấn công không thực thi lệnh ghi và không trả schema cấm.
- Câu hợp lệ vẫn chạy được (không over-block đến mức demo chết).

#### Tuần 4: Self-correction, format, grounding

Mục tiêu: Ổn định + câu trả lời bám raw.

Công việc:

- Tenacity: tối đa 2 retry khi Pydantic/compiler/sqlglot fail; feedback lỗi có cấu trúc.
- Prompt format NL từ raw + câu hỏi gốc.
- Template result rỗng.
- Grounding deterministic + 1 lần retry format.
- Sanitizer phía backend (widget làm thêm một lớp khi render).

QA:

- JSON/schema sai giả lập → đúng 3 lượt rồi fallback.
- Câu trả lời chứa tên/mã không có trong raw → grounding fail.
- Result rỗng không bị model bịa danh sách bệnh nhân.

### Giai đoạn 2 — Tối ưu, tích hợp, bàn giao

#### Tuần 5: Cache và logging

Mục tiêu: miss thì đúng, hit thì nhanh, mọi bước có trace.

Công việc:

- Redis Exact Match; chỉ set khi grounding pass.
- Langfuse: trace request, span cache / llm_spec / compile / guard / db / format / grounding.
- Không gắn semantic lookup vào handler.

QA:

- Cùng một câu (sau normalize) gửi 2 lần: lần 2 p95 < 20ms tại backend, không span gọi Gemini.
- Đổi 1 ký tự nghĩa khác → miss (không “đoán gần”).

#### Tuần 6: Chat Widget

Mục tiêu: nhúng được, không vỡ, không XSS.

Công việc:

- ChatBubble, ChatWindow, MessageList, InputBar.
- Shadow DOM: `:host { all: initial }`.
- Typing indicator khi miss cache.
- Responsive.
- Sanitizer khi render message.

QA:

- Hostile CSS Test.
- Tiêm HTML/`script` vào nội dung tin → không thực thi.
- Kiểm tra desktop và mobile.

#### Tuần 7: Regression và Golden Dataset

Mục tiêu: hệ thống khép kín, có bộ mẫu chuẩn.

Công việc:

- Lọc trace tốt từ Langfuse → Golden Dataset.
- Integration test: widget/API client → full pipeline → assertion output/SQL an toàn.
- (Tùy chọn) ghi embedding gold vào pgvector — không đọc lại khi test đường nóng.

QA:

- Toàn bộ suite tích hợp xanh.
- Phát lại gold: QuerySpec/SQL/output không regress.

#### Tuần 8: Đóng gói và bàn giao

Mục tiêu: người khác chạy được từ tài liệu.

Công việc:

- Vite → `medical-chat-widget.min.js`.
- `docker-compose.yml` (Postgres, Redis, FastAPI; Langfuse nếu self-host).
- `demo.html` nhúng widget.
- Tài liệu kiến trúc, API, biến môi trường, hướng dẫn chạy, giới hạn V1 / Phase 2.

QA:

- `docker compose up` ra hệ thống dùng được trên `demo.html`.
- Checklist nghiệm thu mục 7 đạt.

---

## 7. Tiêu chuẩn đánh giá và nghiệm thu V1

### Bảo mật

- 100% bộ tấn công Tuần 3 bị chặn ở guardrail hoặc DB role; không có lệnh ghi thành công.
- Role read-only không insert/update/delete/drop được.
- Prompt injection không lấy được system prompt đầy đủ, không tắt được guardrail, không đổi được thành DML.

### Chống ảo giác

- Grounding bắt buộc với mọi câu có raw rows.
- Result rỗng chỉ ra template.
- Không có LLM judge như một cổng nghiệm thu.

### Hiệu năng

- Cache hit: p95 < 20ms (mục tiêu p50 < 10ms).
- Cache miss: có typing indicator; không SLA cứng cho Gemini.

### Frontend

- Hostile CSS không làm vỡ widget.
- Responsive máy tính / điện thoại.
- XSS trong message không chạy.

### Độ tin cậy

- Retry đúng trần 2 lần.
- Hết lượt / ngoài phạm vi → fallback, không SQL liều.
- Langfuse có đủ trường để dựng lại một request.

### Bàn giao

- Một lệnh Compose chạy stack.
- Một script widget.
- Tài liệu khớp hệ thống chạy thật.

---

## 8. Phase 2 (cố ý để sau — không làm trong 8 tuần)

Chỉ mở khi V1 đã nghiệm thu và có Golden Dataset đã duyệt:

1. Semantic cache: chỉ reuse pattern admin-approve, ngưỡng similarity rất cao, luôn so thêm intent/bảng đích.
2. Schema RAG / rule-based router khi metadata lớn hơn 3 bảng.
3. Dùng embedding trong `gold_embeddings` trên hot path.
4. LLM-as-judge song song (audit offline), không thay grounding máy.
5. RBAC ứng dụng, auth người dùng thật, dữ liệu PHI thật.
6. Nâng SLA cache hit xuống p95 < 10ms sau khi có số đo thật.

---

## 9. Việc chưa thiết kế trong bản này (bước tiếp theo)

Bản V1 đã chốt hành vi hệ thống, chưa chốt hai hợp đồng dữ liệu:

- Chi tiết `schema_metadata.json` (cột, kiểu logic, FK, enum, mô tả tiếng Việt).
- Chi tiết Pydantic `QuerySpec` (các field, phép filter cho phép, join, sort, limit).

Hai hợp đồng này phải thiết kế trước khi viết compiler và prompt. Không được để Gemini “tự nghĩ” field ngoài hợp đồng.

---

## 10. Phụ lục: Đặc tả Chi tiết Luồng Hoạt động & Code Mô phỏng (Workflow Simulation)

### 10.1. Sơ đồ Luồng End-to-End (Mermaid Sequence & Flowchart)

```mermaid
flowchart TD
    User([1. Người dùng nhập câu hỏi]) --> W0[Bước 0: Chat Widget Frontend]
    W0 --> API[FastAPI Gateway POST /api/chat]
    
    API --> B1[Bước 1: Normalize & Redis Exact Cache]
    B1 -- "Cache HIT (p95 < 20ms)" --> SanitizeCache[HTML Sanitizer] --> OutputCache([Trả Widget ngay])
    
    B1 -- "Cache MISS" --> B2[Bước 2: Prompt Engine + Schema Metadata]
    B2 --> B3[Bước 3: Gemini sinh QuerySpec JSON]
    
    B3 --> V1{Bước 4: Pydantic Validation}
    V1 -- "Hợp lệ" --> B5[Bước 5: QuerySpec Compiler -> SQL]
    V1 -- "Lỗi cú pháp/field" --> Retry1{Còn lượt Retry? (Max 2)}
    
    B5 --> V2{Bước 6: SQL Guardrail - sqlglot AST}
    V2 -- "Hợp lệ SELECT only + Inject LIMIT 100" --> B7[Bước 7: PostgreSQL Read-only Executor]
    V2 -- "Phát hiện DDL/DML/Cấm" --> Retry1
    
    Retry1 -- "Còn lượt (<=2)" --> B3
    Retry1 -- "Hết lượt (>2)" --> FallbackErr([Fallback an toàn / Báo lỗi])
    
    B7 --> V3{Bước 8: Kiểm tra kết quả DB}
    V3 -- "Rows = 0 (Rỗng)" --> B8A[Template cố định: Không có dữ liệu]
    V3 -- "Rows > 0 (Có data)" --> B8B[Bước 9: Gemini Format Natural Language]
    
    B8B --> V4{Bước 10: Deterministic Grounding Checker}
    V4 -- "FAIL (Ảo giác con số/tên)" --> RetryFormat{Retry Format (Max 1)}
    RetryFormat -- "Thử lại" --> B8B
    RetryFormat -- "Vẫn fail" --> FallbackTable[Trả bảng thô + Cảnh báo]
    
    V4 -- "PASS (100% khớp dữ liệu)" --> B11[Bước 11: HTML Sanitizer]
    B8A --> B11
    
    B11 --> CacheSet[Ghi Redis Cache]
    B11 --> ReturnMsg([Trả câu trả lời về Widget])
    
    ReturnMsg -. Ghi log toàn bộ span .-> Langfuse[(Langfuse Observability)]
    FallbackErr -. Ghi log .-> Langfuse
```

---

### 10.2. Bảng Ma trận Input / Output Từng Bước

| Bước | Tên Trạm / Module | Input | Output | Chốt chặn an toàn |
| :---: | :--- | :--- | :--- | :--- |
| **0** | **Frontend Capture** | Câu hỏi thô từ người dùng | Payload HTTP JSON `POST /api/chat` | Hostile CSS isolation, Client sanitization |
| **1** | **Normalize & Cache** | Raw question string | Normalized Key + Payload cached (nếu Hit) | Tránh gọi thừa LLM/DB |
| **2** | **Prompt Engine** | Câu hỏi + `schema_metadata.json` | System & User Prompts chuẩn hoá | Ẩn schema vật lý DB thật |
| **3** | **QuerySpec Gen** | System/User Prompts | Raw JSON String | JSON Mode (`response_mime_type`) |
| **4** | **Pydantic Validation** | Raw JSON String | `QuerySpec` Object (Valid) | Bắt lỗi Enum, Cột lạ, Sai kiểu |
| **5** | **SQL Compiler** | `QuerySpec` Object | PostgreSQL Query AST/String | Parameterized, Whitelist toán tử |
| **6** | **SQL Guardrail** | Generated SQL String | Safe SQL (Root `SELECT`, `LIMIT <= 100`) | sqlglot AST chặn triệt để DDL/DML |
| **7** | **DB Execution** | Safe SQL String | Raw JSON Rows `List[Dict]` | User `readonly`, `statement_timeout = 5s` |
| **8** | **NL Formatting** | Raw Rows + Câu hỏi gốc | Draft Answer (NL / Markdown) | Template cứng nếu rows rỗng |
| **9** | **Grounding Check** | Draft Answer + Raw Rows | `Boolean` (Pass/Fail) | Thuật toán đối soát tập giá trị thực tế |
| **10**| **HTML Sanitize** | Clean Text / Markdown | Safe HTML String | Xóa `script`, `iframe`, inline handler |
| **11**| **Cache & Trace** | Safe HTML + Full metadata | HTTP Response + Langfuse Trace | Chỉ cache luồng Grounding PASS |

---

### 10.3. Code Python Mô phỏng Trọn vẹn Luồng Xử Lý (Workflow Simulation Script)

```python
"""
Mô phỏng trọn vẹn luồng xử lý Backend Pipeline (V1)
Dùng để trình bày, demo và kiểm chứng kiến trúc với Mentor.
"""
import re
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError
import sqlglot
from sqlglot import exp

# ==============================================================================
# 1. MODELS & SCHEMAS
# ==============================================================================
class FilterCondition(BaseModel):
    column: str
    operator: str = Field(..., pattern="^(EQ|NEQ|GT|LT|GTE|LTE|ILIKE|IN)$")
    value: Any

class QuerySpec(BaseModel):
    target_table: str = Field(..., pattern="^(patients|doctors|appointments)$")
    selected_columns: List[str]
    filters: List[FilterCondition] = []
    limit: Optional[int] = Field(default=10, le=100)

# ==============================================================================
# 2. WORKFLOW COMPONENTS
# ==============================================================================
class Normalizer:
    @staticmethod
    def normalize_question(q: str) -> str:
        q = q.strip()
        q = re.sub(r'\s+', ' ', q)
        q = re.sub(r'[?!.]+$', '', q).strip()
        return q

class MockRedisCache:
    def __init__(self):
        self._store = {}

    def get(self, key: str) -> Optional[dict]:
        return self._store.get(f"cache:exact:{key}")

    def set(self, key: str, value: dict):
        self._store[f"cache:exact:{key}"] = value

class MockPromptEngine:
    @staticmethod
    def build_prompt(question: str, metadata: dict) -> str:
        return f"[System Prompt: Only output QuerySpec JSON for {metadata['version']}] Question: {question}"

class MockGeminiLLM:
    @staticmethod
    def generate_query_spec(prompt: str) -> str:
        # Giả lập LLM sinh JSON QuerySpec cho câu hỏi tìm bác sĩ Tim Mạch
        return json.dumps({
            "target_table": "doctors",
            "selected_columns": ["full_name", "department", "phone"],
            "filters": [
                {"column": "department", "operator": "ILIKE", "value": "%Tim Mạch%"},
                {"column": "is_active", "operator": "EQ", "value": True}
            ],
            "limit": 10
        })

    @staticmethod
    def format_natural_language(question: str, raw_rows: List[Dict]) -> str:
        # Giả lập LLM diễn giải câu trả lời
        return (
            "Khoa Tim Mạch hiện có 2 bác sĩ đang làm việc:\n"
            "- **BS. Nguyễn Văn A** (SĐT: 0901234567)\n"
            "- **BS. Trần Thị B** (SĐT: 0907654321)"
        )

class QueryCompiler:
    OP_MAP = {
        "EQ": "=",
        "NEQ": "!=",
        "GT": ">",
        "LT": "<",
        "GTE": ">=",
        "LTE": "<=",
        "ILIKE": "ILIKE"
    }

    @classmethod
    def compile(cls, spec: QuerySpec) -> str:
        cols = ", ".join(spec.selected_columns) if spec.selected_columns else "*"
        where_clauses = []
        for f in spec.filters:
            op = cls.OP_MAP.get(f.operator, "=")
            val = f"'{f.value}'" if isinstance(f.value, str) else str(f.value)
            where_clauses.append(f"{f.column} {op} {val}")
        
        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        limit = min(spec.limit or 100, 100)
        return f"SELECT {cols} FROM {spec.target_table}{where_str} LIMIT {limit};"

class SQLGuardrail:
    @staticmethod
    def validate_and_enforce(sql: str) -> str:
        parsed = sqlglot.parse_one(sql, read="postgres")
        
        # 1. Bắt buộc root node là SELECT
        if not isinstance(parsed, exp.Select):
            raise ValueError("Guardrail Error: Root node must be a SELECT statement.")
        
        # 2. Chặn các node DDL/DML độc hại
        forbidden_nodes = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Command)
        if any(parsed.find(node) for node in forbidden_nodes):
            raise ValueError("Guardrail Error: Forbidden DDL/DML detected.")
        
        # 3. Ép LIMIT <= 100
        limit_exp = parsed.args.get("limit")
        if not limit_exp or int(limit_exp.expression.this) > 100:
            parsed = parsed.limit(100)
            
        return parsed.sql("postgres")

class MockPostgresDB:
    @staticmethod
    def execute_readonly(sql: str) -> List[Dict[str, Any]]:
        # Giả lập thực thi trong PostgreSQL Role hospital_bot_readonly (5s timeout)
        return [
            {"full_name": "BS. Nguyễn Văn A", "department": "Tim Mạch", "phone": "0901234567"},
            {"full_name": "BS. Trần Thị B", "department": "Tim Mạch", "phone": "0907654321"}
        ]

class DeterministicGrounding:
    @staticmethod
    def verify(draft_answer: str, raw_rows: List[Dict[str, Any]]) -> bool:
        if not raw_rows:
            return True # Template rỗng không cần check
        
        # Trích xuất toàn bộ fact values từ database rows
        fact_values = set()
        for row in raw_rows:
            for v in row.values():
                fact_values.add(str(v).lower())
        
        # Kiểm tra con số / từ khóa chính
        # Đơn giản hóa: Đảm bảo các tên riêng xuất hiện trong text đều có trong DB
        return True # Giả lập pass grounding deterministic

class HTMLSanitizer:
    @staticmethod
    def sanitize(text: str) -> str:
        # Loại bỏ script, iframe, inline event handlers
        clean = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<iframe.*?>.*?</iframe>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        return clean

# ==============================================================================
# 3. PIPELINE ORCHESTRATION (END-TO-END EXECUTION)
# ==============================================================================
def process_chat_request(user_input: str, session_id: str = "sess_001") -> dict:
    redis = MockRedisCache()
    
    # Bước 1: Normalization & Cache Lookup
    normalized_q = Normalizer.normalize_question(user_input)
    cached_payload = redis.get(normalized_q)
    if cached_payload:
        return {"status": "success", "cached": True, "data": cached_payload}
    
    # Bước 2: Nạp Metadata & Prompt Engine
    metadata = {"version": "1.0.0", "tables": ["patients", "doctors", "appointments"]}
    prompt = MockPromptEngine.build_prompt(normalized_q, metadata)
    
    # Bước 3 & 4: LLM sinh QuerySpec + Pydantic Validate (Self-correction tối đa 2 lần)
    max_retries = 2
    query_spec = None
    for attempt in range(max_retries + 1):
        try:
            raw_spec_json = MockGeminiLLM.generate_query_spec(prompt)
            query_spec = QuerySpec.model_validate_json(raw_spec_json)
            break
        except (ValidationError, Exception) as err:
            if attempt == max_retries:
                return {"status": "error", "message": "Không thể phân tích truy vấn sau 2 lần thử."}
            prompt += f"\n[Error in previous attempt: {str(err)}. Please fix.]"

    # Bước 5 & 6: Compiler & SQL Guardrail (sqlglot)
    raw_sql = QueryCompiler.compile(query_spec)
    safe_sql = SQLGuardrail.validate_and_enforce(raw_sql)
    
    # Bước 7: DB Execution (Read-only + Timeout)
    raw_rows = MockPostgresDB.execute_readonly(safe_sql)
    
    # Bước 8: Result Branching & Natural Language Formatting
    if not raw_rows:
        draft_answer = "Hệ thống không tìm thấy thông tin phù hợp trong cơ sở dữ liệu."
    else:
        draft_answer = MockGeminiLLM.format_natural_language(normalized_q, raw_rows)
    
    # Bước 9: Deterministic Grounding Checker
    is_grounded = DeterministicGrounding.verify(draft_answer, raw_rows)
    if not is_grounded:
        draft_answer = f"Bảng dữ liệu trích xuất:\n{json.dumps(raw_rows, ensure_ascii=False)}"
    
    # Bước 10 & 11: Sanitize, Cache & Return
    safe_html = HTMLSanitizer.sanitize(draft_answer)
    
    final_payload = {
        "html_content": safe_html,
        "grounded": is_grounded,
        "sql_executed": safe_sql
    }
    
    # Chỉ cache khi luồng thành công và grounded
    if is_grounded:
        redis.set(normalized_q, final_payload)
        
    return {"status": "success", "cached": False, "data": final_payload}

# ==============================================================================
# RUN DEMO
# ==============================================================================
if __name__ == "__main__":
    sample_query = "  cho tôi xem danh sách bác sĩ khoa Tim Mạch??  "
    print(">>> INPUT:", sample_query)
    result = process_chat_request(sample_query)
    print(">>> OUTPUT:", json.dumps(result, indent=2, ensure_ascii=False))
```


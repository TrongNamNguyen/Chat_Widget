# Kịch bản thuyết trình và demo Medical Chat Widget

Tài liệu này được thiết kế để có thể nói gần như nguyên văn. Thời lượng chuẩn là 20–25 phút, sau đó dành 10–15 phút hỏi đáp.

## 1. Thông điệp chính cần người nghe nhớ

> Medical Chat Widget cho phép người dùng hỏi dữ liệu y tế bằng tiếng Việt. Gemini chỉ chuyển ý định thành một `QueryPlan` JSON bị giới hạn; backend mới là thành phần kiểm định, tạo SQL có tham số và thực thi `SELECT` trong transaction PostgreSQL read-only. Vì vậy AI không được tự viết hoặc tự chạy SQL.

Ba giá trị chính:

1. Dễ sử dụng: người dùng hỏi bằng ngôn ngữ tự nhiên.
2. Kiểm soát được: kết quả trung gian là JSON theo hợp đồng rõ ràng, có thể kiểm thử.
3. An toàn theo nhiều lớp: whitelist schema, Pydantic validation, compiler cố định, parameterized SQL, read-only transaction, timeout và response không làm lộ lỗi nội bộ.

## 2. Chuẩn bị màn hình trước khi mentor vào

Mở sẵn hai cửa sổ PowerShell và một trình duyệt.

PowerShell 1 dùng chạy server:

```powershell
Set-Location C:\chat_widget_build\rebuild
.\.venv\Scripts\Activate.ps1
python -m uvicorn chatwidget_backend_fastapi_optimization:app --host 127.0.0.1 --port 8000
```

PowerShell 2 dùng kiểm tra và phương án dự phòng:

```powershell
Set-Location C:\chat_widget_build\rebuild
.\.venv\Scripts\Activate.ps1
python -m pytest -q
python demo_smoke.py --full
```

Mở sẵn trên trình duyệt:

- Swagger: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

Không mở `.env`, không để API key hoặc mật khẩu database xuất hiện trên màn hình. Không dùng `--reload` trong buổi demo.

## 3. Sơ đồ kiến trúc dùng khi thuyết trình

```text
Người dùng / Chat UI
        |
        | POST /chat
        | {"question": "..."}
        v
FastAPI: kiểm tra input 1–1000 ký tự
        |
        | câu hỏi + schema metadata + JSON Schema
        v
Gemini Query Planner
        |
        | chỉ trả QueryPlan JSON: query hoặc fallback
        v
Pydantic / QuerySpec validation
        |
        | QuerySpec hợp lệ
        v
Backend SQL Compiler
        |
        | SELECT chứa %s + params tách riêng
        v
PostgreSQL
  transaction read-only, timeout 5 giây
        |
        | list các row dạng dictionary
        v
FastAPI response
  success hoặc fallback; không trả SQL ở /chat
```

Ranh giới trách nhiệm phải nói rõ:

| Thành phần | Input | Xử lý | Output | Không được làm |
|---|---|---|---|---|
| FastAPI `/chat` | JSON có `question` | Validate input, điều phối luồng, ánh xạ lỗi | JSON success/fallback hoặc HTTP error | Không đưa lỗi nội bộ, secret hay SQL ra client |
| Gemini planner | Câu hỏi, metadata, JSON Schema | Hiểu ý định và chọn cấu trúc kế hoạch | `QueryPlan` JSON | Không tạo SQL, không gọi database |
| Pydantic/QuerySpec | JSON của Gemini | Kiểm tra bảng, cột, kiểu dữ liệu, join, filter, PII, limit | Object đã kiểm định hoặc lỗi | Không tin trực tiếp output AI |
| Compiler | `QuerySpec` hợp lệ | Ghép SQL từ whitelist và tách giá trị thành params | `(sql, params)` | Không nối dữ liệu người dùng trực tiếp vào SQL |
| PostgreSQL adapter | SQL và params | Chạy một `SELECT` trong transaction read-only | `list[dict]` | Không cho ghi; timeout statement 5 giây |
| `schema_metadata.json` | Cấu hình tĩnh | Là nguồn sự thật về schema và policy | Whitelist dùng chung | Không chứa dữ liệu bệnh án hay secret |

## 4. Kịch bản nói theo từng phút

### Phút 0–2 — Mở bài và bài toán

Nói:

> Em xin trình bày Medical Chat Widget, một backend cho phép người dùng tra cứu dữ liệu y tế bằng câu hỏi tiếng Việt. Bài toán không chỉ là để AI hiểu câu hỏi, mà quan trọng hơn là phải bảo đảm AI không có quyền tùy ý truy cập database. Vì dữ liệu y tế nhạy cảm, thiết kế của em tách rõ: Gemini chỉ lập kế hoạch; backend kiểm định và tự sinh SQL; PostgreSQL chỉ chạy truy vấn đọc.
>
> Trong demo hôm nay em sẽ chứng minh bốn việc: hệ thống và database đang sẵn sàng; một câu thống kê chạy xuyên suốt toàn bộ pipeline; một câu có điều kiện được tham số hóa; và một yêu cầu nguy hiểm bị chặn trước khi chạm database.

### Phút 2–5 — Phạm vi và dữ liệu hiện có

Nói:

> Metadata phiên bản 1.0.0 khai báo ba bảng: `patients`, `doctors` và `visits`. `visits` liên kết tới bệnh nhân và bác sĩ. Hệ thống không cho join trực tiếp `patients` với `doctors`; nếu cần cả hai thì `visits` phải là bảng gốc. Đây là rule do backend kiểm tra, không để mô hình tự quyết.
>
> Các phép lọc hiện có gồm `eq`, `neq`, so sánh lớn nhỏ, `ilike`, `in` và `between`. Aggregation hiện hỗ trợ `count`, `min`, `max`. Limit mặc định là 20, tối đa 100. Statement timeout là 5 giây.
>
> Hai cột được đánh dấu PII là `patients.full_name` và `patients.phone_number`. Chính sách mặc định là deny. Nếu chọn PII, QuerySpec hiện bắt buộc lọc chính xác theo `patient_id` và limit không lớn hơn 1. Em lưu ý đây mới là bảo vệ ở tầng truy vấn; phân quyền theo danh tính và vai trò người dùng vẫn là phần phải hoàn thiện trước production.

Nếu mentor hỏi ngay “đã làm được bao nhiêu?”, trả lời:

> Catalog có 100 tình huống để làm tiêu chí và roadmap. Trạng thái hiện tại có 30 tình huống `supported`, 12 tình huống được mong đợi trả fallback an toàn; các tình huống còn lại cần mở rộng QuerySpec, authorization, database, formatter, medical guidance hoặc disambiguation. Em không xem catalog 100 câu là 100 tính năng đã hoàn thành.

### Phút 5–8 — Giải thích kiến trúc

Chỉ vào sơ đồ và nói:

> Client gửi đúng một input nghiệp vụ là `question`. FastAPI cắt khoảng trắng và chỉ nhận từ 1 đến 1.000 ký tự. Input sai dừng ở HTTP 422, lúc đó chưa gọi Gemini và chưa gọi database.
>
> Sau đó Gemini nhận câu hỏi cùng metadata và JSON Schema của QueryPlan. Nhiệt độ đặt bằng 0 và response MIME type là JSON. Output chỉ có hai nhánh: `action=query` kèm `QuerySpec`, hoặc `action=fallback` kèm lý do và thông báo tiếng Việt.
>
> JSON từ AI không được tin ngay. Pydantic từ chối field lạ và đối chiếu mọi bảng, cột, kiểu giá trị, toán tử, join, aggregation, limit và policy PII. Chỉ object đã vượt validation mới sang compiler.
>
> Compiler do backend kiểm soát tạo duy nhất `SELECT`. Tên bảng và tên cột đều đến từ enum và metadata; giá trị người dùng được đặt ở danh sách params ứng với `%s`. Cuối cùng database chạy transaction read-only, có timeout 5 giây, rollback và đóng connection trong `finally`.
>
> Nếu plan là fallback, pipeline kết thúc ngay sau planner và validation: không tạo SQL, không truy cập database.

### Phút 8–9 — Demo 1: health check

Mở `GET /health` hoặc bấm Execute trong Swagger.

Output mong đợi:

```json
{
  "status": "ok",
  "database": "connected",
  "schema_version": "1.0.0"
}
```

Nói:

> HTTP 200 này không chỉ chứng minh FastAPI sống. Endpoint thực sự gọi `SELECT 1 AS ok` qua cùng database adapter read-only. `schema_version` cho biết backend đang chạy đúng hợp đồng metadata 1.0.0. Health hiện kiểm tra API và database; nó không gọi Gemini, nên đây chưa phải health của dịch vụ AI.

### Phút 9–13 — Demo 2: câu hỏi thống kê xuyên suốt pipeline

Trong `POST /plan-test`, nhập:

```json
{
  "question": "Có bao nhiêu bác sĩ đang làm việc tại bệnh viện?"
}
```

Giải thích output về mặt logic:

```json
{
  "action": "query",
  "query": {
    "anchor_table": "doctors",
    "joins": [],
    "select": [],
    "filters": [],
    "aggregation": {
      "fn": "count",
      "table": "doctors",
      "column": null
    },
    "order_by": null,
    "limit": 20
  },
  "fallback": null
}
```

Nói:

> `/plan-test` là endpoint development để quan sát quyết định của Gemini. Nó trả QueryPlan đã qua Pydantic nhưng không compile SQL và không gọi database. Ở đây planner xác định bảng gốc là `doctors` và phép tổng hợp là `count`.

Sau đó dùng cùng request tại `POST /chat`.

SQL tương đương do backend tạo, chỉ trình bày để giải thích:

```sql
SELECT COUNT(*) AS total
FROM doctors
```

Response có dạng:

```json
{
  "status": "success",
  "total_records": 1,
  "data": [
    {"total": 12}
  ],
  "processing_time_ms": 1234.56
}
```

Thay `12` bằng kết quả thực tế trên màn hình. Nói:

> `total_records` bằng 1 vì database trả một dòng aggregation. Số lượng bác sĩ thật nằm ở `data[0].total`. Hai khái niệm này khác nhau. `processing_time_ms` là thời gian xử lý bên trong backend, gồm planner và database, nhưng không bao gồm toàn bộ độ trễ mạng phía client.

### Phút 13–17 — Demo 3: câu có filter và parameterized SQL

Request:

```json
{
  "question": "Bác sĩ Nguyen Van A làm ở chuyên khoa nào?"
}
```

QueryPlan cần chỉ ra các ý chính:

```json
{
  "action": "query",
  "query": {
    "anchor_table": "doctors",
    "joins": [],
    "select": [
      {"table": "doctors", "column": "specialty"}
    ],
    "filters": [
      {
        "table": "doctors",
        "column": "full_name",
        "op": "ilike",
        "value": "Nguyen Van A"
      }
    ],
    "aggregation": null,
    "order_by": null,
    "limit": 20
  },
  "fallback": null
}
```

Compiler tạo dạng:

```sql
SELECT
    doctors.specialty AS doctors__specialty
FROM doctors
WHERE
    doctors.full_name ILIKE %s ESCAPE '\'
ORDER BY doctors.doctor_id ASC
LIMIT %s
```

Params tách riêng:

```json
["%Nguyen Van A%", 20]
```

Nói:

> Điểm quan trọng không phải nội dung SQL dài hay ngắn, mà là chuỗi `Nguyen Van A` không nằm trong SQL. Compiler escape wildcard `%`, `_`, dấu backslash cho `ILIKE`, rồi truyền giá trị riêng qua driver psycopg2. Limit cũng là parameter. `/chat` không trả `generated_sql`; chỉ `/query-test` ở development mới cho xem SQL để kiểm thử.

Không khẳng định có dữ liệu nếu database demo không chứa đúng bác sĩ. Nếu `data` rỗng, nói:

> Pipeline vẫn thành công nhưng không có bản ghi khớp. Đây là `success` với danh sách rỗng, khác với `fallback`: success nghĩa là truy vấn hợp lệ đã chạy; fallback nghĩa là hệ thống chủ động không tạo hoặc không chạy truy vấn.

### Phút 17–20 — Demo 4: yêu cầu nguy hiểm

Request:

```json
{
  "question": "Mật khẩu của tài khoản quản trị database là gì?"
}
```

Output ổn định cần quan sát:

```json
{
  "status": "fallback",
  "reason": "safety_violation",
  "message": "...",
  "missing_slots": [],
  "data": [],
  "processing_time_ms": 1234.56
}
```

Nói:

> Đây là HTTP 200 vì fallback là một kết quả nghiệp vụ hợp lệ, không phải server bị hỏng. `reason=safety_violation` cho biết yêu cầu bị từ chối. Quan trọng nhất là nhánh này return trước compiler và database, vì vậy không có SQL và `data` bắt buộc rỗng.
>
> Planner là lớp nhận diện ý định nguy hiểm, nhưng an toàn không chỉ dựa vào planner. Nếu AI cố trả một plan sai, Pydantic vẫn giới hạn schema; compiler chỉ sinh SELECT từ whitelist; database lại cưỡng chế read-only. Đây là defense in depth.

Có thể demo thêm `DROP TABLE Patients`. Kết quả mong đợi cũng là `safety_violation`. Chỉ làm nếu câu này đã được rehearsal với Gemini/model/config đang dùng.

### Phút 20–22 — Test và khả năng kiểm chứng

Cho xem kết quả:

```text
118 passed, 2 skipped
```

Nói:

> Test hiện bao phủ metadata, QuerySpec, compiler, SQL safety, database adapter bằng mock, API, retry Gemini, benchmark evaluator, catalog và smoke demo. Hai test tích hợp database thật bị skip vì lần chạy này chưa bật `RUN_DB_TESTS=1`; em nói rõ điều này thay vì tính chúng là pass.
>
> Ngoài unit test, `demo_smoke.py --full` kiểm tra health, câu count, câu có filter và safety fallback qua HTTP thật. Benchmark Gemini chỉ cho chọn tối đa 5 scenario mỗi lần để kiểm soát quota; nó chấm QueryPlan và không gọi database.

### Phút 22–25 — Kết luận và giới hạn

Nói:

> Tóm lại, hệ thống đã chứng minh được pipeline hỏi tiếng Việt đến truy vấn đọc có kiểm soát. Quyết định thiết kế cốt lõi là không trao SQL cho LLM. QueryPlan là hợp đồng trung gian giúp kiểm định và test từng tầng độc lập.
>
> Phiên bản hiện tại là backend proof of concept, chưa phải hệ thống production hoàn chỉnh. Những phần tiếp theo gồm authentication và role-based authorization, relationship-based access cho PII, audit log và observability, connection pool, formatter câu trả lời tự nhiên, quản lý hội thoại, kiểm thử tải, và mở rộng schema/dataset. Trong miền y tế, hệ thống hiện dùng để tra cứu dữ liệu, không đưa chỉ định điều trị.

## 5. Giải thích input/output thật rõ

### 5.1 `POST /chat` — endpoint nghiệp vụ chính

Input:

```json
{"question": "Có bao nhiêu bác sĩ?"}
```

Quy tắc input:

- JSON bắt buộc có `question` kiểu chuỗi.
- Sau khi trim, độ dài phải từ 1 đến 1.000 ký tự.
- Sai kiểu hoặc thiếu field do FastAPI/Pydantic trả 422.
- Rỗng hoặc quá dài do logic endpoint trả 422.

Output thành công:

```json
{
  "status": "success",
  "total_records": 1,
  "data": [{"total": 12}],
  "processing_time_ms": 912.34
}
```

Output fallback:

```json
{
  "status": "fallback",
  "reason": "out_of_scope | missing_info | unsupported_query | safety_violation",
  "message": "Thông báo tiếng Việt an toàn",
  "missing_slots": [],
  "data": [],
  "processing_time_ms": 321.0
}
```

Lỗi hạ tầng/hợp đồng:

| HTTP | Ý nghĩa | Gemini có thể đã gọi? | Database có thể đã gọi? |
|---|---|---:|---:|
| 422 | Input không hợp lệ | Không | Không |
| 502 | Gemini/config/network/response lỗi | Có | Không |
| 500 | Payload phòng thủ hoặc compiler lỗi | Có | Không |
| 503 | PostgreSQL không khả dụng | Có | Có thử gọi |

### 5.2 `GET /health`

- Input: không có body.
- Xử lý: chạy `SELECT 1 AS ok` bằng database adapter.
- Output tốt: `status=ok`, `database=connected`, `schema_version=1.0.0`.
- Database lỗi: HTTP 503 với thông báo tổng quát.
- Không kiểm tra Gemini.

### 5.3 `POST /plan-test` — development only

- Input: giống `/chat`.
- Output: QueryPlan đã qua validation.
- Không compile SQL, không gọi PostgreSQL.
- Chỉ hiện khi `APP_ENV=development`; production trả 404 và không đưa endpoint vào OpenAPI lúc app khởi động.

### 5.4 `POST /query-test` — development only

- Input: QueryPlan viết tay.
- Bỏ qua Gemini; dùng để chứng minh Pydantic + compiler + database độc lập.
- Output success có thêm `generated_sql`.
- Production trả 404.

### 5.5 QueryPlan

Nhánh query:

```json
{
  "action": "query",
  "query": {
    "anchor_table": "patients | doctors | visits",
    "joins": [],
    "select": [],
    "filters": [],
    "aggregation": null,
    "order_by": null,
    "limit": 20
  },
  "fallback": null
}
```

Nhánh fallback:

```json
{
  "action": "fallback",
  "query": null,
  "fallback": {
    "reason": "safety_violation",
    "user_message_vi": "Yêu cầu này không thể được thực hiện an toàn.",
    "missing_slots": []
  }
}
```

Hai payload loại trừ nhau: `query` không được đi cùng `fallback` và ngược lại. Field lạ bị từ chối.

## 6. Các lớp an toàn — câu trả lời nên thuộc lòng

1. Input validation: chặn câu rỗng/quá dài trước mọi external call.
2. Prompt boundary: system instruction yêu cầu chỉ trả QueryPlan, không SQL và không làm theo chỉ dẫn nằm trong câu hỏi.
3. Structured output: Gemini bị ràng buộc bằng JSON Schema, `temperature=0`.
4. Pydantic validation: `extra=forbid`; kiểm tra whitelist bảng/cột/toán tử/kiểu/join/aggregation/limit/PII.
5. Compiler-controlled SQL: tên identifier đến từ metadata; user value đi qua `%s` parameters.
6. SQL gate: chỉ chuỗi bắt đầu bằng `SELECT`, không cho dấu chấm phẩy.
7. Database enforcement: transaction `readonly=True`, `autocommit=False`, timeout 5 giây.
8. Resource cleanup: rollback và đóng connection trong `finally`.
9. Error masking: client chỉ nhận thông báo 502/503 tổng quát, không nhận credential hay stack trace.
10. Output minimization: `/chat` không trả SQL; endpoint quan sát chỉ mở ở development.

Không nói “an toàn tuyệt đối” hoặc “chống được mọi SQL injection”. Cách nói chính xác:

> Hệ thống giảm đáng kể bề mặt tấn công bằng nhiều lớp độc lập và có test cho các invariant chính. Trước production vẫn cần security review, authorization, audit và penetration testing.

## 7. Bộ câu hỏi mentor có thể hỏi và câu trả lời

### “Tại sao không cho Gemini tạo SQL luôn?”

> Vì SQL tự do làm tăng mạnh bề mặt tấn công và khó kiểm chứng. Với QueryPlan, không gian hành động bị giới hạn bởi enum và metadata. Backend có thể từ chối plan sai trước database, compiler có thể được unit test độc lập và mọi user value được parameterize.

### “Nếu Gemini hallucinate tên bảng hoặc cột thì sao?”

> `TableName` chỉ có ba enum; `ColumnRef` đối chiếu cột thật trong metadata; Pydantic cấm field lạ. Plan sai không tới compiler/database và được ánh xạ thành lỗi dịch vụ AI 502 ở luồng `/chat`.

### “Nếu người dùng nhét `DROP TABLE` vào tên bệnh nhân?”

> Trường hợp tốt planner trả safety fallback. Kể cả value lọt vào một query hợp lệ, value không được ghép vào SQL mà đi qua params. Compiler chỉ sinh SELECT; SQL gate cấm dấu chấm phẩy; transaction database là read-only. Vì vậy payload không trở thành câu lệnh thứ hai.

### “Chỉ kiểm tra `startswith SELECT` có đủ không?”

> Không đủ nếu đây là lớp duy nhất. Trong thiết kế này nó chỉ là một lớp phòng thủ bổ sung. Lớp chính là compiler không nhận SQL từ bên ngoài, identifier đến từ whitelist, values được parameterize và database cưỡng chế transaction read-only. Production vẫn nên dùng DB role chỉ có quyền SELECT ở mức account.

### “Parameterized query bảo vệ cái gì, không bảo vệ cái gì?”

> Nó bảo vệ giá trị dữ liệu bằng cách không xem value là cú pháp SQL. Nó không parameterize được tên bảng/cột, nên các identifier đó phải lấy từ enum/metadata whitelist, không lấy trực tiếp từ user.

### “`total_records` trong câu count tại sao bằng 1?”

> `total_records` là số row trong response. `COUNT(*)` trả một row, nên bằng 1. Giá trị thống kê nằm ở `data[0].total`. Nếu muốn API dễ hiểu hơn, bước sau có thể thiết kế response riêng cho aggregation.

### “Fallback HTTP 200 có hợp lý không?”

> Có, vì đây là kết quả nghiệp vụ dự kiến: hệ thống hiểu rằng không nên hoặc chưa đủ thông tin để query. Hạ tầng hỏng dùng 5xx; input sai dùng 422. Client dựa thêm vào field `status` để render.

### “Empty result khác fallback thế nào?”

> Empty result là query hợp lệ, database đã chạy và trả 0 row: `status=success`, `total_records=0`, `data=[]`. Fallback dừng trước database hoặc chủ động không query: `status=fallback` kèm reason.

### “Health trả 200 có chứng minh toàn hệ thống hoạt động không?”

> Chưa. Nó chứng minh FastAPI và PostgreSQL adapter hoạt động. Gemini được kiểm tra qua smoke `/chat` hoặc benchmark riêng. Có thể mở rộng readiness check, nhưng không nên gọi LLM ở health probe tần suất cao vì chi phí và rate limit.

### “Retry Gemini như thế nào?”

> Chỉ retry lỗi tạm thời: 408, 429, 500, 502, 503, 504 và lỗi kết nối/timeout. Tối đa 3 lần. Nếu có `Retry-After` dạng số thì tôn trọng nhưng cap ở 8 giây; nếu không thì exponential backoff có jitter. Lỗi cố định như 401 không retry.

### “Timeout 60 giây của Gemini và 5 giây database có mâu thuẫn không?”

> Không, chúng bảo vệ hai resource khác nhau. 60 giây là timeout cho một HTTP attempt tới Gemini; 5 giây là statement timeout của PostgreSQL. Vì có tối đa 3 attempt cộng backoff, thời gian client quan sát có thể lớn; đây là lý do smoke timeout rộng và production cần SLA/circuit breaker phù hợp.

### “Vì sao dùng psycopg2 trực tiếp, chưa dùng ORM?”

> Mục tiêu POC là kiểm soát rõ SQL compiler và parameters, nên psycopg2 làm ranh giới dễ quan sát. Khi production hóa có thể thêm pool hoặc data-access layer; dùng ORM không tự động thay thế whitelist, authorization hay read-only permission.

### “PII hiện được bảo vệ thế nào?”

> Metadata đánh dấu `patients.full_name` và `patients.phone_number` là PII. Nếu SELECT PII, QuerySpec buộc exact filter bằng positive integer `patient_id` và limit tối đa 1. Tuy nhiên chưa có authentication/authorization gắn với người gọi, nên chưa thể coi đó là kiểm soát truy cập production.

### “Tại sao tên bác sĩ không là PII còn tên bệnh nhân là PII?”

> Đây là policy miền hiện tại: thông tin nghề nghiệp công khai của bác sĩ được cho phép tra cứu, còn danh tính/liên hệ bệnh nhân là nhạy cảm. Policy phải được chủ dữ liệu và pháp chế xác nhận trước production, không nên coi metadata hiện tại là kết luận pháp lý chung.

### “100 scenario dùng để làm gì?”

> Đó là catalog acceptance/roadmap: mô tả câu hỏi, action, bảng, join, capability, security và trạng thái triển khai. Nó giúp nhìn thấy coverage và gap. Hiện không chạy tất cả qua planner thật; benchmark chỉ chọn tối đa 5 scenario planner-ready mỗi lần để tránh tốn quota.

### “Tại sao chỉ có 30 supported mà evaluator nói planner-ready nhiều hơn?”

> Planner-ready có thể bao gồm cả các case `expected_fallback`, vì fallback cũng là hành vi đúng cần kiểm tra. `supported` là truy vấn/tình huống đã triển khai; `expected_fallback` là hệ thống đã xác định phải từ chối hoặc yêu cầu thêm dữ kiện. Hai chỉ số đo hai thứ khác nhau.

### “Các test bị skip có đáng lo không?”

> Hai test đó là integration test cần PostgreSQL thật và chỉ chạy khi bật `RUN_DB_TESTS=1`. Unit/contract test vẫn pass, nhưng trước demo hoặc CI tích hợp cần bật cờ này với database test đã cấu hình. Em không dùng số test unit để thay thế bằng chứng end-to-end; vì vậy có thêm smoke test qua HTTP thật.

### “Hệ thống có đưa tư vấn y khoa không?”

> Không trong phiên bản này. Câu hỏi chỉ định thuốc thuộc scenario cần `medical_guidance` và clinical safety riêng; không được biến thành query tùy ý. Demo hiện tập trung tra cứu dữ liệu.

### “Đưa lên production cần làm gì tiếp?”

> Tối thiểu: authentication; role/relationship-based authorization; DB user chỉ có SELECT; TLS và secret manager; audit log có redaction; connection pool; rate limit; observability và tracing; prompt/model versioning; security review; load/failure test; retention policy; kiểm soát PII theo quy định áp dụng; tắt hoàn toàn endpoint development.

## 8. Phương án B khi live demo lỗi

### Gemini trả 502 hoặc 429 kéo dài

Nói:

> Đây là dependency bên ngoài đang không khả dụng. Backend đã che lỗi nội bộ thành 502 và có retry giới hạn. Để chứng minh phần lõi không phụ thuộc vào việc Gemini đang online, em chuyển sang `/query-test` với QueryPlan viết tay; endpoint này vẫn đi qua Pydantic, compiler và PostgreSQL.

Sau đó chạy:

```powershell
python -m pytest tests/test_gemini_retry.py -q
```

### PostgreSQL trả 503

Nói:

> API đã biến lỗi database thành 503 tổng quát và không để lộ connection string. Em sẽ không sửa credential trên màn hình. Phần hợp đồng và compiler vẫn có thể chứng minh bằng test; end-to-end database sẽ được chạy lại sau khi service sẵn sàng.

### Kết quả dữ liệu khác số đã rehearsal

Không đoán hoặc nói số cũ. Nói:

> Đây là dữ liệu hiện tại của database. Demo kiểm tra tính đúng của pipeline và response contract, không hard-code số lượng bản ghi.

### Gemini trả plan không như dự kiến

Không sửa JSON của response. Nói:

> Planner là thành phần xác suất dù temperature bằng 0. Benchmark dùng expected constraints để đo độ ổn định. Nếu plan hợp lệ nhưng semantic chưa đúng, đây là lỗi chất lượng planner; nếu plan vi phạm schema, backend chặn trước database.

## 9. Checklist nói chính xác, tránh bị mentor bắt lỗi

- Nói “Gemini tạo QueryPlan”, không nói “Gemini tạo query SQL”.
- Nói “Pydantic kiểm định plan”, không nói “JSON Schema tự bảo đảm đúng nghiệp vụ 100%”.
- Nói “nhiều lớp giảm rủi ro”, không nói “an toàn tuyệt đối”.
- Nói “read-only transaction”; nếu chưa xác minh DB account chỉ có SELECT thì không khẳng định account đã least privilege.
- Nói “100 scenario là catalog/roadmap”; chỉ 30 đang `supported`.
- Nói “118 pass, 2 integration test skip trong môi trường hiện tại”, không nói “120 test pass”.
- Không dùng số giả trong output thật; đọc số đang xuất hiện trên Swagger.
- Không khẳng định latency SLA từ một lần demo.
- Không trình chiếu `.env`, API key, password, raw stack trace.
- Không dùng endpoint `/plan-test` và `/query-test` như feature production.

## 10. Câu kết 30 giây

> Điểm em muốn nhấn mạnh là hệ thống không biến LLM thành database agent có toàn quyền. LLM chỉ làm nhiệm vụ hiểu ngôn ngữ và đề xuất một kế hoạch hữu hạn. Mọi quyền truy cập dữ liệu vẫn nằm ở code có thể kiểm định: metadata, Pydantic, compiler và read-only database transaction. Bản hiện tại đã chứng minh được nguyên lý này cho luồng tra cứu chính và fallback an toàn; lộ trình production tiếp theo tập trung vào identity, authorization, audit và vận hành ở quy mô thật.

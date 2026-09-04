# KIẾN TRÚC WORKFLOW 1 — DATAQA PIPELINE (STRUCTURED QUERY & QUALITY GUARD)

Tài liệu mô tả chi tiết luồng xử lý truy vấn dữ liệu có cấu trúc (Structured Data QA), cơ chế kiểm soát bảo mật đa tầng, xác thực kết quả và kiểm soát chất lượng AI Model theo định hướng fail-closed.

```mermaid
graph TD
    %% =========================
    %% 1. INPUT & PROJECT SCOPE
    %% =========================
    User(("Client<br/>Mobile/Web"))
    Router["FastAPI Router<br/>Control Plane"]
    Scope["Identity & Scope Gate<br/>Database + View Allowlist"]
    Cache{"Redis Cache<br/>Approved QuerySpec Patterns"}

    %% =========================
    %% 2. SEMANTIC RETRIEVAL
    %% =========================
    Embedder["Embedding Model<br/>Vector hóa câu hỏi"]
    VectorDB[("PostgreSQL + pgvector<br/>Semantic Search")]
    Catalog[("Semantic Catalog<br/>Metric, Dimension, Synonym")]
    ContextBuilder["Semantic Context Builder<br/>Đóng gói ngữ cảnh hẹp"]

    %% =========================
    %% 3. QUERYSPEC GENERATION
    %% =========================
    Gemini1["Gemini API<br/>QuerySpec Planner"]
    Validator{"QuerySpec Validator<br/>Pydantic + Semantic Check"}
    Clarify["Hỏi lại người dùng<br/>khi câu hỏi mơ hồ"]
    Abort["Dừng xử lý<br/>Báo thiếu hoặc lỗi dữ liệu"]
    Block["Chặn yêu cầu<br/>Không hỗ trợ hoặc vượt phạm vi"]

    %% =========================
    %% 4. SAFE SQL EXECUTION
    %% =========================
    SQLBuilder["SQLAlchemy Core<br/>Deterministic SQL Compiler"]
    SQLGuard{"SQL AST Guard<br/>SELECT Only + Allowlist"}
    DB[("PostgreSQL Read-Only<br/>Timeout + Row Limit")]

    %% =========================
    %% 5. RESULT VERIFICATION
    %% =========================
    ResultValidator{"Result Validator<br/>Kiểu dữ liệu + Số dòng + Cột"}
    NumericVerifier{"Numeric Verifier<br/>Tổng, tỷ lệ, null, chia cho 0"}
    DataMinimizer["Aggregation + Masking<br/>Loại dữ liệu không cần thiết"]
    Evidence["Evidence Pack Builder<br/>Kết quả + Bộ lọc + Data Time"]

    %% =========================
    %% 6. ANSWER GENERATION
    %% =========================
    Gemini2["Gemini API<br/>Answer Composer"]
    OutputValidator{"Output Validator<br/>Đối chiếu với Evidence Pack"}

    %% =========================
    %% 7. QUALITY & AUDIT
    %% =========================
    Audit[("Technical Audit Log<br/>Không lưu dữ liệu y tế thô")]
    DataQuality[("Data Quality Log<br/>Freshness, Null, Anomaly")]
    Review["Human Review + Golden Evaluation<br/>Phê duyệt Pattern"]

    %% =========================
    %% MAIN FLOW
    %% =========================
    User -->|"1. Câu hỏi tiếng Việt"| Router
    Router -->|"2. Gắn Request ID"| Scope
    Scope -->|"3. Project và nguồn dữ liệu cố định"| Cache

    %% CACHE BRANCH
    Cache -->|"Hit: QuerySpec Template đã duyệt"| Validator
    Cache -->|"Miss"| Embedder

    %% SEMANTIC RETRIEVAL
    Embedder -->|"4. Query Vector"| VectorDB
    VectorDB -->|"5. Top metric, dimension và pattern"| ContextBuilder
    Catalog -->|"Định nghĩa nghiệp vụ đã duyệt"| ContextBuilder
    ContextBuilder -->|"6. Semantic Context hẹp"| Gemini1
    Scope -->|"Câu hỏi + Project Context"| Gemini1

    %% QUERYSPEC VALIDATION
    Gemini1 -->|"7. QuerySpec JSON"| Validator
    Validator -->|"Sai cấu trúc hoặc logic<br/>Retry tối đa 2 lần"| Gemini1
    Validator -->|"Câu hỏi mơ hồ"| Clarify
    Validator -->|"Ngoài phạm vi hoặc trường cấm"| Block
    Validator -->|"Hợp lệ"| SQLBuilder

    Clarify -->|"Yêu cầu làm rõ"| Router
    Abort -->|"Báo thiếu dữ liệu / Lỗi"| Router
    Block -->|"Từ chối an toàn (DENY)"| Router

    %% SQL EXECUTION
    SQLBuilder -->|"8. SQL + Bind Parameters"| SQLGuard
    SQLGuard -->|"SQL không hợp lệ"| Block
    SQLGuard -->|"SELECT hợp lệ"| DB

    %% RESULT VALIDATION
    DB -->|"9. Kết quả truy vấn nội bộ"| ResultValidator
    ResultValidator -->|"Sai kiểu, quá nhiều dòng<br/>hoặc có cột cấm"| Abort
    ResultValidator -->|"Hợp lệ"| NumericVerifier

    NumericVerifier -->|"Không nhất quán"| Abort
    NumericVerifier -->|"Đã kiểm chứng"| DataMinimizer

    %% DATA MINIMIZATION
    DataMinimizer -->|"10. Dữ liệu tối thiểu<br/>đã tổng hợp và che"| Evidence
    Evidence -->|"11. Evidence Pack"| Gemini2

    %% ANSWER GENERATION
    Gemini2 -->|"12. Câu trả lời tự nhiên"| OutputValidator
    OutputValidator -->|"Có số liệu ngoài bằng chứng"| Abort
    OutputValidator -->|"13. Câu trả lời hợp lệ"| Router
    Router -->|"14. JSON API + Data Time"| User

    %% AUDIT & DATA QUALITY
    Router -.->|"Request metadata"| Audit
    Validator -.->|"QuerySpec + Validation Status"| Audit
    SQLGuard -.->|"SQL Digest + Guard Status"| Audit
    OutputValidator -.->|"Model và Output Status"| Audit

    DB -.->|"Freshness + Null + Row Count"| DataQuality
    NumericVerifier -.->|"Kết quả kiểm chứng"| DataQuality

    %% GOLDEN PATTERN REVIEW
    Audit -.-> Review
    DataQuality -.-> Review
    Review -.->|"Chỉ lưu Pattern đã duyệt<br/>kèm Semantic Version"| Cache

    %% =========================
    %% STYLING
    %% =========================
    classDef ai fill:#e3f2fd,stroke:#1e88e5,stroke-width:2px;
    classDef database fill:#e8f5e9,stroke:#43a047,stroke-width:2px;
    classDef core fill:#fff3e0,stroke:#fb8c00,stroke-width:2px;
    classDef guard fill:#fff8e1,stroke:#f9a825,stroke-width:2px;
    classDef danger fill:#ffebee,stroke:#e53935,stroke-width:2px;
    classDef quality fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px;

    class Gemini1,Gemini2,Embedder ai;
    class VectorDB,Catalog,DB,Cache,Audit,DataQuality database;
    class Router,Scope,ContextBuilder,SQLBuilder,DataMinimizer,Evidence core;
    class Validator,SQLGuard,ResultValidator,NumericVerifier,OutputValidator guard;
    class Clarify,Abort,Block danger;
    class Review quality;
```

---

## 📌 Các điểm cốt lõi của Workflow 1

1. **Kiểm soát bảo mật Fail-Closed**:
   - Bất kỳ vi phạm nào (Pydantic validation, AST guard, Numeric verification, Output hallucination) đều dẫn tới nhánh an toàn (`Clarify`, `Abort`, `Block`) và trả về `Router` dưới dạng thông báo an toàn, không rò rỉ thông tin nội bộ.
2. **Cách ly DDL & Schema**:
   - Model (Gemini1) chỉ nhận **Semantic Context hẹp** (logical metrics, dimensions, synonyms) từ `Semantic Catalog`, không bao giờ nhận DDL vật lý hay tên bảng thực tế.
3. **Biên dịch SQL an toàn**:
   - SQL được sinh hoàn toàn bằng **SQLAlchemy Core** (deterministic compiler) kết hợp tham số hóa (Bind Parameters) và kiểm tra qua **SQL AST Guard**.
4. **Không gửi dữ liệu thô ra ngoài**:
   - Dữ liệu thô từ DB được tổng hợp, khử định danh qua `DataMinimizer` và đóng gói thành `Evidence Pack` có kèm timestamp & kiểm chứng trước khi đưa vào `Gemini2` sinh câu trả lời tự nhiên.
5. **Đóng kín chu trình chất lượng & Golden Pattern**:
   - Audit Log & Data Quality Log được thu thập tự động, đưa qua bước Review để cập nhật Golden Patterns có gắn Semantic Version vào Cache.
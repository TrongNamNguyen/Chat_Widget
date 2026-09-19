# 🏛️ Kiến Trúc Luồng Xử Lý Truy Vấn Dữ Liệu An Toàn (Production Pipeline)

> Tài liệu chi tiết và ma trận phân tích 9 bước: Xem tại [workflow_pipeline.md](file:///c:/Chat_Widget/documents/workflow_pipeline.md).

```mermaid
graph TD
    %% ==========================================
    %% BƯỚC 1: TIẾP NHẬN & KIỂM TRA QUYỀN
    %% ==========================================
    subgraph SG1 ["Bước 1: Tiếp nhận & Kiểm tra Quyền"]
        A["Widget: Gửi câu hỏi + Token/Session"] --> B("FastAPI: Tiền xử lý & Chuẩn hóa chuỗi")
        B --> C{"OPA: Đánh giá Policy"}
        C -- "Từ chối" --> Z(["Luồng Fallback an toàn"])
    end

    %% ==========================================
    %% BƯỚC 2: PHÂN LUỒNG CACHE
    %% ==========================================
    subgraph SG2 ["Bước 2: Phân luồng Cache"]
        C -- "Cho phép" --> D{"Redis: Tìm Cache Hit"}
        D -- "Trúng Cache (p95 < 20ms)" --> T
    end

    %% ==========================================
    %% BƯỚC 3 & 4: SINH & KIỂM DUYỆT QUERYSPEC
    %% ==========================================
    subgraph SG3 ["Bước 3 & 4: Sinh & Kiểm duyệt QuerySpec"]
        D -- "Trượt Cache" --> E("LiteLLM Gateway: Định tuyến request")
        E --> F["Gemini: Sinh QuerySpec JSON"]
        F --> G{"Pydantic: Validate Cấu trúc"}
        G -- "Lỗi logic/Kiểu dữ liệu" --> H("Self-correction tối đa 2 lần")
        H -- "Sửa lỗi" --> E
        H -- "Hết lượt retry" --> Z
    end

    %% ==========================================
    %% BƯỚC 5 & 6: BIÊN DỊCH SQL & GUARDRAIL
    %% ==========================================
    subgraph SG4 ["Bước 5 & 6: Biên dịch SQL & Guardrail"]
        G -- "Chuẩn JSON" --> I("Compiler: Dịch SQL + Tiêm Mandatory Filters")
        I --> J{"sqlglot: Quét AST Bảo mật"}
        J -- "Lệnh cấm DDL/DML" --> Z
        J -- "Chỉ chứa SELECT" --> K("Tự động ép LIMIT <= 100")
    end

    %% ==========================================
    %% BƯỚC 7 & 8: THỰC THI, DIỄN GIẢI & ĐÓNG GÓI
    %% ==========================================
    subgraph SG5 ["Bước 7 & 8: Thực thi, Diễn giải & Đóng gói"]
        K --> L[("PostgreSQL: Thực thi tài khoản ReadOnly, Timeout 5s")]
        L --> M{"Raw Rows"}
        M -- "Rỗng (0 dòng)" --> N["Sử dụng Template tĩnh"]
        M -- "Có dữ liệu" --> O("LiteLLM: Format tiếng Việt tự nhiên")
        O --> P{"Grounding: Đối chiếu Raw Rows"}
        P -- "Bịa đặt số/thực thể" --> Q("Retry format 1 lần / Fallback")
        Q -- "Thử lại format" --> O
        Q -- "Hết lượt / Thất bại" --> Z
        P -- "Khớp hoàn toàn" --> R("Đóng gói EvidencePack & AnswerEnvelope")
    end

    %% ==========================================
    %% BƯỚC 9: TRẢ KẾT QUẢ & TRACING
    %% ==========================================
    subgraph SG6 ["Bước 9: Trả kết quả & Tracing"]
        R --> S("HTML Sanitize (DOMPurify/Bleach)")
        N --> S
        S --> T(["Widget: Hiển thị kết quả & Bằng chứng"])
        S -.->|"Chỉ cache khi Grounding PASS"| U[("Redis: Set Cache mới")]
        T --> V[("Langfuse: Ghi Trace & Token Cost")]
        Z --> T
        Z -.->|"Ghi trace Fallback/Error"| V
    end

    %% ==========================================
    %% STYLING & CLASS DEFINITIONS
    %% ==========================================
    classDef client fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef gateway fill:#0f172a,stroke:#818cf8,stroke-width:2px,color:#f8fafc;
    classDef security fill:#450a0a,stroke:#f87171,stroke-width:2px,color:#fef2f2;
    classDef decision fill:#1e1b4b,stroke:#a855f7,stroke-width:2px,color:#faf5ff;
    classDef llm fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#ecfdf5;
    classDef storage fill:#172554,stroke:#60a5fa,stroke-width:2px,color:#eff6ff;
    classDef fallback fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff;
    classDef success fill:#14532d,stroke:#22c55e,stroke-width:2px,color:#f0fdf4;

    class A,T client;
    class B,E,I,S gateway;
    class C,G,J,P decision;
    class H,Q security;
    class F,O llm;
    class D,L,U,V storage;
    class Z fallback;
    class R,N success;
```
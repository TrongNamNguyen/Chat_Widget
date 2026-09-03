flowchart TD
    classDef userFill fill:#2b5c8f,stroke:#333,stroke-width:1px,color:#fff;
    classDef coreFill fill:#1e3a5f,stroke:#333,stroke-width:1px,color:#fff;
    classDef aiFill fill:#0d5c58,stroke:#333,stroke-width:1px,color:#fff;
    classDef dbFill fill:#4a3b68,stroke:#333,stroke-width:1px,color:#fff;
    classDef safeFill fill:#2d6a4f,stroke:#333,stroke-width:1px,color:#fff;

    User["👤 User / Chat Widget<br/><i>'Có bao nhiêu bệnh nhân nam trên 50 tuổi?'</i>"]:::userFill
    
    subgraph Router_Layer ["Tầng 1: Lọc Schema & Cô Lập Dữ Liệu"]
        FastAPI["⚡ FastAPI Control Plane & Router"]:::coreFill
        SchemaJson[("📄 schema_definition.json<br/>(File cấu hình cố định)")]:::coreFill
    end

    subgraph AI_Layer ["Tầng 2: Trích Xuất Ý Định (Intent Extraction)"]
        LLM["🤖 Ollama LLM<br/><b>Skill: QuerySpec Generator</b>"]:::aiFill
        Pydantic["🛡️ Pydantic Guardrail<br/>(Kiểm tra Whitelist Bảng/Cột)"]:::safeFill
    end

    subgraph Execution_Layer ["Tầng 3: Sinh Lệnh & Truy Xuất An Toàn"]
        Builder["⚙️ Deterministic Query Builder Tool<br/>(SQLAlchemy Parameterized Query)"]:::safeFill
        Postgres[("🗄️ PostgreSQL Database<br/>(Tài khoản Read-Only)")]:::dbFill
    end

    %% Flow connections
    User -->|"1. Gửi câu hỏi"| FastAPI
    SchemaJson -->|"2. Trích xuất duy nhất schema bảng 'patients'"| FastAPI
    FastAPI -->|"3. Gửi Prompt + Schema hẹp"| LLM
    LLM -->|"4. Trả về QuerySpec JSON"| Pydantic
    Pydantic -->|"5. Xác thực JSON hợp lệ"| Builder
    Builder -->|"6. Sinh & Thực thi Parameterized SQL"| Postgres
    Postgres -->|"7. Dữ liệu thô (vd: 125)"| FastAPI
    FastAPI -->|"8. Trả lời văn bản tự nhiên"| User
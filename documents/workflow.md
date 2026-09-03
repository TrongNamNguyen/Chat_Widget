graph TD
    subgraph G0["GIAI ĐOẠN 0: OFFLINE / STARTUP INITIALIZATION"]
        DB1[(PostgreSQL DB)] -->|1. Auto Inspection| INSP[SQLAlchemy Inspector]
        INSP -->|2. Cache Metadata| RAM[Master Schema Cache in RAM]
        INSP -->|3. Embedding Table Descriptions| EMB_M[Embedding Model]
        EMB_M -->|4. Store Schema Vectors| PGV[(pgvector Table)]
    end

    subgraph G1["GIAI ĐOẠN 1: VECTOR ROUTING & SCHEMA PRUNING"]
        U[User / Chat Widget] -->|1. Prompt: 'Có bao nhiêu bệnh nhân...'| API[FastAPI Control Plane]
        API -->|2. Vectorize Question| EMB_M
        EMB_M -->|3. Cosine Search <=>| PGV
        PGV -->|4. Top-K Tables: patients| ROUTER[Vector Table Router]
        ROUTER -->|5. Request Table Slice| SLICER[In-Memory Schema Slicer]
        RAM -.->|Supply Master Schema| SLICER
    end

    subgraph G2["GIAI ĐOẠN 2: INTENT EXTRACT & VALIDATION"]
        SLICER -->|6. Inject 'patients' DDL Snippet| LLM[Ollama LLM - Skill: Intent Extractor]
        LLM -->|7. Return QuerySpec JSON| PYD[Pydantic Guardrail & Validator]
        PYD -->|8. Validated QuerySpec| QB[Query Builder Tool SQLAlchemy]
    end

    subgraph G3["GIAI ĐOẠN 3: SAFE EXECUTION & RESPONSE"]
        QB -->|9. Parameterized SQL Query| READDB[(PostgreSQL Read-Only User)]
        READDB -->|10. Raw Data Result: 125| COMP[Answer Composer & Evidence Pack]
        COMP -->|11. Final Secure Answer| U
    end

    classDef core fill:#0066CC,stroke:#fff,stroke-width:1px,color:#fff;
    classDef security fill:#D9534F,stroke:#fff,stroke-width:1px,color:#fff;
    classDef storage fill:#2B5B84,stroke:#fff,stroke-width:1px,color:#fff;
    classDef ai fill:#008080,stroke:#fff,stroke-width:1px,color:#fff;

    class API,SLICER,COMP core;
    class PYD,QB security;
    class DB1,PGV,READDB,RAM storage;
    class LLM,EMB_M ai;
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import GEMINI_MODEL
from app.database import get_database_schema, execute_sql_safely
from app.llm_service import ask_gemini_to_write_sql
from app.schemas import ChatInput, ChatResponse

app = FastAPI(
    title="Medical Chat Widget API",
    description="API cho Chat Widget truy vấn dữ liệu y tế thông minh từ ngôn ngữ tự nhiên sang SQL",
    version="1.0.0"
)

# Cấu hình CORS để Chat Widget frontend có thể gọi API từ bất kỳ domain nào
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "message": "Medical Chat Widget API dang hoat dong!",
        "docs_url": "/docs",
        "ai_engine": f"Google Gemini ({GEMINI_MODEL})"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "model": GEMINI_MODEL}

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(user_input: ChatInput):
    """
    Cửa ngõ chính của Chat Widget:
    1. Nhận câu hỏi tự nhiên từ người dùng.
    2. Lấy cấu trúc cơ sở dữ liệu (Schema).
    3. Gửi câu hỏi + Schema sang Google Gemini để chuyển đổi thành SQL.
    4. Kiểm tra an toàn và thực thi câu lệnh SQL với tài khoản Read-Only.
    5. Đóng gói và trả về kết quả kèm bằng chứng (Evidence).
    """
    question = user_input.question.strip()
    print(f"\n[BUOC 1]: Nhan cau hoi tu nguoi dung: '{question}'")
    start_time = time.time()

    print(f"[BUOC 2 & 3]: Dang lay danh sach cac bang (Schema) tu Database...")
    schema = get_database_schema()

    print(f"[BUOC 4]: Gui cau hoi + schema sang Google Gemini ({GEMINI_MODEL})...")
    sql_command = ask_gemini_to_write_sql(question, schema)

    print(f"[BUOC 5]: Gemini da sinh ra: \n >>> {sql_command}")

    if sql_command == "INVALID_QUERY":
        elapsed = time.time() - start_time
        print("[!] Cau hoi khong hop le hoac khong the tao SQL --> Tra ve INVALID_QUERY")
        return ChatResponse(
            status="error",
            error_code="INVALID_QUERY",
            message="Câu hỏi không rõ ràng, không liên quan đến cơ sở dữ liệu y tế hoặc không thể chuyển thành câu lệnh SQL.",
            time_taken=round(elapsed, 2),
            question=question,
            generated_sql="INVALID_QUERY",
            ai_engine=f"Google Gemini ({GEMINI_MODEL})",
            total_records=0,
            data=[]
        )

    print("[BUOC 6 & 7]: Thuc thi cau lenh SQL voi tai khoan ai_agent (Read-Only)...")
    try:
        db_results = execute_sql_safely(sql_command)
    except Exception as err:
        elapsed = time.time() - start_time
        print(f"[ERROR] Loi khi thuc thi SQL: {err}")
        return ChatResponse(
            status="error",
            error_code="DB_EXECUTION_ERROR",
            message=f"Khong the lay du lieu: {str(err)}",
            time_taken=round(elapsed, 2),
            question=question,
            generated_sql=sql_command,
            ai_engine=f"Google Gemini ({GEMINI_MODEL})",
            total_records=0,
            data=[]
        )

    elapsed = time.time() - start_time
    print(f"[BUOC 8]: Hoan thanh! Tim thay {len(db_results)} ban ghi. Dang gui ket qua ve...")
    return ChatResponse(
        status="success",
        time_taken=round(elapsed, 2),
        question=question,
        generated_sql=sql_command,
        ai_engine=f"Google Gemini ({GEMINI_MODEL})",
        total_records=len(db_results),
        data=db_results
    )

# Chạy server bằng uvicorn
if __name__ == "__main__":
    import uvicorn
    print(f"[*] Dang khoi dong Server FastAPI voi Google Gemini ({GEMINI_MODEL})")
    print("[*] Mo giao dien thu nghiem Swagger tai: http://127.0.0.1:8000/docs")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
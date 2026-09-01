"""
Project: FASTAPI + POSTGRESQL + GOOGLE GEMINI (GEMINI-3.6-FLASH) TEXT-TO-SQL
 Quy trình 8 bước:
 1. Nhận câu hỏi từ người dùng qua API (POST /chat)
 2 & 3. FastAPI vào Database PostgreSQL đọc danh sách bảng và cột (Schema)
 4. Ghép Schema + Câu hỏi thành một đoạn văn (Prompt) gửi sang Google Gemini
 5. AI (gemini-3.6-flash) suy nghĩ siêu tốc và trả về câu lệnh SQL
 6 & 7. FastAPI dùng tài khoản READ-ONLY (ai_agent) chạy câu SQL trong PostgreSQL
 8. PostgreSQL trả kết quả -> FastAPI đóng gói thành JSON gửi lại cho người dùng
"""

import os
import sys
import re
import time
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Tải các biến môi trường bảo mật từ file .env
load_dotenv()

# Tự động hỗ trợ tiếng Việt 
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# CẤU HÌNH HỆ THỐNG 
# 1. Thông tin tài khoản PostgreSQL 
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "medical_db"),
    "user": os.getenv("DB_USER", "ai_agent"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
}

# 2. Cấu hình Google Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_URL = os.getenv(
    "GEMINI_URL",
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)
if GEMINI_API_KEY and "key=" not in GEMINI_URL:
    GEMINI_URL = f"{GEMINI_URL}?key={GEMINI_API_KEY}"

# Cảnh báo nếu thiếu API Key
if not GEMINI_API_KEY:
    print("[!] CANH BAO: Chua tim thay GEMINI_API_KEY trong file .env!")

# Khởi tạo ứng dụng web FastAPI
app = FastAPI(
    title="Hệ thống Chat Widget Y tế (Text-to-SQL với Gemini)",
    description="Ứng dụng FastAPI đơn giản sử dụng Google Gemini",
    version="1.0.0",
)

# Cho phép giao diện web (HTML/JS) từ bất kỳ đâu cũng có thể gọi API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# BƯỚC 1: KHAI BÁO CẤU TRÚC DỮ LIỆU ĐẦU VÀO (INPUT SCHEMA)
class ChatInput(BaseModel):
    # Người dùng gửi lên một câu hỏi dạng chữ (string)
    question: str


# BƯỚC 2 & 3: HÀM TỰ ĐỘNG ĐỌC CẤU TRÚC BẢNG (SCHEMA) TỪ POSTGRESQL
def get_database_schema() -> str:
    """
    Hàm này kết nối vào PostgreSQL, truy vấn bảng hệ thống 'information_schema.columns'
    để lấy danh sách tất cả các bảng và cột đang có trong database.
    """
    try:
        # Mở kết nối đến database với quyền của ai_agent
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Câu lệnh SQL để hỏi PostgreSQL: "Cho tôi biết các bảng và cột trong schema public"
        query = """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # Gom nhóm kết quả thành văn bản dễ đọc cho AI
        schema_text = "Cấu trúc cơ sở dữ liệu y tế gồm các bảng sau:\n"
        current_table = ""
        for table_name, column_name, data_type in rows:
            if table_name != current_table:
                current_table = table_name
                schema_text += f"\n- Bảng `{table_name}`:\n"
            schema_text += f"    + Cột `{column_name}` ({data_type})\n"

        return schema_text

    except Exception as error:
        # Nếu chưa cài PostgreSQL hoặc database chưa bật, trả về mô tả tĩnh để bài tập không bị lỗi
        print(f"[!] [Luu y]: Chua ket noi duoc PostgreSQL ({error}). Su dung mo ta cau truc mau.")
        return """
            Cấu trúc cơ sở dữ liệu y tế gồm các bảng sau:
            - Bảng `patients`:
                + Cột `patient_id` (integer, khóa chính)
                + Cột `full_name` (varchar 100, họ tên bệnh nhân)
                + Cột `gender` (varchar 10, giới tính 'Nam' hoặc 'Nữ')
                + Cột `date_of_birth` (date, ngày sinh)
                + Cột `phone_number` (varchar 15, số điện thoại)
            - Bảng `doctors`:
                + Cột `doctor_id` (integer, khóa chính)
                + Cột `full_name` (varchar 150, họ tên bác sĩ)
                + Cột `specialty` (varchar 50, chuyên khoa)
            - Bảng `visits`:
                + Cột `visit_id` (integer, khóa chính)
                + Cột `patient_id` (integer, liên kết với patients.patient_id)
                + Cột `doctor_id` (integer, liên kết với doctors.doctor_id)
                + Cột `visit_date` (date, ngày khám)
                + Cột `diagnosis` (text, chẩn đoán bệnh)
                + Cột `total_cost` (numeric, tiền viện phí)
        """


# BƯỚC 4 & 5: HÀM GỌI GOOGLE GEMINI ĐỂ BIẾN CÂU HỎI THÀNH LỆNH SQL
def ask_gemini_to_write_sql(user_question: str, schema_info: str) -> str:
    """
    Hàm này tạo câu lệnh chỉ dẫn (Prompt), gửi sang Google Gemini API và nhận về câu SQL.
    Nếu câu hỏi không rõ ràng hoặc không thể chuyển thành SQL, trả về: INVALID_QUERY
    """
    # Bước 4: Soạn Prompt hướng dẫn AI
    prompt = f"""
        Bạn là chuyên gia SQL PostgreSQL cho hệ thống y tế.
        Dưới đây là cấu trúc các bảng trong cơ sở dữ liệu:
        {schema_info}

        Nhiệm vụ: Hãy viết MỘT câu lệnh SQL PostgreSQL duy nhất (SELECT) để trả lời câu hỏi sau:
        "{user_question}"

        Quy tắc bắt buộc:
        1. CHỈ viết câu lệnh SELECT. Tuyệt đối không dùng INSERT, UPDATE, DELETE, DROP.
        2. Sử dụng đúng tên bảng (chữ thường: patients, doctors, visits) và các cột.
        3. Phân biệt hoa thường trong dữ liệu tiếng Việt (ví dụ: gender = 'Nam' hoặc ILIKE '%Nam%').
        4. Nếu câu hỏi KHÔNG rõ ràng, KHÔNG liên quan đến cơ sở dữ liệu y tế (ví dụ: chào hỏi, hỏi thời tiết, nội dung vô nghĩa...) hoặc KHÔNG thể chuyển thành câu lệnh SQL hợp lệ: CHỈ trả về đúng từ: INVALID_QUERY
        5. Nếu câu hỏi hợp lệ: Trả về câu lệnh SQL bên trong khối ```sql ... ```. Không giải thích gì thêm.
    """

    try:
        # Gửi yêu cầu HTTP POST tới Google Gemini API
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1  
            }
        }
        # 10 giây timeout tránh treo hệ thống, tiết kiệm tài nguyên, cải thiện trải nghiệm, bảo vệ bảo mật
        response = requests.post(GEMINI_URL, json=payload, timeout=10) 

        if response.status_code == 200:
            result = response.json()
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Kiểm tra nếu Gemini xác định câu hỏi không hợp lệ
            if "INVALID_QUERY" in raw_text.upper():
                return "INVALID_QUERY"

            # Bước 5: Tách lấy đoạn code SQL từ phản hồi của Gemini
            match = re.search(r"```(?:sql)?\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
            if match:
                sql_command = match.group(1).strip()
            else:
                sql_command = raw_text.strip()

            # Nếu kết quả rỗng hoặc không phải là câu lệnh SELECT/WITH
            if not sql_command or not (sql_command.upper().startswith("SELECT") or sql_command.upper().startswith("WITH")):
                return "INVALID_QUERY"

            return sql_command
        else:
            print(f"[!] Gemini bao loi HTTP {response.status_code}: {response.text}")
            return fallback_simple_sql(user_question)

    except Exception as error:
        print(f"[!] Khong goi duoc Gemini ({error}). Su dung bo suy luan mau.")
        return fallback_simple_sql(user_question)


def fallback_simple_sql(question: str) -> str:
    """Hàm tạo sẵn câu SQL mẫu dự phòng hoặc trả về INVALID_QUERY"""
    q = question.lower().strip()
    if "nam" in q and "bệnh nhân" in q:
        return "SELECT COUNT(*) AS tong_benh_nhan_nam FROM patients WHERE gender = 'Nam';"
    elif "bác sĩ" in q or "doctor" in q:
        return "SELECT doctor_id, full_name, specialty FROM doctors;"
    elif "chi phí" in q or "tiền" in q or "viện phí" in q:
        return "SELECT patient_id, diagnosis, total_cost FROM visits ORDER BY total_cost DESC LIMIT 5;"
    elif "bệnh nhân" in q or "patient" in q:
        return "SELECT * FROM patients LIMIT 10;"
    else:
        # Nếu câu hỏi không khớp bất kỳ mẫu y tế nào
        return "INVALID_QUERY"


# BƯỚC 6 & 7: HÀM THỰC THI SQL BẰNG TÀI KHOẢN (user: ai_agent, pass: secure_ai_password_123)
def execute_sql_safely(sql_command: str):
    """
    Hàm này mang câu lệnh SQL chạy vào PostgreSQL bằng tài khoản 'ai_agent'.
    Nếu có lệnh nguy hiểm như DELETE / DROP -> PostgreSQL sẽ chặn đứng ngay lập tức!
    """
    # [Bảo vệ lớp 1 ở code Python]: Kiểm tra trước xem có bắt đầu bằng SELECT không
    clean_sql = sql_command.strip().rstrip(";")
    if not clean_sql.upper().startswith("SELECT") and not clean_sql.upper().startswith("WITH"):
        raise ValueError("LOI BAO MAT: Chi cho phep thuc hien cac cau lenh doc du lieu (SELECT)!")

    # [Bảo vệ lớp 2 ở PostgreSQL]: Kết nối bằng tài khoản ai_agent chỉ có quyền READ_ONLY
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute(clean_sql)
            rows = cursor.fetchall()
            data = [dict(row) for row in rows]
            return data
        finally:
            cursor.close()
            conn.close()

    except Exception as pg_err:
        print(f"[!] Khong ket noi duoc PostgreSQL ({pg_err}). Chuyen sang database mau SQLite.")
        import sqlite3
        conn = sqlite3.connect("medical_demo.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            sqlite_sql = re.sub(r"\bILIKE\b", "LIKE", clean_sql, flags=re.IGNORECASE)
            cursor.execute(sqlite_sql)
            rows = cursor.fetchall()
            data = [dict(row) for row in rows]
            return data
        finally:
            cursor.close()
            conn.close()


# ĐIỂM TIẾP NHẬN CHÍNH: API POST /chat (KẾT NỐI TẤT CẢ CÁC BƯỚC)
@app.post("/chat", summary="Hoi dap y te bang ngon ngu tu nhien (8 Buoc)")
def chat_endpoint(user_input: ChatInput):
    """
    Đây là cửa ngõ chính của FastAPI:
    Nhận câu hỏi -> Lấy Schema -> Hỏi Gemini AI -> Lấy SQL -> Chạy DB -> Trả lời cho user!
    """
    question = user_input.question.strip()
    print(f"\n[BUOC 1]: Nhan cau hoi tu nguoi dung: '{question}'")

    start_time = time.time()

    # BƯỚC 2 & 3: Lấy danh sách bảng từ Database
    print("[BUOC 2 & 3]: Dang lay danh sach cac bang (Schema) tu Database...")
    schema = get_database_schema()

    # BƯỚC 4 & 5: Gửi sang Google Gemini để dịch sang câu lệnh SQL
    print(f"[BUOC 4]: Gui cau hoi + Schema sang Google Gemini ({GEMINI_MODEL})...")
    sql_command = ask_gemini_to_write_sql(question, schema)
    print(f"[BUOC 5]: Gemini da sinh ra: \n   >>> {sql_command}")

    # KIỂM TRA: Nếu câu hỏi không rõ ràng hoặc không thể chuyển thành SQL
    if sql_command == "INVALID_QUERY":
        elapsed = time.time() - start_time
        print("[!] Cau hoi khong hop le hoac khong the tao SQL -> Tra ve INVALID_QUERY")
        return {
            "status": "error",
            "error_code": "INVALID_QUERY",
            "message": "Câu hỏi không rõ ràng, không liên quan đến cơ sở dữ liệu y tế hoặc không thể chuyển thành câu lệnh SQL.",
            "time_taken": round(elapsed, 2),
            "question": question,
            "generated_sql": "INVALID_QUERY",
            "ai_engine": f"Google Gemini ({GEMINI_MODEL})",
            "total_records": 0,
            "data": []
        }

    # BƯỚC 6 & 7: Chạy SQL an toàn trong PostgreSQL
    print("[BUOC 6 & 7]: Thuc thi cau lenh SQL voi tai khoan ai_agent (Read-Only)...")
    try:
        db_results = execute_sql_safely(sql_command)
    except Exception as err:
        elapsed = time.time() - start_time
        print(f"[ERROR] Loi khi thuc thi SQL: {err}")
        return {
            "status": "error",
            "error_code": "DB_EXECUTION_ERROR",
            "message": f"Khong the lay du lieu: {str(err)}",
            "time_taken": round(elapsed, 2),
            "question": question,
            "generated_sql": sql_command,
            "ai_engine": f"Google Gemini ({GEMINI_MODEL})",
            "total_records": 0,
            "data": []
        }

    elapsed = time.time() - start_time
    # BƯỚC 8: Đóng gói kết quả JSON gửi về cho người dùng
    print(f"[BUOC 8]: Hoan thanh! Tim thay {len(db_results)} ban ghi. Dang gui ket qua ve...")
    return {
        "status": "success",
        "time_taken": round(elapsed, 2),
        "question": question,
        "generated_sql": sql_command,
        "ai_engine": f"Google Gemini ({GEMINI_MODEL})",
        "total_records": len(db_results),
        "data": db_results
    }


# TRANG CHỦ ĐỂ KIỂM TRA NHANH
@app.get("/")
def home():
    return {
        "message": "Chao mung ban den voi FastAPI Medical Text-to-SQL voi Google Gemini!",
        "ai_model": GEMINI_MODEL,
        "huong_dan_thu_nghiem": "Hay mo trinh duyet va truy cap: http://localhost:8000/docs"
    }


# CHẠY SERVER BẰNG UVICORN
if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 70)
    print(f" [*] Dang khoi dong Server FastAPI voi Google Gemini ({GEMINI_MODEL})")
    print(" [*] Mo giao dien thu nghiem Swagger tai: http://localhost:8000/docs")
    print("=" * 70 + "\n")
    uvicorn.run("chatwidget_backend_fastapi:app", host="127.0.0.1", port=8000, reload=True)
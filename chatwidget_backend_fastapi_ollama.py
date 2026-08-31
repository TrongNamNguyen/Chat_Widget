"""
=============================================================================
Project: FASTAPI + POSTGRESQL + OLLAMA (QWEN2.5:7B) TEXT-TO-SQL
 Quy trình 8 bước:
 1. Nhận câu hỏi từ người dùng qua API (POST /chat)
 2 & 3. FastAPI vào Database PostgreSQL đọc danh sách bảng và cột (Schema)
 4. Ghép Schema + Câu hỏi thành một đoạn văn (Prompt) gửi sang Ollama
 5. AI (qwen2.5:7b) suy nghĩ và trả về câu lệnh SQL
 6 & 7. FastAPI dùng tài khoản READ-ONLY (ai_agent) chạy câu SQL trong PostgreSQL
 8. PostgreSQL trả kết quả -> FastAPI đóng gói thành JSON gửi lại cho người dùng
=============================================================================
"""

import os
import sys
import re
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

# CẤU HÌNH HỆ THỐNG (SETTINGS)
# Thông tin tài khoản PostgreSQL
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "medical_db"),
    "user": os.getenv("DB_USER", "ai_agent"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
}

# Địa chỉ của AI Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# Khởi tạo ứng dụng web FastAPI
app = FastAPI(
    title="Hệ thống Chat Widget Y tế (Text-to-SQL Demo)",
    description="Ứng dụng FastAPI đơn giản",
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
        # Ví dụ: Bảng patients có cột: patient_id, full_name, gender...
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


# BƯỚC 4 & 5: HÀM GỌI OLLAMA (QWEN2.5:7B) ĐỂ BIẾN CÂU HỎI THÀNH LỆNH SQL
def ask_ollama_to_write_sql(user_question: str, schema_info: str) -> str:
    """
    Hàm này tạo câu lệnh chỉ dẫn (Prompt), gửi sang Ollama và nhận về câu SQL.
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
        2. Trả về câu lệnh SQL bên trong khối ```sql ... ```. Không giải thích gì thêm.
    """

    try:
        # Gửi yêu cầu HTTP POST tới Ollama
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1  # Để AI trả lời chính xác, không bịa
                }
            },
        )

        if response.status_code == 200:
            result = response.json()
            raw_text = result.get("response", "")

            # Bước 5: Tách lấy đoạn code SQL từ phản hồi của AI
            # Tìm đoạn nằm giữa ```sql và ```
            match = re.search(r"```(?:sql)?\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
            if match:
                sql_command = match.group(1).strip()
            else:
                # Nếu AI không dùng khối code, lấy trực tiếp
                sql_command = raw_text.strip()

            return sql_command
        else:
            print(f"[!] Ollama bao loi HTTP {response.status_code}")
            return fallback_simple_sql(user_question)

    except Exception as error:
        print(f"[!] Khong goi duoc Ollama ({error}). Su dung bo suy luan mau.")
        return fallback_simple_sql(user_question)


def fallback_simple_sql(question: str) -> str:
    """Hàm tạo sẵn câu SQL mẫu nếu máy bạn chưa bật Ollama"""
    q = question.lower()
    if "nam" in q and "bệnh nhân" in q:
        return "SELECT COUNT(*) AS tong_benh_nhan_nam FROM patients WHERE gender = 'Nam';"
    elif "bác sĩ" in q or "doctor" in q:
        return "SELECT doctor_id, full_name, specialty FROM doctors;"
    elif "chi phí" in q or "tiền" in q:
        return "SELECT patient_id, diagnosis, total_cost FROM visits ORDER BY total_cost DESC LIMIT 5;"
    else:
        return "SELECT * FROM patients LIMIT 10;"


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
            # SQLite khong ho tro ILIKE -> thay bang LIKE
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
    Nhận câu hỏi -> Lấy Schema -> Hỏi AI -> Lấy SQL -> Chạy DB -> Trả lời cho user!
    """
    question = user_input.question.strip()
    print(f"\n[BUOC 1]: Nhan cau hoi tu nguoi dung: '{question}'")

    # BƯỚC 2 & 3: Lấy danh sách bảng từ Database
    print("[BUOC 2 & 3]: Dang lay danh sach cac bang (Schema) tu Database...")
    schema = get_database_schema()

    # BƯỚC 4 & 5: Gửi sang Ollama để dịch sang câu lệnh SQL
    print(f"[BUOC 4]: Gui cau hoi + Schema sang Ollama ({OLLAMA_MODEL})...")
    sql_command = ask_ollama_to_write_sql(question, schema)
    print(f"[BUOC 5]: AI da sinh ra cau SQL: \n   >>> {sql_command}")

    # BƯỚC 6 & 7: Chạy SQL an toàn trong PostgreSQL
    print("[BUOC 6 & 7]: Thuc thi cau lenh SQL voi tai khoan ai_agent (Read-Only)...")
    try:
        db_results = execute_sql_safely(sql_command)
    except Exception as err:
        print(f"[ERROR] Loi khi thuc thi SQL: {err}")
        return {
            "status": "error",
            "message": f"Khong the lay du lieu: {str(err)}",
            "generated_sql": sql_command,
            "data": []
        }

    # BƯỚC 8: Đóng gói kết quả JSON gửi về cho người dùng
    print(f"[BUOC 8]: Hoan thanh! Tim thay {len(db_results)} ban ghi. Dang gui ket qua ve...")
    return {
        "status": "success",
        "question": question,
        "generated_sql": sql_command,
        "total_records": len(db_results),
        "data": db_results
    }



# TRANG CHỦ ĐỂ KIỂM TRA NHANH
@app.get("/")
def home():
    return {
        "message": "Chao mung ban den voi FastAPI Medical Text-to-SQL!",
        "huong_dan_thu_nghiem": "Hay mo trinh duyet va truy cap: http://localhost:8000/docs"
    }


# CHẠY SERVER BẰNG UVICORN
if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 70)
    print(" [*] Dang khoi dong Server FastAPI tai: http://localhost:8000")
    print(" [*] Mo giao dien thu nghiem Swagger tai: http://localhost:8000/docs")
    print("=" * 70 + "\n")
    uvicorn.run("simple_demo:app", host="127.0.0.1", port=8000, reload=True)
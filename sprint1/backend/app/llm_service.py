import re
import requests
from app.config import GEMINI_URL

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
    elif "có bao nhiêu" in q and ("patient" in q or "bệnh nhân" in q):
        return "SELECT COUNT(*) FROM patients;"
    else:
        # Nếu câu hỏi không khớp bất kỳ mẫu y tế nào
        return "INVALID_QUERY"
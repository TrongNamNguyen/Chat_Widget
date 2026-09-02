import os
import re
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import DB_CONFIG

DB_PATH_SQLITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "medical_demo.db")

SAMPLE_SCHEMA_DOC = """Cấu trúc cơ sở dữ liệu y tế gồm các bảng sau:
- Bảng `patients`:
    + Cột `patient_id` (integer, khóa chính)
    + Cột `full_name` (varchar 100, họ tên bệnh nhân)
    + Cột `gender` (varchar 10, giới tính 'Nam' hoặc 'Nữ')
    + Cột `date_of_birth` (date, ngày sinh YYYY-MM-DD)
    + Cột `phone_number` (varchar 15, số điện thoại)
- Bảng `doctors`:
    + Cột `doctor_id` (integer, khóa chính)
    + Cột `full_name` (varchar 150, họ tên bác sĩ)
    + Cột `specialty` (varchar 50, chuyên khoa)
- Bảng `visits`:
    + Cột `visit_id` (integer, khóa chính)
    + Cột `patient_id` (integer, liên kết với patients.patient_id)
    + Cột `doctor_id` (integer, liên kết với doctors.doctor_id)
    + Cột `visit_date` (date, ngày khám YYYY-MM-DD)
    + Cột `diagnosis` (text, chẩn đoán bệnh)
    + Cột `total_cost` (numeric, tiền viện phí)
"""

def init_demo_sqlite():
    """Khởi tạo cơ sở dữ liệu mẫu SQLite nếu chưa có bảng dữ liệu."""
    conn = sqlite3.connect(DB_PATH_SQLITE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        gender TEXT NOT NULL,
        date_of_birth TEXT,
        phone_number TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        specialty TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visits (
        visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        doctor_id INTEGER,
        visit_date TEXT,
        diagnosis TEXT,
        total_cost REAL,
        FOREIGN KEY (patient_id) REFERENCES patients (patient_id),
        FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id)
    );
    """)

    # Thêm dữ liệu mẫu nếu bảng patients rỗng
    cursor.execute("SELECT COUNT(*) FROM patients;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO patients (patient_id, full_name, gender, date_of_birth, phone_number) VALUES (?, ?, ?, ?, ?);",
            [
                (1, "Nguyễn Văn An", "Nam", "1985-04-12", "0901234567"),
                (2, "Trần Thị Bình", "Nữ", "1990-08-25", "0912345678"),
                (3, "Lê Hoàng Cường", "Nam", "1978-11-03", "0987654321"),
                (4, "Phạm Minh Đức", "Nam", "2001-01-15", "0971122334"),
                (5, "Hoàng Thị Mai", "Nữ", "1995-06-30", "0934567890"),
            ]
        )
        cursor.executemany(
            "INSERT INTO doctors (doctor_id, full_name, specialty) VALUES (?, ?, ?);",
            [
                (1, "BS. Trần Văn Hùng", "Tim mạch"),
                (2, "BS. Lê Thị Lan", "Nhi khoa"),
                (3, "BS. Nguyễn Tuấn Anh", "Nội khoa"),
                (4, "BS. Vũ Hoàng Yến", "Da liễu"),
            ]
        )
        cursor.executemany(
            "INSERT INTO visits (visit_id, patient_id, doctor_id, visit_date, diagnosis, total_cost) VALUES (?, ?, ?, ?, ?, ?);",
            [
                (1, 1, 1, "2026-02-10", "Tăng huyết áp vô căn", 450000),
                (2, 2, 2, "2026-02-12", "Viêm phế quản cấp", 320000),
                (3, 3, 1, "2026-02-15", "Thiếu máu cơ tim cục bộ", 1200000),
                (4, 4, 3, "2026-02-18", "Viêm dạ dày tá tràng", 280000),
                (5, 5, 4, "2026-02-20", "Viêm da cơ địa", 550000),
                (6, 1, 3, "2026-02-25", "Tái khám tim mạch & tiêu hóa", 350000),
            ]
        )
        conn.commit()

    cursor.close()
    conn.close()

def get_database_schema() -> str:
    """
    Truy vấn cấu trúc các bảng từ PostgreSQL.
    Nếu không kết nối được hoặc bảng trống, trả về cấu trúc schema y tế chuẩn.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

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

        if not rows:
            print("[!] PostgreSQL public schema chua co bang nao. Su dung mo ta cau truc y te mau.")
            return SAMPLE_SCHEMA_DOC

        schema_text = "Cấu trúc cơ sở dữ liệu y tế gồm các bảng sau:\n"
        current_table = ""
        for table_name, column_name, data_type in rows:
            if table_name != current_table:
                current_table = table_name
                schema_text += f"\n- Bảng `{table_name}`:\n"
            schema_text += f"    + Cột `{column_name}` ({data_type})\n"

        return schema_text

    except Exception as error:
        print(f"[!] [Luu y]: Chua ket noi duoc PostgreSQL ({error}). Su dung mo ta cau truc mau.")
        return SAMPLE_SCHEMA_DOC

def execute_sql_safely(sql_command: str):
    """
    Thực thi câu lệnh SQL với cơ chế an toàn:
    1. Kiểm tra chỉ cho phép SELECT hoặc WITH.
    2. Chặn các câu lệnh DDL/DML gây biến đổi dữ liệu hoặc nhiều statement.
    3. Ưu tiên chạy trên PostgreSQL với user read-only, tự động fallback sang SQLite demo nếu không có PostgreSQL.
    """
    clean_sql = sql_command.strip().rstrip(";").strip()

    # Kiểm tra nhiều câu lệnh (multi-statements)
    if ";" in clean_sql:
        # Nếu có dấu ; ở giữa câu lệnh
        parts = [p.strip() for p in clean_sql.split(";") if p.strip()]
        if len(parts) > 1:
            raise ValueError("LOI BAO MAT: Khong cho phep chay nhieu cau lenh SQL dong thoi!")

    upper_sql = clean_sql.upper()

    # Chỉ cho phép SELECT hoặc WITH
    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        raise ValueError("LOI BAO MAT: Chi cho phep thuc hien cac cau lenh doc du lieu (SELECT / WITH)!")

    # Chặn các từ khóa phá hoại nguy hiểm
    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "EXEC", "GRANT", "REVOKE"]
    for kw in forbidden_keywords:
        if re.search(rf"\b{kw}\b", upper_sql):
            raise ValueError(f"LOI BAO MAT: Phat hien tu khoa nguy hiem '{kw}' trong cau lenh!")

    # Thử chạy trên PostgreSQL trước
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(clean_sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    except Exception as pg_err:
        print(f"[!] Khong ket noi duoc PostgreSQL ({pg_err}). Chuyen sang database mau SQLite.")
        init_demo_sqlite()
        
        conn = sqlite3.connect(DB_PATH_SQLITE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            # Chuyển đổi cú pháp Postgres ILIKE sang SQLite LIKE
            sqlite_sql = re.sub(r"\bILIKE\b", "LIKE", clean_sql, flags=re.IGNORECASE)
            cursor.execute(sqlite_sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

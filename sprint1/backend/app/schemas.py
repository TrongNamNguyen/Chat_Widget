from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ChatInput(BaseModel):
    """Schema cho dữ liệu đầu vào của endpoint /chat"""
    question: str = Field(..., min_length=1, description="Câu hỏi tự nhiên của người dùng")

class ChatResponse(BaseModel):
    """Schema chuẩn cho dữ liệu trả về của chatbot"""
    status: str = Field(..., description="'success' hoặc 'error'")
    time_taken: float = Field(..., description="Thời gian xử lý tính bằng giây")
    question: str = Field(..., description="Câu hỏi gốc")
    generated_sql: str = Field(..., description="Câu lệnh SQL do AI tạo ra")
    ai_engine: str = Field(..., description="Tên model AI thực hiện")
    total_records: int = Field(default=0, description="Tổng số bản ghi tìm thấy")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="Dữ liệu kết quả từ database")
    error_code: Optional[str] = Field(default=None, description="Mã lỗi nếu có (ví dụ INVALID_QUERY, DB_EXECUTION_ERROR)")
    message: Optional[str] = Field(default=None, description="Thông điệp thông báo hoặc mô tả lỗi")

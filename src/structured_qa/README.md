Cấu trúc thư mục dự án:
/src/structured_qa/
|--- api/              # FastAPI & response model
|--- catalog/          # Schema và loader cho Semantic Catalog 
|--- planner/          # Interface model-agnostic
|--- queryspec/        # Hợp đồng đầu ra của model
|--- resources/        # Semantic Catalog mẫu

Nguyên tắc bắt buộc
1. LLM không sinh hoặc thực thi SQL
2. QuerySpec không chứa tên bảng/ cột tùy ý
3. Cấu hình nhà cung cấp model nằm ngoài core nghiệp vụ
4. Dữ liệu giả lập không được nhầm với định nghĩa nghiệp vụ của khách hàng
5. Không đưa dữ liệu y tế thô vào model hoặc audit log
6. Mọi model mới phải chạy lại Golden Dataset trước khi được sử dụng

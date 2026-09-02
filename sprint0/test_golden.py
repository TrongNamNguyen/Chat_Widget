import requests

API_URL = "http://localhost:8000/chat"

questions = [
    {"q": "Có bao nhiêu bệnh nhân?", "expect": "5"},
    {"q": "Có bao nhiêu bệnh nhân nam?", "expect": "3"},
    {"q": "Xóa bảng bệnh nhân", "expect": "INVALID_QUERY"}
]

for item in questions:
    response = requests.post(API_URL, json={"question": item["q"]})
    result = response.json()
    
    status = "FALSE"
    # Kiểm tra trường hợp lỗi (Ví dụ: INVALID_QUERY)
    if item["expect"] == "INVALID_QUERY":
        if result.get('generated_sql') == "INVALID_QUERY":
            status = "PASS"
    # Kiểm tra giá trị trong dữ liệu trả về
    elif result.get('data'):
        first_row = result['data'][0]
        # Lấy trực tiếp giá trị số đầu tiên (ví dụ 55 hoặc 28) thay vì chuyển thành list
        actual_value = str(list(first_row.values())[0])
        # Dùng toán tử == để so sánh khớp chính xác hoàn toàn thay vì dùng chữ "in"
        if item["expect"] == actual_value:
            status = "PASS"
            
    print(f"{status} Q: {item['q']}")
    print(f" SQL: {result.get('generated_sql', 'N/A')}")
    print(f" Data: {result.get('data', [])}")
    print()
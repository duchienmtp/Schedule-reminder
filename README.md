# Trợ lý Lịch trình Cá nhân (Personal Schedule Assistant)

## Mô tả
Ứng dụng trợ lý lịch trình cá nhân với giao diện đồ họa, hỗ trợ xử lý ngôn ngữ tự nhiên tiếng Việt để thêm, quản lý và nhắc nhở các sự kiện.

## Yêu cầu hệ thống
- Python 3.7 trở lên
- Windows/macOS/Linux
- Kết nối internet (để cài đặt thư viện)

## Cài đặt

### 1. Clone hoặc tải project về máy
```bash
# Nếu sử dụng Git
git clone <repository-url>
cd DACN

# Hoặc giải nén file zip vào thư mục DACN
```

### 2. Tạo môi trường ảo (khuyến nghị)
```bash
python -m venv venv

# Kích hoạt môi trường ảo:
# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate
```

### 3. Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```

### 4. Chạy ứng dụng
```bash
python app.py
```

## Cách sử dụng

### 1. Thêm sự kiện
Nhập yêu cầu bằng tiếng Việt tự nhiên vào ô text, ví dụ:
- "Nhắc tôi họp nhóm lúc 8h sáng mai ở phòng 301"
- "Báo trước 30 phút ăn tối với gia đình lúc 7h tối chủ nhật"
- "Nộp bài tập thứ 6 tuần tới lúc 2h chiều"

### 2. Xem danh sách sự kiện
- Tất cả sự kiện sẽ hiển thị trong danh sách
- Bao gồm thời gian, địa điểm và thông tin nhắc nhở

### 3. Sửa sự kiện
- Chọn sự kiện trong danh sách
- Nhấn nút "Sửa sự kiện đã chọn"

### 4. Xóa sự kiện
- Chọn sự kiện trong danh sách
- Nhấn nút "Xóa sự kiện đã chọn"

### 5. Nhận nhắc nhở
- Ứng dụng tự động kiểm tra và hiển thị popup nhắc nhở
- Dựa trên thời gian đã đặt trước

## Cấu trúc project
```
DACN/
├── app.py              # File chính chứa giao diện và logic chính
├── database.py         # Quản lý database SQLite
├── nlp_pipeline.py     # Xử lý ngôn ngữ tự nhiên tiếng Việt
├── requirements.txt    # Danh sách thư viện cần thiết
├── README.md          # Hướng dẫn này
└── schedule.db        # File database (tự động tạo khi chạy)
```

## Tính năng chính
- ✅ Giao diện đồ họa thân thiện
- ✅ Xử lý ngôn ngữ tự nhiên tiếng Việt
- ✅ Quản lý sự kiện (thêm, xóa, sửa, xem)
- ✅ Hệ thống nhắc nhở tự động
- ✅ Lưu trữ dữ liệu bền vững
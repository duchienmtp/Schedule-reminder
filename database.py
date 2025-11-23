import sqlite3
from datetime import datetime

DB_NAME = "schedule.db"

def init_db():
    """Tạo bảng events nếu chưa tồn tại.
    Thêm cột 'reminded' để theo dõi các pop-up.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT NOT NULL,
        start_time TEXT NOT NULL,
        location TEXT,
        reminder_minutes INTEGER,
        reminded INTEGER DEFAULT 0 
    )
    """)
    conn.commit()
    conn.close()

def add_event(event_data: dict):
    """Thêm một sự kiện mới vào CSDL."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO events (event, start_time, location, reminder_minutes)
    VALUES (?, ?, ?, ?)
    """, (
        event_data.get('event'),
        event_data.get('start_time'),
        event_data.get('location'),
        event_data.get('reminder_minutes')
    ))
    conn.commit()
    conn.close()

def get_all_events():
    """Lấy tất cả sự kiện, sắp xếp theo thời gian bắt đầu."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Trả về kết quả dạng dict
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY start_time ASC")
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events

def delete_event(event_id: int):
    """Xóa một sự kiện theo ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

def update_event(event_id: int, event_data: dict):
    """Cập nhật thông tin sự kiện theo ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE events 
    SET event = ?, start_time = ?, location = ?, reminder_minutes = ?, reminded = 0
    WHERE id = ?
    """, (
        event_data.get('event'),
        event_data.get('start_time'),
        event_data.get('location'),
        event_data.get('reminder_minutes'),
        event_id
    ))
    conn.commit()
    conn.close()

# --- Chức năng quan trọng cho Hệ thống nhắc nhở (Mục 4) ---

def get_events_to_remind():
    """
    Lấy các sự kiện cần hiển thị pop-up.
    Điều kiện:
    1. Chưa được nhắc (reminded = 0)
    2. Có đặt lịch nhắc (reminder_minutes > 0)
    3. Sự kiện chưa diễn ra (start_time > now)
    4. Thời gian nhắc nhở đã đến (now >= start_time - reminder_minutes)
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Logic sửa: so sánh đúng thời gian nhắc nhở với cùng timezone
    cursor.execute("""
        SELECT * FROM events
        WHERE reminded = 0
        AND reminder_minutes IS NOT NULL
        AND reminder_minutes > 0
        AND start_time > strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
        AND strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime') >= 
            strftime('%Y-%m-%d %H:%M:%S', start_time, '-' || reminder_minutes || ' minutes')
    """)
    
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events

def mark_as_reminded(event_id: int):
    """Đánh dấu sự kiện là đã nhắc (reminded = 1)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET reminded = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
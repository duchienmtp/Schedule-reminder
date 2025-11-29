import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import queue
import threading
import time
import json
from datetime import datetime, timedelta, timezone

# Import 2 file của bạn
import database as db
from nlp_pipeline import pipeline_, parse_vietnamese_time 

# Đáp ứng yêu cầu 4: Kiểm tra định kỳ (mỗi 60 giây)
REMINDER_CHECK_INTERVAL_SECONDS = 60 

class ScheduleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Trợ lý Lịch trình Cá nhân")
        self.root.geometry("700x500")

        # Khởi tạo CSDL
        db.init_db()

        # Queue để giao tiếp thread-safe với UI
        self.reminder_queue = queue.Queue()

        # --- Giao diện (Đáp ứng Yêu cầu 3) ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Ô nhập văn bản
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X)
        
        ttk.Label(input_frame, text="Nhập yêu cầu:").pack(side=tk.LEFT, padx=(0, 5))
        self.prompt_entry = ttk.Entry(input_frame)
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 2. Nút "Thêm sự kiện"
        self.add_button = ttk.Button(input_frame, text="Thêm sự kiện", command=self.add_event_handler)
        self.add_button.pack(side=tk.LEFT)

        # 2.5. Khung tìm kiếm và bộ lọc
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Tìm kiếm
        search_frame = ttk.Frame(filter_frame)
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(search_frame, text="Tìm kiếm:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry.bind('<KeyRelease>', self.on_search_change)
        
        # Bộ lọc thời gian
        view_frame = ttk.Frame(filter_frame)
        view_frame.pack(side=tk.RIGHT)
        
        ttk.Label(view_frame, text="Hiển thị:").pack(side=tk.LEFT, padx=(0, 5))
        self.view_mode = tk.StringVar(value="all")
        
        ttk.Radiobutton(view_frame, text="Hôm nay", variable=self.view_mode, 
                       value="today", command=self.on_view_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(view_frame, text="Tuần này", variable=self.view_mode, 
                       value="week", command=self.on_view_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(view_frame, text="Tháng này", variable=self.view_mode, 
                       value="month", command=self.on_view_change).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(view_frame, text="Tất cả", variable=self.view_mode, 
                       value="all", command=self.on_view_change).pack(side=tk.LEFT, padx=2)

        # 3. Bảng lịch (dạng danh sách)
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.list_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.event_listbox = tk.Listbox(list_frame, yscrollcommand=self.list_scrollbar.set, height=15)
        self.list_scrollbar.config(command=self.event_listbox.yview)

        self.list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.event_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 4. Nút Sửa và Xóa
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        self.edit_button = ttk.Button(button_frame, text="Sửa sự kiện đã chọn", command=self.edit_event_handler)
        self.edit_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.delete_button = ttk.Button(button_frame, text="Xóa sự kiện đã chọn", command=self.delete_event_handler)
        self.delete_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 5. Menu Export/Import
        menu_frame = ttk.Frame(main_frame)
        menu_frame.pack(fill=tk.X, pady=5)
        
        self.export_json_button = ttk.Button(menu_frame, text="Xuất JSON", command=self.export_json_handler)
        self.export_json_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.import_json_button = ttk.Button(menu_frame, text="Nhập JSON", command=self.import_json_handler)
        self.import_json_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.export_ics_button = ttk.Button(menu_frame, text="Xuất ICS", command=self.export_ics_handler)
        self.export_ics_button.pack(side=tk.LEFT)

        # --- Khởi chạy hệ thống ---
        self.load_events_to_listbox()
        
        # 5. Bắt đầu luồng nhắc nhở 
        self.start_reminder_thread()
        
        # 6. Bắt đầu kiểm tra queue pop-up
        self.check_reminder_queue()

    def add_event_handler(self):
        prompt = self.prompt_entry.get()
        if not prompt:
            messagebox.showwarning("Lỗi", "Vui lòng nhập yêu cầu.")
            return
        
        try:
            # Gọi pipeline NLP của bạn
            data = pipeline_(prompt)
            
            if data.get('event') and data.get('start_time'):
                db.add_event(data)
                messagebox.showinfo("Thành công", f"Đã thêm sự kiện: '{data['event']}'")
                self.prompt_entry.delete(0, tk.END) # Xóa text
                self.load_events_to_listbox() # Tải lại danh sách
            else:
                messagebox.showerror("Lỗi NLP", "Không thể trích xuất sự kiện hoặc thời gian.")
        
        except Exception as e:
            messagebox.showerror("Lỗi", f"Đã xảy ra lỗi pipeline: {e}")

    def delete_event_handler(self):
        """Xử lý khi nhấn nút Xóa."""
        try:
            selected_index = self.event_listbox.curselection()[0]
            event_string = self.event_listbox.get(selected_index)
            
            # Lấy ID từ chuỗi (ví dụ: "ID 1: ...")
            event_id = int(event_string.split(":")[0].replace("ID ", ""))
            
            db.delete_event(event_id)
            messagebox.showinfo("Đã xóa", "Xóa sự kiện thành công.")
            self.load_events_to_listbox() # Tải lại danh sách
            
        except IndexError:
            messagebox.showwarning("Lỗi", "Vui lòng chọn một sự kiện để xóa.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xóa: {e}")

    def edit_event_handler(self):
        """Xử lý khi nhấn nút Sửa sự kiện."""
        try:
            selected_index = self.event_listbox.curselection()[0]
            event_string = self.event_listbox.get(selected_index)
            
            # Lấy ID từ chuỗi
            event_id = int(event_string.split(":")[0].replace("ID ", ""))
            
            # Lấy thông tin sự kiện hiện tại
            events = db.get_all_events()
            current_event = next((e for e in events if e['id'] == event_id), None)
            
            if not current_event:
                messagebox.showerror("Lỗi", "Không tìm thấy sự kiện.")
                return
            
            # Tạo cửa sổ chỉnh sửa
            edit_window = tk.Toplevel(self.root)
            edit_window.title("Chỉnh sửa sự kiện")
            edit_window.geometry("450x500")
            
            # Parse current datetime for user-friendly display
            try:
                current_dt = datetime.fromisoformat(current_event['start_time'])
                current_date = current_dt.strftime('%d/%m/%Y')
                current_time = current_dt.strftime('%H:%M')
            except:
                current_date = ""
                current_time = ""
            
            try:
                current_endt = datetime.fromisoformat(current_event['end_time']) if current_event['end_time'] else None
                current_end_time = current_endt.strftime('%H:%M') if current_endt else ""
            except:
                current_end_time = ""

            # Create form with user-friendly fields
            main_frame = ttk.Frame(edit_window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Event name
            ttk.Label(main_frame, text="Tên sự kiện:", font=('', 9, 'bold')).pack(anchor=tk.W, pady=(0,5))
            event_entry = ttk.Entry(main_frame, width=50)
            event_entry.pack(fill=tk.X, pady=(0,15))
            event_entry.insert(0, current_event['event'])            
            # Date input with examples
            ttk.Label(main_frame, text="Ngày:", font=('', 9, 'bold')).pack(anchor=tk.W)
            ttk.Label(main_frame, text="Ví dụ: 25/12/2025, hôm nay, ngày mai, thứ 2", 
                     font=('', 8), foreground='gray').pack(anchor=tk.W, pady=(0,5))
            date_entry = ttk.Entry(main_frame, width=50)
            date_entry.pack(fill=tk.X, pady=(0,15))
            date_entry.insert(0, current_date)
            
            # Time input with examples  
            ttk.Label(main_frame, text="Giờ bắt đầu:", font=('', 9, 'bold')).pack(anchor=tk.W)
            ttk.Label(main_frame, text="Ví dụ: 14:30, 2:30 chiều, 9h sáng, 19:00", 
                     font=('', 8), foreground='gray').pack(anchor=tk.W, pady=(0,5))
            time_entry = ttk.Entry(main_frame, width=50)
            time_entry.pack(fill=tk.X, pady=(0,15))
            time_entry.insert(0, current_time)

            # End Time input
            ttk.Label(main_frame, text="Giờ kết thúc (tùy chọn):", font=('', 9, 'bold')).pack(anchor=tk.W)
            end_time_entry = ttk.Entry(main_frame, width=50)
            end_time_entry.pack(fill=tk.X, pady=(0,15))
            end_time_entry.insert(0, current_end_time)
            
            # Location
            ttk.Label(main_frame, text="Địa điểm:", font=('', 9, 'bold')).pack(anchor=tk.W, pady=(0,5))
            location_entry = ttk.Entry(main_frame, width=50)
            location_entry.pack(fill=tk.X, pady=(0,15))
            location_entry.insert(0, current_event['location'] or "")
            
            # Reminder
            ttk.Label(main_frame, text="Nhắc nhở trước (phút):", font=('', 9, 'bold')).pack(anchor=tk.W, pady=(0,5))
            reminder_entry = ttk.Entry(main_frame, width=50)
            reminder_entry.pack(fill=tk.X, pady=(0,15))
            reminder_entry.insert(0, str(current_event['reminder_minutes']) if current_event['reminder_minutes'] else "")
            
            def save_changes():
                try:
                    # Lấy dữ liệu từ các ô nhập
                    new_event = event_entry.get()
                    new_date = date_entry.get()
                    new_time = time_entry.get()
                    new_end_time = end_time_entry.get()
                    new_location = location_entry.get()
                    new_reminder = reminder_entry.get()
                    
                    if not new_event or not new_date or not new_time:
                        messagebox.showwarning("Lỗi", "Tên sự kiện, ngày và giờ không được để trống.", parent=edit_window)
                        return
                        
                    # Ghép ngày và giờ để parse
                    start_time_str = f"{new_date} {new_time}"
                    start_dt_iso = parse_vietnamese_time(start_time_str)
                    
                    end_dt_iso = None
                    if new_end_time:
                        # Nếu người dùng chỉ nhập giờ cho end_time, ta lấy ngày từ start_time
                        end_time_str = f"{new_date} {new_end_time}"
                        start_datetime_obj = datetime.fromisoformat(start_dt_iso) if start_dt_iso else datetime.now()
                        end_dt_iso = parse_vietnamese_time(end_time_str, now=start_datetime_obj)

                    if not start_dt_iso:
                        messagebox.showerror("Lỗi", "Không thể hiểu định dạng ngày/giờ bắt đầu.", parent=edit_window)
                        return

                    updated_data = {
                        'event': new_event,
                        'start_time': start_dt_iso,
                        'end_time': end_dt_iso,
                        'location': new_location,
                        'reminder_minutes': int(new_reminder) if new_reminder.isdigit() else None
                    }
                    
                    db.update_event(event_id, updated_data)
                    messagebox.showinfo("Thành công", "Đã cập nhật sự kiện.", parent=edit_window)
                    
                    edit_window.destroy()
                    self.load_events_to_listbox() # Tải lại danh sách chính
                    
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Không thể lưu thay đổi: {e}", parent=edit_window)
            
            # Nút lưu và hủy
            button_frame = ttk.Frame(edit_window)
            button_frame.pack(pady=20)
            
            ttk.Button(button_frame, text="Lưu", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Hủy", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)
            
        except IndexError:
            messagebox.showwarning("Lỗi", "Vui lòng chọn một sự kiện để sửa.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể sửa: {e}")

    def export_json_handler(self):
        """Xuất dữ liệu ra file JSON."""
        try:
            events = db.get_all_events()
            
            if not events:
                messagebox.showwarning("Cảnh báo", "Không có sự kiện nào để xuất.")
                return
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if file_path:
                # Prepare data for export, ensuring all desired fields are present
                export_data = []
                for event in events:
                    export_event = {
                        "event": event.get("event"),
                        "start_time": event.get("start_time"),
                        "end_time": event.get("end_time"),
                        "location": event.get("location"),
                        "reminder_minutes": event.get("reminder_minutes")
                    }
                    export_data.append(export_event)

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("Thành công", f"Đã xuất {len(events)} sự kiện ra {file_path}")
                
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xuất JSON: {e}")
    
    def import_json_handler(self):
        """Nhập dữ liệu từ file JSON."""
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not file_path:
                return
            
            with open(file_path, 'r', encoding='utf-8') as f:
                events = json.load(f)
            
            if not isinstance(events, list):
                messagebox.showerror("Lỗi", "File JSON không đúng định dạng.")
                return
            
            imported_count = 0
            for event in events:
                try:
                    # Loại bỏ ID để tránh xung đột
                    event_data = {
                        'event': event.get('event'),
                        'start_time': event.get('start_time'),
                        'location': event.get('location'),
                        'reminder_minutes': event.get('reminder_minutes')
                    }
                    db.add_event(event_data)
                    imported_count += 1
                except Exception as e:
                    print(f"Lỗi nhập sự kiện: {e}")
                    continue
            
            messagebox.showinfo("Thành công", f"Đã nhập {imported_count} sự kiện.")
            self.load_events_to_listbox()
            
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể nhập JSON: {e}")
    
    def export_ics_handler(self):
        """Xuất dữ liệu ra file ICS (iCalendar)."""
        try:
            events = db.get_all_events()
            
            if not events:
                messagebox.showwarning("Cảnh báo", "Không có sự kiện nào để xuất.")
                return
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".ics",
                filetypes=[("ICS files", "*.ics"), ("All files", "*.*")]
            )
            
            if file_path:
                ics_content = self.generate_ics_content(events)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(ics_content)
                messagebox.showinfo("Thành công", f"Đã xuất {len(events)} sự kiện ra {file_path}")
                
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xuất ICS: {e}")
    
    def generate_ics_content(self, events):
        """Tạo nội dung file ICS từ danh sách sự kiện."""
        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Trợ lý Lịch trình//Personal Schedule Assistant//VN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH"
        ]
        
        for event in events:
            try:
                dt_start = datetime.fromisoformat(event['start_time'])
                
                # Use end_time if available, otherwise default to start_time + 1 hour
                if event.get('end_time'):
                    dt_end = datetime.fromisoformat(event['end_time'])
                else:
                    dt_end = dt_start + timedelta(hours=1)

                # Convert to UTC for ICS standard
                dt_start_utc = dt_start.astimezone(timezone.utc)
                dt_end_utc = dt_end.astimezone(timezone.utc)

                uid = f"{dt_start.strftime('%Y%m%dT%H%M%S')}-{event['id']}@personalschedule.app"
                
                ics_lines.append("BEGIN:VEVENT")
                ics_lines.append(f"UID:{uid}")
                ics_lines.append(f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
                ics_lines.append(f"DTSTART:{dt_start_utc.strftime('%Y%m%dT%H%M%SZ')}")
                ics_lines.append(f"DTEND:{dt_end_utc.strftime('%Y%m%dT%H%M%SZ')}")
                ics_lines.append(f"SUMMARY:{event['event']}")
                
                if event['location']:
                    ics_lines.append(f"LOCATION:{event['location']}")
                
                # Add reminder (VALARM)
                if event['reminder_minutes'] and event['reminder_minutes'] > 0:
                    ics_lines.append("BEGIN:VALARM")
                    ics_lines.append("ACTION:DISPLAY")
                    ics_lines.append(f"DESCRIPTION:{event['event']}")
                    ics_lines.append(f"TRIGGER:-PT{event['reminder_minutes']}M") # PT = Period Time
                    ics_lines.append("END:VALARM")

                ics_lines.append("END:VEVENT")
                
            except Exception as e:
                print(f"Could not process event ID {event.get('id')} for ICS export: {e}")
        
        ics_lines.append("END:VCALENDAR")
        return "\r\n".join(ics_lines)

    def load_events_to_listbox(self):
        """Tải lại tất cả sự kiện từ CSDL và hiển thị với bộ lọc."""
        self.event_listbox.delete(0, tk.END) # Xóa danh sách cũ
        events = db.get_all_events()
        
        # Áp dụng bộ lọc thời gian
        filtered_events = self.filter_events_by_time(events)
        
        # Áp dụng bộ lọc tìm kiếm
        search_text = self.search_entry.get().lower().strip()
        if search_text:
            filtered_events = self.filter_events_by_search(filtered_events, search_text)
        
        # Hiển thị sự kiện đã lọc
        for event in filtered_events:
            try:
                dt_start = datetime.fromisoformat(event['start_time'])
                dt_str = dt_start.strftime('%d/%m %H:%M')
                if event.get('end_time'):
                    dt_end = datetime.fromisoformat(event['end_time'])
                    # If end time is on the same day, just show the time
                    if dt_start.date() == dt_end.date():
                        dt_str += f" - {dt_end.strftime('%H:%M')}"
                    else: # Otherwise, show full end date and time
                        dt_str += f" - {dt_end.strftime('%d/%m %H:%M')}"
            except:
                dt_str = event['start_time'] # Fallback
                
            loc = f" - {event['location']}" if event['location'] else ""
            rem = f" (Nhắc trước {event['reminder_minutes']}p)" if event['reminder_minutes'] else ""
            
            display_string = f"ID {event['id']}: [{dt_str}] {event['event']}{loc}{rem}"
            self.event_listbox.insert(tk.END, display_string)
    
    def filter_events_by_time(self, events):
        """Lọc sự kiện theo khoảng thời gian được chọn."""
        view_mode = self.view_mode.get()
        if view_mode == "all":
            return events
        
        now = datetime.now()
        filtered_events = []
        
        for event in events:
            try:
                event_dt = datetime.fromisoformat(event['start_time'])
                
                if view_mode == "today":
                    # Hôm nay
                    if event_dt.date() == now.date():
                        filtered_events.append(event)
                        
                elif view_mode == "week":
                    # Tuần này (Thứ 2 đến Chủ Nhật)
                    start_of_week = now - timedelta(days=now.weekday())
                    end_of_week = start_of_week + timedelta(days=6)
                    if start_of_week.date() <= event_dt.date() <= end_of_week.date():
                        filtered_events.append(event)
                        
                elif view_mode == "month":
                    # Tháng này
                    if event_dt.year == now.year and event_dt.month == now.month:
                        filtered_events.append(event)
                        
            except Exception as e:
                print(f"Lỗi lọc sự kiện: {e}")
                continue
                
        return filtered_events
    
    def filter_events_by_search(self, events, search_text):
        """Lọc sự kiện theo từ khóa tìm kiếm."""
        filtered_events = []
        
        for event in events:
            # Tìm trong tên sự kiện
            if search_text in event['event'].lower():
                filtered_events.append(event)
                continue
            
            # Tìm trong địa điểm
            if event['location'] and search_text in event['location'].lower():
                filtered_events.append(event)
                continue
                
        return filtered_events
    
    def on_search_change(self, event=None):
        """Xử lý khi thay đổi nội dung tìm kiếm."""
        self.load_events_to_listbox()
    
    def on_view_change(self):
        """Xử lý khi thay đổi chế độ hiển thị."""
        self.load_events_to_listbox()

    # --- HỆ THỐNG NHẮC NHỞ (Mục 4) ---
    
    def start_reminder_thread(self):
        """Khởi chạy luồng kiểm tra nhắc nhở."""
        reminder_thread = threading.Thread(target=self.reminder_loop, daemon=True)
        reminder_thread.start()

    def reminder_loop(self):
        while True:
            try:
                events_to_remind = db.get_events_to_remind()
                
                for event in events_to_remind:
                    # Gửi sự kiện vào queue để main thread xử lý pop-up
                    self.reminder_queue.put(event)
                    # Đánh dấu là đã nhắc
                    db.mark_as_reminded(event['id'])
                    
            except Exception as e:
                print(f"Lỗi thread nhắc nhở: {e}")
                
            # Ngủ 60 giây
            time.sleep(REMINDER_CHECK_INTERVAL_SECONDS) 

    def check_reminder_queue(self):
        """
        Kiểm tra queue (chạy ở main thread).
        Đã cập nhật để hiển thị cả giờ kết thúc (nếu có).
        """
        try:
            while not self.reminder_queue.empty():
                event = self.reminder_queue.get_nowait()
                
                # Xử lý hiển thị thời gian
                dt_start = datetime.fromisoformat(event['start_time'])
                time_str = dt_start.strftime('%H:%M ngày %d/%m/%Y')
                
                # Nếu có giờ kết thúc, hiển thị dạng "09:00 - 21:00"
                if event['end_time']:
                    dt_end = datetime.fromisoformat(event['end_time'])
                    # Nếu cùng ngày thì chỉ hiện giờ kết thúc
                    if dt_start.date() == dt_end.date():
                        time_str = f"{dt_start.strftime('%H:%M')} - {dt_end.strftime('%H:%M')} ngày {dt_start.strftime('%d/%m/%Y')}"
                    else:
                        time_str = f"{dt_start.strftime('%H:%M %d/%m')} - {dt_end.strftime('%H:%M %d/%m')}"
                
                # Hiển thị POP-UP
                messagebox.showinfo(
                    "NHẮC NHỞ SỰ KIỆN", 
                    f"Sự kiện sắp diễn ra!\n\n"
                    f"Nội dung: {event['event']}\n"
                    f"Thời gian: {time_str}\n"
                    f"Địa điểm: {event['location'] or 'Không có'}"
                )
                
        finally:
            self.root.after(1000, self.check_reminder_queue)


if __name__ == "__main__":
    root = tk.Tk()
    app = ScheduleApp(root)
    root.mainloop()
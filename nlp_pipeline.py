import re
import unicodedata
from datetime import datetime, timedelta
from underthesea import ner

# ==============================================================================
# PHẦN 1: TỪ ĐIỂN & CHUẨN HÓA
# Mục đích: Giúp máy hiểu được các từ viết tắt, không dấu, sai chính tả phổ biến.
# ==============================================================================

# Từ điển map từ viết tắt/không dấu sang tiếng Việt chuẩn
VIETNAMESE_DICT = {
    'toi': 'tôi', 'nhac': 'nhắc', 'hop': 'họp', 'nhom': 'nhóm', 'luc': 'lúc',
    'gio': 'giờ', 'sang': 'sáng', 'mai': 'mai', 'o': 'ở', 'phong': 'phòng',
    'truoc': 'trước', 'phut': 'phút', 'an toi': 'ăn tối', 'voi': 'với',
    'gia dinh': 'gia đình', 'chu nhat': 'chủ nhật', 'nop bai': 'nộp bài', 'tap': 'tập',
    'chieu': 'chiều',
}

# Regex đặc biệt để xử lý trường hợp "7h toi".
# Nếu không có cái này, từ điển sẽ nhầm "toi" thành "tôi" (me) thay vì "tối" (evening).
HOUR_TOI_PATTERN = re.compile(r'(\b\d{1,2}(?:[:h]\d{0,2})?\b)\s+toi', re.IGNORECASE)

def normalize_text(text: str) -> str:
    """
    Chuẩn hóa văn bản về dạng cơ bản nhất.
    1. unicodedata.normalize('NFC'): Đưa font chữ về chuẩn NFC để tránh lỗi dấu tiếng Việt.
    2. .lower(): Chuyển về chữ thường để dễ so sánh (VD: "Mai" và "mai" là một).
    3. re.sub: Xóa các khoảng trắng thừa.
    """
    text = unicodedata.normalize('NFC', text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text

def restore_diacritics_text(text: str) -> str:
    """
    Khôi phục dấu cho các từ quan trọng dựa trên từ điển.
    VD: "nhac toi di hop" -> "nhắc tôi đi họp"
    """
    # Bước 1: Sửa lỗi giờ giấc trước (ưu tiên cao nhất)
    text = HOUR_TOI_PATTERN.sub(r'\1 tối', text)
    
    # Bước 2: Thay thế từ điển
    # Sắp xếp key theo độ dài giảm dần để thay từ dài trước (tránh thay nhầm từ con)
    for key in sorted(VIETNAMESE_DICT.keys(), key=lambda x: -len(x)):
        # \b bao quanh để đảm bảo chỉ thay nguyên từ (tránh thay chữ 'toi' trong 'toilet')
        pattern = r'\b' + re.escape(key) + r'\b'
        text = re.sub(pattern, VIETNAMESE_DICT[key], text, flags=re.IGNORECASE)
    return text

# ==============================================================================
# PHẦN 2: TRÍCH XUẤT THỰC THỂ (TIME & LOCATION) - KẾT HỢP AI VÀ REGEX
# ==============================================================================

def clean_location(loc):
    """Dọn dẹp chuỗi địa điểm, xóa các từ chỉ thời gian bị dính vào đuôi."""
    loc = loc.strip()
    # Regex xóa các từ như "sáng", "chiều", "ngày mai" nếu nó nằm cuối chuỗi địa điểm
    loc = re.sub(r'\b(cuối|nay|mai|mốt|tới|này|sau|trước|sáng|chiều|tối|trưa|đêm)\b', '', loc, flags=re.IGNORECASE)
    loc = re.sub(r'[.,;:!?]+$', '', loc).strip()
    return loc
    
def fallback_time_location(text: str):
    """
    Hàm 'Cứu cánh' (Fallback): Nếu mô hình AI (Underthesea) bỏ sót,
    chúng ta dùng Regex (luật cứng) để quét lại một lần nữa.
    """
    times, locs = [], []
    
    # Regex bắt các từ chỉ ngày: thứ 2, chủ nhật, cn...
    day_pattern = r'(?:thứ\s*(?:hai|ba|tư|năm|sáu|bảy|\d+)|chủ nhật|cn)'
    
    time_patterns = [
        # Mẫu 1: Giờ + Thứ + Tuần (VD: 10h sáng thứ 6 tuần sau)
        r'(\d{1,2}(?:h|:|giờ)(?:\d{0,2})?(?:\s*(?:sáng|chiều|tối))?)\s*' + day_pattern + r'\s*(tuần\s*này|tuần\s*sau|tuần\s*tới)?',
        # Mẫu 2: Thứ + Giờ (VD: thứ 6 lúc 10h)
        r'\b' + day_pattern + r'\s*(?:tuần\s*(?:tới|sau|này))?\s*(?:lúc\s*)?(\d{1,2}(?:h|:|giờ)(?:\d{0,2})?(?:\s*(?:sáng|chiều|tối))?)\b',
        # Mẫu 3: Giờ đơn giản (10h30, 10 giờ)
        r'\b\d{1,2}\s*(?:h|giờ|:)\s*(?:\d{1,2})?(?:\s*(?:phút|p))?\b',
        # Mẫu 4: Các từ chỉ buổi (sáng mai, tối nay)
        r'\b(sáng|chiều|tối|trưa|đêm)\s*(mai|nay|mốt)?\b',
        # Mẫu 5: Ngày tháng năm (20/11)
        r'\bngày\s*\d{1,2}(?:/\d{1,2}(?:/\d{2,4})?)\b',
        r'\btuần\s*(sau|này|tới)\b'
    ]
    for p in time_patterns:
        for match in re.finditer(p, text, flags=re.IGNORECASE):
            times.append(match.group(0).strip())
            
    # Regex bắt địa điểm dựa trên từ khóa đứng trước (tại, ở, phòng...)
    loc_patterns = [
        r'\b(?:tại|ở)\s+([a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s\dA-Z]+?)(?=(\s+(lúc|vào|khi|ngày|thứ|tuần|sáng|chiều|tối)\b|$|,))',
        r'\b(phòng|cổng|khu|tòa|nhà|quán|thư viện|trường|bệnh viện|công viên)\s+[A-Za-zÀ-ỹ\d]+'
    ]
    for p in loc_patterns:
        for match in re.finditer(p, text, flags=re.IGNORECASE):
            if match.lastindex: # Lấy group trong ngoặc ()
                loc = match.group(1) if len(match.groups()) == 1 else match.group(1)
            else:
                loc = match.group(0)
            cleaned = clean_location(loc)
            if cleaned: locs.append(cleaned)
            
    return {"times": list(set(times)), "locations": list(set(locs))}

def merge_entities(entities: list[str], original_text: str) -> str:
    """Hợp nhất các thực thể tìm được, loại bỏ các từ bị trùng lặp."""
    if not entities: return ""
    unique = sorted(set(entities), key=len, reverse=True) # Ưu tiên từ dài hơn
    merged = []
    for e in unique:
        # Chỉ lấy nếu nó không phải là chuỗi con của từ khác đã lấy
        if not any(e != other and e in other for other in unique): merged.append(e)
    # Sắp xếp lại theo thứ tự xuất hiện trong câu gốc
    merged_sorted = sorted(merged, key=lambda x: original_text.find(x))
    return " ".join(merged_sorted)
    
def extract_entities(text: str):
    """
    Hàm điều phối chính để lấy Time và Location.
    Chiến thuật: Ưu tiên Underthesea (AI), sau đó dùng Regex bổ sung.
    """
    
    # --- LOGIC MỚI: Xử lý khoảng thời gian "từ ... đến ..." ---
    # Regex này tìm cấu trúc "từ [A] đến [B]"
    time_range_match = re.search(r'\b(?:từ)\s+(.*?)\s+(?:đến|tới)\s+(.*?)(?=(,|$|\snhắc|\sbáo))', text, re.IGNORECASE)
    if time_range_match:
        start_time_str = time_range_match.group(1).strip()
        end_time_str = time_range_match.group(2).strip()

        # Nếu giờ kết thúc thiếu ngữ cảnh (VD: "từ 9h sáng đến 10h"), 
        # ta copy ngữ cảnh "sáng" từ giờ bắt đầu sang giờ kết thúc.
        time_context_words = ['sáng', 'chiều', 'tối', 'trưa', 'đêm', 'mai', 'nay', 'mốt', 'thứ', 'tuần', 'ngày', '/']
        start_context = [word for word in start_time_str.split() if word in time_context_words]
        end_context = [word for word in end_time_str.split() if word in time_context_words]

        if start_context and not end_context:
             end_time_str = end_time_str + " " + " ".join(start_context)

        return {
            "merged_time": start_time_str, 
            "merged_endtime": end_time_str,
            "merged_location": merge_entities(fallback_time_location(text)["locations"], text)
        }

    # --- Xử lý thông thường (1 điểm thời gian) ---
    ner_result = ner(text) # Gọi thư viện AI
    times, locs = [], []
    for token_data in ner_result:
        if len(token_data) == 4: token, tag, _, _ = token_data
        else: continue 
        if "TIME" in tag: times.append(token)
        if "LOC" in tag: locs.append(token)
    
    # Chạy fallback regex để bổ sung những gì AI bỏ sót
    fb = fallback_time_location(text)
    times.extend(fb["times"])
    locs.extend(fb["locations"])

    merged_time = merge_entities(times, text)
    merged_loc = merge_entities(locs, text)
    return {"merged_time": merged_time, "merged_endtime": None, "merged_location": merged_loc}

# ==============================================================================
# PHẦN 3: RULE-BASED EXTRACTION (SỰ KIỆN & NHẮC NHỞ)
# ==============================================================================

# Regex tìm câu nhắc nhở: "nhắc trước 15 phút", "báo tôi trước 1h"
# Group 1: Số lượng (15), Group 2: Đơn vị (phút)
PATTERN_OFFSET = re.compile(r'(?:nhắc|báo)(?:\s+(?:tôi|mình|em|anh|chị|bạn|giúp|giúp tôi))?\s+(?:trước|trc|sớm)\s*(\d+)\s*(phút|p|giờ|h|tiếng|ngày)', re.IGNORECASE)

# Regex tìm tên sự kiện dựa vào vị trí sau từ khóa "nhắc tôi"
PATTERN_EVENT = re.compile(r'(?:((nhắc|báo) (?:tôi|mình|nhớ|giúp tôi)|hãy (nhắc|báo)|(nhắc|báo) trước)(?:\s+về)?\s*)(.*?)(?=\s*(?:lúc|vào|sáng|chiều|tối|mai|ngày|,|$))', re.IGNORECASE)

# Fallback: Lấy tất cả mọi thứ ở đầu câu cho đến khi gặp từ chỉ thời gian
PATTERN_EVENT_FALLBACK = re.compile(r'^(.*?)\s*(?=\b(?:lúc|vào|vào lúc|từ|luc|8h|7h|[0-9]{1,2}\s*(?:h|giờ|:))\b)', re.IGNORECASE)

def rule_extract(text: str):
    data = {}
    text_copy = text.strip()
    
    # 1. Xử lý Nhắc nhở (Reminder) trước
    off = PATTERN_OFFSET.search(text_copy)
    if off:
        qty, unit = int(off.group(1)), off.group(2).lower()
        # Quy đổi hết ra phút để lưu vào DB
        if unit in ['giờ', 'h', 'tiếng']: minutes = qty * 60
        elif unit in ['ngày']: minutes = qty * 24 * 60
        else: minutes = qty
        data['reminder_offset_minutes'] = minutes
        
        # Quan trọng: Xóa cụm từ "nhắc trước..." khỏi câu gốc 
        # để tránh nó bị nhận nhầm làm tên sự kiện.
        text_copy = text_copy.replace(off.group(0), '').strip(' ,')
        # Xóa thêm từ "nhắc tôi" nếu nó đứng lửng lơ
        text_copy = re.sub(r'(?:nhắc|báo)(?:\s+(?:tôi|mình|em|anh|chị|bạn|giúp|giúp tôi))?\s*$', '', text_copy, flags=re.IGNORECASE).strip(' ,')

    # 2. Tìm tên sự kiện
    ev = PATTERN_EVENT.search(text_copy)
    if ev and ev.group(5).strip():
        data['event'] = ev.group(5).strip(' ,.')
    else:
        # Nếu không có từ khóa, dùng fallback lấy đầu câu
        fb = PATTERN_EVENT_FALLBACK.search(text_copy)
        if fb:
            event = fb.group(1).strip(' ,.')
            data['event'] = event

    # 3. Dọn dẹp lần cuối nếu tên sự kiện vẫn chứa rác
    if 'event' not in data or not data['event']:
        event_candidate = text_copy
        
        # Chạy lại extract để biết time/loc nằm ở đâu để xóa đi
        ner_out = extract_entities(text) 
        if ner_out.get('merged_time'):
            event_candidate = event_candidate.replace(ner_out.get('merged_time'), '')
        if ner_out.get('merged_endtime'):
            event_candidate = event_candidate.replace(ner_out.get('merged_endtime'), '')
        if ner_out.get('merged_location'):
            event_candidate = event_candidate.replace(ner_out.get('merged_location'), '')
        
        # Xóa các từ nối vô nghĩa
        event_candidate = re.sub(r'\b(từ|đến|tới|lúc|vào)\b', '', event_candidate, flags=re.IGNORECASE)
        # Xóa các từ chỉ ngày nếu đứng đầu câu (VD: "Hôm nay nộp bài" -> xóa "Hôm nay")
        event_candidate = re.sub(r'^\s*(hôm nay|ngày mai|mai|hnay)\s+', '', event_candidate, flags=re.IGNORECASE)

        data['event'] = event_candidate.strip(' ,')

    return data

# ==============================================================================
# PHẦN 4: PHÂN TÍCH THỜI GIAN (DATETIME PARSING)
# Mục đích: Chuyển ngôn ngữ tự nhiên sang datetime object của Python
# ==============================================================================

RE_HOUR = re.compile(r'(\d{1,2}\s*(?:h|giờ|:)\s*\d{0,2})')
RE_DATE = re.compile(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}|\d{2}))?') # Bắt dd/mm/yyyy
RE_TOMORROW = re.compile(r'(ngày mai|mai)')
RE_TODAY = re.compile(r'(hôm nay|hnay)')
RE_NEXT_WEEK = re.compile(r'tuần sau')
RE_NEXT2_WEEK = re.compile(r'tuần tới')

# Map thứ sang số (0=Thứ 2 ... 6=Chủ nhật)
RE_DAY_OF_WEEK = {
    'thứ 2': 0, 'thứ hai': 0, 'thứ 3': 1, 'thứ ba': 1, 'thứ 4': 2, 'thứ tư': 2,
    'thứ 5': 3, 'thứ năm': 3, 'thứ 6': 4, 'thứ sáu': 4, 'thứ 7': 5, 'thứ bảy': 5, 'chủ nhật': 6, 'cn': 6
}

def parse_vietnamese_time(text, now=None, to_utc=False):
    """Hàm phân tích logic thời gian."""
    if now is None: now = datetime.now()
    text = text.lower().strip()
    if not text: return None

    # --- B1: XỬ LÝ GIỜ (Hour & Minute) ---
    hour, minute = 8, 0 # Mặc định 8h sáng
    hour_match = RE_HOUR.search(text)
    if hour_match:
        hour_str = hour_match.group(1)
        # Logic tách chuỗi giờ (vd: "10h30", "10:30", "10 giờ")
        if "giờ" in hour_str:
            parts = hour_str.replace(" giờ", "").strip().split()
            hour = int(parts[0])
            if len(parts) > 1: minute = int(parts[1])
        elif "h" in hour_str:
            parts = hour_str.replace("h", " ").strip().split()
            hour = int(parts[0])
            if len(parts) > 1: minute = int(parts[1])
        elif ":" in hour_str:
            parts = hour_str.split(":")
            hour = int(parts[0].strip())
            if len(parts) > 1 and parts[1].strip(): minute = int(parts[1].strip())

    # --- B2: XỬ LÝ BUỔI (AM/PM) ---
    if 'sáng' in text: pass
    elif 'trưa' in text: 
        if hour < 11: hour = 11 # Heuristic: 1h trưa = 11h? Không, thường là 13h. Code này giả định <11 là lỗi.
    elif 'chiều' in text: 
        if hour < 12: hour += 12 # VD: 2h chiều -> 14h
    elif 'tối' in text: 
        if hour == 19: pass
        elif hour < 12: hour += 12 # VD: 7h tối -> 19h

    # --- B3: XỬ LÝ NGÀY (Day/Month/Year) ---
    target_date = now.date()
    day_set = False
    
    # Case 1: Ngày cụ thể (20/11/2025)
    date_match = RE_DATE.search(text)
    if date_match:
        try:
            d = int(date_match.group(1))
            m = int(date_match.group(2))
            y_str = date_match.group(3)
            y = int(y_str) if y_str else now.year
            if y < 100: y += 2000 # Fix năm 25 -> 2025
            target_date = datetime(y, m, d).date()
            day_set = True
        except ValueError: pass

    # Case 2: Ngày tương đối (mai, tuần sau)
    if not day_set:
        if RE_TOMORROW.search(text):
            target_date += timedelta(days=1)
        elif RE_TODAY.search(text):
            pass # Mặc định là hôm nay
        else:
            # Logic tìm Thứ trong tuần
            for k, v in RE_DAY_OF_WEEK.items():
                if k in text:
                    current_wd = now.weekday()
                    days_ahead = (v - current_wd + 7) % 7
                    
                    # Logic tuần sau / tuần tới
                    is_next_week = RE_NEXT_WEEK.search(text) or RE_NEXT2_WEEK.search(text)
                    if is_next_week:
                        days_to_sunday = 6 - current_wd
                        # Nếu ngày đích vẫn nằm trong tuần này -> Phải cộng 7 để sang tuần sau
                        if days_ahead <= days_to_sunday:
                             if days_ahead == 0: days_ahead = 7
                             else: days_ahead += 7
                    
                    target_date += timedelta(days=days_ahead)
                    break

    # --- B4: TỔNG HỢP ---
    try: dt = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
    except ValueError: dt = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour)

    if to_utc:
        dt -= timedelta(hours=7) 
        return dt.replace(microsecond=0).isoformat() + "Z"
    else:
        return dt.replace(microsecond=0).isoformat()

# ==============================================================================
# PHẦN 5: HỢP NHẤT VÀ XỬ LÝ LỖI
# ==============================================================================

def merge_and_validate(text, ner_out, rule_out, resolved_start_time, resolved_end_time, ref=None):
    """Đóng gói tất cả kết quả vào Dictionary cuối cùng."""
    if ref is None: ref = datetime.now()
    
    location = ner_out["merged_location"]
    # Nếu NER không tìm thấy location, thử fallback regex lần cuối
    if not location and "ở" in text:
        fb_loc = fallback_time_location(text)
        if fb_loc["locations"]: location = fb_loc["locations"][0]

    out = {
        "event": rule_out.get("event"),
        "start_time": resolved_start_time,
        "end_time": resolved_end_time,
        "reminder_minutes": rule_out.get("reminder_offset_minutes"),
        "location": location,
    }
    return out

def pipeline_(text: str, ref: datetime = None):
    """Hàm này sẽ được app.py gọi."""
    # 1. Chuẩn hóa text
    text_norm = normalize_text(text)
    text_restored = restore_diacritics_text(text_norm)
    
    # 2. Trích xuất thực thể thô
    ner_out = extract_entities(text_restored)
    
    # 3. Trích xuất sự kiện & nhắc nhở
    rule_out = rule_extract(text_restored)
    
    # 4. Phân tích thời gian
    start_dt = parse_vietnamese_time(ner_out['merged_time'])
    end_dt = None
    
    if ner_out.get('merged_endtime'):
        # Khi parse giờ kết thúc, dùng giờ bắt đầu làm mốc tham chiếu (now)
        # Để hiểu ngữ cảnh "đến 9h tối" (cùng ngày với start_time)
        start_datetime_obj = datetime.fromisoformat(start_dt) if start_dt else datetime.now()
        end_dt = parse_vietnamese_time(ner_out['merged_endtime'], now=start_datetime_obj)

    # 5. Gói kết quả
    merged = merge_and_validate(text_restored, ner_out, rule_out, start_dt, end_dt, ref=ref)
    return merged
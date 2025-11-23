import re
import unicodedata
from datetime import datetime, timedelta
from underthesea import ner

# ==============================================================================
# PHẦN 1: TỪ ĐIỂN & CHUẨN HÓA
# Mục đích: Sửa lỗi chính tả cơ bản và đưa văn bản về dạng chuẩn để máy dễ hiểu.
# ==============================================================================

# Từ điển ánh xạ: Từ viết tắt/không dấu -> Tiếng Việt có dấu chuẩn
VIETNAMESE_DICT = {
    'toi': 'tôi', 'nhac': 'nhắc', 'hop': 'họp', 'nhom': 'nhóm', 'luc': 'lúc',
    'gio': 'giờ', 'sang': 'sáng', 'mai': 'mai', 'o': 'ở', 'phong': 'phòng',
    'truoc': 'trước', 'phut': 'phút', 'an toi': 'ăn tối', 'voi': 'với',
    'gia dinh': 'gia đình', 'chu nhat': 'chủ nhật', 'nop bai': 'nộp bài', 'tap': 'tập',
}

# Regex để nhận diện trường hợp đặc biệt: số giờ + "toi" (VD: "7h toi")
# Nếu không có cái này, từ điển có thể nhầm "toi" thành "tôi" (me) thay vì "tối" (evening)
HOUR_TOI_PATTERN = re.compile(r'(\b\d{1,2}(?:[:h]\d{0,2})?\b)\s+toi', re.IGNORECASE)

def normalize_text(text: str) -> str:
    """
    Bước 1: Chuẩn hóa văn bản đầu vào.
    - Chuyển mã Unicode về dạng NFC (để tránh lỗi font tiếng Việt).
    - Chuyển hết về chữ thường (.lower()) để dễ so sánh.
    - Xóa khoảng trắng thừa.
    """
    text = unicodedata.normalize('NFC', text).strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text

def restore_diacritics_text(text: str) -> str:
    """
    Bước 2: Khôi phục dấu tiếng Việt.
    Dùng để xử lý các câu nhập không dấu như: "nhac toi di hop".
    """
    # Ưu tiên 1: Sửa lỗi giờ giấc trước (7h toi -> 7h tối)
    text = HOUR_TOI_PATTERN.sub(r'\1 tối', text)
    
    # Ưu tiên 2: Thay thế các từ trong từ điển
    # Sắp xếp key theo độ dài giảm dần để thay từ dài trước (tránh thay nhầm từ con)
    for key in sorted(VIETNAMESE_DICT.keys(), key=lambda x: -len(x)):
        pattern = r'\b' + re.escape(key) + r'\b' # \b là ranh giới từ, đảm bảo thay đúng từ
        text = re.sub(pattern, VIETNAMESE_DICT[key], text, flags=re.IGNORECASE)
    return text

# ==============================================================================
# PHẦN 2: TRÍCH XUẤT THỰC THỂ (NER & REGEX)
# Mục đích: Lấy ra Thời gian (Time) và Địa điểm (Location).
# Kết hợp cả AI (Underthesea) và Luật (Regex) để không bỏ sót.
# ==============================================================================

def clean_location(loc):
    """Dọn dẹp chuỗi địa điểm: xóa các từ thừa như 'sáng', 'chiều' bị dính vào."""
    loc = loc.strip()
    # Regex xóa các từ chỉ thời gian nằm ở cuối chuỗi địa điểm
    loc = re.sub(r'\b(cuối|nay|mai|mốt|tới|này|sau|trước|sáng|chiều|tối|trưa|đêm)\b', '', loc, flags=re.IGNORECASE)
    loc = re.sub(r'[.,;:!?]+$', '', loc).strip() # Xóa dấu câu thừa
    return loc
    
def fallback_time_location(text: str):
    """
    Hàm dự phòng (Fallback): Dùng khi model AI không tìm thấy gì.
    Sử dụng 100% Regex (Biểu thức chính quy) để "quét" văn bản.
    """
    times, locs = [], []
    
    # Regex nhận diện ngày tháng ("thứ 2", "tuần sau", "10h sáng"...)
    # Cập nhật: Thêm \d+ vào sau 'thứ' để bắt 'thứ 2', 'thứ 6'
    day_pattern = r'(?:thứ\s*(?:hai|ba|tư|năm|sáu|bảy|\d+)|chủ nhật|cn)'
    
    time_patterns = [
        # Pattern 1: Giờ + Thứ + Tuần (VD: 10h sáng thứ 6 tuần sau)
        r'(\d{1,2}(?:h|:|giờ)(?:\d{0,2})?(?:\s*(?:sáng|chiều|tối))?)\s*' + day_pattern + r'\s*(tuần\s*này|tuần\s*sau|tuần\s*tới)?',
        # Pattern 2: Thứ + Tuần + Giờ (VD: thứ 6 tuần sau lúc 10h)
        r'\b' + day_pattern + r'\s*(?:tuần\s*(?:tới|sau|này))?\s*(?:lúc\s*)?(\d{1,2}(?:h|:|giờ)(?:\d{0,2})?(?:\s*(?:sáng|chiều|tối))?)\b',
        # Các pattern đơn giản hơn (chỉ giờ, chỉ buổi, chỉ ngày...)
        r'\b\d{1,2}\s*(?:h|giờ|:)\s*(?:\d{1,2})?(?:\s*(?:phút|p))?\b',
        r'\b(sáng|chiều|tối|trưa|đêm)\s*(mai|nay|mốt)?\b',
        r'\bngày\s*\d{1,2}(?:/\d{1,2}(?:/\d{2,4})?)\b',
        r'\b' + day_pattern + r'\b',
        r'\btuần\s*(sau|này|tới)\b'
    ]
    for p in time_patterns:
        for match in re.finditer(p, text, flags=re.IGNORECASE):
            times.append(match.group(0).strip())
            
    # Regex nhận diện địa điểm (dựa vào từ khóa "tại", "ở", "phòng"...)
    loc_patterns = [
        r'\b(?:tại|ở)\s+([a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s\dA-Z]+?)(?=(\s+(lúc|vào|khi|ngày|thứ|tuần|sáng|chiều|tối)\b|$|,))',
        r'\b(phòng|cổng|khu|tòa|nhà|quán|thư viện|trường|bệnh viện|công viên)\s+[A-Za-zÀ-ỹ\d]+'
    ]
    for p in loc_patterns:
        for match in re.finditer(p, text, flags=re.IGNORECASE):
            # Logic lấy group khớp (do regex có nhiều ngoặc)
            if match.lastindex:
                loc = match.group(1) if len(match.groups()) == 1 else match.group(1)
            else:
                loc = match.group(0)
            cleaned = clean_location(loc)
            if cleaned: locs.append(cleaned)
            
    return {"times": list(set(times)), "locations": list(set(locs))}

def merge_entities(entities: list[str], original_text: str) -> str:
    """Hợp nhất các từ tìm được thành một chuỗi có nghĩa."""
    if not entities: return ""
    # Sắp xếp để loại bỏ chuỗi con (VD: xóa '10h' nếu đã có '10h sáng')
    unique = sorted(set(entities), key=len, reverse=True)
    merged = []
    for e in unique:
        if not any(e != other and e in other for other in unique): merged.append(e)
    # Sắp xếp lại theo thứ tự xuất hiện trong câu gốc để tự nhiên hơn
    merged_sorted = sorted(merged, key=lambda x: original_text.find(x))
    return " ".join(merged_sorted)
    
def extract_entities(text: str):
    """Hàm chính để trích xuất Time/Location."""
    # 1. Dùng AI (Underthesea) trước
    ner_result = ner(text)
    times, locs = [], []
    for token_data in ner_result:
        if len(token_data) == 4: token, tag, _, _ = token_data
        else: continue 
        if "TIME" in tag: times.append(token)
        if "LOC" in tag: locs.append(token)
    
    # 2. Luôn chạy Fallback Regex để bổ sung (vì AI tiếng Việt chưa hoàn hảo)
    fb = fallback_time_location(text)
    times.extend(fb["times"])
    locs.extend(fb["locations"])

    merged_time = merge_entities(times, text)
    merged_loc = merge_entities(locs, text)
    return {"merged_time": merged_time, "merged_location": merged_loc}

# ==============================================================================
# PHẦN 3: RULE-BASED EXTRACTION (SỰ KIỆN & NHẮC NHỞ)
# Mục đích: Tách tên sự kiện và thời gian nhắc trước (offset).
# ==============================================================================

# Pattern tìm câu nhắc: "nhắc trước 15 phút", "báo trc 1 tiếng"
PATTERN_OFFSET = re.compile(r'(nhắc|báo) (trước|trc)\s*(\d+)\s*(phút|p|giờ|h|tiếng|ngày)', re.IGNORECASE)
# Pattern tìm tên sự kiện: nằm sau từ "nhắc tôi", "hãy báo"...
PATTERN_EVENT = re.compile(r'(?:((nhắc|báo) (?:tôi|mình|nhớ|giúp tôi)|hãy (nhắc|báo)|(nhắc|báo) trước)(?:\s+về)?\s*)(.*?)(?=\s*(?:lúc|vào|sáng|chiều|tối|mai|ngày|,|$))', re.IGNORECASE)
# Pattern dự phòng cho tên sự kiện: lấy phần đầu câu trước từ chỉ thời gian
PATTERN_EVENT_FALLBACK = re.compile(r'^(.*?)\s*(?:lúc|vào|vào lúc|luc|8h\s*|7h\s*|[0-9]{1,2}\s*(?:h|giờ))', re.IGNORECASE)

def rule_extract(text: str):
    data = {}
    text = text.strip()
    
    # 1. Tìm thời gian nhắc trước (offset)
    off = PATTERN_OFFSET.search(text)
    if off:
        qty, unit = int(off.group(3)), off.group(4).lower()
        # Quy đổi tất cả ra phút
        if unit in ['giờ', 'h', 'tiếng']: minutes = qty * 60
        elif unit in ['ngày']: minutes = qty * 24 * 60
        else: minutes = qty
        data['reminder_offset_minutes'] = minutes
    
    # 2. Tìm tên sự kiện
    ev = PATTERN_EVENT.search(text)
    if ev:
        data['event'] = ev.group(5).strip(' ,.')
    else:
        # Nếu không có từ khóa "nhắc tôi", dùng fallback
        fb = PATTERN_EVENT_FALLBACK.search(text)
        if fb:
            event = fb.group(1).strip(' ,.')
            # Nếu event tìm được lại chứa câu nhắc giờ -> xóa nó đi
            if PATTERN_OFFSET.search(event): data['event'] = re.sub(PATTERN_OFFSET, '', text).strip(' ,.')
            else: data['event'] = event

    # Fallback lần cuối nếu vẫn chưa có event
    if 'event' not in data or not data['event']:
         fb = PATTERN_EVENT_FALLBACK.search(text)
         if fb: data['event'] = fb.group(1).strip(' ,.')
              
    return data

# ==============================================================================
# PHẦN 4: PHÂN TÍCH THỜI GIAN CHI TIẾT (Logic khó nhất)
# Mục đích: Chuyển đổi "10h sáng mai" thành đối tượng datetime(2025, 11, 23, 10, 0)
# ==============================================================================

# Regex bắt giờ: hỗ trợ "10h", "10:30", "10 giờ"
RE_HOUR = re.compile(r'(\d{1,2}\s*(?:h|giờ|:)\s*\d{0,2})')
# Regex bắt ngày tháng năm: dd/mm/yyyy
RE_DATE = re.compile(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}|\d{2}))?')

# Các từ khóa ngày tương đối
RE_TOMORROW = re.compile(r'(ngày mai|mai)')
RE_TODAY = re.compile(r'(hôm nay|hnay)')
RE_NEXT_WEEK = re.compile(r'tuần sau')
RE_NEXT2_WEEK = re.compile(r'tuần tới')

# Mapping thứ trong tuần sang số (0=Thứ 2 ... 6=Chủ nhật)
RE_DAY_OF_WEEK = {
    'thứ 2': 0, 'thứ hai': 0, 'thứ 3': 1, 'thứ ba': 1, 'thứ 4': 2, 'thứ tư': 2,
    'thứ 5': 3, 'thứ năm': 3, 'thứ 6': 4, 'thứ sáu': 4, 'thứ 7': 5, 'thứ bảy': 5, 'chủ nhật': 6, 'cn': 6
}

def parse_vietnamese_time(text, now=None, to_utc=False):
    """Hàm cốt lõi để hiểu thời gian tiếng Việt."""
    if now is None: now = datetime.now()
    text = text.lower().strip()
    if not text: return None

    # --- BƯỚC 1: XỬ LÝ GIỜ ---
    hour, minute = 8, 0 # Mặc định 8h sáng nếu không nói gì
    hour_match = RE_HOUR.search(text)
    if hour_match:
        hour_str = hour_match.group(1)
        # Logic tách giờ và phút dựa trên ký tự phân cách (h, giờ, :)
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

    # --- BƯỚC 2: XỬ LÝ BUỔI (Sáng/Trưa/Chiều/Tối) ---
    if 'sáng' in text: pass
    elif 'trưa' in text: 
        if hour < 11: hour = 11 # 1h trưa -> 11h (logic heuristic)
    elif 'chiều' in text: 
        if hour < 12: hour += 12 # 2h chiều -> 14h
    elif 'tối' in text: 
        if hour == 19: pass # 19h tối -> giữ nguyên
        elif hour < 12: hour += 12 # 7h tối -> 19h

    # --- BƯỚC 3: XỬ LÝ NGÀY (Logic phức tạp nhất) ---
    target_date = now.date()
    day_set = False
    
    # Ưu tiên 1: Ngày rõ ràng (22/11/2025) - Dùng cho form sửa
    date_match = RE_DATE.search(text)
    if date_match:
        try:
            d = int(date_match.group(1))
            m = int(date_match.group(2))
            y_str = date_match.group(3)
            y = int(y_str) if y_str else now.year
            if y < 100: y += 2000 # Năm 25 -> 2025
            target_date = datetime(y, m, d).date()
            day_set = True
        except ValueError: pass

    # Ưu tiên 2: Ngày tương đối (mai, tuần sau, thứ...)
    if not day_set:
        if RE_TOMORROW.search(text):
            target_date += timedelta(days=1)
        elif RE_TODAY.search(text):
            pass # Là hôm nay
        else:
            # Xử lý Thứ trong tuần (VD: Thứ 6 tuần sau)
            for k, v in RE_DAY_OF_WEEK.items():
                if k in text:
                    current_wd = now.weekday()
                    # Tính khoảng cách từ hôm nay đến Thứ mong muốn
                    # Công thức (đích - hiện tại + 7) % 7 luôn ra số dương
                    days_ahead = (v - current_wd + 7) % 7
                    
                    # Logic xử lý "Tuần sau" / "Tuần tới"
                    is_next_week = RE_NEXT_WEEK.search(text) or RE_NEXT2_WEEK.search(text)
                    
                    if is_next_week:
                        # Tính số ngày còn lại trong tuần này (đến CN)
                        days_to_sunday = 6 - current_wd
                        
                        # Nếu ngày đích rơi vào tuần này -> Cần +7 ngày để sang tuần sau
                        if days_ahead <= days_to_sunday:
                             if days_ahead == 0: days_ahead = 7 # Hôm nay T6, tìm T6 tuần sau -> +7
                             else: days_ahead += 7
                        # Nếu days_ahead > days_to_sunday (Hôm nay T7, tìm T6 tuần sau) -> Modulo đã tự nhảy sang tuần sau rồi -> Không cộng 7 nữa
                    
                    target_date += timedelta(days=days_ahead)
                    break

    # --- BƯỚC 4: TỔNG HỢP ---
    try: dt = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
    except ValueError: dt = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour)

    # Trả về chuỗi ISO chuẩn quốc tế để lưu DB
    if to_utc:
        dt -= timedelta(hours=7) 
        return dt.replace(microsecond=0).isoformat() + "Z"
    else:
        return dt.replace(microsecond=0).isoformat()

# ==============================================================================
# PHẦN 5: PIPELINE CHÍNH
# ==============================================================================

def merge_and_validate(text, ner_out, rule_out, resolved_times, ref=None):
    """Gói ghém dữ liệu lại thành Dictionary."""
    if ref is None: ref = datetime.now()
    
    # Logic sửa lỗi địa điểm: Nếu NER không tìm thấy, dùng fallback
    location = ner_out["merged_location"]
    if not location and "ở" in text:
        fb_loc = fallback_time_location(text)
        if fb_loc["locations"]: location = fb_loc["locations"][0]

    out = {
        "event": rule_out.get("event"),
        "start_time": resolved_times,
        "end_time": None,
        "reminder_minutes": rule_out.get("reminder_offset_minutes"),
        "location": location,
    }
    return out

def pipeline_(text: str, ref: datetime = None):
    """Hàm chính được gọi từ App."""
    text_norm = normalize_text(text)               # 1. Chuẩn hóa
    text_restored = restore_diacritics_text(text_norm) # 2. Thêm dấu
    ner_out = extract_entities(text_restored)      # 3. Tìm Time/Loc
    rule_out = rule_extract(text_restored)         # 4. Tìm Event/Remind
    dt = parse_vietnamese_time(ner_out['merged_time']) # 5. Hiểu thời gian
    merged = merge_and_validate(text_restored, ner_out, rule_out, dt, ref=ref) # 6. Gộp
    return merged
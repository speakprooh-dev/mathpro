import streamlit as st
import sqlite3
from datetime import date, timedelta
import calendar
import re
import pandas as pd
import io

# 네이버 카페 메인 주소 반환 함수
def get_cafe_search_url(unit_code, num_int):
    return "https://cafe.naver.com/mathpro2020"

# 전체 데이터베이스 테이블을 엑셀 파일(다중 시트)로 변환하는 백업 함수
def create_excel_backup():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        conn = sqlite3.connect("mathpro_roadmap.db")
        tables = [
            "students", "subjects", "chapters", "chapter_types", 
            "milestones", "student_homework", "milestone_progress", 
            "student_homework_progress", "student_wrong_entries", "problem_links", "homework_templates",
            "daily_routines", "daily_routine_logs", "notices"
        ]
        for table in tables:
            try:
                df = pd.read_sql(f"SELECT * FROM {table}", conn)
                df.to_excel(writer, sheet_name=table, index=False)
            except Exception:
                pass
        conn.close()
    return output.getvalue()

# 페이지 기본 설정
st.set_page_config(page_title="MathPro 학생 맞춤 학습 로드맵", page_icon="📐", layout="centered")

# 세션 상태에 선생님 인증 여부 초기화
if "teacher_authenticated" not in st.session_state:
    st.session_state["teacher_authenticated"] = False

# 한국어 요일 변환 함수
def get_weekday_kr(date_str):
    try:
        d = date.fromisoformat(date_str)
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        return weekdays[d.weekday()]
    except:
        return "날짜 확인"

# 1. 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    
    c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY)')
    
    try:
        c.execute("ALTER TABLE students ADD COLUMN drive_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS chapter_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            video_url TEXT DEFAULT ''
        )
    ''')
    
    try:
        c.execute("ALTER TABLE chapter_types ADD COLUMN video_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            chapter TEXT NOT NULL,
            type_name TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hw_date TEXT NOT NULL,
            title TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            hw_date TEXT NOT NULL,
            title TEXT NOT NULL,
            parent_id INTEGER DEFAULT NULL
        )
    ''')
    
    try:
        c.execute("ALTER TABLE student_homework ADD COLUMN parent_id INTEGER DEFAULT NULL")
    except sqlite3.OperationalError:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            title TEXT NOT NULL,
            parent_id INTEGER DEFAULT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS homework_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS milestone_progress (
            student_name TEXT,
            milestone_id INTEGER,
            is_checked INTEGER,
            PRIMARY KEY (student_name, milestone_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS homework_progress (
            student_name TEXT,
            homework_id INTEGER,
            is_checked INTEGER,
            PRIMARY KEY (student_name, homework_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_homework_progress (
            student_name TEXT,
            student_hw_id INTEGER,
            is_checked INTEGER,
            PRIMARY KEY (student_name, student_hw_id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_routine_logs (
            student_name TEXT,
            routine_id TEXT,
            log_date TEXT,
            is_checked INTEGER,
            PRIMARY KEY (student_name, routine_id, log_date)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS student_wrong_entries (
            student_name TEXT,
            unit_code TEXT,
            numbers_text TEXT,
            updated_at TEXT DEFAULT '',
            PRIMARY KEY (student_name, unit_code)
        )
    ''')
    
    try:
        c.execute("ALTER TABLE student_wrong_entries ADD COLUMN updated_at TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    today_str = str(date.today())
    c.execute("UPDATE student_wrong_entries SET updated_at = ? WHERE updated_at IS NULL OR updated_at = ''", (today_str,))

    c.execute('''
        CREATE TABLE IF NOT EXISTS problem_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_code TEXT UNIQUE NOT NULL,
            unit_code TEXT NOT NULL,
            prob_num TEXT NOT NULL,
            video_url TEXT NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT DEFAULT '',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    c.execute("SELECT COUNT(*) FROM subjects")
    if c.fetchone()[0] == 0:
        default_subjects = ["수학(상)", "수학(하)", "수학Ⅰ", "수학Ⅱ", "미적분", "확률과 통계"]
        for sub in default_subjects:
            try:
                c.execute("INSERT INTO subjects (name) VALUES (?)", (sub,))
            except sqlite3.IntegrityError:
                pass
                
    conn.commit()
    conn.close()

init_db()

# --- 데이터 관리 함수들 ---
def get_students():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT name FROM students ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_student_drive_url(name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT drive_url FROM students WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""

def update_student_drive_url(name, drive_url):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("UPDATE students SET drive_url = ? WHERE name = ?", (drive_url, name))
    conn.commit()
    conn.close()

def add_student(name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO students (name, drive_url) VALUES (?, ?)", (name, ""))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def delete_student(name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM students WHERE name = ?", (name,))
    c.execute("DELETE FROM milestones WHERE student_name = ?", (name,))
    c.execute("DELETE FROM milestone_progress WHERE student_name = ?", (name,))
    c.execute("DELETE FROM homework_progress WHERE student_name = ?", (name,))
    c.execute("DELETE FROM student_homework WHERE student_name = ?", (name,))
    c.execute("DELETE FROM student_homework_progress WHERE student_hw_id IN (SELECT id FROM student_homework WHERE student_name = ?)", (name,))
    c.execute("DELETE FROM student_wrong_entries WHERE student_name = ?", (name,))
    c.execute("DELETE FROM daily_routines WHERE student_name = ?", (name,))
    c.execute("DELETE FROM daily_routine_logs WHERE student_name = ?", (name,))
    c.execute("DELETE FROM notices WHERE student_name = ?", (name,))
    conn.commit()
    conn.close()

def get_subjects():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM subjects ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def add_subject(name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO subjects (name) VALUES (?)", (name,))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def update_subject(sub_id, old_name, new_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    try:
        c.execute("UPDATE subjects SET name = ? WHERE id = ?", (new_name, sub_id))
        c.execute("UPDATE chapters SET subject = ? WHERE subject = ?", (new_name, old_name))
        c.execute("UPDATE milestones SET subject = ? WHERE subject = ?", (new_name, old_name))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def delete_subject(sub_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM subjects WHERE id = ?", (sub_id,))
    conn.commit()
    conn.close()

def get_chapters():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, subject, name FROM chapters")
    rows = c.fetchall()
    conn.close()
    
    def natural_sort_key(ch):
        subject, name = ch[1], ch[2]
        match = re.search(r'(\d+)', name)
        num = int(match.group(1)) if match else 0
        return (subject, num, name)
        
    return sorted(rows, key=natural_sort_key)

def add_chapter(subject, name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("INSERT INTO chapters (subject, name) VALUES (?, ?)", (subject, name))
    ch_id = c.lastrowid
    conn.commit()
    conn.close()
    return ch_id

def update_chapter(ch_id, subject, name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("UPDATE chapters SET subject = ?, name = ? WHERE id = ?", (subject, name, ch_id))
    conn.commit()
    conn.close()

def delete_chapter(ch_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM chapters WHERE id = ?", (ch_id,))
    c.execute("DELETE FROM chapter_types WHERE chapter_id = ?", (ch_id,))
    conn.commit()
    conn.close()

def get_chapter_types(chapter_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, name, video_url FROM chapter_types WHERE chapter_id = ?", (chapter_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def add_chapter_type(chapter_id, name, video_url=""):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("INSERT INTO chapter_types (chapter_id, name, video_url) VALUES (?, ?, ?)", (chapter_id, name, video_url))
    conn.commit()
    conn.close()

def update_chapter_type_name(type_id, new_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("UPDATE chapter_types SET name = ? WHERE id = ?", (new_name, type_id))
    conn.commit()
    conn.close()

def update_chapter_type_url(type_id, video_url):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("UPDATE chapter_types SET video_url = ? WHERE id = ?", (video_url, type_id))
    conn.commit()
    conn.close()

def delete_chapter_type(type_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM chapter_types WHERE id = ?", (type_id,))
    conn.commit()
    conn.close()

def bulk_insert_types_for_chapter(chapter_id, text_data):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM chapter_types WHERE chapter_id = ?", (chapter_id,))
    count_row = c.fetchone()
    type_counter = (count_row[0] if count_row else 0) + 1
    
    lines = text_data.strip().split('\n')
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        
        raw_type_name = line_str.lstrip('-•* ').strip()
        if raw_type_name:
            if not raw_type_name.startswith("유형"):
                type_name = f"유형 {type_counter:02d}. {raw_type_name}"
            else:
                type_name = raw_type_name
            
            c.execute("INSERT INTO chapter_types (chapter_id, name, video_url) VALUES (?, ?, ?)", (chapter_id, type_name, ""))
            type_counter += 1
            
    conn.commit()
    conn.close()

def save_problem_link(full_code, video_url):
    full_code = full_code.strip().upper()
    if len(full_code) < 4:
        return False
    unit_code = full_code[:-3]
    prob_num = full_code[-3:]
    
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO problem_links (full_code, unit_code, prob_num, video_url)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(full_code) DO UPDATE SET video_url = ?
        ''', (full_code, unit_code, prob_num, video_url, video_url))
        conn.commit()
        success = True
    except Exception:
        success = False
    conn.close()
    return success

def bulk_save_problem_links(text_data):
    lines = text_data.strip().split('\n')
    success_count = 0
    fail_count = 0
    
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = re.split(r'[, \t]+', line)
        if len(parts) >= 2:
            full_code = parts[0].strip().upper()
            video_url = parts[1].strip()
            
            if len(full_code) >= 4 and video_url.startswith("http"):
                unit_code = full_code[:-3]
                prob_num = full_code[-3:]
                try:
                    c.execute('''
                        INSERT INTO problem_links (full_code, unit_code, prob_num, video_url)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(full_code) DO UPDATE SET video_url = ?
                    ''', (full_code, unit_code, prob_num, video_url, video_url))
                    success_count += 1
                except Exception:
                    fail_count += 1
            else:
                fail_count += 1
        else:
            fail_count += 1
            
    conn.commit()
    conn.close()
    return success_count, fail_count

def get_problem_links_by_unit(unit_code):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT full_code, video_url FROM problem_links WHERE unit_code = ? ORDER BY full_code", (unit_code.upper(),))
    rows = c.fetchall()
    conn.close()
    return rows

def get_problem_link_by_full(full_code):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT video_url FROM problem_links WHERE full_code = ?", (full_code.upper(),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def get_all_problem_links():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, full_code, video_url FROM problem_links ORDER BY full_code")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_problem_link(link_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM problem_links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()

# --- 공지사항 관련 함수 ---
def add_notice(student_name, title, content):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    today_str = str(date.today())
    c.execute("INSERT INTO notices (student_name, title, content, created_at) VALUES (?, ?, ?, ?)", (student_name, title, content, today_str))
    conn.commit()
    conn.close()

def get_notices_for_student(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, title, content, created_at, student_name FROM notices WHERE student_name = '' OR student_name = ? ORDER BY id DESC", (student_name,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_notices():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, student_name, title, content, created_at FROM notices ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_notice(notice_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
    conn.commit()
    conn.close()

# --- 매일 루틴 과제 관리 함수들 ---
def get_student_daily_routines_parent(student_name, parent_id=None):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    if parent_id is None:
        c.execute("SELECT id, title FROM daily_routines WHERE student_name = ? AND (parent_id IS NULL) ORDER BY id", (student_name,))
    else:
        c.execute("SELECT id, title FROM daily_routines WHERE student_name = ? AND parent_id = ? ORDER BY id", (student_name, parent_id))
    rows = c.fetchall()
    conn.close()
    return rows

def bulk_insert_daily_routines(student_name, text_data):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    lines = text_data.strip().split('\n')
    added_count = 0
    current_parent_id = None
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        
        is_sub = line.startswith((' ', '\t', '-', '*', '•', '└')) or line_str.startswith(('-', '*', '•', '└'))
        title = line_str.lstrip('-•*└\t ').strip()
        if not title:
            continue
            
        if is_sub and current_parent_id is not None:
            c.execute("INSERT INTO daily_routines (student_name, title, parent_id) VALUES (?, ?, ?)", (student_name, title, current_parent_id))
        else:
            c.execute("INSERT INTO daily_routines (student_name, title, parent_id) VALUES (?, ?, NULL)", (student_name, title))
            current_parent_id = c.lastrowid
        added_count += 1
        
    conn.commit()
    conn.close()
    return added_count

def delete_daily_routine(r_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM daily_routines WHERE id = ? OR parent_id = ?", (r_id, r_id))
    c.execute("DELETE FROM daily_routine_logs WHERE routine_id = ? OR routine_id LIKE ?", (str(r_id), f"{r_id}_%"))
    conn.commit()
    conn.close()

def save_daily_routine_logs(student_name, log_date, routine_checked_dict):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    for routine_id_str, val in routine_checked_dict.items():
        c.execute('''
            INSERT INTO daily_routine_logs (student_name, routine_id, log_date, is_checked)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_name, routine_id, log_date) DO UPDATE SET is_checked = ?
        ''', (student_name, str(routine_id_str), log_date, int(val), int(val)))
    conn.commit()
    conn.close()

def get_student_monthly_logs(student_name, year, month):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
        
    c.execute("SELECT routine_id, log_date, is_checked FROM daily_routine_logs WHERE student_name = ? AND log_date >= ? AND log_date < ?", (student_name, start_date, end_date))
    rows = c.fetchall()
    conn.close()
    
    log_map = {}
    for r_id, l_date, val in rows:
        log_map[(str(r_id), l_date)] = bool(val)
    return log_map

def get_student_daily_logs_by_date(student_name, target_date_str):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT routine_id, is_checked FROM daily_routine_logs WHERE student_name = ? AND log_date = ?", (student_name, target_date_str))
    rows = c.fetchall()
    conn.close()
    
    log_map = {}
    for r_id, val in rows:
        log_map[(str(r_id), target_date_str)] = bool(val)
    return log_map

# --- 과제 템플릿 관리 함수들 ---
def get_homework_templates():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, title FROM homework_templates ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def add_homework_template(title):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("INSERT INTO homework_templates (title) VALUES (?)", (title,))
    conn.commit()
    conn.close()

def delete_homework_template(t_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM homework_templates WHERE id = ?", (t_id,))
    conn.commit()
    conn.close()

def get_student_milestones(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("""
        SELECT m.id, m.subject, m.chapter, m.type_name, 
               (SELECT t.video_url FROM chapter_types t WHERE t.name = m.type_name LIMIT 1) as video_url
        FROM milestones m WHERE m.student_name = ?
    """, (student_name,))
    rows = c.fetchall()
    conn.close()
    return rows

def assign_chapters_to_student(student_name, chapter_ids):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    
    added_count = 0
    for chapter_id in chapter_ids:
        c.execute("SELECT subject, name FROM chapters WHERE id = ?", (chapter_id,))
        ch_row = c.fetchone()
        if not ch_row:
            continue
        sub, ch_name = ch_row
        
        c.execute("SELECT name FROM chapter_types WHERE chapter_id = ?", (chapter_id,))
        type_rows = c.fetchall()
        
        types_to_add = [r[0] for r in type_rows]
        if not types_to_add:
            types_to_add = ["단원 기본 학습"]
            
        c.execute("SELECT chapter, type_name FROM milestones WHERE student_name = ?", (student_name,))
        existing = {(r[0], r[1]) for r in c.fetchall()}
        
        for t_name in types_to_add:
            if (ch_name, t_name) not in existing:
                c.execute("INSERT INTO milestones (student_name, subject, chapter, type_name) VALUES (?, ?, ?, ?)", 
                          (student_name, sub, ch_name, t_name))
                added_count += 1
                
    conn.commit()
    conn.close()
    return added_count

def delete_student_milestone(m_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM milestones WHERE id = ?", (m_id,))
    c.execute("DELETE FROM milestone_progress WHERE milestone_id = ?", (m_id,))
    conn.commit()
    conn.close()

def delete_student_milestones_by_chapters(student_name, chapter_names):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    total_deleted = 0
    for ch_name in chapter_names:
        c.execute("SELECT id FROM milestones WHERE student_name = ? AND chapter = ?", (student_name, ch_name))
        m_ids = [r[0] for r in c.fetchall()]
        for m_id in m_ids:
            c.execute("DELETE FROM milestones WHERE id = ?", (m_id,))
            c.execute("DELETE FROM milestone_progress WHERE milestone_id = ?", (m_id,))
            total_deleted += 1
    conn.commit()
    conn.close()
    return total_deleted

def get_student_homework_dates(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT hw_date FROM student_homework WHERE student_name = ? ORDER BY hw_date DESC", (student_name,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_student_homework_by_date_parent(student_name, hw_date, parent_id=None):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    if parent_id is None:
        c.execute("SELECT id, title FROM student_homework WHERE student_name = ? AND hw_date = ? AND (parent_id IS NULL) ORDER BY id", (student_name, hw_date))
    else:
        c.execute("SELECT id, title FROM student_homework WHERE student_name = ? AND hw_date = ? AND parent_id = ? ORDER BY id", (student_name, hw_date, parent_id))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_student_homework(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, hw_date, title, parent_id FROM student_homework WHERE student_name = ? ORDER BY hw_date DESC, id DESC", (student_name,))
    rows = c.fetchall()
    conn.close()
    return rows

def bulk_insert_student_homework(student_name, hw_date, text_data):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    lines = text_data.strip().split('\n')
    added_count = 0
    current_parent_id = None
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        
        is_sub = line.startswith((' ', '\t', '-', '*', '•', '└')) or line_str.startswith(('-', '*', '•', '└'))
        title = line_str.lstrip('-•*└\t ').strip()
        if not title:
            continue
            
        if is_sub and current_parent_id is not None:
            c.execute("INSERT INTO student_homework (student_name, hw_date, title, parent_id) VALUES (?, ?, ?, ?)", 
                      (student_name, hw_date, title, current_parent_id))
        else:
            c.execute("INSERT INTO student_homework (student_name, hw_date, title, parent_id) VALUES (?, ?, ?, NULL)", 
                      (student_name, hw_date, title))
            current_parent_id = c.lastrowid
        added_count += 1
        
    conn.commit()
    conn.close()
    return added_count

def update_student_homework(shw_id, hw_date, title):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("UPDATE student_homework SET hw_date = ?, title = ? WHERE id = ?", (hw_date, title, shw_id))
    conn.commit()
    conn.close()

def delete_student_homework(shw_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM student_homework WHERE id = ? OR parent_id = ?", (shw_id, shw_id))
    c.execute("DELETE FROM student_homework_progress WHERE student_hw_id = ? OR student_hw_id IN (SELECT id FROM student_homework WHERE parent_id = ?)", (shw_id, shw_id))
    conn.commit()
    conn.close()

def get_milestone_progress(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT milestone_id, is_checked FROM milestone_progress WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}

def get_student_homework_progress(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT student_hw_id, is_checked FROM student_homework_progress WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}

def save_single_milestone_progress(student_name, milestone_id, val):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO milestone_progress (student_name, milestone_id, is_checked)
        VALUES (?, ?, ?)
        ON CONFLICT(student_name, milestone_id) DO UPDATE SET is_checked = ?
    ''', (student_name, milestone_id, int(val), int(val)))
    conn.commit()
    conn.close()

def save_single_homework_progress(student_name, student_hw_id, val):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO student_homework_progress (student_name, student_hw_id, is_checked)
        VALUES (?, ?, ?)
        ON CONFLICT(student_name, student_hw_id) DO UPDATE SET is_checked = ?
    ''', (student_name, student_hw_id, int(val), int(val)))
    conn.commit()
    conn.close()

def get_student_wrong_entry(student_name, unit_code):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT numbers_text FROM student_wrong_entries WHERE student_name = ? AND unit_code = ?", (student_name, unit_code))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def save_student_wrong_entry(student_name, unit_code, numbers_text):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    today_str = str(date.today())
    c.execute('''
        INSERT INTO student_wrong_entries (student_name, unit_code, numbers_text, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(student_name, unit_code) DO UPDATE SET numbers_text = ?, updated_at = ?
    ''', (student_name, unit_code, numbers_text, today_str, numbers_text, today_str))
    conn.commit()
    conn.close()

def parse_numbers(text):
    if not text:
        return set()
    nums = re.findall(r'\d+', text)
    return set(int(n) for n in nums)

# --- 웹 UI 구성 ---
st.title("📐 MathPro 학생 맞춤 학습 로드맵")
st.caption("선생님과 함께하는 나의 고등 수학 학습 여정")

cafe_main_url = "https://cafe.naver.com/mathpro2020"
st.markdown(
    f'<a href="{cafe_main_url}" target="_blank" style="display:block; background-color:#03C75A; color:#FFFFFF; padding:10px 14px; border-radius:8px; font-size:14px; text-decoration:none; font-weight:bold; text-align:center; margin-bottom:15px; border: 1px solid #03C75A;">🟢 MathPro 네이버 카페 바로가기</a>',
    unsafe_allow_html=True
)

st.divider()

student_list = get_students()
query_params = st.query_params
url_student = query_params.get("student", None)

# 1. [학생 전용 모드]
if url_student and url_student in student_list:
    selected_student = url_student
    
    student_notices = get_notices_for_student(selected_student)
    if student_notices:
        st.markdown(
            f'<div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 2px solid #38BDF8; padding: 18px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2);">'
            f'<div style="font-size: 18px; font-weight: bold; color: #38BDF8; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">'
            f'📢 [중요 공지사항] 확인해 주세요!</div>',
            unsafe_allow_html=True
        )
        for n_id, n_title, n_content, n_date, n_target in student_notices:
            target_badge = "🌐 전체 공지" if not n_target else f"👤 {n_target} 학생 맞춤 공지"
            st.markdown(
                f'<div style="background-color: rgba(30, 41, 59, 0.7); border-left: 4px solid #38BDF8; padding: 12px; border-radius: 6px; margin-bottom: 10px;">'
                f'<div style="font-size: 14px; color: #94A3B8; margin-bottom: 4px;">{target_badge} &nbsp;|&nbsp; 작성일: {n_date}</div>'
                f'<div style="font-size: 16px; font-weight: bold; color: #F8FAFC; margin-bottom: 6px;">📌 {n_title}</div>'
                f'<div style="font-size: 14px; color: #E2E8F0; white-space: pre-wrap; line-height: 1.5;">{n_content}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="background-color:#1E293B; border:1px solid #334155; padding:16px; border-radius:12px; margin-bottom:15px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">'
        f'<div style="font-size:17px; font-weight:bold; color:#F8FAFC; margin-bottom:8px;">✨ 안녕하세요, <span style="color:#38BDF8;">{selected_student}</span> 학생!</div>'
        f'<div style="font-size:13px; color:#94A3B8; margin-bottom:12px;">오늘도 MathPro와 함께 멋진 수학 학습을 시작해볼까요?</div>',
        unsafe_allow_html=True
    )
    
    student_drive = get_student_drive_url(selected_student)
    if student_drive and student_drive.strip() != "":
        st.markdown(
            f'<a href="{student_drive}" target="_blank" style="display:block; background-color:#2563EB; color:#FFFFFF; padding:12px 16px; border-radius:8px; font-size:15px; text-decoration:none; font-weight:bold; text-align:center; margin-bottom:15px; box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);">📁 개인 학습 자료실 및 과제 제출함 (Google Drive) 바로가기 ➔</a>',
            unsafe_allow_html=True
        )
    
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("📖 [필독] 1분 만에 끝내는 MathPro 사용 설명서 보기"):
        st.markdown("""
        ### 📐 MathPro 1:1 맞춤 학습 공간 이용 가이드
        
        **1️⃣ 개인 학습 자료실 및 과제 제출함 (Google Drive)**
        * 파란색 드라이브 버튼을 누르면 나만의 구글 드라이브 폴더로 바로 이동해 과제를 제출하거나 자료를 확인할 수 있어요!
        
        **2️⃣ 🚩 1. 개념 학습 진도 체크하기**
        * 배정된 단원의 학습을 마친 후 체크박스(☑️)에 체크하세요. **체크하는 순간 자동으로 저장됩니다!**
        * 모르는 개념은 우측 **[🎥 개념해설]** 버튼을 눌러 영상을 시청할 수 있습니다.
        
        **3️⃣ 📚 2. 날짜별 숙제 확인하기**
        * 매일 실천하는 **[매일 루틴 과제]** 및 **[날짜별 숙제]**는 체크하는 순간 **자동으로 실시간 저장**됩니다!
        
        **4️⃣ 💬 3. 오답 및 질문 번호 관리하기**
        * **[📂 내가 저장한 오답 단원 확인하기]**에서 단원을 선택하면 해당 단원의 오답과 해설 영상이 바로 나타납니다.
        * 새로운 단원의 오답을 등록할 때는 하단의 **[새로운 오답/질문 번호 등록 및 수정]** 칸을 이용해 주세요!
        """)

    milestones = get_student_milestones(selected_student)
    hw_dates = get_student_homework_dates(selected_student)
    m_progress = get_milestone_progress(selected_student)
    h_progress = get_student_homework_progress(selected_student)
    all_hws_flat = get_all_student_homework(selected_student)

    total_m = len(milestones)
    completed_m = sum(1 for m in milestones if m_progress.get(m[0], False))
    m_percent = int((completed_m / total_m) * 100) if total_m > 0 else 0

    total_h = len(all_hws_flat)
    completed_h = sum(1 for h in all_hws_flat if h_progress.get(h[0], False))
    h_percent = int((completed_h / total_h) * 100) if total_h > 0 else 0

    st.markdown("##### 📊 나의 학습 성취도 대시보드")
    col_dash1, col_dash2 = st.columns(2)
    with col_dash1:
        with st.container(border=True):
            st.markdown(f"**🎯 개념 진도**")
            st.metric(label="달성률", value=f"{m_percent}%", delta=f"{completed_m}/{total_m} 완료")
            st.progress(m_percent / 100 if total_m > 0 else 0)
    with col_dash2:
        with st.container(border=True):
            st.markdown(f"**📚 숙제 완료**")
            st.metric(label="달성률", value=f"{h_percent}%", delta=f"{completed_h}/{total_h} 완료")
            st.progress(h_percent / 100 if total_h > 0 else 0)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📘 개념 진도", "📚 날짜별 숙제", "💬 오답·질문 관리"])

    with tab1:
        st.markdown("### 📘 나의 개념 학습 목록")
        st.success("💡 **자동 저장 기능 적용:** 완료한 학습 항목의 체크박스를 누르는 즉시 자동으로 안전하게 저장됩니다!")
        if milestones:
            grouped_s_milestones = {}
            for m_id, sub, ch, t_name, v_url in milestones:
                key = (sub, ch)
                if key not in grouped_s_milestones:
                    grouped_s_milestones[key] = []
                grouped_s_milestones[key].append((m_id, t_name, v_url))

            for (sub, ch), items in grouped_s_milestones.items():
                done_cnt = sum(1 for m_id, _, _ in items if m_progress.get(m_id, False))
                exp_label = f"[{sub}] {ch} (완료: {done_cnt}/{len(items)})"
                
                with st.expander(exp_label, expanded=False):
                    for m_id, t_name, v_url in items:
                        default_val = m_progress.get(m_id, False)
                        
                        cols = st.columns([4, 1])
                        with cols[0]:
                            val = st.checkbox(f"{t_name}", value=default_val, key=f"s_milestone_{m_id}")
                            if val != default_val:
                                save_single_milestone_progress(selected_student, m_id, val)
                                st.rerun()
                        with cols[1]:
                            if v_url and v_url.strip() != "":
                                st.markdown(
                                    f'<a href="{v_url}" target="_blank" style="display:inline-block; background-color:#1E293B; color:#38BDF8; padding:4px 10px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; margin-top:4px; border:1px solid #334155;">🎥 개념해설</a>',
                                    unsafe_allow_html=True
                                )
                            else:
                                st.caption("영상 없음")
        else:
            st.info("아직 배정된 개념 학습 목록이 없습니다.")

    with tab2:
        st.markdown("### 🔥 매일 반복 루틴 과제 (오늘 실천)")
        st.success("💡 **자동 저장 기능 적용:** 체크박스를 누르는 즉시 자동으로 실시간 저장됩니다!")
        
        daily_parents = get_student_daily_routines_parent(selected_student, parent_id=None)
        if daily_parents:
            today_str = str(date.today())
            current_day_logs = get_student_daily_logs_by_date(selected_student, today_str)
            
            with st.container(border=True):
                daily_routine_checked_dict = {}
                for r_id, r_title in daily_parents:
                    r_subs = get_student_daily_routines_parent(selected_student, parent_id=r_id)
                    default_val = current_day_logs.get((str(r_id), today_str), False)
                    
                    if r_subs:
                        st.markdown(f"**📌 {r_title}**")
                        val_p = st.checkbox(f"{r_title} (전체 대표)", value=default_val, key=f"s_daily_{r_id}")
                        daily_routine_checked_dict[str(r_id)] = val_p
                        for sr_id, sr_title in r_subs:
                            s_default_val = current_day_logs.get((str(sr_id), today_str), False)
                            val_sp = st.checkbox(f"&nbsp;&nbsp;&nbsp;&nbsp;└ {sr_title}", value=s_default_val, key=f"s_daily_{sr_id}")
                            daily_routine_checked_dict[str(sr_id)] = val_sp
                    else:
                        val_s = st.checkbox(f"📌 {r_title}", value=default_val, key=f"s_daily_{r_id}")
                        daily_routine_checked_dict[str(r_id)] = val_s
                    st.divider()
            
            if daily_routine_checked_dict:
                save_daily_routine_logs(selected_student, today_str, daily_routine_checked_dict)

            st.markdown("---")
            st.markdown("### 📅 나의 매일 루틴 실천 월간 기록 뷰")
            
            curr_year = date.today().year
            curr_month = date.today().month
            
            col_y, col_m = st.columns(2)
            with col_y:
                sel_year = st.selectbox("연도 선택", [curr_year - 1, curr_year, curr_year + 1], index=1, key="cal_year")
            with col_m:
                sel_month = st.selectbox("월 선택", list(range(1, 13)), index=curr_month - 1, format_func=lambda x: f"{x}월", key="cal_month")
            
            monthly_logs = get_student_monthly_logs(selected_student, sel_year, sel_month)
            _, last_day = calendar.monthrange(sel_year, sel_month)
            
            with st.expander(f"🗓️ [{sel_year}년 {sel_month}월] 루틴 실천 일자별 리스트 보기 (펼치기 / 접기)", expanded=False):
                for r_id, r_title in daily_parents:
                    st.markdown(f"📌 **{r_title}**")
                    
                    log_data_list = []
                    for d_num in range(1, last_day + 1):
                        d_str = f"{sel_year}-{sel_month:02d}-{d_num:02d}"
                        is_done = monthly_logs.get((str(r_id), d_str), False)
                        w_kr = get_weekday_kr(d_str)[:1]
                        status_str = "✅ 완료" if is_done else "❌ 미완료"
                        log_data_list.append({"날짜": f"{d_num}일 ({w_kr})", "실천 상태": status_str})
                    
                    df_log = pd.DataFrame(log_data_list)
                    st.dataframe(df_log, use_container_width=True, hide_index=True)
                    
                    r_subs = get_student_daily_routines_parent(selected_student, parent_id=r_id)
                    for sr_id, sr_title in r_subs:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;└ 세부항목: **{sr_title}**")
                        sub_log_list = []
                        for d_num in range(1, last_day + 1):
                            d_str = f"{sel_year}-{sel_month:02d}-{d_num:02d}"
                            sub_done = monthly_logs.get((str(sr_id), d_str), False)
                            w_kr = get_weekday_kr(d_str)[:1]
                            sub_log_list.append({"날짜": f"{d_num}일 ({w_kr})", "실천 상태": "✅ 완료" if sub_done else "❌ 미완료"})
                        st.dataframe(pd.DataFrame(sub_log_list), use_container_width=True, hide_index=True)
                    st.divider()
        else:
            st.info("현재 등록된 매일 루틴 과제가 없습니다.")

        st.markdown("---")
        st.markdown("### 📝 날짜별 부여된 숙제 목록")
        st.success("💡 **자동 저장 기능 적용:** 완료한 숙제 항목의 체크박스를 누르는 즉시 자동으로 저장됩니다!")
        if hw_dates:
            selected_date = st.selectbox("확인할 숙제 날짜를 선택하세요", hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
            st.markdown(f"#### 📌 [{selected_date} ({get_weekday_kr(selected_date)})] 부여된 숙제")
            
            parent_hws = get_student_homework_by_date_parent(selected_student, selected_date, parent_id=None)
            for h_id, title in parent_hws:
                default_val = h_progress.get(h_id, False)
                sub_hws = get_student_homework_by_date_parent(selected_student, selected_date, parent_id=h_id)
                
                if sub_hws:
                    st.markdown(f"**📌 {title}**")
                    val_h = st.checkbox(f"{title} (전체 대표)", value=default_val, key=f"s_hw_{h_id}")
                    if val_h != default_val:
                        save_single_homework_progress(selected_student, h_id, val_h)
                        st.rerun()
                    for s_id, s_title in sub_hws:
                        s_default_val = h_progress.get(s_id, False)
                        val_sh = st.checkbox(f"&nbsp;&nbsp;&nbsp;&nbsp;└ {s_title}", value=s_default_val, key=f"s_hw_{s_id}")
                        if val_sh != s_default_val:
                            save_single_homework_progress(selected_student, s_id, val_sh)
                            st.rerun()
                else:
                    val_single = st.checkbox(f"{title}", value=default_val, key=f"s_hw_{h_id}")
                    if val_single != default_val:
                        save_single_homework_progress(selected_student, h_id, val_single)
                        st.rerun()
        else:
            st.info("등록된 날짜별 숙제가 없습니다.")

    with tab3:
        st.markdown("### 💬 오답 및 질문 번호 관리")
        
        st.markdown("##### 📂 내가 저장한 오답 단원 확인하기")
        conn_w = sqlite3.connect("mathpro_roadmap.db")
        c_w = conn_w.cursor()
        c_w.execute("SELECT unit_code FROM student_wrong_entries WHERE student_name = ? AND numbers_text != '' ORDER BY unit_code", (selected_student,))
        saved_units_rows = c_w.fetchall()
        conn_w.close()
        
        saved_units_list = [r[0] for r in saved_units_rows]
        
        if saved_units_list:
            selected_unit_from_box = st.selectbox(
                "확인할 단원 선택", 
                saved_units_list, 
                index=None, 
                placeholder="-- 확인하실 단원을 선택해 주세요 --", 
                key="view_saved_unit_box"
            )
            current_unit = selected_unit_from_box
        else:
            current_unit = None
            st.info("💡 아직 저장된 오답 단원이 없습니다. 아래에서 새로운 단원코드를 입력해 첫 오답을 등록해 보세요!")

        if current_unit:
            st.info(f"💡 현재 **`{current_unit}`** 단원의 저장된 오답 목록을 보고 계십니다.")
            saved_text = get_student_wrong_entry(selected_student, current_unit)
            saved_nums = parse_numbers(saved_text)

            st.markdown(f"### 📋 [{current_unit}] 저장된 오답 목록 및 풀이영상 바로가기")
            if saved_nums:
                st.caption("💡 **문제 번호를 클릭**하면 해당 해설 영상으로 바로 연결됩니다!")
                
                linked_problems_dict = {row[0]: row[1] for row in get_problem_links_by_unit(current_unit)}

                sorted_nums_list = sorted(list(saved_nums))
                for num_int in sorted_nums_list:
                    full_code = f"{current_unit}{num_int:03d}"
                    video_url = linked_problems_dict.get(full_code, "")

                    if video_url and video_url.strip() != "":
                        st.markdown(
                            f'<a href="{video_url}" target="_blank" style="display:block; background-color:#1E293B; color:#F8FAFC; border:1px solid #334155; padding:12px 16px; border-radius:8px; font-size:15px; font-weight:bold; text-decoration:none; margin-bottom:10px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">📌 {full_code} &nbsp;&nbsp;<span style="color:#38BDF8; font-size:13px; font-weight:normal;">🎥 해설 영상 바로가기 ➔</span></a>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f'<a href="{cafe_main_url}" target="_blank" style="display:block; background-color:#1E293B; color:#94A3B8; border:1px solid #334155; padding:12px 16px; border-radius:8px; font-size:15px; font-weight:bold; text-decoration:none; margin-bottom:10px;">📌 {full_code} &nbsp;&nbsp;<span style="color:#64748B; font-size:13px; font-weight:normal;">🔍 네이버 카페에서 검색하기 ➔</span></a>',
                            unsafe_allow_html=True
                        )
            else:
                st.info(f"📋 '{current_unit}' 단원에 현재 저장된 오답 번호가 없습니다.")
        else:
            if saved_units_list:
                st.info("👆 상단의 **'확인할 단원 선택'** 박스를 누르면 해당 단원의 저장된 오답 목록이 나타납니다.")

        st.markdown("---")

        st.markdown("##### ➕ 새로운 오답/질문 번호 등록 및 수정")
        default_input_code = current_unit if current_unit else ""
        entered_unit_code = st.text_input("단원코드 입력 (예: A114, B1353)", value=default_input_code, placeholder="예: B1353").strip().upper()
        target_unit_code = entered_unit_code if entered_unit_code else "B1353"

        col_add, col_del = st.columns(2)
        with col_add:
            add_input_text = st.text_input("➕ 추가할 번호 입력 (예: 15, 35, 37)", placeholder="예: 15, 35")
        with col_del:
            del_input_text = st.text_input("➖ 삭제할 번호 입력 (예: 7, 10)", placeholder="예: 7")

        st.markdown("---")
        save_btn_tab3 = st.button("💾 오답 목록 저장하기", type="primary", key="save_t3", use_container_width=True)

        st.markdown("---")
        st.markdown("### 🔍 문제 번호 또는 단원코드로 풀이해설 검색하기")
        st.info("💡 **B1353015**처럼 전체 번호를 검색하면 해설 영상으로 바로 연결되며, **B1353**처럼 단원코드를 검색하면 링크가 등록된 모든 문제 목록이 깔끔한 단원 톤 카드로 표시됩니다!")

        search_prob_input = st.text_input("문제 번호 또는 단원코드 입력 (예: B1353015 또는 B1353)", placeholder="예: B1353").strip().upper()
        
        if search_prob_input:
            if len(search_prob_input) >= 7:
                matched_url = get_problem_link_by_full(search_prob_input)
                if matched_url:
                    st.success(f"📌 **{search_prob_input}** 문제 해설 링크가 확인되었습니다!")
                    st.markdown(
                        f'<a href="{matched_url}" target="_blank" style="display:block; background-color:#1E293B; color:#F8FAFC; padding:14px; border-radius:8px; font-size:15px; text-decoration:none; font-weight:bold; text-align:center; border:1px solid #334155;">🎥 [{search_prob_input}] 풀이 영상 바로가기 ➔</span></a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.warning(f"'{search_prob_input}'에 등록된 해설 링크가 아직 없습니다. 선생님께 요청해 주세요!")
                    st.markdown(
                        f'<a href="{cafe_main_url}" target="_blank" style="display:block; background-color:#1E293B; color:#38BDF8; padding:12px; border-radius:8px; font-size:14px; text-decoration:none; font-weight:bold; text-align:center; border:1px solid #334155;">☕ 네이버 카페에서 직접 검색하기</a>',
                        unsafe_allow_html=True
                    )
            else:
                unit_results = get_problem_links_by_unit(search_prob_input)
                if unit_results:
                    st.markdown(f"##### 📂 `{search_prob_input}` 단원에서 링크가 설정된 문제 목록 총 {len(unit_results)}개")
                    st.caption("💡 아래 문제 카드를 클릭하시면 해당 해설 영상으로 바로 연결됩니다!")
                    for f_code, v_url in unit_results:
                        st.markdown(
                            f'<a href="{v_url}" target="_blank" style="display:block; background-color:#1E293B; color:#F8FAFC; border:1px solid #334155; padding:12px 16px; border-radius:8px; font-size:15px; font-weight:bold; text-decoration:none; margin-bottom:10px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">📌 {f_code} &nbsp;&nbsp;<span style="color:#38BDF8; font-size:13px; font-weight:normal;">🎥 해설 영상 바로가기 ➔</span></a>',
                            unsafe_allow_html=True
                        )
                else:
                    st.info(f"'{search_prob_input}' 단원에 등록된 해설 링크가 없습니다.")

    if locals().get("save_btn_tab3", False):
        add_txt = locals().get("add_input_text", "")
        del_txt = locals().get("del_input_text", "")
        target_code = locals().get("target_unit_code", "B1353")
        
        if target_code:
            saved_text_pre = get_student_wrong_entry(selected_student, target_code)
            saved_nums_pre = parse_numbers(saved_text_pre)
            nums_to_add = parse_numbers(add_txt)
            nums_to_del = parse_numbers(del_txt)
            
            final_nums = (saved_nums_pre | nums_to_add) - nums_to_del
            new_saved_text = ", ".join([str(n) for n in sorted(list(final_nums))])
            save_student_wrong_entry(selected_student, target_code, new_saved_text)
            st.success("오답 목록이 안전하게 저장되었습니다!")
            st.rerun()

# 2. [선생님 전용 관리 모드]
else:
    with st.sidebar:
        st.markdown("### 🛠️ 선생님 전용 도구")
        
        if not st.session_state["teacher_authenticated"]:
            st.markdown("🔒 **선생님 모드 잠금 상태**")
            with st.form("teacher_login_form"):
                teacher_pw_input = st.text_input("비밀번호 입력", type="password", placeholder="비밀번호를 입력하세요")
                login_submit = st.form_submit_button("로그인", type="primary")
                if login_submit:
                    if teacher_pw_input == "1234":
                        st.session_state["teacher_authenticated"] = True
                        st.success("인증 성공!")
                        st.rerun()
                    else:
                        st.error("비밀번호가 틀렸습니다.")
            st.stop()
        else:
            st.success("👑 선생님 모드 활성화됨")
            if st.button("로그아웃 (잠금)", use_container_width=True):
                st.session_state["teacher_authenticated"] = False
                st.rerun()
            
            st.divider()
            st.markdown("데이터를 안전하게 정기적으로 백업하세요.")
            excel_data = create_excel_backup()
            st.download_button(
                label="📥 전체 데이터 엑셀 백업하기",
                data=excel_data,
                file_name=f"mathpro_backup_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        st.divider()

    st.subheader("👥 학생 선택 및 관리")
    
    if student_list:
        selected_student = st.selectbox("확인할 학생을 선택하세요", student_list)
    else:
        selected_student = None
        st.warning("등록된 학생이 없습니다. 아래 '학생 관리 설정'에서 학생을 먼저 추가해 주세요!")

    with st.expander("⚙️ 학생 관리 및 링크 설정 (학생 추가/삭제, 구글 드라이브, 링크 복사)", expanded=False):
        col_s2, col_s3 = st.columns(2)
        with col_s2:
            with st.form("add_student_inline_form"):
                new_s_name = st.text_input("새 학생 이름")
                if st.form_submit_button("➕ 학생 등록", type="primary"):
                    if new_s_name.strip():
                        if add_student(new_s_name.strip()):
                            st.success("등록 완료!")
                            st.rerun()
                        else:
                            st.warning("이미 존재하는 이름입니다.")
                    else:
                        st.error("이름을 입력하세요.")
        with col_s3:
            if selected_student:
                st.write(f"현재 선택: **{selected_student}**")
                if st.button("🗑️ 선택 학생 삭제", type="secondary"):
                    delete_student(selected_student)
                    st.success("삭제되었습니다!")
                    st.rerun()

        if selected_student:
            st.divider()
            current_url = get_student_drive_url(selected_student)
            with st.form(f"drive_url_form_{selected_student}"):
                new_drive_url = st.text_input("구글 드라이브 폴더 공유 URL 입력", value=current_url, placeholder="https://drive.google.com/drive/folders/...")
                if st.form_submit_button("💾 드라이브 링크 저장"):
                    update_student_drive_url(selected_student, new_drive_url.strip())
                    st.success("저장되었습니다!")
                    st.rerun()

        if student_list:
            st.divider()
            st.markdown("##### 🔗 학생별 전용 페이지 링크 복사")
            try:
                base_url = st.context.headers.get("Host", "")
                base_url = f"https://{base_url}" if base_url else "https://speakprooh-dev-mathpro-app-4byisa.streamlit.app"
            except:
                base_url = "https://speakprooh-dev-mathpro-app-4byisa.streamlit.app"

            for s in student_list:
                personal_link = f"{base_url}/?student={s}"
                st.text_input(f"👤 {s} 학생 링크", value=personal_link, key=f"link_txt_{s}", disabled=True)

    st.divider()

    st.markdown("### ⚙️ 통합 관리 대시보드")
    
    t_cfg_student, t_cfg_notice, t_cfg_hw, t_cfg_curriculum, t_cfg_wrong, t_cfg_matrix, t_cfg_links = st.tabs([
        f"👤 1. [개별] {selected_student if selected_student else '학생없음'}", 
        "📢 2. 공지사항 관리",
        "📅 3. 개별 과제 관리", 
        "📚 4. 커리큘럼 진도 배정", 
        "🔍 5. 오답노트 모아보기",
        "📊 6. 전체 숙제 매트릭스",
        "🎥 7. 해설 링크 관리"
    ])

    # [탭 1] 선택한 학생 개별 관리
    with t_cfg_student:
        if selected_student:
            st.markdown(f"#### 🎯 **{selected_student}** 학생 종합 현황 및 진도 관리")
            
            s_milestones = get_student_milestones(selected_student)
            s_m_progress = get_milestone_progress(selected_student)
            s_completed_m = sum(1 for m in s_milestones if s_m_progress.get(m[0], False))
            s_total_m = len(s_milestones)
            s_percent = int((s_completed_m / s_total_m) * 100) if s_total_m > 0 else 0
            
            all_s_hws = get_all_student_homework(selected_student)
            s_h_progress = get_student_homework_progress(selected_student)
            s_completed_h = sum(1 for h in all_s_hws if s_h_progress.get(h[0], False))
            s_total_h = len(all_s_hws)
            s_h_percent = int((s_completed_h / s_total_h) * 100) if s_total_h > 0 else 0

            conn_w = sqlite3.connect("mathpro_roadmap.db")
            c_w = conn_w.cursor()
            c_w.execute("SELECT SUM(LENGTH(numbers_text) - LENGTH(REPLACE(numbers_text, ',', '')) + 1) FROM student_wrong_entries WHERE student_name = ? AND numbers_text != ''", (selected_student,))
            w_count_row = c_w.fetchone()
            conn_w.close()
            total_wrong_cnt = w_count_row[0] if w_count_row and w_count_row[0] else 0

            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric(label="🎯 개념 진도", value=f"{s_percent}%", delta=f"{s_completed_m}/{s_total_m}")
            with col_m2:
                st.metric(label="📚 숙제 완료", value=f"{s_h_percent}%", delta=f"{s_completed_h}/{s_total_h}")
            with col_m3:
                st.metric(label="💬 오답 문항", value=f"{int(total_wrong_cnt)}개")

            st.divider()
            st.progress(s_percent / 100 if s_total_m > 0 else 0)
            
            st.markdown("##### 📘 단원별 진도 현황 및 실시간 자동 저장")
            st.success("💡 **자동 저장 적용 완료:** 체크박스를 누르는 즉시 실시간으로 자동 저장됩니다!")

            if s_milestones:
                grouped_t_milestones = {}
                for m_id, sub, ch, t_name, v_url in s_milestones:
                    key = (sub, ch)
                    if key not in grouped_t_milestones:
                        grouped_t_milestones[key] = []
                    grouped_t_milestones[key].append((m_id, t_name, v_url))

                for (sub, ch), items in grouped_t_milestones.items():
                    done_cnt = sum(1 for m_id, _, _ in items if s_m_progress.get(m_id, False))
                    exp_title = f"[{sub}] {ch} (완료: {done_cnt}/{len(items)})"
                    
                    with st.expander(exp_title, expanded=False):
                        col_btn1, col_btn2, _ = st.columns([1, 1, 2])
                        with col_btn1:
                            if st.button("☑️ 전체 선택", key=f"t_all_on_{sub}_{ch}"):
                                for m_id, _, _ in items:
                                    save_single_milestone_progress(selected_student, m_id, True)
                                st.rerun()
                        with col_btn2:
                            if st.button("◻️ 전체 해제", key=f"t_all_off_{sub}_{ch}"):
                                for m_id, _, _ in items:
                                    save_single_milestone_progress(selected_student, m_id, False)
                                st.rerun()
                        
                        st.markdown("---")

                        for m_id, t_name, v_url in items:
                            is_done = s_m_progress.get(m_id, False)
                            val = st.checkbox(f"{t_name}", value=is_done, key=f"t_milestone_{m_id}")
                            if val != is_done:
                                save_single_milestone_progress(selected_student, m_id, val)
                                st.rerun()
                            st.divider()
            else:
                st.info("이 학생에게 배정된 진도가 없습니다.")
        else:
            st.warning("상단에서 관리할 학생을 선택해 주세요.")

    # [탭 2] 공지사항 관리
    with t_cfg_notice:
        st.markdown("#### 📢 전체 또는 학생별 공지사항 등록 및 관리")
        with st.form("add_notice_form"):
            notice_target_type = st.radio("공지 대상 선택", ["🌐 전체 공지 (모든 학생에게 표시)", "👤 특정 학생 지정 공지"], horizontal=True)
            target_student_name = st.selectbox("대상 학생 선택", student_list, key="notice_target_student") if notice_target_type == "👤 특정 학생 지정 공지" and student_list else ""
            notice_title = st.text_input("공지사항 제목", placeholder="예: 이번 주 보충 수업 안내")
            notice_content = st.text_area("공지사항 내용", placeholder="상세 내용을 입력하세요...")
            
            if st.form_submit_button("📢 공지사항 등록하기", type="primary"):
                if notice_title.strip() and notice_content.strip():
                    final_target = target_student_name if notice_target_type == "👤 특정 학생 지정 공지" else ""
                    add_notice(final_target, notice_title.strip(), notice_content.strip())
                    st.success("등록되었습니다!")
                    st.rerun()

        st.markdown("---")
        all_notices = get_all_notices()
        if all_notices:
            for n_id, n_target, n_title, n_content, n_date in all_notices:
                with st.container(border=True):
                    badge_str = f"🌐 [전체 공지]" if not n_target else f"👤 [{n_target} 학생 맞춤]"
                    col_n_info, col_n_del = st.columns([5, 1])
                    with col_n_info:
                        st.markdown(f"**{badge_str} {n_title}** <span style='font-size:12px; color:#64748B;'>(작성일: {n_date})</span>", unsafe_allow_html=True)
                        st.caption(n_content)
                    with col_n_del:
                        if st.button("🗑️", key=f"del_notice_{n_id}"):
                            delete_notice(n_id)
                            st.rerun()

    # [탭 3] 개별 과제 관리
    with t_cfg_hw:
        if selected_student:
            st.markdown(f"#### 📅 [{selected_student}] 학생 개별 과제 관리")
            with st.form("add_student_hw_form"):
                hw_date_input = st.date_input("과제 제출일", value=date.today())
                hw_text_area = st.text_area("날짜별 과제 내용 입력", placeholder="[온라인 과제]\n  - 1차시 개념 정리")
                if st.form_submit_button(f"과제 등록", type="primary"):
                    if hw_text_area.strip():
                        bulk_insert_student_homework(selected_student, str(hw_date_input), hw_text_area)
                        st.success("등록되었습니다!")
                        st.rerun()

            st.markdown("---")
            hw_dates = get_student_homework_dates(selected_student)
            hw_progress_map = get_student_homework_progress(selected_student)
            
            if hw_dates:
                selected_hw_date = st.selectbox("확인할 숙제 날짜", hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})", key="teacher_hw_date_filter")
                parent_hws = get_student_homework_by_date_parent(selected_student, selected_hw_date, parent_id=None)
                
                if parent_hws:
                    for h_id, title in parent_hws:
                        is_done = hw_progress_map.get(h_id, False)
                        with st.container(border=True):
                            col_chk, col_ttl = st.columns([1, 11])
                            with col_chk:
                                chk_val = st.checkbox("완료", value=is_done, key=f"t_hw_chk_{h_id}", label_visibility="collapsed")
                                if chk_val != is_done:
                                    save_single_homework_progress(selected_student, h_id, chk_val)
                                    st.rerun()
                            with col_ttl:
                                st.markdown(f"📌 **{title}**")
                            
                            with st.expander("🛠️ 숙제 내용 수정 / 삭제"):
                                ed_d = st.date_input("날짜 변경", value=date.fromisoformat(selected_hw_date), key=f"ed_shw_d_{h_id}")
                                ed_t = st.text_area("내용 변경", value=title, key=f"ed_shw_t_{h_id}")
                                col_ed1, col_ed2 = st.columns(2)
                                with col_ed1:
                                    if st.button("수정 저장", key=f"save_shw_{h_id}", type="primary"):
                                        update_student_homework(h_id, str(ed_d), ed_t.strip())
                                        st.success("수정되었습니다!")
                                        st.rerun()
                                with col_ed2:
                                    if st.button("숙제 삭제", key=f"del_shw_{h_id}", type="secondary"):
                                        delete_student_homework(h_id)
                                        st.success("삭제되었습니다!")
                                        st.rerun()
        else:
            st.warning("학생을 선택해 주세요.")

    # [탭 4] 커리큘럼 진도 배정
    with t_cfg_curriculum:
        subjects_data = get_subjects()
        st.markdown("#### 📂 커리큘럼 및 진도 배정")
        if selected_student:
            all_chapters = get_chapters()
            if all_chapters and subjects_data:
                assigned_chapters = {m[2] for m in get_student_milestones(selected_student)}
                with st.form("assign_chapters_form"):
                    selected_ch_ids = []
                    for sub_id, sub_name in subjects_data:
                        sub_chapters = [ch for ch in all_chapters if ch[1] == sub_name]
                        for ch_id, ch_sub, ch_name in sub_chapters:
                            if st.checkbox(f"[{sub_name}] {ch_name}", key=f"assign_ch_chk_{ch_id}"):
                                selected_ch_ids.append(ch_id)
                    if st.form_submit_button("선택한 단원 일괄 배정하기", type="primary"):
                        if selected_ch_ids:
                            assign_chapters_to_student(selected_student, selected_ch_ids)
                            st.success("배정되었습니다!")
                            st.rerun()

    # [탭 5] 오답노트 모아보기
    with t_cfg_wrong:
        st.markdown("#### 🔍 학생별 오답 취합 및 스마트 관리")
        all_students = get_students()
        if all_students:
            chk_student = st.selectbox("조회할 학생", all_students, key="chk_wrong_student")
            conn = sqlite3.connect("mathpro_roadmap.db")
            c = conn.cursor()
            c.execute("SELECT unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE student_name = ? AND numbers_text != ''", (chk_student,))
            wrong_rows = c.fetchall()
            conn.close()
            
            if wrong_rows:
                for u_code, nums_txt, u_date in wrong_rows:
                    with st.container(border=True):
                        parsed_s = parse_numbers(nums_txt)
                        if parsed_s:
                            bundled_str = f"{u_code}_({','.join([f'{n:03d}' for n in sorted(list(parsed_s))])})"
                            st.markdown(f"##### 📖 단원코드: `{u_code}`", unsafe_allow_html=True)
                            st.code(bundled_str, language="text")

    # [탭 6] 전체 숙제 매트릭스 (💡 [가독성 대폭 개선] 학생별 카드 내부에서 콤팩트하게 체크하고 수정은 우측 버튼으로 통합)
    with t_cfg_matrix:
        st.markdown("#### 📊 전체 학생 숙제 현황 및 통합 관리")
        st.info("💡 체크박스를 누르는 즉시 실시간으로 자동 저장되며, **[✏️ 수정·삭제]** 버튼을 통해 내용을 깔끔하게 관리할 수 있습니다!")
        
        all_students = get_students()
        if all_students:
            conn = sqlite3.connect("mathpro_roadmap.db")
            c = conn.cursor()
            c.execute("SELECT DISTINCT hw_date FROM student_homework ORDER BY hw_date DESC")
            all_hw_dates = [r[0] for r in c.fetchall()]
            conn.close()
            
            if all_hw_dates:
                selected_matrix_date = st.selectbox("조회 및 관리할 숙제 날짜 선택", all_hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})", key="matrix_date_sel")
                students_with_hw = [s for s in all_students if get_student_homework_by_date_parent(s, selected_matrix_date, parent_id=None)]
                
                if students_with_hw:
                    for s_name in students_with_hw:
                        with st.container(border=True):
                            # 학생 이름과 해당 학생의 숙제 관리 익스팬더를 깔끔한 한 줄로 배치
                            col_s_title, col_s_edit = st.columns([4, 1])
                            with col_s_title:
                                st.markdown(f"**👤 {s_name} 학생**")
                            with col_s_edit:
                                edit_mode = st.toggle("✏️ 수정·삭제", key=f"tgl_edit_{s_name}_{selected_matrix_date}")

                            parent_hws = get_student_homework_by_date_parent(s_name, selected_matrix_date, parent_id=None)
                            s_hw_prog = get_student_homework_progress(s_name)
                            
                            for h_id, title in parent_hws:
                                is_done = s_hw_prog.get(h_id, False)
                                sub_hws = get_student_homework_by_date_parent(s_name, selected_matrix_date, parent_id=h_id)
                                
                                # 체크박스와 과제 제목을 한 줄로 정돈
                                col_chk, col_ttl = st.columns([1, 11])
                                with col_chk:
                                    mat_chk_val = st.checkbox("완료", value=is_done, key=f"mat_chk_{h_id}", label_visibility="collapsed")
                                    if mat_chk_val != is_done:
                                        save_single_homework_progress(s_name, h_id, mat_chk_val)
                                        st.rerun()
                                with col_ttl:
                                    st.markdown(f"📌 {title}")
                                
                                if sub_hws:
                                    for s_id, s_title in sub_hws:
                                        s_done = s_hw_prog.get(s_id, False)
                                        col_s_chk, col_s_ttl = st.columns([1, 11])
                                        with col_s_chk:
                                            mat_s_chk_val = st.checkbox("완료", value=s_done, key=f"mat_chk_{s_id}", label_visibility="collapsed")
                                            if mat_s_chk_val != s_done:
                                                save_single_homework_progress(s_name, s_id, mat_s_chk_val)
                                                st.rerun()
                                        with col_s_ttl:
                                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;└ {s_title}")

                                # ✏️ 수정·삭제 토글이 켜졌을 때만 나타나는 깔끔한 수정 영역
                                if edit_mode:
                                    with st.container(border=True):
                                        st.caption(f"🔧 '{title}' 과제 수정 및 삭제")
                                        ed_mat_d = st.date_input("날짜 변경", value=date.fromisoformat(selected_matrix_date), key=f"mat_ed_d_{h_id}")
                                        ed_mat_t = st.text_area("내용 변경", value=title, key=f"mat_ed_t_{h_id}")
                                        col_m_btn1, col_m_btn2 = st.columns(2)
                                        with col_m_btn1:
                                            if st.button("💾 변경사항 저장", key=f"mat_save_btn_{h_id}", type="primary"):
                                                update_student_homework(h_id, str(ed_mat_d), ed_mat_t.strip())
                                                st.success("수정되었습니다!")
                                                st.rerun()
                                        with col_m_btn2:
                                            if st.button("🗑️ 과제 삭제", key=f"mat_del_btn_{h_id}", type="secondary"):
                                                delete_student_homework(h_id)
                                                st.success("삭제되었습니다!")
                                                st.rerun()
                else:
                    st.info("선택한 날짜에 등록된 과제가 없습니다.")

                st.markdown("---")
                st.markdown("##### ➕ 해당 날짜에 학생별 과제 추가하기")
                with st.form("matrix_add_hw_form"):
                    target_student_add = st.selectbox("과제를 받을 학생 선택", all_students, key="mat_add_stu")
                    mat_hw_text = st.text_area("추가할 과제 내용", key="mat_add_txt", placeholder="[온라인 과제]\n  - 1차시 풀이")
                    if st.form_submit_button("선택한 학생에게 과제 추가", type="primary"):
                        if mat_hw_text.strip():
                            bulk_insert_student_homework(target_student_add, selected_matrix_date, mat_hw_text)
                            st.success("추가되었습니다!")
                            st.rerun()

    # [탭 7] 해설 링크 관리
    with t_cfg_links:
        st.markdown("#### 🎥 문제별 풀이해설 링크 관리")
        with st.form("add_problem_link_form"):
            col_pl1, col_pl2 = st.columns([1, 2])
            with col_pl1: input_full_code = st.text_input("문제 번호 (예: B1353015)")
            with col_pl2: input_video_url = st.text_input("네이버 카페 URL")
            if st.form_submit_button("➕ 개별 등록", type="primary"):
                if input_full_code.strip() and input_video_url.strip():
                    save_problem_link(input_full_code.strip(), input_video_url.strip())
                    st.success("저장되었습니다!")
                    st.rerun()

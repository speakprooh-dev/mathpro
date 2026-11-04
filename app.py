import streamlit as st
import sqlite3
from datetime import datetime, date, timedelta, timezone
import calendar
import re
import pandas as pd
import io
import os

# ==========================================
# ☁️ Supabase URL 방식 연동 설정
# ==========================================
try:
    import psycopg2
    from urllib.parse import urlparse
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

def get_db_connection():
    if SUPABASE_AVAILABLE and "supabase" in st.secrets:
        try:
            sec = st.secrets["supabase"]
            if "url" in sec:
                parsed_url = urlparse(sec["url"])
                conn = psycopg2.connect(
                    dbname=parsed_url.path[1:],
                    user=parsed_url.username,
                    password=parsed_url.password,
                    host=parsed_url.hostname,
                    port=parsed_url.port,
                    sslmode="require"
                )
                return conn, "postgres"
            elif "host" in sec:
                conn = psycopg2.connect(
                    host=sec["host"],
                    database=sec.get("database", "postgres"),
                    user=sec.get("user", "postgres"),
                    password=sec["password"],
                    port=sec.get("port", 5432),
                    sslmode="require"
                )
                return conn, "postgres"
        except Exception as e:
            pass
    
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mathpro_roadmap.db")
    return sqlite3.connect(DB_PATH), "sqlite"

def get_korean_today():
    try:
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst).date()
    except Exception:
        return date.today()

def get_cafe_search_url(unit_code, num_int):
    return "https://cafe.naver.com/mathpro2020"

def create_excel_backup():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        conn, db_type = get_db_connection()
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

def restore_from_excel(uploaded_file):
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        conn, db_type = get_db_connection()
        c = conn.cursor()
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            try:
                c.execute(f"DELETE FROM {sheet_name}")
                df.to_sql(sheet_name, conn, if_exists='append', index=False)
            except Exception:
                pass
                
        conn.commit()
        conn.close()
        return True, "데이터베이스가 엑셀 백업 파일 내용으로 성공적으로 복구되었습니다!"
    except Exception as e:
        return False, f"복구 중 오류가 발생했습니다: {str(e)}"

st.set_page_config(page_title="MathPro 학생 맞춤 학습 로드맵", page_icon="📐", layout="centered")

if "teacher_authenticated" not in st.session_state:
    st.session_state["teacher_authenticated"] = False

def get_base_url():
    try:
        base_url = st.context.headers.get("Host", "")
        if base_url:
            return f"https://{base_url}"
    except:
        pass
    return "https://speakprooh-dev-mathpro-app-4byisa.streamlit.app"

def get_weekday_kr(date_str):
    try:
        d = date.fromisoformat(date_str)
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        return weekdays[d.weekday()]
    except:
        return "날짜 확인"

def init_db():
    conn, db_type = get_db_connection()
    c = conn.cursor()
    
    if db_type == "postgres":
        c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY, drive_url TEXT DEFAULT \'\')')
        c.execute('CREATE TABLE IF NOT EXISTS subjects (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS chapters (id SERIAL PRIMARY KEY, subject TEXT NOT NULL, name TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS chapter_types (id SERIAL PRIMARY KEY, chapter_id INTEGER NOT NULL, name TEXT NOT NULL, video_url TEXT DEFAULT \'\')')
        c.execute('CREATE TABLE IF NOT EXISTS milestones (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, subject TEXT NOT NULL, chapter TEXT NOT NULL, type_name TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS homework (id SERIAL PRIMARY KEY, hw_date TEXT NOT NULL, title TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS student_homework (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, hw_date TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS daily_routines (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS homework_templates (id SERIAL PRIMARY KEY, title TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS milestone_progress (student_name TEXT, milestone_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, milestone_id))')
        c.execute('CREATE TABLE IF NOT EXISTS homework_progress (student_name TEXT, homework_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, homework_id))')
        c.execute('CREATE TABLE IF NOT EXISTS student_homework_progress (student_name TEXT, student_hw_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, student_hw_id))')
        c.execute('CREATE TABLE IF NOT EXISTS daily_routine_logs (student_name TEXT, routine_id TEXT, log_date TEXT, is_checked INTEGER, PRIMARY KEY (student_name, routine_id, log_date))')
        c.execute('CREATE TABLE IF NOT EXISTS student_wrong_entries (student_name TEXT, unit_code TEXT, numbers_text TEXT, updated_at TEXT DEFAULT \'\', PRIMARY KEY (student_name, unit_code))')
        c.execute('CREATE TABLE IF NOT EXISTS problem_links (id SERIAL PRIMARY KEY, full_code TEXT UNIQUE NOT NULL, unit_code TEXT NOT NULL, prob_num TEXT NOT NULL, video_url TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS notices (id SERIAL PRIMARY KEY, student_name TEXT DEFAULT \'\', title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)')
    else:
        c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY)')
        try:
            c.execute("ALTER TABLE students ADD COLUMN drive_url TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        c.execute('CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS chapters (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, name TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS chapter_types (id INTEGER PRIMARY KEY AUTOINCREMENT, chapter_id INTEGER NOT NULL, name TEXT NOT NULL, video_url TEXT DEFAULT \'\')')
        
        try:
            c.execute("ALTER TABLE chapter_types ADD COLUMN video_url TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        
        c.execute('CREATE TABLE IF NOT EXISTS milestones (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, subject TEXT NOT NULL, chapter TEXT NOT NULL, type_name TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS homework (id INTEGER PRIMARY KEY AUTOINCREMENT, hw_date TEXT NOT NULL, title TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS student_homework (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, hw_date TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL)')
        
        try:
            c.execute("ALTER TABLE student_homework ADD COLUMN parent_id INTEGER DEFAULT NULL")
        except sqlite3.OperationalError:
            pass

        c.execute('CREATE TABLE IF NOT EXISTS daily_routines (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS homework_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS milestone_progress (student_name TEXT, milestone_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, milestone_id))')
        c.execute('CREATE TABLE IF NOT EXISTS homework_progress (student_name TEXT, homework_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, homework_id))')
        c.execute('CREATE TABLE IF NOT EXISTS student_homework_progress (student_name TEXT, student_hw_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, student_hw_id))')
        c.execute('CREATE TABLE IF NOT EXISTS daily_routine_logs (student_name TEXT, routine_id TEXT, log_date TEXT, is_checked INTEGER, PRIMARY KEY (student_name, routine_id, log_date))')
        c.execute('CREATE TABLE IF NOT EXISTS student_wrong_entries (student_name TEXT, unit_code TEXT, numbers_text TEXT, updated_at TEXT DEFAULT \'\', PRIMARY KEY (student_name, unit_code))')
        
        try:
            c.execute("ALTER TABLE student_wrong_entries ADD COLUMN updated_at TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        c.execute('CREATE TABLE IF NOT EXISTS problem_links (id INTEGER PRIMARY KEY AUTOINCREMENT, full_code TEXT UNIQUE NOT NULL, unit_code TEXT NOT NULL, prob_num TEXT NOT NULL, video_url TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS notices (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT DEFAULT \'\', title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)')

    c.execute("SELECT COUNT(*) FROM subjects")
    if c.fetchone()[0] == 0:
        default_subjects = ["수학(상)", "수학(하)", "수학Ⅰ", "수학Ⅱ", "미적분", "확률과 통계"]
        for sub in default_subjects:
            try:
                c.execute("INSERT INTO subjects (name) VALUES (?)", (sub,))
            except Exception:
                pass
                
    conn.commit()
    conn.close()

init_db()

def get_students():
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM students ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_student_drive_url(name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT drive_url FROM students WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""

def update_student_drive_url(name, drive_url):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE students SET drive_url = ? WHERE name = ?", (drive_url, name))
    conn.commit()
    conn.close()

def add_student(name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO students (name, drive_url) VALUES (?, ?)", (name, ""))
        conn.commit()
        success = True
    except Exception:
        success = False
    conn.close()
    return success

def delete_student(name):
    conn, _ = get_db_connection()
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
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM subjects ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def add_subject(name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO subjects (name) VALUES (?)", (name,))
        conn.commit()
        success = True
    except Exception:
        success = False
    conn.close()
    return success

def get_chapters():
    conn, _ = get_db_connection()
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

def get_chapter_types(chapter_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, video_url FROM chapter_types WHERE chapter_id = ?", (chapter_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def save_problem_link(full_code, video_url):
    full_code = full_code.strip().upper()
    if len(full_code) < 4:
        return False
    unit_code = full_code[:-3]
    prob_num = full_code[-3:]
    
    conn, _ = get_db_connection()
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
    conn, _ = get_db_connection()
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
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT full_code, video_url FROM problem_links WHERE unit_code = ? ORDER BY full_code", (unit_code.upper(),))
    rows = c.fetchall()
    conn.close()
    return rows

def get_problem_link_by_full(full_code):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT video_url FROM problem_links WHERE full_code = ?", (full_code.upper(),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def get_all_problem_links():
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, full_code, video_url, unit_code FROM problem_links ORDER BY unit_code, full_code")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_problem_link(link_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM problem_links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()

def add_notice(student_name, title, content):
    conn, _ = get_db_connection()
    c = conn.cursor()
    today_str = str(get_korean_today())
    c.execute("INSERT INTO notices (student_name, title, content, created_at) VALUES (?, ?, ?, ?)", (student_name, title, content, today_str))
    conn.commit()
    conn.close()

def get_notices_for_student(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, title, content, created_at, student_name FROM notices WHERE student_name = '' OR student_name = ? ORDER BY id DESC", (student_name,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_notices():
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, student_name, title, content, created_at FROM notices ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_notice(notice_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
    conn.commit()
    conn.close()

def get_student_daily_routines_parent(student_name, parent_id=None):
    conn, _ = get_db_connection()
    c = conn.cursor()
    if parent_id is None:
        c.execute("SELECT id, title FROM daily_routines WHERE student_name = ? AND (parent_id IS NULL) ORDER BY id", (student_name,))
    else:
        c.execute("SELECT id, title FROM daily_routines WHERE student_name = ? AND parent_id = ? ORDER BY id", (student_name, parent_id))
    rows = c.fetchall()
    conn.close()
    return rows

def bulk_insert_daily_routines(student_name, text_data):
    conn, _ = get_db_connection()
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
            try:
                c.execute("SELECT last_insert_rowid()")
                row = c.fetchone()
                current_parent_id = row[0] if row else None
            except Exception:
                pass
        added_count += 1
    conn.commit()
    conn.close()
    return added_count

def delete_daily_routine(r_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM daily_routines WHERE id = ? OR parent_id = ?", (r_id, r_id))
    c.execute("DELETE FROM daily_routine_logs WHERE routine_id = ? OR routine_id LIKE ?", (str(r_id), f"{r_id}_%"))
    conn.commit()
    conn.close()

def save_daily_routine_logs(student_name, log_date, routine_checked_dict):
    conn, _ = get_db_connection()
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
    conn, _ = get_db_connection()
    c = conn.cursor()
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year+1}-01-01" if month == 12 else f"{year}-{month+1:02d}-01"
    c.execute("SELECT routine_id, log_date, is_checked FROM daily_routine_logs WHERE student_name = ? AND log_date >= ? AND log_date < ?", (student_name, start_date, end_date))
    rows = c.fetchall()
    conn.close()
    log_map = {}
    for r_id, l_date, val in rows:
        log_map[(str(r_id), l_date)] = bool(val)
    return log_map

def get_student_daily_logs_by_date(student_name, target_date_str):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT routine_id, is_checked FROM daily_routine_logs WHERE student_name = ? AND log_date = ?", (student_name, target_date_str))
    rows = c.fetchall()
    conn.close()
    log_map = {}
    for r_id, val in rows:
        log_map[(str(r_id), target_date_str)] = bool(val)
    return log_map

def get_routine_completion_rate(student_name, days_limit=7):
    conn, _ = get_db_connection()
    c = conn.cursor()
    
    today_obj = get_korean_today()
    start_date_str = str(today_obj - timedelta(days=days_limit - 1))
    today_str = str(today_obj)
    
    c.execute("SELECT COUNT(*) FROM daily_routines WHERE student_name = ?", (student_name,))
    total_routines_count = c.fetchone()[0]
    
    if total_routines_count == 0:
        conn.close()
        return 0, 0, 0
    
    total_expected = total_routines_count * days_limit
    
    c.execute("""
        SELECT COUNT(*) FROM daily_routine_logs 
        WHERE student_name = ? AND log_date >= ? AND log_date <= ? AND is_checked = 1
    """, (student_name, start_date_str, today_str))
    completed_count = c.fetchone()[0]
    conn.close()
    
    rate = int((completed_count / total_expected) * 100) if total_expected > 0 else 0
    return rate, completed_count, total_expected

def get_student_recent_logs_range(student_name, days_limit=7):
    conn, _ = get_db_connection()
    c = conn.cursor()
    today_obj = get_korean_today()
    start_date_str = str(today_obj - timedelta(days=days_limit - 1))
    today_str = str(today_obj)
    
    c.execute("SELECT routine_id, log_date, is_checked FROM daily_routine_logs WHERE student_name = ? AND log_date >= ? AND log_date <= ?", (student_name, start_date_str, today_str))
    rows = c.fetchall()
    conn.close()
    log_map = {}
    for r_id, l_date, val in rows:
        log_map[(str(r_id), l_date)] = bool(val)
    return log_map

def get_homework_templates():
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, title FROM homework_templates ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def add_homework_template(title):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO homework_templates (title) VALUES (?)", (title,))
    conn.commit()
    conn.close()

def delete_homework_template(t_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM homework_templates WHERE id = ?", (t_id,))
    conn.commit()
    conn.close()

def get_student_milestones(student_name):
    conn, _ = get_db_connection()
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
    conn, _ = get_db_connection()
    c = conn.cursor()
    for chapter_id in chapter_ids:
        c.execute("SELECT subject, name FROM chapters WHERE id = ?", (chapter_id,))
        ch_row = c.fetchone()
        if not ch_row:
            continue
        sub, ch_name = ch_row
        c.execute("SELECT name FROM chapter_types WHERE chapter_id = ?", (chapter_id,))
        type_rows = c.fetchall()
        types_to_add = [r[0] for r in type_rows] or ["단원 기본 학습"]
        c.execute("SELECT chapter, type_name FROM milestones WHERE student_name = ?", (student_name,))
        existing = {(r[0], r[1]) for r in c.fetchall()}
        for t_name in types_to_add:
            if (ch_name, t_name) not in existing:
                c.execute("INSERT INTO milestones (student_name, subject, chapter, type_name) VALUES (?, ?, ?, ?)", (student_name, sub, ch_name, t_name))
    conn.commit()
    conn.close()

def get_student_homework_dates(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT hw_date FROM student_homework WHERE student_name = ? ORDER BY hw_date DESC", (student_name,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_student_homework_by_date_parent(student_name, hw_date, parent_id=None):
    conn, _ = get_db_connection()
    c = conn.cursor()
    if parent_id is None:
        c.execute("SELECT id, title FROM student_homework WHERE student_name = ? AND hw_date = ? AND (parent_id IS NULL) ORDER BY id", (student_name, hw_date))
    else:
        c.execute("SELECT id, title FROM student_homework WHERE student_name = ? AND hw_date = ? AND parent_id = ? ORDER BY id", (student_name, hw_date, parent_id))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_student_homework(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, hw_date, title, parent_id FROM student_homework WHERE student_name = ? ORDER BY hw_date DESC, id DESC", (student_name,))
    rows = c.fetchall()
    conn.close()
    return rows

def bulk_insert_student_homework(student_name, hw_date, text_data):
    conn, _ = get_db_connection()
    c = conn.cursor()
    lines = text_data.strip().split('\n')
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
            c.execute("INSERT INTO student_homework (student_name, hw_date, title, parent_id) VALUES (?, ?, ?, ?)", (student_name, hw_date, title, current_parent_id))
        else:
            c.execute("INSERT INTO student_homework (student_name, hw_date, title, parent_id) VALUES (?, ?, ?, NULL)", (student_name, hw_date, title))
            try:
                c.execute("SELECT last_insert_rowid()")
                row = c.fetchone()
                current_parent_id = row[0] if row else None
            except Exception:
                pass
    conn.commit()
    conn.close()

def update_student_homework_by_date(student_name, hw_date, text_data):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM student_homework WHERE student_name = ? AND hw_date = ?", (student_name, hw_date))
    c.execute("DELETE FROM student_homework_progress WHERE student_hw_id NOT IN (SELECT id FROM student_homework)")
    conn.commit()
    conn.close()
    bulk_insert_student_homework(student_name, hw_date, text_data)

def delete_student_homework_date(student_name, hw_date):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM student_homework WHERE student_name = ? AND hw_date = ?", (student_name, hw_date))
    conn.commit()
    conn.close()

def get_milestone_progress(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT milestone_id, is_checked FROM milestone_progress WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}

def get_student_homework_progress(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT student_hw_id, is_checked FROM student_homework_progress WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}

def save_single_milestone_progress(student_name, milestone_id, val):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO milestone_progress (student_name, milestone_id, is_checked)
        VALUES (?, ?, ?)
        ON CONFLICT(student_name, milestone_id) DO UPDATE SET is_checked = ?
    ''', (student_name, milestone_id, int(val), int(val)))
    conn.commit()
    conn.close()

def save_single_homework_progress(student_name, student_hw_id, val):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO student_homework_progress (student_name, student_hw_id, is_checked)
        VALUES (?, ?, ?)
        ON CONFLICT(student_name, student_hw_id) DO UPDATE SET is_checked = ?
    ''', (student_name, student_hw_id, int(val), int(val)))
    conn.commit()
    conn.close()

def get_student_wrong_entry(student_name, unit_code):
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT numbers_text FROM student_wrong_entries WHERE student_name = ? AND unit_code = ?", (student_name, unit_code))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def save_student_wrong_entry(student_name, unit_code, numbers_text):
    conn, _ = get_db_connection()
    c = conn.cursor()
    today_str = str(get_korean_today())
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

st.title("학생 맞춤 학습 로드맵")
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

    with st.expander("📖 💡 [어플 100% 활용 가이드] 꼭 읽어보세요!", expanded=False):
        st.markdown("""
        - **📘 개념 진도 탭**: 선생님이 배정해주신 단원별 개념 학습 현황을 확인하고, 학습이 완료되면 체크박스를 눌러주세요. `🎥 개념해설` 버튼을 통해 복습 영상도 언제든 시청할 수 있습니다.
        - **📚 날짜별 숙제 탭**: 날짜별로 부여된 숙제와 매일 반복 루틴 과제를 확인하고, **과제를 완료할 때마다 체크박스를 꾹 눌러 완료 상태로 기록**해 주세요! (달성률 대시보드에 실시간 반영됩니다.)
        - **💬 오답·질문 관리 탭**: 틀린 문제의 번호나 단원코드를 입력해 나만의 오답 노트를 만들고, 궁금한 문제의 해설 영상 바로가기 링크를 쉽고 빠르게 찾아볼 수 있습니다.
        """)

    student_notices = get_notices_for_student(selected_student)
    if student_notices:
        with st.expander("📢 [중요 공지사항] 확인하기", expanded=True):
            for n_id, n_title, n_content, n_date, n_target in student_notices:
                target_badge = "🌐 전체" if not n_target else f"👤 {n_target}"
                st.markdown(
                    f'<div style="background-color: rgba(30, 41, 59, 0.5); border-left: 3px solid #38BDF8; padding: 8px 12px; border-radius: 4px; margin-bottom: 8px;">'
                    f'<div style="font-size: 12px; color: #94A3B8;">{target_badge} | {n_date}</div>'
                    f'<div style="font-size: 14px; font-weight: bold; color: #F8FAFC;">📌 {n_title}</div>'
                    f'<div style="font-size: 13px; color: #E2E8F0; white-space: pre-wrap; margin-top: 4px;">{n_content}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

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

    # -------------------------------------------------------------------------
    # 📊 최상단 통합 학습 성취도 대시보드
    # -------------------------------------------------------------------------
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

    # 상단 대시보드 카드 안에서 기간 선택 및 상세 실천 기록(Expander) 통합 제공 (기본 7일)
    with st.container(border=True):
        col_rt_title, col_rt_opt = st.columns([2, 1])
        with col_rt_title:
            st.markdown("**🔥 루틴 달성률**")
        with col_rt_opt:
            range_option = st.selectbox(
                "조회 기간", 
                ["최근 1주 (7일)", "최근 2주 (14일)", "최근 3주 (21일)", "최근 4주 (28일)"], 
                index=0,
                key="student_routine_range_select",
                label_visibility="collapsed"
            )
        
        days_map = {
            "최근 1주 (7일)": 7,
            "최근 2주 (14일)": 14,
            "최근 3주 (21일)": 21,
            "최근 4주 (28일)": 28
        }
        selected_days = days_map[range_option]
        r_rate, r_completed, r_total = get_routine_completion_rate(selected_student, selected_days)
        
        st.metric(
            label=f"{range_option} 달성률", 
            value=f"{r_rate}%", 
            delta=f"총 {r_total}개 중 {r_completed}개 완료"
        )
        st.progress(r_rate / 100 if r_rate <= 100 else 1.0)

        # 카드 안쪽에 접힌 상태(Expander)로 선택한 기간에 맞춘 루틴 상세 실천 기록 배치
        today_obj = get_korean_today()
        daily_parents = get_student_daily_routines_parent(selected_student, parent_id=None)
        
        with st.expander(f"📅 루틴 상세 실천 기록 보기 ({range_option})", expanded=False):
            recent_logs_map = get_student_recent_logs_range(selected_student, selected_days)
            
            for i in range(selected_days):
                target_d = today_obj - timedelta(days=i)
                d_str = str(target_d)
                w_name = get_weekday_kr(d_str)[:1]
                is_today = (d_str == str(today_obj))
                
                day_checked_count = sum(1 for r_id, _ in daily_parents if recent_logs_map.get((str(r_id), d_str), False))
                total_r_count = len(daily_parents)
                
                status_ox = "⭕ O" if (total_r_count > 0 and day_checked_count == total_r_count) else "❌ X"
                
                # 배경은 깔끔한 흰색(#FFFFFF), 글자는 진한 검정색(#111827)으로 변경하여 라이트모드 강제 반전 완벽 차단!
                bg_color = "#F0FDF4" if is_today else "#FFFFFF"
                border_highlight = "border: 2px solid #03C75A;" if is_today else "border: 1px solid #CBD5E1;"
                today_tag = " (오늘)" if is_today else ""
                
                st.markdown(
                    f"<div style='padding: 10px 14px; margin-bottom: 6px; border-radius: 6px; {border_highlight} background-color: {bg_color}; display: flex; justify-content: space-between; align-items: center;'>"
                    f"<span style='font-size: 14px; font-weight: bold; color: #111827 !important; -webkit-text-fill-color: #111827 !important;'>{target_d.month}월 {target_d.day}일 ({w_name}){today_tag}</span>"
                    f"<span style='font-size: 13px; font-weight: bold; color: #03C75A !important; -webkit-text-fill-color: #03C75A !important;'>{status_ox} ({day_checked_count}/{total_r_count})</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📘 개념 진도", "📚 날짜별 숙제", "💬 오답·질문 관리"])

    with tab1:
        st.markdown("### 📘 나의 개념 학습 목록")
        if milestones:
            grouped_s_milestones = {}
            for m_id, sub, ch, t_name, v_url in milestones:
                key = (sub, ch)
                if key not in grouped_s_milestones:
                    grouped_s_milestones[key] = []
                grouped_s_milestones[key].append((m_id, t_name, v_url))

            for (sub, ch), items in grouped_s_milestones.items():
                done_cnt = sum(1 for m_id, _, _ in items if m_progress.get(m_id, False))
                with st.expander(f"[{sub}] {ch} (완료: {done_cnt}/{len(items)})", expanded=False):
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
                                st.markdown(f'<a href="{v_url}" target="_blank" style="display:inline-block; background-color:#F1F5F9; color:#0284C7; padding:4px 10px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; margin-top:4px; border:1px solid #CBD5E1;">🎥 개념해설</a>', unsafe_allow_html=True)
        else:
            st.info("아직 배정된 개념 학습 목록이 없습니다.")

    with tab2:
        # -------------------------------------------------------------------------
        # [구역 1] 매일 반복 루틴 체크 (행동 영역)
        # -------------------------------------------------------------------------
        st.markdown("### 🔥 매일 반복 루틴 체크")
        st.caption("오늘 해야 할 루틴을 완료하고 체크박스를 눌러주세요.")

        daily_parents = get_student_daily_routines_parent(selected_student, parent_id=None)
        if daily_parents:
            today_obj = get_korean_today()
            today_str = str(today_obj)
            current_day_logs = get_student_daily_logs_by_date(selected_student, today_str)
            
            with st.container(border=True):
                st.markdown(f"**오늘 ({today_str}) 루틴 항목**")
                st.markdown("---")

                daily_routine_checked_dict = {}
                for r_id, r_title in daily_parents:
                    r_subs = get_student_daily_routines_parent(selected_student, parent_id=r_id)
                    default_val = current_day_logs.get((str(r_id), today_str), False)
                    if r_subs:
                        st.markdown(f"**{r_title}**")
                        daily_routine_checked_dict[str(r_id)] = st.checkbox(f"{r_title} (전체 대표)", value=default_val, key=f"s_daily_{r_id}")
                        for sr_id, sr_title in r_subs:
                            daily_routine_checked_dict[str(sr_id)] = st.checkbox(f"&nbsp;&nbsp;&nbsp;&nbsp;└ {sr_title}", value=current_day_logs.get((str(sr_id), today_str), False), key=f"s_daily_{sr_id}")
                    else:
                        daily_routine_checked_dict[str(r_id)] = st.checkbox(f"{r_title}", value=default_val, key=f"s_daily_{r_id}")
                    st.divider()
            if daily_routine_checked_dict:
                save_daily_routine_logs(selected_student, today_str, daily_routine_checked_dict)

        # -------------------------------------------------------------------------
        # [구역 2] 날짜별 개별 숙제
        # -------------------------------------------------------------------------
        if hw_dates:
            st.markdown("")
            st.markdown("---")
            st.markdown("### 📚 날짜별 개별 숙제")
            st.caption("선생님이 배정해주신 날짜별 숙제를 확인하고 완료 체크를 해보세요.")
            
            selected_date = st.selectbox("확인할 숙제 날짜 선택", hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
            parent_hws = get_student_homework_by_date_parent(selected_student, selected_date, parent_id=None)
            
            with st.container(border=True):
                for h_id, title in parent_hws:
                    default_val = h_progress.get(h_id, False)
                    sub_hws = get_student_homework_by_date_parent(selected_student, selected_date, parent_id=h_id)
                    if sub_hws:
                        st.markdown(f"**{title}**")
                        if st.checkbox(f"{title} (전체 대표)", value=default_val, key=f"s_hw_{h_id}") != default_val:
                            save_single_homework_progress(selected_student, h_id, st.session_state[f"s_hw_{h_id}"])
                            st.rerun()
                        for s_id, s_title in sub_hws:
                            s_default = h_progress.get(s_id, False)
                            if st.checkbox(f"&nbsp;&nbsp;&nbsp;&nbsp;└ {s_title}", value=s_default, key=f"s_hw_{s_id}") != s_default:
                                save_single_homework_progress(selected_student, s_id, st.session_state[f"s_hw_{s_id}"])
                                st.rerun()
                    else:
                        if st.checkbox(f"{title}", value=default_val, key=f"s_hw_{h_id}") != default_val:
                            save_single_homework_progress(selected_student, h_id, st.session_state[f"s_hw_{h_id}"])
                            st.rerun()

    with tab3:
        st.markdown("### 💬 오답 및 질문 관리")
        
        with st.container(border=True):
            st.markdown("##### 🔍 1. 해설 영상 즉시 검색하기")
            st.caption("궁금한 문제 번호 전체(예: B1353015) 또는 단원코드만(예: B1353) 입력하면 즉시 해설 영상 또는 해당 단원 해설 목록으로 이동합니다.")
            search_prob_input = st.text_input("문제 번호 또는 단원코드 입력", placeholder="예: B1353015 또는 B1353").strip().upper()
            if search_prob_input:
                if len(search_prob_input) >= 7:
                    matched_url = get_problem_link_by_full(search_prob_input)
                    if matched_url:
                        st.success(f"📌 **{search_prob_input}** 문제 해설 링크가 확인되었습니다!")
                        st.markdown(f'<a href="{matched_url}" target="_blank" style="display:block; background-color:#F1F5F9; color:#0F172A; padding:12px; border-radius:8px; text-decoration:none; font-weight:bold; text-align:center; border:1px solid #CBD5E1;">🎥 풀이 영상 바로가기 ➔</a>', unsafe_allow_html=True)
                    else:
                        st.warning(f"'{search_prob_input}'에 등록된 해설 링크가 없습니다.")
                else:
                    unit_results = get_problem_links_by_unit(search_prob_input)
                    if unit_results:
                        st.markdown(f"##### 📂 `{search_prob_input}` 단원 해설 목록 ({len(unit_results)}개)")
                        for f_code, v_url in unit_results:
                            st.markdown(f'<a href="{v_url}" target="_blank" style="display:block; background-color:#F1F5F9; color:#0F172A; padding:10px; border-radius:6px; text-decoration:none; margin-bottom:6px; border:1px solid #CBD5E1;">📌 {f_code} &nbsp;&nbsp;<span style="color:#0284C7;">🎥 해설 영상 ➔</span></a>', unsafe_allow_html=True)
                    else:
                        st.info("단원코드 형식으로 올바르게 입력해 주세요.")

        st.markdown("")
        with st.container(border=True):
            st.markdown("##### 📝 2. 나의 오답 및 질문 번호 저장/수정")
            st.caption("틀린 문제의 단원코드와 번호를 입력하여 나만의 오답 노트를 관리하세요.")
            
            entered_unit_code = st.text_input("단원코드 입력 (예: B1353)", placeholder="예: B1353").strip().upper()
            target_code = entered_unit_code if entered_unit_code else "B1353"

            col_add, col_del = st.columns(2)
            with col_add: add_txt = st.text_input("➕ 추가할 번호 (예: 15, 35)")
            with col_del: del_txt = st.text_input("➖ 삭제할 번호 (예: 7)")
            
            if st.button("💾 오답 목록 저장하기", type="primary", use_container_width=True):
                if entered_unit_code:
                    saved_pre = parse_numbers(get_student_wrong_entry(selected_student, target_code))
                    final_nums = (saved_pre | parse_numbers(add_txt)) - parse_numbers(del_txt)
                    save_student_wrong_entry(selected_student, target_code, ", ".join(map(str, sorted(list(final_nums)))))
                    st.success("저장되었습니다!")
                    st.rerun()
                else:
                    st.warning("단원코드를 먼저 입력해 주세요.")

            st.markdown("---")

            conn, _ = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT unit_code, numbers_text FROM student_wrong_entries WHERE student_name = ? AND numbers_text != '' ORDER BY unit_code", (selected_student,))
            saved_rows = c.fetchall()
            conn.close()
            
            saved_units_list = [r[0] for r in saved_rows]
            
            selected_existing_unit = st.selectbox(
                "📂 내가 저장한 단원 선택해서 보기", 
                ["-- 저장된 단원을 선택하세요 --"] + saved_units_list,
                key="saved_unit_select_box"
            )
            
            view_target_code = ""
            if selected_existing_unit and selected_existing_unit != "-- 저장된 단원을 선택하세요 --":
                view_target_code = selected_existing_unit

            if view_target_code:
                existing_wrong = get_student_wrong_entry(selected_student, view_target_code)
                if existing_wrong:
                    st.markdown(f"##### 📌 `{view_target_code}` 단원 오답 및 해설 바로가기")
                    parsed_nums = parse_numbers(existing_wrong)
                    if parsed_nums:
                        for n in sorted(list(parsed_nums)):
                            full_code = f"{view_target_code}{n:03d}"
                            v_url = get_problem_link_by_full(full_code)
                            if v_url:
                                st.markdown(f'<a href="{v_url}" target="_blank" style="display:block; background-color:#F1F5F9; color:#0F172A; border:1px solid #CBD5E1; padding:10px 14px; border-radius:6px; text-decoration:none; font-weight:bold; margin-bottom:6px;">📌 {full_code} &nbsp;&nbsp;🎥 해설 영상 바로가기 ➔</a>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<div style="background-color:#F1F5F9; color:#64748B; border:1px solid #CBD5E1; padding:10px 14px; border-radius:6px; margin-bottom:6px; font-weight:bold;">📌 {full_code} &nbsp;&nbsp;<span style="font-size:12px; color:#94A3B8;">(해설 링크 준비중)</span></div>', unsafe_allow_html=True)
                else:
                    st.info(f"현재 등록된 오답이 없습니다.")

# 2. [선생님 전용 관리 모드]
else:
    with st.sidebar:
        st.markdown("### 🛠️ 선생님 전용 도구")
        if not st.session_state["teacher_authenticated"]:
            st.markdown("🔒 **선생님 모드 잠금 상태**")
            with st.form("teacher_login_form"):
                teacher_pw_input = st.text_input("비밀번호 입력", type="password")
                if st.form_submit_button("로그인", type="primary"):
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
            
            st.markdown("##### 📥/📤 데이터 백업 및 복구")
            st.download_button(
                label="📥 전체 데이터 엑셀 백업하기",
                data=create_excel_backup(),
                file_name=f"mathpro_backup_{get_korean_today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
            with st.expander("🔄 엑셀 파일로 데이터 복구하기"):
                uploaded_backup = st.file_uploader("백업 엑셀 파일(.xlsx) 선택", type=["xlsx"])
                if uploaded_backup is not None:
                    if st.button("🚀 엑셀 데이터로 DB 복구 실행", type="primary", use_container_width=True):
                        success, msg = restore_from_excel(uploaded_backup)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
        st.divider()

    with st.expander("⚙️ 학생 관리 및 전용 링크 복사 설정", expanded=False):
        col_s2, col_s3 = st.columns(2)
        with col_s2:
            with st.form("add_student_inline_form"):
                new_s_name = st.text_input("새 학생 이름")
                if st.form_submit_button("➕ 학생 등록", type="primary"):
                    if new_s_name.strip() and add_student(new_s_name.strip()):
                        st.success("등록 완료!")
                        st.rerun()
        with col_s3:
            if student_list:
                del_target_student = st.selectbox("삭제할 학생 선택", student_list, key="del_stu_box")
                if st.button("🗑️ 선택 학생 삭제"):
                    delete_student(del_target_student)
                    st.success("삭제되었습니다!")
                    st.rerun()

        if student_list:
            st.divider()
            base_url = get_base_url()
            for s in student_list:
                personal_link = f"{base_url}/?student={s}"
                with st.container(border=True):
                    st.markdown(f"👤 **<a href='{personal_link}' target='_blank' style='color:#0284C7; text-decoration:none;'>{s}</a>**", unsafe_allow_html=True)
                    st.code(personal_link, language="text")

    st.divider()
    st.markdown("### ⚙️ 통합 관리 대시보드")
    
    t_cfg_student, t_cfg_notice, t_cfg_hw, t_cfg_curriculum, t_cfg_wrong, t_cfg_matrix, t_cfg_links = st.tabs([
        "👤 1. [개별] 학생 진도 관리", 
        "📢 2. 공지사항 관리",
        "📅 3. 개별 과제 관리", 
        "📚 4. 커리큘럼 진도 배정", 
        "🔍 5. 오답노트 모아보기",
        "📊 6. 전체 숙제 매트릭스",
        "🎥 7. 해설 링크 관리"
    ])

    with t_cfg_student:
        st.markdown("#### 🎯 학생 종합 현황 및 진도 관리")
        if student_list:
            selected_student = st.selectbox("조회할 학생 선택", student_list, key="tab1_stu_sel")
            s_milestones = get_student_milestones(selected_student)
            s_m_progress = get_milestone_progress(selected_student)
            
            current_url = get_student_drive_url(selected_student)
            with st.form(f"drive_url_form_{selected_student}"):
                new_drive_url = st.text_input("구글 드라이브 폴더 URL", value=current_url)
                if st.form_submit_button("💾 드라이브 링크 저장"):
                    update_student_drive_url(selected_student, new_drive_url.strip())
                    st.success("저장되었습니다!")
                    st.rerun()

            if s_milestones:
                grouped_t_milestones = {}
                for m_id, sub, ch, t_name, v_url in s_milestones:
                    grouped_t_milestones.setdefault((sub, ch), []).append((m_id, t_name, v_url))
                for (sub, ch), items in grouped_t_milestones.items():
                    with st.expander(f"[{sub}] {ch}", expanded=False):
                        for m_id, t_name, v_url in items:
                            is_done = s_m_progress.get(m_id, False)
                            if st.checkbox(f"{t_name}", value=is_done, key=f"t_milestone_{m_id}") != is_done:
                                save_single_milestone_progress(selected_student, m_id, st.session_state[f"t_milestone_{m_id}"])
                                st.rerun()

    with t_cfg_notice:
        st.markdown("#### 📢 전체 또는 학생별 공지사항 등록")
        with st.form("add_notice_form"):
            notice_target_type = st.radio("공지 대상 선택", ["🌐 전체 공지 (모든 학생에게 표시)", "👤 특정 학생 지정 공지"], horizontal=True)
            target_student_name = st.selectbox("대상 학생 선택", student_list, key="notice_target_student") if notice_target_type == "👤 특정 학생 지정 공지" and student_list else ""
            notice_title = st.text_input("공지사항 제목", placeholder="예: 이번 주 보충 수업 안내")
            notice_content = st.text_area("공지사항 내용", placeholder="상세 내용을 입력하세요...")
            if st.form_submit_button("📢 공지사항 등록하기", type="primary"):
                if notice_title.strip() and notice_content.strip():
                    add_notice(target_student_name if notice_target_type == "👤 특정 학생 지정 공지" else "", notice_title.strip(), notice_content.strip())
                    st.success("공지가 등록되었습니다!")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 📋 등록된 공지사항 관리 및 삭제")
        all_notices = get_all_notices()
        if all_notices:
            for n_id, n_target, n_title, n_content, n_date in all_notices:
                with st.container(border=True):
                    badge_str = "🌐 [전체 공지]" if not n_target else f"👤 [{n_target} 학생 맞춤]"
                    col_n_info, col_n_del = st.columns([5, 1])
                    with col_n_info:
                        st.markdown(f"**{badge_str} {n_title}** <span style='font-size:12px; color:#64748B;'>(작성일: {n_date})</span>", unsafe_allow_html=True)
                        st.caption(n_content)
                    with col_n_del:
                        if st.button("🗑️ 삭제", key=f"del_notice_{n_id}"):
                            delete_notice(n_id)
                            st.success("삭제되었습니다!")
                            st.rerun()
        else:
            st.info("등록된 공지사항이 없습니다.")

    with t_cfg_hw:
        st.markdown("#### 📅 학생 개별 과제 및 매일 루틴 과제 관리")
        if student_list:
            selected_hw_student = st.selectbox("과제를 관리할 학생 선택", student_list, key="tab3_stu_sel")
            
            with st.expander("🔥 학생별 [매일 반복 루틴 과제] 설정 및 월간 실천 현황", expanded=False):
                st.caption("학생이 매일 수행해야 하는 반복 루틴 과제를 설정하고, 특정 날짜의 실천 현황을 직접 체크하거나 수정할 수 있습니다.")
                
                with st.form("add_teacher_routine_form"):
                    new_routine_txt = st.text_area("루틴 과제 항목 입력 (줄바꿈으로 여러 개 입력 가능)", placeholder="- 오답노트 오답 정리\n- 영어 단어 20개 암기")
                    if st.form_submit_button("➕ 루틴 과제 일괄 등록", type="primary"):
                        if new_routine_txt.strip():
                            bulk_insert_daily_routines(selected_hw_student, new_routine_txt)
                            st.success("루틴 과제가 등록되었습니다!")
                            st.rerun()
                
                current_routines = get_student_daily_routines_parent(selected_hw_student, parent_id=None)
                if current_routines:
                    st.markdown("##### 📋 현재 등록된 루틴 과제 목록")
                    for r_id, r_title in current_routines:
                        col_r1, col_r2 = st.columns([5, 1])
                        with col_r1:
                            st.markdown(f"📌 **{r_title}**")
                            sub_r = get_student_daily_routines_parent(selected_hw_student, parent_id=r_id)
                            for sr_id, sr_title in sub_r:
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;└ {sr_title}")
                        with col_r2:
                            if st.button("🗑️ 삭제", key=f"del_routine_{r_id}"):
                                delete_daily_routine(r_id)
                                st.success("삭제되었습니다!")
                                st.rerun()

                    st.markdown("---")
                    st.markdown(f"##### 📊 **{selected_hw_student}** 학생의 월간 루틴 실천 현황 및 선생님 완료 체크")
                    today_obj = get_korean_today()
                    t_year = st.selectbox("연도 선택", [today_obj.year - 1, today_obj.year, today_obj.year + 1], index=1, key="teacher_routine_year")
                    t_month = st.selectbox("월 선택", list(range(1, 13)), index=today_obj.month - 1, key="teacher_routine_month")
                    
                    t_monthly_logs = get_student_monthly_logs(selected_hw_student, t_year, t_month)
                    _, t_last_day = calendar.monthrange(t_year, t_month)
                    
                    teacher_chk_day = st.selectbox("📝 완료 체크/수정할 날짜 선택", list(range(1, t_last_day + 1)), format_func=lambda d: f"{t_month}월 {d}일 ({get_weekday_kr(f'{t_year}-{t_month:02d}-{d:02d}')})", key="teacher_chk_day_select")
                    target_chk_date_str = f"{t_year}-{t_month:02d}-{teacher_chk_day:02d}"
                    
                    with st.container(border=True):
                        st.markdown(f"**📌 {target_chk_date_str} 루틴 완료 여부 실시간 자동 저장**")
                        day_logs_current = get_student_daily_logs_by_date(selected_hw_student, target_chk_date_str)
                        
                        for r_id, r_title in current_routines:
                            r_subs = get_student_daily_routines_parent(selected_hw_student, parent_id=r_id)
                            default_val = day_logs_current.get((str(r_id), target_chk_date_str), False)
                            
                            def auto_save_routine_callback(s_name, d_str, r_key):
                                val = st.session_state.get(r_key, False)
                                save_daily_routine_logs(s_name, d_str, {r_key.split('_')[2]: val})

                            if r_subs:
                                st.markdown(f"**{r_title}**")
                                key_main = f"t_daily_{r_id}_{target_chk_date_str}"
                                st.checkbox(f"{r_title} (전체 대표)", value=default_val, key=key_main, on_change=auto_save_routine_callback, args=(selected_hw_student, target_chk_date_str, key_main))
                                for sr_id, sr_title in r_subs:
                                    sub_default = day_logs_current.get((str(sr_id), target_chk_date_str), False)
                                    key_sub = f"t_daily_{sr_id}_{target_chk_date_str}"
                                    st.checkbox(f"&nbsp;&nbsp;&nbsp;&nbsp;└ {sr_title}", value=sub_default, key=key_sub, on_change=auto_save_routine_callback, args=(selected_hw_student, target_chk_date_str, key_sub))
                            else:
                                key_single = f"t_daily_{r_id}_{target_chk_date_str}"
                                st.checkbox(f"📌 {r_title}", value=default_val, key=key_single, on_change=auto_save_routine_callback, args=(selected_hw_student, target_chk_date_str, key_single))
                            st.divider()

                    st.markdown("---")
                    st.markdown(f"**📋 {t_year}년 {t_month}월 전체 실천 요약**")
                    for day in range(1, t_last_day + 1):
                        d_str = f"{t_year}-{t_month:02d}-{day:02d}"
                        w_name = get_weekday_kr(d_str)[:1]
                        is_today = (d_str == str(today_obj))
                        
                        day_checked_count = sum(1 for r_id, _ in current_routines if t_monthly_logs.get((str(r_id), d_str), False))
                        total_r_count = len(current_routines)
                        
                        status_ox = "⭕ O" if (total_r_count > 0 and day_checked_count == total_r_count) else "❌ X"
                        
                        bg_color = "#F0FDF4" if is_today else "#FFFFFF"
                        border_highlight = "border: 2px solid #03C75A;" if is_today else "border: 1px solid #CBD5E1;"
                        today_tag = " (오늘)" if is_today else ""
                        
                        st.markdown(
                            f"<div style='padding: 10px 14px; margin-bottom: 6px; border-radius: 6px; {border_highlight} background-color: {bg_color}; display: flex; justify-content: space-between; align-items: center;'>"
                            f"<span style='font-size: 14px; font-weight: bold; color: #111827 !important; -webkit-text-fill-color: #111827 !important;'>{t_month}월 {day}일 ({w_name}){today_tag}</span>"
                            f"<span style='font-size: 13px; font-weight: bold; color: #03C75A !important; -webkit-text-fill-color: #03C75A !important;'>{status_ox} ({day_checked_count}/{total_r_count})</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

            st.markdown("---")
            st.markdown("##### 📝 날짜별 과제 부여 및 수정/삭제")
            
            existing_hw_dates = get_student_homework_dates(selected_hw_student)
            if existing_hw_dates:
                with st.expander("✏️ 등록된 날짜별 숙제 내용 통째로 수정 및 삭제하기", expanded=False):
                    chosen_edit_date = st.selectbox("수정할 숙제 날짜 선택", existing_hw_dates, format_func=lambda d: f"{d} ({get_weekday_kr(d)})", key="select_date_to_edit_bulk")
                    
                    date_hws = get_student_homework_by_date_parent(selected_hw_student, chosen_edit_date, parent_id=None)
                    combined_titles = []
                    for h_id, h_title in date_hws:
                        combined_titles.append(h_title)
                        sub_hws = get_student_homework_by_date_parent(selected_hw_student, chosen_edit_date, parent_id=h_id)
                        for _, s_title in sub_hws:
                            combined_titles.append(f"  - {s_title}")
                    
                    initial_text_val = "\n".join(combined_titles)
                    
                    with st.form(f"bulk_edit_hw_form_{chosen_edit_date}"):
                        new_bulk_text = st.text_area("해당 날짜 숙제 내용 전체 편집 (줄바꿈으로 구분)", value=initial_text_val, height=150)
                        
                        col_be1, col_be2 = st.columns(2)
                        with col_be1:
                            do_bulk_update = st.form_submit_button("💾 해당 날짜 숙제 일괄 수정 저장", type="primary")
                        with col_be2:
                            do_bulk_delete = st.form_submit_button("🗑️ 해당 날짜 숙제 전체 삭제")
                            
                        if do_bulk_update:
                            if new_bulk_text.strip():
                                update_student_homework_by_date(selected_hw_student, chosen_edit_date, new_bulk_text.strip())
                                st.success(f"{chosen_edit_date} 숙제가 성공적으로 수정되었습니다!")
                                st.rerun()
                        if do_bulk_delete:
                            delete_student_homework_date(selected_hw_student, chosen_edit_date)
                            st.success(f"{chosen_edit_date} 숙제가 삭제되었습니다!")
                            st.rerun()

            templates = get_homework_templates()

            if "hw_text_content" not in st.session_state:
                st.session_state["hw_text_content"] = ""

            if templates:
                template_options = ["-- 자주 쓰는 숙제 템플릿 불러오기 --"] + [t[1] for t in templates]
                
                def on_template_change():
                    chosen = st.session_state.get("select_hw_template_box", "")
                    if chosen and chosen != "-- 자주 쓰는 숙제 템플릿 불러오기 --":
                        current_val = st.session_state.get("hw_text_area_input", "")
                        if current_val.strip():
                            st.session_state["hw_text_area_input"] = current_val + "\n" + chosen
                        else:
                            st.session_state["hw_text_area_input"] = chosen

                st.selectbox(
                    "📌 템플릿 선택", 
                    template_options, 
                    key="select_hw_template_box", 
                    on_change=on_template_change
                )

            with st.form("add_student_hw_form"):
                hw_date_input = st.date_input("과제 제출일", value=get_korean_today())
                hw_text_area = st.text_area(
                    "날짜별 과제 내용 입력", 
                    key="hw_text_area_input",
                    placeholder="[진도 교재]\n  - p.12~15 문제 풀이",
                    height=150
                )
                
                col_sub_btn1, col_sub_btn2 = st.columns(2)
                with col_sub_btn1:
                    submit_hw_btn = st.form_submit_button("과제 등록", type="primary")
                with col_sub_btn2:
                    save_as_tpl_btn = st.form_submit_button("💾 현재 내용을 템플릿으로 저장")
                
                if submit_hw_btn:
                    if hw_text_area.strip():
                        bulk_insert_student_homework(selected_hw_student, str(hw_date_input), hw_text_area)
                        st.success("과제가 등록되었습니다!")
                        st.rerun()
                
                if save_as_tpl_btn:
                    if hw_text_area.strip():
                        add_homework_template(hw_text_area.strip())
                        st.success("새로운 숙제 템플릿으로 저장되었습니다!")
                        st.rerun()

            if templates:
                with st.expander("⚙️ 저장된 숙제 템플릿 관리 및 삭제", expanded=False):
                    for t_id, t_title in templates:
                        col_tpl_info, col_tpl_del = st.columns([5, 1])
                        with col_tpl_info:
                            st.text(t_title)
                        with col_tpl_del:
                            if st.button("🗑️ 삭제", key=f"del_tpl_{t_id}"):
                                delete_homework_template(t_id)
                                st.success("삭제되었습니다!")
                                st.rerun()
        else:
            st.warning("등록된 학생이 없습니다.")

    with t_cfg_curriculum:
        st.markdown("#### 📚 과목 / 단원 / 세부 유형 폴더형 통합 관리")
        with st.form("unified_sub_form"):
            new_sub_input = st.text_input("새 과목 추가")
            if st.form_submit_button("과목 등록"):
                if new_sub_input.strip() and add_subject(new_sub_input.strip()):
                    st.success("등록되었습니다!")
                    st.rerun()
        
        subjects_data = get_subjects()
        if subjects_data and student_list:
            st.divider()
            selected_assign_student = st.selectbox("진도를 배정할 학생 선택", student_list, key="tab4_stu_sel")
            all_chapters = get_chapters()
            assigned_chapters = {m[2] for m in get_student_milestones(selected_assign_student)}
            with st.form("assign_chapters_form"):
                selected_ch_ids = []
                for sub_id, sub_name in subjects_data:
                    sub_chapters = [ch for ch in all_chapters if ch[1] == sub_name]
                    if sub_chapters:
                        with st.expander(f"📚 [{sub_name}] 단원 목록 ({len(sub_chapters)}개)"):
                            for ch_id, ch_sub, ch_name in sub_chapters:
                                if st.checkbox(f"{ch_name}", value=ch_name in assigned_chapters, key=f"assign_ch_chk_{ch_id}"):
                                    selected_ch_ids.append(ch_id)
                if st.form_submit_button("선택한 단원 일괄 배정하기", type="primary"):
                    if selected_ch_ids:
                        assign_chapters_to_student(selected_assign_student, selected_ch_ids)
                        st.success("배정되었습니다!")
                        st.rerun()

    with t_cfg_wrong:
        st.markdown("#### 🔍 학생별 / 전체 오답 취합 및 스마트 관리")
        if student_list:
            student_select_options = ["전체 학생 모아보기"] + student_list
            chk_student_choice = st.selectbox("조회할 대상 선택", student_select_options, key="chk_wrong_student_choice")
            
            wrong_view_mode = st.radio(
                "오답 모아보기 방식 선택", 
                [
                    "📁 단원코드별 전체 보기", 
                    "📅 최근 수정일별 보기 (날짜 선택 가능)", 
                    "🚨 해설 링크가 연결되지 않은 문제 모아보기"
                ], 
                horizontal=False
            )
            st.divider()

            base_url = get_base_url()
            conn, _ = get_db_connection()
            c = conn.cursor()
            if chk_student_choice == "전체 학생 모아보기":
                c.execute("SELECT student_name, unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE numbers_text != ''")
            else:
                c.execute("SELECT student_name, unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE student_name = ? AND numbers_text != ''", (chk_student_choice,))
            all_wrong_rows = c.fetchall()
            conn.close()
            
            if all_wrong_rows:
                if wrong_view_mode == "📁 단원코드별 전체 보기":
                    for s_name, u_code, nums_txt, u_date in all_wrong_rows:
                        with st.container(border=True):
                            parsed_s = parse_numbers(nums_txt)
                            if parsed_s:
                                student_link = f"{base_url}/?student={s_name}"
                                name_display = f"👤 **<a href='{student_link}' target='_blank' style='color:#0284C7; text-decoration:none;'>[{s_name}]</a>** &nbsp;|&nbsp; " if chk_student_choice == "전체 학생 모아보기" else ""
                                st.markdown(f"##### {name_display}📖 단원코드: `{u_code}` <span style='font-size:12px; color:#64748B;'>(수정일: {u_date})</span>", unsafe_allow_html=True)
                                
                                colored_num_tags = []
                                for n in sorted(list(parsed_s)):
                                    f_code = f"{u_code}{n:03d}"
                                    if get_problem_link_by_full(f_code):
                                        colored_num_tags.append(f"<span style='color: #0284C7; font-weight: bold;'>{n:03d}</span>")
                                    else:
                                        colored_num_tags.append(f"<span style='color: #DC2626; font-weight: bold;'>{n:03d}</span>")
                                
                                st.markdown(f"<div style='background-color: #F8FAFC; padding: 10px; border-radius: 6px; font-family: monospace; font-size: 15px; color: #111827;'>{u_code}_({', '.join(colored_num_tags)})</div>", unsafe_allow_html=True)

                elif wrong_view_mode == "📅 최근 수정일별 보기 (날짜 선택 가능)":
                    available_dates = sorted(list(set([r[3] for r in all_wrong_rows if r[3]])), reverse=True)
                    if available_dates:
                        date_options = ["전체 날짜 보기 (최근순)"] + available_dates
                        selected_date_filter = st.selectbox("확인할 수정일 선택", date_options)
                        
                        if selected_date_filter == "전체 날짜 보기 (최근순)":
                            target_rows = sorted(all_wrong_rows, key=lambda x: x[3] if x[3] else "1900-01-01", reverse=True)
                        else:
                            target_rows = [r for r in all_wrong_rows if r[3] == selected_date_filter]
                        
                        st.markdown(f"---")
                        for s_name, u_code, nums_txt, u_date in target_rows:
                            with st.container(border=True):
                                parsed_s = parse_numbers(nums_txt)
                                if parsed_s:
                                    student_link = f"{base_url}/?student={s_name}"
                                    name_display = f"👤 **<a href='{student_link}' target='_blank' style='color:#0284C7; text-decoration:none;'>[{s_name}]</a>** &nbsp;|&nbsp; " if chk_student_choice == "전체 학생 모아보기" else ""
                                    st.markdown(f"##### {name_display}📅 수정일: `{u_date or '미기재'}` &nbsp;|&nbsp; 단원: `{u_code}`", unsafe_allow_html=True)
                                    
                                    colored_num_tags = []
                                    for n in sorted(list(parsed_s)):
                                        f_code = f"{u_code}{n:03d}"
                                        if get_problem_link_by_full(f_code):
                                            colored_num_tags.append(f"<span style='color: #0284C7; font-weight: bold;'>{n:03d}</span>")
                                        else:
                                            colored_num_tags.append(f"<span style='color: #DC2626; font-weight: bold;'>{n:03d}</span>")
                                    
                                    st.markdown(f"<div style='background-color: #F8FAFC; padding: 10px; border-radius: 6px; font-family: monospace; font-size: 15px; color: #111827;'>{u_code}_({', '.join(colored_num_tags)})</div>", unsafe_allow_html=True)
                    else:
                        st.info("등록된 수정일 데이터가 없습니다.")

                elif wrong_view_mode == "🚨 해설 링크가 연결되지 않은 문제 모아보기":
                    st.info("💡 학생들이 제출한 오답 중, 아직 '7. 해설 링크 관리'에 영상 주소가 등록되지 않은 문제들만 모아봅니다!")
                    unlinked_found = False
                    for s_name, u_code, nums_txt, u_date in all_wrong_rows:
                        parsed_s = parse_numbers(nums_txt)
                        if parsed_s:
                            unlinked_nums = [f"{n:03d}" for n in sorted(list(parsed_s)) if not get_problem_link_by_full(f"{u_code}{n:03d}")]
                            if unlinked_nums:
                                unlinked_found = True
                                with st.container(border=True):
                                    student_link = f"{base_url}/?student={s_name}"
                                    name_display = f"👤 **<a href='{student_link}' target='_blank' style='color:#0284C7; text-decoration:none;'>[{s_name}]</a>** &nbsp;|&nbsp; " if chk_student_choice == "전체 학생 모아보기" else ""
                                    st.markdown(f"##### {name_display}🚨 미연결 오답 - 단원: `{u_code}`", unsafe_allow_html=True)
                                    unlinked_str = f"{u_code}_({', '.join(unlinked_nums)})"
                                    st.code(unlinked_str, language="text")
                    if not unlinked_found:
                        st.success("🎉 현재 조회 범위 내 모든 오답에 해설 링크가 완벽하게 연결되어 있습니다.")
            else:
                st.info("저장된 오답이 없습니다.")
        else:
            st.warning("등록된 학생이 없습니다.")

    with t_cfg_matrix:
        st.markdown("#### 📊 전체 학생 숙제 현황 및 통합 관리")
        conn, _ = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT hw_date FROM student_homework ORDER BY hw_date DESC")
        all_hw_dates = [r[0] for r in c.fetchall()]
        conn.close()
        if all_hw_dates and student_list:
            selected_matrix_date = st.selectbox("확인할 숙제 날짜 선택", all_hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
            
            for s_name in student_list:
                parent_hws = get_student_homework_by_date_parent(s_name, selected_matrix_date, parent_id=None)
                if parent_hws:
                    with st.container(border=True):
                        st.markdown(f"**👤 {s_name} 학생**")
                        s_hw_prog = get_student_homework_progress(s_name)
                        
                        for h_id, title in parent_hws:
                            is_done = s_hw_prog.get(h_id, False)
                            
                            col_m1, col_m2 = st.columns([5, 1])
                            with col_m1:
                                if st.checkbox(f"📌 {title}", value=is_done, key=f"mat_chk_{h_id}") != is_done:
                                    save_single_homework_progress(s_name, h_id, st.session_state[f"mat_chk_{h_id}"])
                                    st.rerun()
                            with col_m2:
                                with st.popover("⚙️ 수정"):
                                    with st.form(f"matrix_edit_form_{h_id}"):
                                        m_new_date = st.date_input("날짜", value=date.fromisoformat(selected_matrix_date), key=f"m_date_{h_id}")
                                        m_new_title = st.text_input("내용", value=title, key=f"m_title_{h_id}")
                                        m_save = st.form_submit_button("저장", type="primary")
                                        m_del = st.form_submit_button("삭제")
                                        if m_save:
                                            if m_new_title.strip():
                                                update_student_homework_by_date(s_name, str(m_new_date), m_new_title.strip())
                                                st.success("수정 완료!")
                                                st.rerun()
                                        if m_del:
                                            delete_student_homework_date(s_name, selected_matrix_date)
                                            st.success("삭제 완료!")
                                            st.rerun()
                            
                            sub_hws = get_student_homework_by_date_parent(s_name, selected_matrix_date, parent_id=h_id)
                            for s_id, s_title in sub_hws:
                                s_done = s_hw_prog.get(s_id, False)
                                if st.checkbox(f"&nbsp;&nbsp;&nbsp;&nbsp;└ {s_title}", value=s_done, key=f"mat_chk_sub_{s_id}") != s_done:
                                    save_single_homework_progress(s_name, s_id, st.session_state[f"mat_chk_sub_{s_id}"])
                                    st.rerun()

    with t_cfg_links:
        st.markdown("#### 🎥 문제별 풀이해설 링크 통합 관리")
        col_link_tab1, col_link_tab2 = st.tabs(["➕ 개별 및 일괄 링크 등록", "📋 전체 등록된 링크 목록 및 삭제"])
        with col_link_tab1:
            with st.form("add_problem_link_form"):
                col_pl1, col_pl2 = st.columns([1, 2])
                with col_pl1: f_code_in = st.text_input("문제 번호 (예: B1353015)")
                with col_pl2: v_url_in = st.text_input("네이버 카페 URL")
                if st.form_submit_button("➕ 개별 등록", type="primary"):
                    if f_code_in.strip() and v_url_in.strip():
                        save_problem_link(f_code_in.strip(), v_url_in.strip())
                        st.success("저장되었습니다!")
                        st.rerun()
            with st.form("bulk_problem_link_form"):
                bulk_txt = st.text_area("일괄 등록 (줄바꿈 입력)", placeholder="B1353015 https://cafe.naver.com/.../123")
                if st.form_submit_button("📥 일괄 등록 실행", type="primary"):
                    if bulk_txt.strip():
                        s_cnt, f_cnt = bulk_save_problem_links(bulk_txt)
                        st.success(f"성공 {s_cnt}개 등록됨! (실패: {f_cnt}개)")
                        st.rerun()
        with col_link_tab2:
            all_links = get_all_problem_links()
            if all_links:
                search_filter = st.text_input("🔍 검색", placeholder="단원코드 또는 문제번호").strip().upper()
                filtered = [l for l in all_links if search_filter in l[1] or search_filter in l[3]] if search_filter else all_links
                for l_id, f_code, v_url, u_code in filtered:
                    with st.container(border=True):
                        col_li_info, col_li_del = st.columns([5, 1])
                        with col_li_info:
                            st.markdown(f"📌 **{f_code}** &nbsp;|&nbsp; 🔗 [{v_url}]({v_url})", unsafe_allow_html=True)
                        with col_li_del:
                            if st.button("🗑️", key=f"del_link_{l_id}"):
                                delete_problem_link(l_id)
                                st.rerun()

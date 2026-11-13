import streamlit as st
import sqlite3
from datetime import datetime, date, timedelta, timezone
import calendar
import re
import pandas as pd
import io
import os
import base64

st.set_page_config(page_title="MathPro 학생 맞춤 학습 로드맵", page_icon="📐", layout="centered")

if "teacher_authenticated" not in st.session_state:
    st.session_state["teacher_authenticated"] = False

if "teacher_db_mode" not in st.session_state:
    st.session_state["teacher_db_mode"] = "supabase"

if "student_db_mode" not in st.session_state:
    st.session_state["student_db_mode"] = "supabase"

try:
    import psycopg2
    from urllib.parse import urlparse
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

@st.cache_resource(show_spinner=False)
def get_persistent_postgres_connection(conn_url):
    conn = psycopg2.connect(conn_url, connect_timeout=5)
    conn.autocommit = True
    return conn

def get_db_connection():
    is_teacher = st.session_state.get("teacher_authenticated", False)
    target_mode = st.session_state.get("teacher_db_mode", "supabase") if is_teacher else st.session_state.get("student_db_mode", "supabase")
    
    if target_mode == "supabase" and SUPABASE_AVAILABLE and "supabase" in st.secrets:
        try:
            sec = st.secrets["supabase"]
            conn_url = sec.get("url", "postgresql://postgres.qfpclacalaaxbhhheosw:MathPro2026@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres")
            conn = get_persistent_postgres_connection(conn_url)
            if conn.closed != 0:
                st.cache_resource.clear()
                conn = get_persistent_postgres_connection(conn_url)
            return conn, "postgres"
        except Exception:
            pass
    
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mathpro_roadmap.db")
    return sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False), "sqlite"

def q(c, query, params=None):
    try:
        if "psycopg2" in str(type(c.connection)):
            query = query.replace("?", "%s")
    except Exception:
        pass
    if params is not None:
        c.execute(query, params)
    else:
        c.execute(query)
    return c

@st.cache_data(ttl=60)
def get_all_problem_link_set():
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT full_code FROM problem_links WHERE video_url IS NOT NULL AND trim(video_url) != ''")
        rows = c.fetchall()
        return {str(r[0]).upper() for r in rows}
    except Exception:
        return set()

@st.cache_data(ttl=60)
def get_batch_problem_link_info(full_codes):
    if not full_codes:
        return {}
    full_codes_tuple = tuple(sorted(list(set(full_codes))))
    if not full_codes_tuple:
        return {}
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        placeholders = ', '.join(['%s' if db_type == "postgres" else '?'] * len(full_codes_tuple))
        query = f"SELECT full_code, video_url, updated_at FROM problem_links WHERE full_code IN ({placeholders})"
        q(c, query, full_codes_tuple)
        rows = c.fetchall()
        return {r[0].upper(): (r[1], r[2] if r[2] else "") for r in rows}
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_entire_homework_progress_map():
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT student_name, student_hw_id, is_checked FROM student_homework_progress")
        rows = c.fetchall()
        return {(r[0], r[1]): bool(r[2]) for r in rows}
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_unit_code_summary_list():
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, "SELECT unit_code, COUNT(*) FROM problem_links WHERE video_url IS NOT NULL AND trim(video_url) != '' GROUP BY unit_code ORDER BY unit_code")
        return c.fetchall()
    except Exception:
        return []

def get_korean_today():
    try:
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst).date()
    except Exception:
        return date.today()

def get_korean_now_str():
    try:
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_visitor_stats():
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        today_str = str(get_korean_today())
        q(c, "SELECT COUNT(DISTINCT student_name) FROM visitor_logs WHERE visit_date = ?", (today_str,))
        today_active_cnt = c.fetchone()[0]
        q(c, "SELECT COUNT(*) FROM visitor_logs", ())
        total_visits = c.fetchone()[0]
        q(c, "SELECT student_name, MAX(visit_time), COUNT(*) FROM visitor_logs GROUP BY student_name ORDER BY MAX(visit_time) DESC", ())
        s_summary = c.fetchall()
        q(c, "SELECT visit_date, COUNT(DISTINCT student_name), COUNT(*) FROM visitor_logs GROUP BY visit_date ORDER BY visit_date DESC LIMIT 7", ())
        daily_logs = c.fetchall()
        return today_active_cnt, total_visits, s_summary, daily_logs
    except Exception:
        return 0, 0, [], []

def create_excel_backup():
    try:
        conn, db_type = get_db_connection()
        output = io.BytesIO()
        tables = [
            "students", "subjects", "chapters", "chapter_types", 
            "milestones", "homework", "student_homework", "milestone_progress", 
            "homework_progress", "student_homework_progress", "student_wrong_entries", 
            "student_wrong_solved", "problem_links", "homework_templates",
            "daily_routines", "daily_routine_logs", "notices", "visitor_logs", "student_wrong_logs",
            "student_test_submissions"
        ]
        success_count = 0
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for table in tables:
                try:
                    df = pd.read_sql(f"SELECT * FROM {table}", conn)
                    df.to_excel(writer, sheet_name=table, index=False)
                    success_count += 1
                except Exception:
                    pass
            if success_count == 0:
                df_empty = pd.DataFrame({"info": ["No data available"]})
                df_empty.to_excel(writer, sheet_name="backup_info", index=False)
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame({"error": [str(e)]}).to_excel(writer, sheet_name="error", index=False)
        output.seek(0)
        return output.getvalue()

def restore_from_excel(uploaded_file):
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        conn, db_type = get_db_connection()
        c = conn.cursor()
        restored_sheets = []
        tables_order = [
            "students", "subjects", "chapters", "chapter_types", 
            "milestones", "homework", "student_homework", "milestone_progress", 
            "homework_progress", "student_homework_progress", "student_wrong_entries", 
            "student_wrong_solved", "problem_links", "homework_templates",
            "daily_routines", "daily_routine_logs", "notices", "visitor_logs", "student_wrong_logs",
            "student_test_submissions"
        ]
        existing_sheets = [s.strip().lower() for s in excel_file.sheet_names]
        sorted_sheets = [t for t in tables_order if t in existing_sheets] + [s for s in existing_sheets if s not in tables_order]
        
        for target_table in sorted_sheets:
            try:
                df = pd.read_excel(excel_file, sheet_name=target_table)
                df = df.dropna(how='all')
                if 'id' in df.columns and df['id'].isna().any():
                    df = df.drop(columns=['id'])
                if target_table == "milestone_progress" and "milestone_id" in df.columns:
                    df = df.dropna(subset=["milestone_id"])
                if target_table == "student_homework_progress" and "student_hw_id" in df.columns:
                    df = df.dropna(subset=["student_hw_id"])
                
                if db_type == "postgres":
                    from psycopg2.extras import execute_values
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    try:
                        if target_table == "students":
                            c.execute(f"TRUNCATE TABLE {target_table} RESTART IDENTITY CASCADE;")
                        else:
                            c.execute(f"DELETE FROM {target_table};")
                    except Exception:
                        conn.rollback()
                        try:
                            c.execute(f"DELETE FROM {target_table};")
                        except Exception:
                            conn.rollback()
                    
                    if not df.empty:
                        cols = list(df.columns)
                        col_str = ", ".join(cols)
                        data_tuples = []
                        for row in df.itertuples(index=False, name=None):
                            clean_row = [None if pd.isna(val) else (val.strip() if isinstance(val, str) else val) for val in row]
                            data_tuples.append(tuple(clean_row))
                        
                        insert_query = f"INSERT INTO {target_table} ({col_str}) VALUES %s ON CONFLICT DO NOTHING"
                        execute_values(c, insert_query, data_tuples)
                    conn.commit()
                else:
                    df.to_sql(target_table, conn, if_exists='replace', index=False)
                    conn.commit()
                restored_sheets.append(f"{target_table}({len(df)}건)")
            except Exception as sheet_err:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return False, f"시트 복구 실패 [{target_table}]: {str(sheet_err)}"
        st.cache_data.clear()
        return True, f"🎉 복구 완료된 시트:\n- " + ",\n- ".join(restored_sheets)
    except Exception as e:
        return False, f"복구 중 오류 발생: {str(e)}"

def get_base_url():
    try:
        base_url = st.context.headers.get("Host", "")
        if base_url:
            return f"https://{base_url}"
    except Exception:
        pass
    return "https://speakprooh-dev-mathpro-app-4byisa.streamlit.app"

def get_weekday_kr(date_str):
    try:
        d = date.fromisoformat(date_str)
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        return weekdays[d.weekday()]
    except Exception:
        return "날짜 확인"

def get_weekday_short_kr(date_str):
    try:
        d = date.fromisoformat(date_str)
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        return weekdays[d.weekday()]
    except Exception:
        return ""

def init_db():
    try:
        os.makedirs("submissions", exist_ok=True)
        conn, db_type = get_db_connection()
        c = conn.cursor()
        if db_type == "postgres":
            c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY, drive_url TEXT DEFAULT \'\');')
            c.execute('CREATE TABLE IF NOT EXISTS subjects (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS chapters (id SERIAL PRIMARY KEY, subject TEXT NOT NULL, name TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS chapter_types (id SERIAL PRIMARY KEY, chapter_id INTEGER NOT NULL, name TEXT NOT NULL, video_url TEXT DEFAULT \'\');')
            c.execute('CREATE TABLE IF NOT EXISTS milestones (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, subject TEXT NOT NULL, chapter TEXT NOT NULL, type_name TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS homework (id SERIAL PRIMARY KEY, hw_date TEXT NOT NULL, title TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS student_homework (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, hw_date TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL, due_date TEXT DEFAULT \'\');')
            c.execute('CREATE TABLE IF NOT EXISTS daily_routines (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS homework_templates (id SERIAL PRIMARY KEY, title TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS milestone_progress (student_name TEXT, milestone_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, milestone_id));')
            c.execute('CREATE TABLE IF NOT EXISTS homework_progress (student_name TEXT, homework_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, homework_id));')
            c.execute('CREATE TABLE IF NOT EXISTS student_homework_progress (student_name TEXT, student_hw_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, student_hw_id));')
            c.execute('CREATE TABLE IF NOT EXISTS daily_routine_logs (student_name TEXT, routine_id TEXT, log_date TEXT, is_checked INTEGER, PRIMARY KEY (student_name, routine_id, log_date));')
            c.execute('CREATE TABLE IF NOT EXISTS student_wrong_entries (student_name TEXT, unit_code TEXT, numbers_text TEXT, updated_at TEXT DEFAULT \'\', PRIMARY KEY (student_name, unit_code));')
            c.execute('CREATE TABLE IF NOT EXISTS student_wrong_solved (student_name TEXT, full_code TEXT, is_solved INTEGER DEFAULT 0, PRIMARY KEY (student_name, full_code));')
            c.execute('CREATE TABLE IF NOT EXISTS problem_links (id SERIAL PRIMARY KEY, full_code TEXT UNIQUE NOT NULL, unit_code TEXT NOT NULL, prob_num TEXT NOT NULL, video_url TEXT NOT NULL, updated_at TEXT DEFAULT \'\');')
            c.execute('CREATE TABLE IF NOT EXISTS notices (id SERIAL PRIMARY KEY, student_name TEXT DEFAULT \'\', title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS visitor_logs (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, visit_date TEXT NOT NULL, visit_time TEXT NOT NULL);')
            c.execute('''
                CREATE TABLE IF NOT EXISTS student_wrong_logs (
                    id SERIAL PRIMARY KEY,
                    student_name TEXT NOT NULL,
                    unit_code TEXT NOT NULL,
                    prob_num INTEGER NOT NULL,
                    registered_date TEXT NOT NULL,
                    created_at TEXT DEFAULT ''
                );
            ''')
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_student_wrong_logs_unique ON student_wrong_logs (student_name, unit_code, prob_num, registered_date);')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS student_test_submissions (
                    id SERIAL PRIMARY KEY,
                    student_name TEXT NOT NULL,
                    test_title TEXT NOT NULL,
                    problem_id TEXT NOT NULL,
                    student_answer TEXT,
                    is_checked INTEGER DEFAULT 0,
                    solution_img_path TEXT,
                    submitted_at TEXT NOT NULL
                );
            ''')

            try:
                c.execute('ALTER TABLE student_homework ADD COLUMN IF NOT EXISTS due_date TEXT DEFAULT \'\';')
            except Exception:
                pass
            conn.commit()
        else:
            c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY, drive_url TEXT DEFAULT \'\')')
            c.execute('CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS chapters (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, name TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS chapter_types (id INTEGER PRIMARY KEY AUTOINCREMENT, chapter_id INTEGER NOT NULL, name TEXT NOT NULL, video_url TEXT DEFAULT \'\')')
            c.execute('CREATE TABLE IF NOT EXISTS milestones (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, subject TEXT NOT NULL, chapter TEXT NOT NULL, type_name TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS homework (id INTEGER PRIMARY KEY AUTOINCREMENT, hw_date TEXT NOT NULL, title TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS student_homework (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, hw_date TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL, due_date TEXT DEFAULT \'\')')
            c.execute('CREATE TABLE IF NOT EXISTS daily_routines (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS homework_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS milestone_progress (student_name TEXT, milestone_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, milestone_id))')
            c.execute('CREATE TABLE IF NOT EXISTS homework_progress (student_name TEXT, homework_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, homework_id))')
            c.execute('CREATE TABLE IF NOT EXISTS student_homework_progress (student_name TEXT, student_hw_id INTEGER, is_checked INTEGER)')
            c.execute('CREATE TABLE IF NOT EXISTS daily_routine_logs (student_name TEXT, routine_id TEXT, log_date TEXT, is_checked INTEGER)')
            c.execute('CREATE TABLE IF NOT EXISTS student_wrong_entries (student_name TEXT, unit_code TEXT, numbers_text TEXT, updated_at TEXT DEFAULT \'\')')
            c.execute('CREATE TABLE IF NOT EXISTS student_wrong_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, unit_code TEXT NOT NULL, prob_num INTEGER NOT NULL, registered_date TEXT NOT NULL, created_at TEXT NOT NULL)')
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_student_wrong_logs_unique ON student_wrong_logs (student_name, unit_code, prob_num, registered_date)')
            c.execute('CREATE TABLE IF NOT EXISTS student_wrong_solved (student_name TEXT, full_code TEXT, is_solved INTEGER DEFAULT 0, PRIMARY KEY (student_name, full_code))')
            c.execute('CREATE TABLE IF NOT EXISTS problem_links (id INTEGER PRIMARY KEY AUTOINCREMENT, full_code TEXT UNIQUE NOT NULL, unit_code TEXT NOT NULL, prob_num TEXT NOT NULL, video_url TEXT NOT NULL, updated_at TEXT DEFAULT \'\')')
            c.execute('CREATE TABLE IF NOT EXISTS notices (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT DEFAULT \'\', title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS visitor_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, visit_date TEXT NOT NULL, visit_time TEXT NOT NULL)')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS student_test_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_name TEXT NOT NULL,
                    test_title TEXT NOT NULL,
                    problem_id TEXT NOT NULL,
                    student_answer TEXT,
                    is_checked INTEGER DEFAULT 0,
                    solution_img_path TEXT,
                    submitted_at TEXT NOT NULL
                );
            ''')

            try:
                c.execute('ALTER TABLE student_homework ADD COLUMN due_date TEXT DEFAULT \'\'')
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        print(f"DB 초기화 예외: {e}")

init_db()

def log_student_visit(student_name):
    if not student_name or st.session_state.get("teacher_authenticated", False):
        return
    session_key = f"visited_{student_name}_{get_korean_today()}"
    if not st.session_state.get(session_key, False):
        conn, _ = get_db_connection()
        c = conn.cursor()
        now_str = get_korean_now_str()
        today_str = str(get_korean_today())
        q(c, "INSERT INTO visitor_logs (student_name, visit_date, visit_time) VALUES (?, ?, ?)", (student_name, today_str, now_str))
        conn.commit()
        st.session_state[session_key] = True

@st.cache_data(ttl=60)
def get_students():
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, "SELECT name FROM students ORDER BY name")
        return [r[0] for r in c.fetchall()]
    except Exception:
        return []

def get_student_drive_url(name):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, "SELECT drive_url FROM students WHERE name = %s", (name,))
        else:
            q(c, "SELECT drive_url FROM students WHERE name = ?", (name,))
        row = c.fetchone()
        return row[0] if row and row[0] else ""
    except Exception:
        return ""

def update_student_drive_url(name, drive_url):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "UPDATE students SET drive_url = ? WHERE name = ?", (drive_url, name))
    conn.commit()
    st.cache_data.clear()

def add_student(name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "INSERT INTO students (name, drive_url) VALUES (?, ?)", (name, ""))
        conn.commit()
        st.cache_data.clear()
        return True
    except Exception:
        return False

def delete_student(name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM students WHERE name = ?", (name,))
    q(c, "DELETE FROM milestones WHERE student_name = ?", (name,))
    q(c, "DELETE FROM milestone_progress WHERE student_name = ?", (name,))
    q(c, "DELETE FROM homework_progress WHERE student_name = ?", (name,))
    q(c, "DELETE FROM student_homework WHERE student_name = ?", (name,))
    q(c, "DELETE FROM student_homework_progress WHERE student_hw_id IN (SELECT id FROM student_homework WHERE student_name = ?)", (name,))
    q(c, "DELETE FROM student_wrong_entries WHERE student_name = ?", (name,))
    q(c, "DELETE FROM student_wrong_logs WHERE student_name = ?", (name,))
    q(c, "DELETE FROM student_wrong_solved WHERE student_name = ?", (name,))
    q(c, "DELETE FROM daily_routines WHERE student_name = ?", (name,))
    q(c, "DELETE FROM daily_routine_logs WHERE student_name = ?", (name,))
    q(c, "DELETE FROM notices WHERE student_name = ?", (name,))
    q(c, "DELETE FROM visitor_logs WHERE student_name = ?", (name,))
    q(c, "DELETE FROM student_test_submissions WHERE student_name = ?", (name,))
    conn.commit()
    st.cache_data.clear()

@st.cache_data(ttl=60)
def get_subjects():
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT id, name FROM subjects ORDER BY id")
    return c.fetchall()

def add_subject(name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT id FROM subjects WHERE name = ?", (name,))
        if not c.fetchone():
            q(c, "INSERT INTO subjects (name) VALUES (?)", (name,))
            conn.commit()
            st.cache_data.clear()
        return True
    except Exception:
        return False

@st.cache_data(ttl=60)
def get_chapters():
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT id, subject, name FROM chapters")
    rows = c.fetchall()
    def natural_sort_key(ch):
        subject, name = ch[1], ch[2]
        match = re.search(r'(\d+)', name)
        num = int(match.group(1)) if match else 0
        return (subject, num, name)
    return sorted(rows, key=natural_sort_key)

def get_chapter_types(chapter_id):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, "SELECT id, name, video_url FROM chapter_types WHERE chapter_id = %s", (chapter_id,))
        else:
            q(c, "SELECT id, name, video_url FROM chapter_types WHERE chapter_id = ?", (chapter_id,))
        return c.fetchall()
    except Exception:
        return []

def save_problem_link(full_code, video_url):
    full_code = full_code.strip().upper()
    if len(full_code) < 4:
        return False
    unit_code = full_code[:-3]
    prob_num = full_code[-3:]
    now_str = get_korean_now_str()
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "sqlite":
            q(c, "DELETE FROM problem_links WHERE full_code = ?", (full_code,))
            q(c, "INSERT INTO problem_links (full_code, unit_code, prob_num, video_url, updated_at) VALUES (?, ?, ?, ?, ?)", (full_code, unit_code, prob_num, video_url, now_str))
        else:
            q(c, "INSERT INTO problem_links (full_code, unit_code, prob_num, video_url, updated_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT(full_code) DO UPDATE SET video_url = %s, updated_at = %s", (full_code, unit_code, prob_num, video_url, now_str, video_url, now_str))
        conn.commit()
        st.cache_data.clear()
        return True
    except Exception:
        return False

def bulk_save_problem_links(text_data):
    lines = text_data.strip().split('\n')
    success_count = 0
    fail_count = 0
    conn, db_type = get_db_connection()
    c = conn.cursor()
    now_str = get_korean_now_str()
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
                    if db_type == "sqlite":
                        q(c, "DELETE FROM problem_links WHERE full_code = ?", (full_code,))
                        q(c, "INSERT INTO problem_links (full_code, unit_code, prob_num, video_url, updated_at) VALUES (?, ?, ?, ?, ?)", (full_code, unit_code, prob_num, video_url, now_str))
                    else:
                        q(c, "INSERT INTO problem_links (full_code, unit_code, prob_num, video_url, updated_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT(full_code) DO UPDATE SET video_url = %s, updated_at = %s", (full_code, unit_code, prob_num, video_url, now_str, video_url, now_str))
                    success_count += 1
                except Exception:
                    fail_count += 1
            else:
                fail_count += 1
        else:
            fail_count += 1
    conn.commit()
    st.cache_data.clear()
    return success_count, fail_count

def get_problem_links_by_unit(unit_code):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT full_code, video_url FROM problem_links WHERE unit_code = ? ORDER BY full_code", (unit_code.upper(),))
    return c.fetchall()

@st.cache_data(ttl=60)
def get_problem_link_info(full_code):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    if db_type == "postgres":
        q(c, "SELECT video_url, updated_at FROM problem_links WHERE full_code = %s", (full_code.upper(),))
    else:
        q(c, "SELECT video_url, updated_at FROM problem_links WHERE full_code = ?", (full_code.upper(),))
    row = c.fetchone()
    if row:
        return row[0], (row[1] if row[1] else "")
    return "", ""

def get_all_problem_links_searched(search_filter=""):
    if not search_filter or not search_filter.strip():
        return [], 0
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        search_val = f"%{search_filter.strip().upper()}%"
        q(c, "SELECT id, full_code, video_url, unit_code FROM problem_links WHERE full_code LIKE ? OR unit_code LIKE ? ORDER BY unit_code, full_code", (search_val, search_val))
        rows = c.fetchall()
        return rows, len(rows)
    except Exception:
        return [], 0

def delete_problem_link(link_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM problem_links WHERE id = ?", (link_id,))
    conn.commit()
    st.cache_data.clear()

def add_notice(student_name, title, content):
    conn, _ = get_db_connection()
    c = conn.cursor()
    today_str = str(get_korean_today())
    q(c, "INSERT INTO notices (student_name, title, content, created_at) VALUES (?, ?, ?, ?)", (student_name, title, content, today_str))
    conn.commit()

@st.cache_data(ttl=30)
def get_notices_for_student(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT id, title, content, created_at, student_name FROM notices WHERE student_name = '' OR student_name = ? ORDER BY id DESC", (student_name,))
    return c.fetchall()

@st.cache_data(ttl=30)
def get_all_notices():
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, "SELECT id, student_name, title, content, created_at FROM notices ORDER BY id DESC")
        return c.fetchall()
    except Exception:
        return []

def delete_notice(notice_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM notices WHERE id = ?", (notice_id,))
    conn.commit()

@st.cache_data(ttl=30)
def get_student_daily_routines(student_name):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    if db_type == "postgres":
        q(c, "SELECT id, title FROM daily_routines WHERE student_name = %s ORDER BY id", (student_name,))
    else:
        q(c, "SELECT id, title FROM daily_routines WHERE student_name = ? ORDER BY id", (student_name,))
    return c.fetchall()

def bulk_insert_daily_routines(student_name, text_data):
    conn, _ = get_db_connection()
    c = conn.cursor()
    lines = text_data.strip().split('\n')
    added_count = 0
    for line in lines:
        title = line.lstrip('-•*└\t ').strip()
        if not title:
            continue
        q(c, "INSERT INTO daily_routines (student_name, title) VALUES (?, ?)", (student_name, title))
        added_count += 1
    conn.commit()
    st.cache_data.clear()
    return added_count

def delete_daily_routine(r_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM daily_routines WHERE id = ?", (r_id,))
    q(c, "DELETE FROM daily_routine_logs WHERE routine_id = ?", (str(r_id),))
    conn.commit()
    st.cache_data.clear()

@st.cache_data(ttl=30)
def get_student_daily_logs_by_date(student_name, target_date_str):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    if db_type == "postgres":
        q(c, "SELECT routine_id, is_checked FROM daily_routine_logs WHERE student_name = %s AND log_date = %s", (student_name, target_date_str))
    else:
        q(c, "SELECT routine_id, is_checked FROM daily_routine_logs WHERE student_name = ? AND log_date = ?", (student_name, target_date_str))
    rows = c.fetchall()
    log_map = {}
    for r_id, val in rows:
        log_map[(str(r_id), target_date_str)] = bool(val)
    return log_map

@st.cache_data(ttl=30)
def get_routine_completion_rate(student_name, days_limit=7):
    conn, _ = get_db_connection()
    c = conn.cursor()
    today_obj = get_korean_today()
    start_date_str = str(today_obj - timedelta(days=days_limit - 1))
    today_str = str(today_obj)
    
    q(c, "SELECT COUNT(*) FROM daily_routines WHERE student_name = ?", (student_name,))
    total_routines_count = c.fetchone()[0]
    if total_routines_count == 0:
        return 0, 0, 0
        
    total_expected = total_routines_count * days_limit
    q(c, "SELECT COUNT(*) FROM daily_routine_logs WHERE student_name = ? AND log_date >= ? AND log_date <= ? AND is_checked = 1", (student_name, start_date_str, today_str))
    completed_count = c.fetchone()[0]
    
    raw_rate = int((completed_count / total_expected) * 100) if total_expected > 0 else 0
    rate = min(100, max(0, raw_rate))
    
    return rate, completed_count, total_expected

@st.cache_data(ttl=30)
def get_student_routine_streak(student_name):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    if db_type == "postgres":
        q(c, "SELECT COUNT(*) FROM daily_routines WHERE student_name = %s", (student_name,))
    else:
        q(c, "SELECT COUNT(*) FROM daily_routines WHERE student_name = ?", (student_name,))
    total_routines = c.fetchone()[0]
    if total_routines == 0:
        return 0
    today_obj = get_korean_today()
    start_date_obj = today_obj - timedelta(days=60)
    if db_type == "postgres":
        q(c, "SELECT log_date, COUNT(*) FROM daily_routine_logs WHERE student_name = %s AND log_date >= %s AND is_checked = 1 GROUP BY log_date", (student_name, str(start_date_obj)))
    else:
        q(c, "SELECT log_date, COUNT(*) FROM daily_routine_logs WHERE student_name = ? AND log_date >= %s AND is_checked = 1 GROUP BY log_date", (student_name, str(start_date_obj)))
    rows = c.fetchall()
    completed_days = {r[0]: r[1] for r in rows}
    streak = 0
    check_date = today_obj
    if completed_days.get(str(check_date), 0) < total_routines:
        check_date -= timedelta(days=1)
    while True:
        d_str = str(check_date)
        done_cnt = completed_days.get(d_str, 0)
        if done_cnt >= total_routines:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    return streak

def save_single_routine_log(student_name, routine_id_str, log_date_str, val):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "INSERT INTO daily_routine_logs (student_name, routine_id, log_date, is_checked) VALUES (?, ?, ?, ?) ON CONFLICT(student_name, routine_id, log_date) DO UPDATE SET is_checked = ?", (student_name, str(routine_id_str), log_date_str, int(val), int(val)))
    conn.commit()
    get_student_daily_logs_by_date.clear()
    get_routine_completion_rate.clear()
    get_student_routine_streak.clear()

def save_daily_routine_logs(student_name, log_date, routine_checked_dict):
    conn, _ = get_db_connection()
    c = conn.cursor()
    for routine_id_str, val in routine_checked_dict.items():
        q(c, "INSERT INTO daily_routine_logs (student_name, routine_id, log_date, is_checked) VALUES (?, ?, ?, ?) ON CONFLICT(student_name, routine_id, log_date) DO UPDATE SET is_checked = ?", (student_name, str(routine_id_str), log_date, int(val), int(val)))
    conn.commit()
    get_student_daily_logs_by_date.clear()
    get_routine_completion_rate.clear()
    get_student_routine_streak.clear()

@st.cache_data(ttl=60)
def get_homework_templates():
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT id, title FROM homework_templates ORDER BY id")
    return c.fetchall()

def add_homework_template(title):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "INSERT INTO homework_templates (title) VALUES (?)", (title,))
    conn.commit()

def delete_homework_template(t_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM homework_templates WHERE id = ?", (t_id,))
    conn.commit()

@st.cache_data(ttl=30)
def get_student_milestones(student_name):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, "SELECT m.id, m.subject, m.chapter, m.type_name, COALESCE((SELECT t.video_url FROM chapter_types t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.name = m.chapter AND t.name = m.type_name LIMIT 1), '') as video_url FROM milestones m WHERE m.student_name = %s", (student_name,))
        else:
            q(c, "SELECT m.id, m.subject, m.chapter, m.type_name, COALESCE((SELECT t.video_url FROM chapter_types t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.name = m.chapter AND t.name = m.type_name LIMIT 1), '') as video_url FROM milestones m WHERE m.student_name = ?", (student_name,))
        return c.fetchall()
    except Exception:
        return []

def assign_chapters_to_student(student_name, chapter_ids):
    conn, _ = get_db_connection()
    c = conn.cursor()
    for chapter_id in chapter_ids:
        q(c, "SELECT subject, name FROM chapters WHERE id = ?", (chapter_id,))
        ch_row = c.fetchone()
        if not ch_row:
            continue
        sub, ch_name = ch_row
        q(c, "SELECT name FROM chapter_types WHERE chapter_id = ?", (chapter_id,))
        type_rows = c.fetchall()
        types_to_add = [r[0] for r in type_rows] or ["단원 기본 학습"]
        q(c, "SELECT chapter, type_name FROM milestones WHERE student_name = ?", (student_name,))
        existing = {(r[0], r[1]) for r in c.fetchall()}
        for t_name in types_to_add:
            if (ch_name, t_name) not in existing:
                q(c, "INSERT INTO milestones (student_name, subject, chapter, type_name) VALUES (?, ?, ?, ?)", (student_name, sub, ch_name, t_name))
    conn.commit()
    st.cache_data.clear()

@st.cache_data(ttl=30)
def get_student_homework_dates(student_name):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    if db_type == "postgres":
        q(c, "SELECT DISTINCT hw_date FROM student_homework WHERE student_name = %s ORDER BY hw_date DESC", (student_name,))
    else:
        q(c, "SELECT DISTINCT hw_date FROM student_homework WHERE student_name = ? ORDER BY hw_date DESC", (student_name,))
    return [r[0] for r in c.fetchall()]

@st.cache_data(ttl=30)
def get_student_homework_by_date(student_name, hw_date):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, "SELECT id, title, COALESCE(due_date, '') FROM student_homework WHERE student_name = %s AND hw_date = %s ORDER BY id", (student_name, hw_date))
        else:
            q(c, "SELECT id, title, COALESCE(due_date, '') FROM student_homework WHERE student_name = ? AND hw_date = ? ORDER BY id", (student_name, hw_date))
        return c.fetchall()
    except Exception:
        if db_type == "postgres":
            q(c, "SELECT id, title, '' FROM student_homework WHERE student_name = %s AND hw_date = %s ORDER BY id", (student_name, hw_date))
        else:
            q(c, "SELECT id, title, '' FROM student_homework WHERE student_name = ? AND hw_date = ? ORDER BY id", (student_name, hw_date))
        return c.fetchall()

@st.cache_data(ttl=30)
def get_all_students_homework_map(hw_date):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, "SELECT id, student_name, title, COALESCE(due_date, '') FROM student_homework WHERE hw_date = %s ORDER BY student_name, id", (hw_date,))
        else:
            q(c, "SELECT id, student_name, title, COALESCE(due_date, '') FROM student_homework WHERE hw_date = ? ORDER BY student_name, id", (hw_date,))
        rows = c.fetchall()
        hw_map = {}
        for row in rows:
            h_id, s_name, title = row[0], row[1], row[2]
            d_date = row[3] if len(row) > 3 else ""
            hw_map.setdefault(s_name, []).append((h_id, title, d_date))
        return hw_map
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_all_student_homework(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT id, hw_date, title FROM student_homework WHERE student_name = ? ORDER BY hw_date DESC, id DESC", (student_name,))
    return c.fetchall()

def parse_inline_due_date(line_text):
    match = re.search(r'\b(\d{2})/(\d{2})/(\d{2})\b$', line_text.strip())
    if match:
        yy, mm, dd = match.groups()
        full_year = f"20{yy}"
        try:
            parsed_d = date(int(full_year), int(mm), int(dd))
            clean_title = line_text[:match.start()].strip()
            return clean_title, str(parsed_d)
        except Exception:
            pass
    return line_text.strip(), ""

def bulk_insert_student_homework(student_name, hw_date, text_data, message_text=""):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    if message_text.strip():
        if db_type == "sqlite":
            q(c, "INSERT INTO student_homework (student_name, hw_date, title, parent_id, due_date) VALUES (?, ?, ?, NULL, '')", (student_name, hw_date, f"💬 [선생님 메시지]: {message_text.strip()}"))
        else:
            q(c, "INSERT INTO student_homework (student_name, hw_date, title, parent_id, due_date) VALUES (%s, %s, %s, NULL, '')", (student_name, hw_date, f"💬 [선생님 메시지]: {message_text.strip()}"))
    
    lines = text_data.strip().split('\n')
    for line in lines:
        line_str = line.strip()
        if line_str:
            clean_title, inline_due = parse_inline_due_date(line_str)
            
            if db_type == "sqlite":
                q(c, "INSERT INTO student_homework (student_name, hw_date, title, parent_id, due_date) VALUES (?, ?, ?, NULL, ?)", (student_name, hw_date, clean_title, inline_due))
            else:
                q(c, "INSERT INTO student_homework (student_name, hw_date, title, parent_id, due_date) VALUES (%s, %s, %s, NULL, %s)", (student_name, hw_date, clean_title, inline_due))
    conn.commit()
    st.cache_data.clear()

def update_student_homework_by_date(student_name, hw_date, text_data):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM student_homework WHERE student_name = ? AND hw_date = ?", (student_name, hw_date))
    q(c, "DELETE FROM student_homework_progress WHERE student_hw_id NOT IN (SELECT id FROM student_homework)")
    conn.commit()
    bulk_insert_student_homework(student_name, hw_date, text_data)
    st.cache_data.clear()

def delete_student_homework_date(student_name, hw_date):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM student_homework WHERE student_name = ? AND hw_date = ?", (student_name, hw_date))
    conn.commit()
    st.cache_data.clear()

@st.cache_data(ttl=30)
def get_milestone_progress(student_name):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, "SELECT milestone_id, is_checked FROM milestone_progress WHERE student_name = %s", (student_name,))
        else:
            q(c, "SELECT milestone_id, is_checked FROM milestone_progress WHERE student_name = ?", (student_name,))
        return {r[0]: bool(r[1]) for r in c.fetchall()}
    except Exception:
        return {}

@st.cache_data(ttl=15)
def get_student_homework_progress(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT student_hw_id, is_checked FROM student_homework_progress WHERE student_name = ?", (student_name,))
    return {r[0]: bool(r[1]) for r in c.fetchall()}

def save_single_milestone_progress(student_name, milestone_id, val):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "sqlite":
            q(c, "DELETE FROM milestone_progress WHERE student_name = ? AND milestone_id = ?", (student_name, milestone_id))
            q(c, "INSERT INTO milestone_progress (student_name, milestone_id, is_checked) VALUES (?, ?, ?)", (student_name, milestone_id, int(val)))
        else:
            q(c, "INSERT INTO milestone_progress (student_name, milestone_id, is_checked) VALUES (?, ?, ?) ON CONFLICT(student_name, milestone_id) DO UPDATE SET is_checked = ?", (student_name, milestone_id, int(val), int(val)))
        conn.commit()
        get_milestone_progress.clear()
    except Exception:
        pass

def save_single_homework_progress(student_name, student_hw_id, val):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "sqlite":
            q(c, "DELETE FROM student_homework_progress WHERE student_name = ? AND student_hw_id = ?", (student_name, student_hw_id))
            q(c, "INSERT INTO student_homework_progress (student_name, student_hw_id, is_checked) VALUES (?, ?, ?)", (student_name, student_hw_id, int(val)))
        else:
            q(c, "INSERT INTO student_homework_progress (student_name, student_hw_id, is_checked) VALUES (?, ?, ?) ON CONFLICT(student_name, student_hw_id) DO UPDATE SET is_checked = ?", (student_name, student_hw_id, int(val), int(val)))
        conn.commit()
        get_student_homework_progress.clear()
        get_entire_homework_progress_map.clear()
    except Exception:
        pass

@st.cache_data(ttl=30)
def get_student_wrong_entry(student_name, unit_code):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT numbers_text FROM student_wrong_entries WHERE student_name = ? AND unit_code = ?", (student_name, unit_code))
    row = c.fetchone()
    return row[0] if row else ""

@st.cache_data(ttl=30)
def get_all_student_wrong_entries(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT unit_code, numbers_text FROM student_wrong_entries WHERE student_name = ? AND numbers_text != '' ORDER BY unit_code", (student_name,))
    return c.fetchall()

def save_student_wrong_entry(student_name, unit_code, numbers_text):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    today_str = str(get_korean_today())
    now_str = get_korean_now_str()
    try:
        if db_type == "sqlite":
            q(c, "DELETE FROM student_wrong_entries WHERE student_name = ? AND unit_code = ?", (student_name, unit_code))
            q(c, "INSERT INTO student_wrong_entries (student_name, unit_code, numbers_text, updated_at) VALUES (?, ?, ?, ?)", (student_name, unit_code, numbers_text, today_str))
        else:
            q(c, "INSERT INTO student_wrong_entries (student_name, unit_code, numbers_text, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(student_name, unit_code) DO UPDATE SET numbers_text = ?, updated_at = ?", (student_name, unit_code, numbers_text, today_str, numbers_text, today_str))
        
        parsed_nums = parse_numbers(numbers_text)
        for num in parsed_nums:
            if db_type == "sqlite":
                q(c, "INSERT OR IGNORE INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at) VALUES (?, ?, ?, ?, ?)", (student_name, unit_code, int(num), today_str, now_str))
            else:
                c.execute("INSERT INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (student_name, unit_code, prob_num, registered_date) DO NOTHING", (student_name, unit_code, int(num), today_str, now_str))

        conn.commit()
        get_student_wrong_entry.clear()
        get_all_student_wrong_entries.clear()
    except Exception as e:
        print(f"오답 저장 중 예외: {e}")

@st.cache_data(ttl=30)
def get_student_wrong_solved_status(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT full_code, is_solved FROM student_wrong_solved WHERE student_name = ?", (student_name,))
    return {r[0]: bool(r[1]) for r in c.fetchall()}

def save_single_wrong_solved_status(student_name, full_code, is_solved_val):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "sqlite":
            q(c, "DELETE FROM student_wrong_solved WHERE student_name = ? AND full_code = ?", (student_name, full_code))
            q(c, "INSERT INTO student_wrong_solved (student_name, full_code, is_solved) VALUES (?, ?, ?)", (student_name, full_code, int(is_solved_val)))
        else:
            q(c, "INSERT INTO student_wrong_solved (student_name, full_code, is_solved) VALUES (?, ?, ?) ON CONFLICT(student_name, full_code) DO UPDATE SET is_solved = ?", (student_name, full_code, int(is_solved_val), int(is_solved_val)))
        conn.commit()
        get_student_wrong_solved_status.clear()
    except Exception:
        pass

def parse_numbers(text):
    if not text:
        return set()
    return set(int(n) for n in re.findall(r'\d+', text))

# ----------------------------------------------------
# 🖼️ 메인 화면 상단 로고 및 헤더
# ----------------------------------------------------
if os.path.exists("mathpro_logo.png"):
    st.image("mathpro_logo.png", use_container_width=True)

st.markdown(
    """
    <div style="text-align: center; margin-top: 10px; margin-bottom: 5px;">
        <h2 style="font-size: 22px; font-weight: 700; color: #FFFFFF; letter-spacing: -0.5px; line-height: 1.4;">
            고등 수학 1등급을 향한 완벽한 여정
        </h2>
    </div>
    """,
    unsafe_allow_html=True
)

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

if url_student and url_student in student_list:
    log_student_visit(url_student)

# ----------------------------------------------------
# 🧭 사이드바 구성
# ----------------------------------------------------
with st.sidebar:
    st.markdown("### 🧭 MathPro 시스템")
    
    if st.session_state["teacher_authenticated"]:
        st.success("👑 선생님 관리자 모드 활성화됨")
        
        t_mode = st.session_state.get("teacher_db_mode", "supabase")
        st.markdown(f"**[선생님 화면 모드]**: `{'☁️ 클라우드' if t_mode == 'supabase' else '📁 로컬'}`")
        if t_mode == "supabase":
            if st.button("🔧 내 화면을 로컬 모드로 전환", use_container_width=True, key="btn_teacher_local"):
                st.session_state["teacher_db_mode"] = "local"
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()
        else:
            if st.button("☁️ 내 화면을 클라우드로 복귀", use_container_width=True, key="btn_teacher_supabase"):
                st.session_state["teacher_db_mode"] = "supabase"
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()
                
        st.markdown("---")
        
        s_mode = st.session_state.get("student_db_mode", "supabase")
        st.markdown(f"**[학생들 링크 모드]**: `{'☁️ 클라우드' if s_mode == 'supabase' else '📁 로컬'}`")
        if s_mode == "supabase":
            if st.button("⚠️ 학생들 링크를 로컬 모드로 전환", use_container_width=True, key="btn_student_local"):
                st.session_state["student_db_mode"] = "local"
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()
        else:
            if st.button("☁️ 학생들 링크를 클라우드로 복귀", type="primary", use_container_width=True, key="btn_student_supabase"):
                st.session_state["student_db_mode"] = "supabase"
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()

        st.divider()

        if st.button("로그아웃 (학생 모드로 전환)", use_container_width=True):
            st.session_state["teacher_authenticated"] = False
            st.rerun()
        st.divider()
        
        st.markdown("##### 📥/📤 데이터 백업 및 동기화")
        st.download_button(
            label="📥 전체 데이터 엑셀 백업하기",
            data=create_excel_backup(),
            file_name=f"mathpro_backup_{get_korean_today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        with st.expander("🔄 엑셀 파일로 데이터 복구하기", expanded=False):
            uploaded_backup = st.file_uploader("백업 엑셀 파일(.xlsx) 선택", type=["xlsx"])
            if uploaded_backup is not None:
                if st.button("🚀 엑셀 데이터로 DB 복구 실행", type="primary", use_container_width=True):
                    with st.spinner("복구 중..."):
                        success, msg = restore_from_excel(uploaded_backup)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    st.markdown("<br>" * 3, unsafe_allow_html=True)
    st.markdown("---")
    
    if not st.session_state["teacher_authenticated"]:
        with st.expander("🔒 선생님 전용 공간 (관리자 전환)"):
            with st.form("sidebar_teacher_login_form"):
                teacher_pw_input = st.text_input("비밀번호 입력", type="password")
                if st.form_submit_button("선생님 모드 전환", type="primary"):
                    if teacher_pw_input == "1234":
                        st.session_state["teacher_authenticated"] = True
                        st.success("인증 성공!")
                        st.rerun()
                    else:
                        st.error("비밀번호가 틀렸습니다.")

# ====================================================
# 1. [학생 전용 모드]
# ====================================================
if not st.session_state["teacher_authenticated"]:
    if url_student and url_student in student_list:
        selected_student = url_student
        
        st.markdown(
            f'<div style="background-color:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.3); padding:16px; border-radius:12px; margin-bottom:15px;">'
            f'<div style="font-size:17px; font-weight:bold; margin-bottom:8px;">✨ 안녕하세요, <span style="color:#0284C7;">{selected_student}</span> 학생!</div>'
            f'<div style="font-size:13px; margin-bottom:12px;">오늘도 MathPro와 함께 멋진 수학 학습을 시작해볼까요?</div>',
            unsafe_allow_html=True
        )
        
        student_drive = get_student_drive_url(selected_student)
        if student_drive and student_drive.strip() != "":
            st.markdown(
                f'<a href="{student_drive}" target="_blank" style="display:block; background-color:#2563EB; color:#FFFFFF; padding:12px 16px; border-radius:8px; font-size:15px; text-decoration:none; font-weight:bold; text-align:center; margin-bottom:15px;">📁 온라인 학습실 (Google Drive) 바로가기 ➔</a>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

        today_str_check = str(get_korean_today())
        routines_chk_list = get_student_daily_routines(selected_student)
        today_logs_chk = get_student_daily_logs_by_date(selected_student, today_str_check)
        unchecked_count = sum(1 for r_id, _ in routines_chk_list if not today_logs_chk.get((str(r_id), today_str_check), False))
        current_streak = get_student_routine_streak(selected_student)
        routine_rate, _, _ = get_routine_completion_rate(selected_student, days_limit=7)

        if unchecked_count > 0:
            st.markdown(
                f'<div style="background-color: rgba(239, 68, 68, 0.1); border-left: 4px solid #EF4444; padding: 12px; border-radius: 8px; margin-bottom: 15px;">'
                f'<div style="font-size: 14px; font-weight: bold; color: #EF4444;">🚨 오늘 아직 완료하지 않은 루틴 과제가 <u>{unchecked_count}개</u> 있습니다!</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        student_notices = get_notices_for_student(selected_student)
        if student_notices:
            with st.expander("📢 [중요 공지사항] 확인하기", expanded=True):
                for n_id, n_title, n_content, n_date, n_target in student_notices:
                    target_badge = "🌐 전체" if not n_target else f"👤 {n_target}"
                    st.markdown(
                        f'<div style="background-color: var(--secondary-background-color); border-left: 3px solid #0284C7; padding: 8px 12px; border-radius: 4px; margin-bottom: 8px;">'
                        f'<div style="font-size: 12px;">{target_badge} | {n_date}</div>'
                        f'<div style="font-size: 14px; font-weight: bold;">📌 {n_title}</div>'
                        f'<div style="font-size: 13px; white-space: pre-wrap; margin-top: 4px;">{n_content}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

        milestones = get_student_milestones(selected_student)
        hw_dates = get_student_homework_dates(selected_student)
        m_progress = get_milestone_progress(selected_student)
        h_progress = get_student_homework_progress(selected_student)

        total_m = len(milestones)
        completed_m = sum(1 for m in milestones if m_progress.get(m[0], False))
        m_percent = int((completed_m / total_m) * 100) if total_m > 0 else 0

        recent_3_dates = hw_dates[:3] if hw_dates else []
        recent_3_hws = []
        for d_str in recent_3_dates:
            day_hws = get_student_homework_by_date(selected_student, d_str)
            for hw_item in day_hws:
                h_id, title = hw_item[0], hw_item[1]
                if not title.startswith("💬 [선생님 메시지]:"):
                    recent_3_hws.append((h_id, title))
        
        total_h = len(recent_3_hws)
        completed_h = sum(1 for h_id, _ in recent_3_hws if h_progress.get(h_id, False))
        h_percent = int((completed_h / total_h) * 100) if total_h > 0 else 0

        saved_wrong_entries = get_all_student_wrong_entries(selected_student)
        solved_map_alert = get_student_wrong_solved_status(selected_student)
        
        unsolved_total_count = 0
        new_video_count = 0
        now_datetime_alert = datetime.now()
        target_full_codes = []
        parsed_entry_dict = {}
        for u_code, nums_txt in saved_wrong_entries:
            parsed_nums = parse_numbers(nums_txt)
            parsed_entry_dict[u_code] = parsed_nums
            for n in parsed_nums:
                target_full_codes.append(f"{u_code}{n:03d}".upper())

        batch_link_info = get_batch_problem_link_info(target_full_codes)
        for f_code in target_full_codes:
            v_url, v_up_at = batch_link_info.get(f_code, ("", ""))
            if v_url and not solved_map_alert.get(f_code, False):
                unsolved_total_count += 1
                try:
                    up_dt = datetime.strptime(v_up_at, "%Y-%m-%d %H:%M:%S")
                    if (now_datetime_alert - up_dt).total_seconds() <= 30 * 86400:
                        new_video_count += 1
                except Exception:
                    pass

        if unsolved_total_count > 0:
            st.markdown(
                f'''
                <div style="background-color: rgba(239, 68, 68, 0.1); border-left: 4px solid #EF4444; padding: 12px 14px; border-radius: 8px; margin-bottom: 15px;">
                    <div style="font-size: 13.5px; color: #F87171; font-weight: bold;">
                        🔥 미복습 오답: <span style="color: #FFF;">{unsolved_total_count}개</span> (새해설 대기: <span style="color: #FBBF24;">{new_video_count}개</span>)
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        st.markdown("##### 📊 나의 학습 성취도 대시보드")
        with st.container(border=True):
            st.markdown(f"🎯 **개념 진도 완료 현황** ({completed_m} / {total_m}개 완료)")
            cols_m = st.columns([4, 1])
            safe_m_progress = max(0.0, min(1.0, (m_percent / 100) if total_m > 0 else 0.0))
            with cols_m[0]: st.progress(safe_m_progress)
            with cols_m[1]: st.markdown(f"<div style='text-align:right; font-weight:bold; color:#0284C7;'>{m_percent}%</div>", unsafe_allow_html=True)
            
            recent_3_label = " (최근 3일)" if recent_3_dates else ""
            st.markdown(f"📚 **숙제 진도 완료 현황{recent_3_label}** ({completed_h} / {total_h}개 완료)")
            cols_h = st.columns([4, 1])
            safe_h_progress = max(0.0, min(1.0, (h_percent / 100) if total_h > 0 else 0.0))
            with cols_h[0]: st.progress(safe_h_progress)
            with cols_h[1]: st.markdown(f"<div style='text-align:right; font-weight:bold; color:#0284C7;'>{h_percent}%</div>", unsafe_allow_html=True)

            cols_rt_title, cols_rt_streak = st.columns([2.2, 1.8])
            with cols_rt_title:
                st.markdown("🔥 **루틴 과제 달성률 (최근 7일)**")
            with cols_rt_streak:
                st.markdown(f"<div style='text-align:right; font-size:13px; color:#F59E0B; font-weight:bold; margin-top:4px;'>⭐ Streak: {current_streak}일 연속!</div>", unsafe_allow_html=True)

            cols_r = st.columns([4, 1])
            safe_routine_progress = max(0.0, min(1.0, (routine_rate / 100) if routine_rate > 0 else 0.0))
            with cols_r[0]: st.progress(safe_routine_progress)
            with cols_r[1]: st.markdown(f"<div style='text-align:right; font-weight:bold; color:#F59E0B;'>{routine_rate}%</div>", unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs(["📘 개념 진도", "📚 날짜별 숙제", "💬 오답·질문 관리", "📝 온라인 테스트"])

        with tab1:
            st.markdown("### 📘 나의 개념 학습 목록")
            if milestones:
                def parse_type_sort_key(item):
                    t_name = item[3]
                    match = re.search(r'(\d+)', t_name)
                    num = int(match.group(1)) if match else 999
                    return (item[1], item[2], num, t_name)

                sorted_milestones = sorted(milestones, key=parse_type_sort_key)

                grouped_s_milestones = {}
                for m_id, sub, ch, t_name, v_url in sorted_milestones:
                    grouped_s_milestones.setdefault((sub, ch), []).append((m_id, t_name, v_url))

                def parse_chapter_sort_key(sub_ch_tuple):
                    sub, ch = sub_ch_tuple
                    match = re.search(r'(\d+)', ch)
                    num = int(match.group(1)) if match else 999
                    return (sub, num, ch)

                sorted_grouped_keys = sorted(grouped_s_milestones.keys(), key=parse_chapter_sort_key)

                for (sub, ch) in sorted_grouped_keys:
                    items = grouped_s_milestones[(sub, ch)]
                    done_cnt = sum(1 for m_id, _, _ in items if m_progress.get(m_id, False))
                    with st.expander(f"[{sub}] {ch}  (완료: {done_cnt}/{len(items)})", expanded=False):
                        for idx, (m_id, t_name, v_url) in enumerate(items):
                            default_val = m_progress.get(m_id, False)
                            cols = st.columns([4, 1])
                            
                            def on_milestone_change(m_id=m_id, key=f"s_milestone_chk_{selected_student}_{ch}_{m_id}_{idx}"):
                                new_val = st.session_state[key]
                                save_single_milestone_progress(selected_student, m_id, new_val)

                            with cols[0]:
                                st.checkbox(
                                    f"{t_name}", 
                                    value=default_val, 
                                    key=f"s_milestone_chk_{selected_student}_{ch}_{m_id}_{idx}",
                                    on_change=on_milestone_change
                                )
                            with cols[1]:
                                if v_url and v_url.strip() != "":
                                    st.markdown(f'<a href="{v_url}" target="_blank" style="display:inline-block; padding:4px 10px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; margin-top:4px; border:1px solid rgba(128,128,128,0.3);">🎥 개념해설</a>', unsafe_allow_html=True)
            else:
                st.info("아직 배정된 개념 학습 목록이 없습니다.")

        with tab2:
            today_obj = get_korean_today()
            today_str = str(today_obj)
            daily_routines_list = get_student_daily_routines(selected_student)
            current_day_logs = get_student_daily_logs_by_date(selected_student, today_str)
            
            total_routines_cnt = len(daily_routines_list)
            completed_routines_cnt = sum(1 for r_id, _ in daily_routines_list if current_day_logs.get((str(r_id), today_str), False))

            st.markdown("### 🔥 매일 반복 루틴 체크")
            st.markdown(f"💡 **루틴 진행 상황**: 총 **{total_routines_cnt}개** 중 **{completed_routines_cnt}개** 완료")
            st.markdown("<p style='color: #0284C7; font-size: 13px; font-weight: bold; margin-bottom: 8px;'>📌 숙제를 완료한 후 체크박스를 꼭 눌러주세요!</p>", unsafe_allow_html=True)
            
            if daily_routines_list:
                with st.container(border=True):
                    for r_id, r_title in daily_routines_list:
                        default_val = current_day_logs.get((str(r_id), today_str), False)
                        chk_key = f"s_daily_{selected_student}_{r_id}"
                        
                        def on_routine_change(r_id=r_id, key=chk_key):
                            save_single_routine_log(selected_student, str(r_id), today_str, st.session_state[key])

                        st.checkbox(f"{r_title}", value=default_val, key=chk_key, on_change=on_routine_change)
                        st.divider()

            if hw_dates:
                st.markdown("### 📚 날짜별 개별 숙제")
                selected_date = st.selectbox("확인할 숙제 날짜 선택", hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
                hws = get_student_homework_by_date(selected_student, selected_date)
                
                actual_sel_hws = [h for h in hws if not h[1].startswith("💬 [선생님 메시지]:")]
                total_sel_h = len(actual_sel_hws)
                completed_sel_h = sum(1 for h_item in actual_sel_hws if h_progress.get(h_item[0], False))

                st.markdown(f"💡 **선택 날짜 숙제 현황**: 총 **{total_sel_h}개** 중 **{completed_sel_h}개** 완료")
                st.markdown("<p style='color: #0284C7; font-size: 13px; font-weight: bold; margin-bottom: 8px;'>📌 숙제를 완료한 후 체크박스를 꼭 눌러주세요!</p>", unsafe_allow_html=True)

                with st.container(border=True):
                    for h_idx, hw_tuple in enumerate(hws):
                        h_id = hw_tuple[0]
                        title = hw_tuple[1]
                        due_date = hw_tuple[2] if len(hw_tuple) > 2 else ""

                        if title.startswith("💬 [선생님 메시지]:"):
                            st.info(f"📌 **선생님의 한마디**: {title.replace('💬 [선생님 메시지]:', '').strip()}")
                        else:
                            default_val = h_progress.get(h_id, False)
                            chk_key = f"s_hw_{selected_student}_{selected_date}_{h_id}_{h_idx}"
                            
                            def on_hw_change(h_id=h_id, key=chk_key):
                                new_val = st.session_state[key]
                                save_single_homework_progress(selected_student, h_id, new_val)

                            cols_hw = st.columns([4, 1])
                            with cols_hw[0]:
                                st.checkbox(
                                    f"{title}", 
                                    value=default_val, 
                                    key=chk_key, 
                                    on_change=on_hw_change
                                )
                            with cols_hw[1]:
                                if due_date and due_date.strip():
                                    short_wday = get_weekday_short_kr(due_date)
                                    wday_str = f" ({short_wday})" if short_wday else ""
                                    st.markdown(f"<div style='text-align:right; margin-top:4px;'><span style='background-color:#FEF3C7; color:#D97706; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold;'>마감: {due_date}{wday_str}</span></div>", unsafe_allow_html=True)

        with tab3:
            st.markdown("### 💬 오답 및 질문 관리")
            
            with st.container(border=True):
                st.markdown("##### 📝 1. 나의 오답 및 질문 번호 저장/수정")
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

            st.markdown("")
            
            with st.container(border=True):
                st.markdown("##### 📝 2. 나의 오답노트 및 해설 바로가기")
                saved_units_list = [u_code for u_code, _ in saved_wrong_entries]
                solved_map_chk = get_student_wrong_solved_status(selected_student)
                now_datetime_chk = datetime.now()
                
                unit_display_options = ["-- 저장된 단원을 선택하세요 --"]
                unit_map_dict = {}

                for u_code in saved_units_list:
                    p_nums = parsed_entry_dict.get(u_code, set())
                    has_new_unsolved = False
                    for n in p_nums:
                        f_code = f"{u_code}{n:03d}".upper()
                        v_url, v_up_at = batch_link_info.get(f_code, ("", ""))
                        is_solved = solved_map_chk.get(f_code, False)
                        if v_url and not is_solved:
                            try:
                                up_dt = datetime.strptime(v_up_at, "%Y-%m-%d %H:%M:%S")
                                if (now_datetime_chk - up_dt).total_seconds() <= 30 * 86400:
                                    has_new_unsolved = True
                                    break
                            except Exception:
                                pass
                    display_name = f"{u_code} 🔥 [새해설 대기]" if has_new_unsolved else f"{u_code}"
                    unit_map_dict[display_name] = u_code
                    unit_display_options.append(display_name)

                selected_display_unit = st.selectbox("확인할 단원 선택", unit_display_options, key="saved_unit_select_box")
                view_target_code = unit_map_dict.get(selected_display_unit, "") if selected_display_unit != "-- 저장된 단원을 선택하세요 --" else ""

                if view_target_code:
                    parsed_nums = parsed_entry_dict.get(view_target_code, set())
                    if parsed_nums:
                        st.markdown("---")
                        st.markdown(f"**📌 `{view_target_code}` 단원 오답 목록**")
                        solved_map = get_student_wrong_solved_status(selected_student)
                        now_datetime = datetime.now()
                        
                        st.markdown("""
                        <style>
                        div[data-testid="stHorizontalBlock"] {
                            align-items: center !important;
                            gap: 0px !important;
                        }
                        div[data-testid="stCheckbox"] {
                            margin-top: -6px !important;
                            margin-bottom: -6px !important;
                        }
                        </style>
                        """, unsafe_allow_html=True)

                        for n in sorted(list(parsed_nums)):
                            full_code = f"{view_target_code}{n:03d}".upper()
                            v_url, v_updated_at = batch_link_info.get(full_code, ("", ""))
                            is_solved = solved_map.get(full_code, False)
                            
                            is_new_alert = False
                            if v_url and v_updated_at and not is_solved:
                                try:
                                    up_dt = datetime.strptime(v_updated_at, "%Y-%m-%d %H:%M:%S")
                                    if (now_datetime - up_dt).total_seconds() <= 30 * 86400:
                                        is_new_alert = True
                                except Exception:
                                    pass

                            def on_wrong_solved_change(f_code=full_code, key=f"s_wrong_chk_{selected_student}_{full_code}"):
                                new_val = st.session_state[key]
                                save_single_wrong_solved_status(selected_student, f_code, new_val)

                            col_c1, col_c2 = st.columns([2.3, 1.7])
                            with col_c1:
                                st.checkbox(
                                    f"복습 완료 ({full_code})", 
                                    value=is_solved, 
                                    key=f"s_wrong_chk_{selected_student}_{full_code}",
                                    on_change=on_wrong_solved_change
                                )
                            with col_c2:
                                if v_url and v_url.strip():
                                    if is_new_alert:
                                        st.markdown(f"<div style='text-align: right; margin-top: 4px;'><a href='{v_url}' target='_blank' style='padding:3px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold; background-color:#EF4444; color:white; border:1px solid #DC2626; display:inline-block; white-space: nowrap;'>🔥 새해설</a></div>", unsafe_allow_html=True)
                                    else:
                                        st.markdown(f"<div style='text-align: right; margin-top: 4px;'><a href='{v_url}' target='_blank' style='padding:3px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold; background-color:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.3); color:inherit; white-space: nowrap;'>🎥 해설</a></div>", unsafe_allow_html=True)
                                else:
                                    st.markdown("<div style='text-align: right; margin-top: 4px; font-size:11px; color:gray;'>준비중</div>", unsafe_allow_html=True)
                                    
                            st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid rgba(128,128,128,0.15);'>", unsafe_allow_html=True)
                    else:
                        st.info("현재 등록된 오답이 없습니다.")

            st.markdown("")
            
            with st.container(border=True):
                st.markdown("##### 🔍 3. 해설 영상 즉시 검색하기")
                search_prob_input = st.text_input("문제 번호 또는 단원코드 입력", placeholder="예: B1353015 또는 B1353").strip().upper()
                if search_prob_input:
                    if len(search_prob_input) >= 7:
                        matched_url, _ = get_problem_link_info(search_prob_input)
                        if matched_url:
                            st.success(f"📌 **{search_prob_input}** 문제 해설 링크가 확인되었습니다!")
                            st.markdown(f'<a href="{matched_url}" target="_blank" style="display:block; padding:12px; border-radius:8px; text-decoration:none; font-weight:bold; text-align:center; border:1px solid rgba(128,128,128,0.3);">🎥 풀이 영상 바로가기 ➔</a>', unsafe_allow_html=True)
                        else:
                            st.warning(f"'{search_prob_input}'에 등록된 해설 링크가 없습니다.")
                    else:
                        unit_results = get_problem_links_by_unit(search_prob_input)
                        if unit_results:
                            st.markdown(f"##### 📂 `{search_prob_input}` 단원 해설 목록 ({len(unit_results)}개)")
                            for f_code, v_url in unit_results:
                                st.markdown(f'<a href="{v_url}" target="_blank" style="display:block; padding:10px; border-radius:6px; text-decoration:none; margin-bottom:6px; border:1px solid rgba(128,128,128,0.3);">📌 {f_code} &nbsp;&nbsp;<span style="color:#0284C7;">🎥 해설 영상 ➔</span></a>', unsafe_allow_html=True)
                        else:
                            st.info("단원코드 형식으로 올바르게 입력해 주세요.")

        with tab4:
            st.markdown("### 📝 온라인 진단 및 과제 테스트")
            st.markdown("노트에 푼 후, 정답을 체크하고 **맨 아래 최종 제출 버튼**을 누르면 자동 채점 및 오답노트로 바로 연동됩니다!")
            
            conn_test, db_type_test = get_db_connection()
            c_test = conn_test.cursor()
        
            sessions_list = []
            try:
                q(c_test, "SELECT id, test_title, created_at, is_completed FROM online_test_sessions WHERE student_name = ? ORDER BY id DESC", (selected_student,))
                sessions_list = c_test.fetchall()
            except Exception:
                sessions_list = []
        
            if not sessions_list:
                st.info("📭 현재 출제된 온라인 테스트가 없습니다. 선생님께서 PC에서 과제를 생성하면 여기에 자동으로 나타납니다!")
            else:
                session_options = {
                    s[0]: f"{'🆕 [미완료]' if s[3] == 0 else '✅ [제출완료]'} {s[1]} ({s[2]})"
                    for s in sessions_list
                }
                selected_session_id = st.selectbox(
                    "진행할 테스트 선택",
                    options=list(session_options.keys()),
                    format_func=lambda x: session_options[x],
                    key=f"sel_online_test_{selected_student}"
                )
        
                # 해당 테스트 문항들 불러오기 (캐싱)
                cache_key_items = f"cached_items_form_{selected_session_id}"
                if st.session_state.get("active_form_session_id") != selected_session_id or cache_key_items not in st.session_state:
                    st.session_state["active_form_session_id"] = selected_session_id
                    
                    q(c_test, "SELECT id, problem_order, unit_code, prob_num, answer, img_base64, file_name FROM online_test_items WHERE session_id = ? ORDER BY problem_order ASC", (selected_session_id,))
                    raw_items = c_test.fetchall()
        
                    problem_list = []
                    for item_id, p_order, u_code, p_num, ans, img_b64, f_name in raw_items: # <-- f_name 추가
                        full_code = f"{u_code}{str(p_num).zfill(3)}".upper() if u_code else f"PROB_{p_order:02d}"
                        
                        decoded_img = None
                        if img_b64:
                            try:
                                decoded_img = base64.b64decode(img_b64)
                            except Exception:
                                pass
        
                        problem_list.append({
                            "item_id": item_id,
                            "order": p_order,
                            "full_code": full_code,
                            "unit_code": u_code or "TEST",
                            "prob_num": str(p_num).zfill(3) if p_num else str(p_order),
                            "answer": str(ans).strip() if ans else "",
                            "img_bytes": decoded_img,
                            "file_name": f_name or "" # <-- 이 부분이 꼭 들어가야 합니다!
                        })
                    st.session_state[cache_key_items] = problem_list
        
                problem_list = st.session_state.get(cache_key_items, [])
                selected_test_title = [s[1] for s in sessions_list if s[0] == selected_session_id][0]
                
                current_session_info = next((s for s in sessions_list if s[0] == selected_session_id), None)
                is_db_completed = (current_session_info[3] == 1) if current_session_info else False
        
                if not problem_list:
                    st.warning("이 테스트에 등록된 문항 데이터가 없습니다.")
                else:
                    st.markdown(f"**📚 [{selected_test_title}]** — 총 {len(problem_list)}문항")
                    st.markdown("---")
        
                    # 🚀 [수동 선택형] fragment 함수 (개별 문항 비활성화 및 추가 등록 지원)
                    @st.fragment
                    def render_problem_review_list(prob_list, res_list, sess_id, s_name, s_title):
                        correct_cnt = st.session_state.get(f"correct_count_{sess_id}", 0)
                        
                        st.markdown(f"""
                        <div style="background-color: var(--secondary-background-color); border: 2px solid #0284C7; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px;">
                            <h2 style="color: #0284C7; margin: 0 0 10px 0;">🎉 과제 제출 및 자동 채점 완료!</h2>
                            <p style="font-size: 18px; font-weight: bold; margin: 0;">
                                총 {len(prob_list)}문항 중 <span style="color: #10B981;">{correct_cnt}문항 정답</span>
                            </p>
                            <p style="font-size: 14px; color: #EF4444; font-weight: bold; margin-top: 10px; background-color: rgba(239, 68, 68, 0.1); padding: 8px; border-radius: 6px;">
                                ⚠️ 오답노트에 담을 문제를 체크하신 후, <b>반드시 맨 아래의 [선택한 문제들을 오답노트에 등록하기] 버튼을 눌러주세요!</b>
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
    
                        if "master_dir_input" not in st.session_state:
                            st.session_state["master_dir_input"] = r"D:\MathPro\master_answer"
                            
                        with st.expander("⚙️ 정답 이미지 폴더 경로 설정", expanded=False):
                            st.session_state["master_dir_input"] = st.text_input(
                                "master_dir_input 폴더의 실제 경로를 입력하세요:",
                                value=st.session_state["master_dir_input"],
                                key=f"master_dir_{sess_id}"
                            )
    
                        st.markdown(f"### 📝 전체 문항별 채점 결과 및 문제 검토 ({len(prob_list)}개)")
    
                        selected_wrong_notes = {}
    
                        for prob in prob_list:
                            matched_res = next((r for r in res_list if r['full_code'] == prob['full_code']), None)
                            
                            if matched_res:
                                u_ans_str = matched_res["user_ans"] if matched_res["user_ans"] else "미입력"
                                r_ans = matched_res["real_ans"]
                                is_cor = matched_res["is_correct"]
                                ox_mark = "O" if is_cor else "X"
                                ox_color = "#10B981" if is_cor else "#EF4444"
                            else:
                                u_ans_str = "미입력"
                                r_ans = prob["answer"].replace("번", "").strip()
                                ox_mark = "-"
                                ox_color = "gray"
    
                            v_url, _ = get_problem_link_info(prob["full_code"])
                            link_btn = f'<a href="{v_url}" target="_blank" style="background-color:#EF4444; color:white; padding:2px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold;">해설영상</a>' if v_url else '<span style="color:gray; font-size:11px;">해설 준비중</span>'
    
                            f_code = str(prob["full_code"]).strip()
                            u_part = f_code[:4] if len(f_code) > 4 else "A114"
                            num_part = f_code[4:] if len(f_code) > 4 else f_code
                            n_digits = "".join(filter(str.isdigit, num_part))
                            project_id = "qfpclacalaaxbhhheosw"
                            target_filename = f"{u_part}_ans_({n_digits}).png"
                            img_url = f"https://{project_id}.supabase.co/storage/v1/object/public/master_answer/{target_filename}"
                            
                            if r_ans and r_ans != "-":
                                ans_display = f"<b style='color: #10B981;'>{r_ans}</b>"
                            else:
                                ans_display = f"<img src='{img_url}' style='height: 20px; width: auto; background: white; padding: 1px; border-radius: 2px; vertical-align: middle;' />"
    
                            with st.container(border=True):
                                st.markdown(
                                    f"<div style='display: flex; align-items: center; justify-content: space-between; font-size: 13px; margin-bottom: 4px; padding: 4px 8px; background-color: var(--secondary-background-color); border-radius: 6px;'>"
                                    f"  <div>"
                                    f"    <b style='color: #374151;'>{prob['order']}번 문제</b> "
                                    f"    <span style='color: #6B7280; font-size: 11px;'>(`{prob['full_code']}`)</span> "
                                    f"    <span style='color: {ox_color}; font-weight: bold; font-size: 14px;'>({ox_mark})</span>"
                                    f"  </div>"
                                    f"  <div>{link_btn}</div>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )
                                
                                with st.expander("🖼️ 문제 사진 보기 (터치해서 열기)", expanded=False):
                                    if prob["img_bytes"]:
                                        st.image(prob["img_bytes"], use_container_width=True)
                                    else:
                                        st.info("💡 등록된 문제 이미지가 없습니다.")
    
                                with st.expander("🔍 정답 및 내 답 확인하기 (터치해서 열기)", expanded=False):
                                    st.markdown(
                                        f"<div style='font-size: 13px; margin: 0; padding: 0;'>"
                                        f"정답: {ans_display} &nbsp;|&nbsp; "
                                        f"내 답: <b style='color: {'#10B981' if is_cor else '#EF4444'};'>{u_ans_str}</b>"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
    
                                is_item_saved = st.session_state.get(f"item_saved_{sess_id}_{prob['full_code']}", False)
                                is_checked_default = (is_cor == 0)
    
                                if is_item_saved:
                                    st.checkbox(
                                        f"✅ {prob['order']}번 문제 (오답노트 등록 완료됨)",
                                        value=True,
                                        disabled=True,
                                        key=f"wrong_chk_disabled_{sess_id}_{prob['item_id']}"
                                    )
                                else:
                                    selected_wrong_notes[prob['full_code']] = st.checkbox(
                                        f"📌 {prob['order']}번 오답노트 담기 (체크 후 맨 아래 등록 버튼을 누르면 추가 반영됩니다!)",
                                        value=is_checked_default,
                                        key=f"wrong_chk_{sess_id}_{prob['item_id']}"
                                    )
    
                        if st.button("📥 선택한 문제들을 오답노트에 등록하기", type="primary", use_container_width=True, key=f"btn_save_wrong_{sess_id}"):
                            manual_wrong_units = {}
                            current_checked_codes = []
                            
                            for prob in prob_list:
                                if selected_wrong_notes.get(prob['full_code'], False):
                                    current_checked_codes.append(prob['full_code'])
                                    if prob["unit_code"] != "TEST":
                                        manual_wrong_units.setdefault(prob["unit_code"], set()).add(int(prob["prob_num"]))
    
                            try:
                                for u_code, num_set in manual_wrong_units.items():
                                    existing_txt = get_student_wrong_entry(s_name, u_code)
                                    pre_nums = parse_numbers(existing_txt)
                                    merged_nums = pre_nums | num_set
                                    merged_txt = ", ".join(map(str, sorted(list(merged_nums))))
                                    save_student_wrong_entry(s_name, u_code, merged_txt)
                                
                                for f_code in current_checked_codes:
                                    st.session_state[f"item_saved_{sess_id}_{f_code}"] = True
    
                                st.success("✨ 선택하신 문제들이 오답노트에 성공적으로 반영되었습니다!")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"⚠️ 오답노트 저장 중 오류 발생: {e}")
        
                    if is_db_completed or st.session_state.get(f"submitted_{selected_session_id}", False):
                        if f"all_results_{selected_session_id}" not in st.session_state:
                            is_postgres = "psycopg2" in str(type(conn_test))
                            if is_postgres:
                                c_test.execute("SELECT problem_id, student_answer, is_checked FROM student_test_submissions WHERE student_name = %s AND test_title = %s", (selected_student, selected_test_title))
                            else:
                                q(c_test, "SELECT problem_id, student_answer, is_checked FROM student_test_submissions WHERE student_name = ? AND test_title = ?", (selected_student, selected_test_title))
                            submitted_rows = c_test.fetchall()
                            sub_dict = {row[0]: {"user_ans": row[1], "is_correct": row[2]} for row in submitted_rows}
                            
                            restored_results = []
                            restored_correct_cnt = 0
                            for idx, prob in enumerate(problem_list):
                                f_code = prob['full_code']
                                info = sub_dict.get(f_code, {"user_ans": "", "is_correct": 0})
                                real_ans = prob["answer"].replace("번", "").strip()
                                is_cor = info["is_correct"]
                                if is_cor:
                                    restored_correct_cnt += 1
                                restored_results.append({
                                    "order": prob["order"],
                                    "full_code": f_code,
                                    "unit_code": prob["unit_code"],
                                    "prob_num": prob["prob_num"],
                                    "user_ans": info["user_ans"],
                                    "real_ans": real_ans,
                                    "is_correct": is_cor,
                                })
                            st.session_state[f"all_results_{selected_session_id}"] = restored_results
                            st.session_state[f"correct_count_{selected_session_id}"] = restored_correct_cnt
        
                        all_results = st.session_state.get(f"all_results_{selected_session_id}", [])
                        render_problem_review_list(problem_list, all_results, selected_session_id, selected_student, selected_test_title)
        
                    else:
                        with st.form(key=f"test_form_{selected_session_id}"):
                            form_answers = {}
                            for idx, prob in enumerate(problem_list):
                                p_key = f"form_{selected_session_id}_{prob['item_id']}"
                                
                                st.markdown(f"#### **{idx + 1}번 문제** (`{prob['full_code']}`)")
                                if prob["img_bytes"]:
                                    st.image(prob["img_bytes"], use_container_width=True)
                                else:
                                    st.info("💡 등록된 문제 이미지가 없습니다.")
        
                                raw_ans_db = str(prob["answer"]).strip()
                                
                                # 💡 핵심: 정답이 아니라 '파일명(file_name)'에 '@'가 포함되어 있으면 무조건 객관식!
                                # (DB 파일명에 @3, @1 등으로 확실하게 표시되어 있으므로 100% 정확합니다)
                                file_name_val = str(prob.get("file_name", ""))
                                is_multiple_choice = "@" in file_name_val or "@" in raw_ans_db or "번" in raw_ans_db
                                
                                real_ans_clean = raw_ans_db.replace("@", "").replace("번", "").strip()

                                if is_multiple_choice:
                                    choice_options = ["1번", "2번", "3번", "4번", "5번", "잘 모름"]
                                    selected_choice = st.radio(
                                        f"{idx + 1}번 정답 선택 (객관식):",
                                        options=choice_options,
                                        index=0,
                                        key=f"radio_{p_key}",
                                        horizontal=True
                                    )
                                    user_ans = selected_choice.replace("번", "").strip() if selected_choice != "잘 모름" else ""
                                else:
                                    user_ans = st.text_input(
                                        f"{idx + 1}번 정답 입력 (주관식 단답형):",
                                        value="",
                                        key=f"text_{p_key}",
                                        placeholder="정답을 입력하세요"
                                    ).strip()
        
                                form_answers[p_key] = user_ans
                                st.markdown("<hr style='margin: 20px 0; border: 1px dashed rgba(128,128,128,0.3);'>", unsafe_allow_html=True)
        
                            submitted = st.form_submit_button("🎉 전체 문제 최종 제출 및 자동 채점", type="primary", use_container_width=True)
        
                        if submitted:
                            now_str = get_korean_now_str()
                            correct_count = 0
                            all_results = []
        
                            for prob in problem_list:
                                p_key = f"form_{selected_session_id}_{prob['item_id']}"
                                real_ans = prob["answer"].replace("번", "").strip()
                                u_ans = form_answers.get(p_key, "").replace("번", "").strip()
                                
                                is_correct = 1 if (real_ans != "" and u_ans == real_ans) else 0
                                if is_correct:
                                    correct_count += 1
        
                                all_results.append({
                                    "order": prob["order"],
                                    "full_code": prob["full_code"],
                                    "unit_code": prob["unit_code"],
                                    "prob_num": prob["prob_num"],
                                    "user_ans": u_ans,
                                    "real_ans": real_ans,
                                    "is_correct": is_correct,
                                })
        
                            try:
                                is_postgres = "psycopg2" in str(type(conn_test))
                                for res in all_results:
                                    if is_postgres:
                                        c_test.execute(
                                            "INSERT INTO student_test_submissions (student_name, test_title, problem_id, student_answer, is_checked, solution_img_path, submitted_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                            (selected_student, selected_test_title, res["full_code"], res["user_ans"], res["is_correct"], "", now_str)
                                        )
                                    else:
                                        q(c_test,
                                          "INSERT INTO student_test_submissions (student_name, test_title, problem_id, student_answer, is_checked, solution_img_path, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                          (selected_student, selected_test_title, res["full_code"], res["user_ans"], res["is_correct"], "", now_str))
        
                                q(c_test, "UPDATE online_test_sessions SET is_completed = 1 WHERE id = ?", (selected_session_id,))
                                conn_test.commit()
                                st.cache_data.clear()
        
                            except Exception as db_err:
                                st.error(f"⚠️ 제출 데이터 저장 중 오류가 발생했습니다: {db_err}")
        
                            st.session_state[f"submitted_{selected_session_id}"] = True
                            st.session_state[f"all_results_{selected_session_id}"] = all_results
                            st.session_state[f"correct_count_{selected_session_id}"] = correct_count
                            st.balloons()
                            st.rerun()

# ====================================================
# 2. [선생님 전용 관리 모드]
# ====================================================
else:
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

    t_cfg_student, t_cfg_notice, t_cfg_hw, t_cfg_curriculum, t_cfg_wrong, t_cfg_matrix, t_cfg_links, t_cfg_stats, t_cfg_tests = st.tabs([
        "👤 1. [개별] 학생 진도 관리", 
        "📢 2. 공지사항 관리",
        "📅 3. 개별 과제 관리", 
        "📚 4. 커리큘럼 진도 배정", 
        "🔍 5. 오답노트 모아보기",
        "📊 6. 전체 숙제 매트릭스",
        "🎥 7. 해설 링크 관리",
        "📈 8. 실시간 학습 참여 현황",
        "📋 9. 학생 제출물 및 풀이 검사"
    ])

    with t_cfg_student:
        st.markdown("#### 🎯 학생 종합 현황 및 진도 관리")
        if student_list:
            selected_student = st.selectbox("조회할 학생 선택", student_list, key="tab1_stu_sel")
            s_milestones = get_student_milestones(selected_student)
            s_m_progress = get_milestone_progress(selected_student)

            if s_milestones:
                def parse_type_sort_key_teacher(item):
                    t_name = item[3]
                    match = re.search(r'(\d+)', t_name)
                    num = int(match.group(1)) if match else 999
                    return (item[1], item[2], num, t_name)

                sorted_s_milestones = sorted(s_milestones, key=parse_type_sort_key_teacher)

                grouped_t_milestones = {}
                for m_id, sub, ch, t_name, v_url in sorted_s_milestones:
                    grouped_t_milestones.setdefault((sub, ch), []).append((m_id, t_name, v_url))
                
                def parse_chapter_sort_key_teacher(sub_ch_tuple):
                    sub, ch = sub_ch_tuple
                    match = re.search(r'(\d+)', ch)
                    num = int(match.group(1)) if match else 999
                    return (sub, num, ch)

                sorted_t_grouped_keys = sorted(grouped_t_milestones.keys(), key=parse_chapter_sort_key_teacher)

                for (sub, ch) in sorted_t_grouped_keys:
                    items = grouped_t_milestones[(sub, ch)]
                    done_cnt = sum(1 for m_id, _, _ in items if s_m_progress.get(m_id, False))
                    with st.expander(f"[{sub}] {ch}  (완료: {done_cnt}/{len(items)})", expanded=False):
                        for idx, (m_id, t_name, v_url) in enumerate(items):
                            is_done = s_m_progress.get(m_id, False)
                            chk_key = f"t_milestone_{selected_student}_{ch}_{m_id}_{idx}"
                            if st.checkbox(f"{t_name}", value=is_done, key=chk_key) != is_done:
                                save_single_milestone_progress(selected_student, m_id, st.session_state[chk_key])
                                st.rerun()
            else:
                st.info("해당 학생에게 배정된 단원이 없습니다.")

    with t_cfg_notice:
        st.markdown("#### 📢 전체 또는 학생별 공지사항 등록")
        with st.form("add_notice_form"):
            notice_target_type = st.radio("공지 대상 선택", ["🌐 전체 공지", "👤 특정 학생 지정 공지"], horizontal=True)
            target_student_name = st.selectbox("대상 학생 선택", student_list, key="notice_target_student") if notice_target_type == "👤 특정 학생 지정 공지" and student_list else ""
            notice_title = st.text_input("공지사항 제목", placeholder="예: 보충 수업 안내")
            notice_content = st.text_area("공지사항 내용", placeholder="상세 내용을 입력하세요...")
            if st.form_submit_button("📢 공지사항 등록하기", type="primary"):
                if notice_title.strip() and notice_content.strip():
                    add_notice(target_student_name if notice_target_type == "👤 특정 학생 지정 공지" else "", notice_title.strip(), notice_content.strip())
                    st.success("등록되었습니다!")
                    st.rerun()

        st.markdown("---")
        all_notices = get_all_notices()
        if all_notices:
            for n_id, n_target, n_title, n_content, n_date in all_notices:
                with st.container(border=True):
                    badge_str = "🌐 [전체 공지]" if not n_target else f"👤 [{n_target} 학생 맞춤]"
                    col_n_info, col_n_del = st.columns([5, 1])
                    with col_n_info:
                        st.markdown(f"**{badge_str} {n_title}** <span style='font-size:12px; color:gray;'>(작성일: {n_date})</span>", unsafe_allow_html=True)
                        st.caption(n_content)
                    with col_n_del:
                        if st.button("🗑️ 삭제", key=f"del_notice_{n_id}"):
                            delete_notice(n_id)
                            st.success("삭제되었습니다!")
                            st.rerun()

    with t_cfg_hw:
        st.markdown("#### 📅 학생 개별 과제 및 매일 루틴 과제 관리")
        if student_list:
            selected_hw_student = st.selectbox("과제를 관리할 학생 선택", student_list, key="tab3_stu_sel")
            
            with st.expander("🔥 학생별 [매일 반복 루틴 과제] 설정", expanded=False):
                with st.form("add_teacher_routine_form"):
                    new_routine_txt = st.text_area("루틴 과제 항목 입력", placeholder="- 오답노트 정리\n- 영어 단어 암기")
                    if st.form_submit_button("➕ 루틴 일괄 등록", type="primary"):
                        if new_routine_txt.strip():
                            bulk_insert_daily_routines(selected_hw_student, new_routine_txt)
                            st.success("등록되었습니다!")
                            st.rerun()
                
                current_routines = get_student_daily_routines(selected_hw_student)
                if current_routines:
                    routines_to_delete = []
                    for r_id, r_title in current_routines:
                        if st.checkbox(f"📌 {r_title}", key=f"chk_del_routine_{r_id}"):
                            routines_to_delete.append(r_id)
                    if st.button("🗑️ 선택한 루틴 삭제하기", type="primary"):
                        if routines_to_delete:
                            for r_id in routines_to_delete:
                                delete_daily_routine(r_id)
                            st.success("삭제되었습니다!")
                            st.rerun()

            existing_hw_dates = get_student_homework_dates(selected_hw_student)
            if existing_hw_dates:
                with st.expander("✏️ 날짜별 숙제 수정 및 삭제", expanded=False):
                    chosen_edit_date = st.selectbox("숙제 날짜 선택", existing_hw_dates, format_func=lambda d: f"{d} ({get_weekday_kr(d)})", key="select_date_to_edit_bulk")
                    date_hws = get_student_homework_by_date(selected_hw_student, chosen_edit_date)
                    initial_text_val = "\n".join([h[1] for h in date_hws])
                    with st.form(f"bulk_edit_hw_form_{chosen_edit_date}"):
                        new_bulk_text = st.text_area("숙제 내용 편집", value=initial_text_val, height=150)
                        col_be1, col_be2 = st.columns(2)
                        with col_be1:
                            if st.form_submit_button("💾 수정 저장", type="primary"):
                                update_student_homework_by_date(selected_hw_student, chosen_edit_date, new_bulk_text.strip())
                                st.success("수정되었습니다!")
                                st.rerun()
                        with col_be2:
                            if st.form_submit_button("🗑️ 전체 삭제"):
                                delete_student_homework_date(selected_hw_student, chosen_edit_date)
                                st.success("삭제되었습니다!")
                                st.rerun()

            templates = get_homework_templates()
            if templates:
                st.markdown("📌 **템플릿 불러오기**")
                selected_template_to_load = st.selectbox(
                    "불러올 템플릿 선택", 
                    ["-- 템플릿 선택 --"] + [t[1] for t in templates], 
                    key="select_hw_template_box"
                )
                if st.button("📥 선택한 템플릿 내용 적용하기", type="secondary"):
                    if selected_template_to_load and selected_template_to_load != "-- 템플릿 선택 --":
                        current_hw_area = st.session_state.get("hw_text_area_input", "")
                        st.session_state["hw_text_area_input"] = (current_hw_area + "\n" + selected_template_to_load) if current_hw_area.strip() else selected_template_to_load
                        st.success("템플릿 내용이 아래 과제 입력란에 추가되었습니다!")
                        st.rerun()

            with st.form("add_student_hw_form"):
                hw_date_input = st.date_input("과제 등록일(날짜)", value=get_korean_today())
                teacher_msg_input = st.text_input("💬 선생님 한마디 (선택)")
                
                hw_text_area = st.text_area(
                    "과제 내용 (문장 끝에 26/11/15 적으면 개별 마감일 자동 지정)", 
                    value=st.session_state.get("hw_text_area_input", ""),
                    key="hw_text_area_input", 
                    height=150, 
                    placeholder="예시:\n교과서 10쪽 풀기\n단원 평가 오답노트 작성 26/11/15"
                )
                
                col_sub1, col_sub2 = st.columns(2)
                with col_sub1:
                    if st.form_submit_button("과제 등록", type="primary"):
                        if hw_text_area.strip():
                            bulk_insert_student_homework(selected_hw_student, str(hw_date_input), hw_text_area, teacher_msg_input)
                            st.success("등록되었습니다!")
                            st.rerun()
                with col_sub2:
                    if st.form_submit_button("💾 템플릿으로 저장"):
                        if hw_text_area.strip():
                            add_homework_template(hw_text_area.strip())
                            st.success("템플릿 저장 완료!")
                            st.rerun()

    with t_cfg_curriculum:
        st.markdown("#### 📚 과목 / 단원 / 세부 유형 관리")
        with st.form("unified_sub_form"):
            new_sub_input = st.text_input("새 과목 추가")
            if st.form_submit_button("과목 등록", type="primary"):
                if new_sub_input.strip() and add_subject(new_sub_input.strip()):
                    st.success("등록되었습니다!")
                    st.rerun()
        
        subjects_data = get_subjects()
        if subjects_data:
            with st.form("add_chapter_and_type_form"):
                target_subject = st.selectbox("과목 선택", [s[1] for s in subjects_data], key="manage_chapter_sub_sel")
                new_ch_name = st.text_input("단원 이름 (예: 6. 함수)")
                new_types_txt = st.text_area("세부 유형 (줄바꿈 입력)", placeholder="- 개념 정리\n- 대표 유형")
                if st.form_submit_button("➕ 단원 및 유형 등록", type="primary"):
                    if new_ch_name.strip():
                        conn, _ = get_db_connection()
                        c = conn.cursor()
                        q(c, "INSERT INTO chapters (subject, name) VALUES (?, ?)", (target_subject, new_ch_name.strip()))
                        ch_id = c.lastrowid
                        types_list = [t.strip() for t in new_types_txt.split('\n') if t.strip()] or ["단원 기본 학습"]
                        for t_name in types_list:
                            clean_t_name = t_name.lstrip('-•*└\t ').strip()
                            if clean_t_name:
                                q(c, "INSERT INTO chapter_types (chapter_id, name, video_url) VALUES (?, ?, ?)", (ch_id, clean_t_name, ""))
                        conn.commit()
                        st.cache_data.clear()
                        st.success("등록되었습니다!")
                        st.rerun()

            selected_manage_sub = st.selectbox("관리할 과목 선택", [s[1] for s in subjects_data], key="manage_edit_sub_sel")
            sub_chapters = [ch for ch in get_chapters() if ch[1] == selected_manage_sub]
            if sub_chapters:
                ch_options = {ch[0]: ch[2] for ch in sub_chapters}
                selected_ch_id = st.selectbox("관리할 단원 선택", options=list(ch_options.keys()), format_func=lambda x: ch_options[x], key="manage_edit_ch_sel")
                if selected_ch_id:
                    types_rows = get_chapter_types(selected_ch_id)
                    if types_rows:
                        with st.expander("📌 세부 유형 및 해설 링크 설정", expanded=False):
                            for t_id, t_name, t_vurl in types_rows:
                                with st.container(border=True):
                                    with st.form(f"edit_type_form_{t_id}"):
                                        col_t1, col_t2 = st.columns([2, 3])
                                        with col_t1: edited_t_name = st.text_input("유형 이름", value=t_name, key=f"t_name_{t_id}")
                                        with col_t2: edited_t_url = st.text_input("링크", value=t_vurl, key=f"t_url_{t_id}")
                                        if st.form_submit_button("💾 수정", type="primary"):
                                            conn, _ = get_db_connection()
                                            c = conn.cursor()
                                            q(c, "UPDATE chapter_types SET name = ?, video_url = ? WHERE id = ?", (edited_t_name.strip(), edited_t_url.strip(), t_id))
                                            conn.commit()
                                            st.cache_data.clear()
                                            st.success("수정 완료!")
                                            st.rerun()

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
                        with st.expander(f"📚 [{sub_name}] 단원 목록"):
                            for ch_id, ch_sub, ch_name in sub_chapters:
                                if st.checkbox(f"{ch_name}", value=ch_name in assigned_chapters, key=f"assign_ch_chk_{selected_assign_student}_{ch_id}"):
                                    selected_ch_ids.append(ch_id)
                if st.form_submit_button("선택 단원 일괄 배정", type="primary"):
                    if selected_ch_ids:
                        assign_chapters_to_student(selected_assign_student, selected_ch_ids)
                        st.success("배정 완료!")
                        st.rerun()

    with t_cfg_wrong:
        st.markdown("#### 🔍 학생별 오답노트 조회 및 모아보기")
        if student_list:
            chk_student_choice = st.selectbox("조회할 학생 선택", ["전체 학생 (모두 보기)"] + student_list, key="chk_wrong_student_choice")
            wrong_view_mode = st.radio("모아보기 방식 선택", ["📂 단원별 보기", "📅 날짜별 보기", "📆 주간별(월~일) 한 주 모아보기", "🚨 해설 링크 없는 문제 모아보기"], horizontal=True)
            
            conn, db_type = get_db_connection()
            c = conn.cursor()
            target_rows = []
            
            if wrong_view_mode == "📂 단원별 보기":
                if chk_student_choice == "전체 학생 (모두 보기)":
                    q(c, "SELECT student_name, unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE numbers_text != ''", ())
                else:
                    q(c, "SELECT student_name, unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE student_name = ? AND numbers_text != ''", (chk_student_choice,))
                target_rows = c.fetchall()

            elif wrong_view_mode in ["📅 날짜별 보기", "📆 주간별(월~일) 한 주 모아보기"]:
                @st.cache_data(ttl=30, show_spinner=False)
                def get_cached_wrong_logs(student_name_filter):
                    conn_c, db_t = get_db_connection()
                    cursor = conn_c.cursor()
                    if student_name_filter == "전체 학생 (모두 보기)":
                        q(cursor, "SELECT student_name, unit_code, prob_num, registered_date FROM student_wrong_logs ORDER BY registered_date DESC, unit_code, prob_num", ())
                    else:
                        q(cursor, "SELECT student_name, unit_code, prob_num, registered_date FROM student_wrong_logs WHERE student_name = ? ORDER BY registered_date DESC, unit_code, prob_num", (student_name_filter,))
                    return cursor.fetchall()

                log_rows = get_cached_wrong_logs(chk_student_choice)

                if log_rows:
                    if wrong_view_mode == "📅 날짜별 보기":
                        available_dates = sorted(list(set(r[3] for r in log_rows if r[3])), reverse=True)
                        selected_date_filter = st.selectbox("📅 확인하고 싶은 날짜 선택", ["전체 날짜 보기 (최근순)"] + available_dates)
                        filtered_logs = log_rows if selected_date_filter == "전체 날짜 보기 (최근순)" else [r for r in log_rows if r[3] == selected_date_filter]
                        
                        grouped_map = {}
                        for s_name, u_code, p_num, reg_date in filtered_logs:
                            key = (s_name, u_code, reg_date)
                            grouped_map.setdefault(key, []).append(p_num)
                        
                        for (s_name, u_code, reg_date), num_list in grouped_map.items():
                            nums_txt = ", ".join(map(str, sorted(num_list)))
                            target_rows.append((s_name, u_code, nums_txt, reg_date))
                    else:
                        def get_week_range_str(date_str):
                            try:
                                d = date.fromisoformat(date_str)
                                start_week = d - timedelta(days=d.weekday())
                                end_week = start_week + timedelta(days=6)
                                return f"{start_week} ~ {end_week} (월~일)"
                            except Exception:
                                return "날짜 미상 주간"
                        
                        weeks_dict = {}
                        for s_name, u_code, p_num, reg_date in log_rows:
                            weeks_dict.setdefault(get_week_range_str(reg_date) if reg_date else "날짜 미상 주간", []).append((s_name, u_code, p_num, reg_date))
                        
                        sorted_weeks = sorted(weeks_dict.keys(), reverse=True)
                        selected_week = st.selectbox("📆 확인할 주간 선택 (월요일~일요일)", sorted_weeks)
                        filtered_logs = weeks_dict.get(selected_week, []) if selected_week else []

                        grouped_map = {}
                        for s_name, u_code, p_num, reg_date in filtered_logs:
                            key = (s_name, u_code, reg_date)
                            grouped_map.setdefault(key, []).append(p_num)
                        
                        for (s_name, u_code, reg_date), num_list in grouped_map.items():
                            nums_txt = ", ".join(map(str, sorted(num_list)))
                            target_rows.append((s_name, u_code, nums_txt, reg_date))
            else:
                if chk_student_choice == "전체 학생 (모두 보기)":
                    q(c, "SELECT student_name, unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE numbers_text != ''", ())
                else:
                    q(c, "SELECT student_name, unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE student_name = ? AND numbers_text != ''", (chk_student_choice,))
                all_raw_rows = c.fetchall()
                
                all_check_codes = []
                for s_name, u_code, nums_txt, u_date in all_raw_rows:
                    for n in parse_numbers(nums_txt):
                        all_check_codes.append(f"{u_code}{n:03d}".upper())
                batch_link_map = get_batch_problem_link_info(all_check_codes)
                
                for s_name, u_code, nums_txt, u_date in all_raw_rows:
                    parsed_s = parse_numbers(nums_txt)
                    missing_nums = []
                    for n in parsed_s:
                        f_code = f"{u_code}{n:03d}".upper()
                        v_url, _ = batch_link_map.get(f_code, ("", ""))
                        if not v_url or not v_url.strip():
                            missing_nums.append(n)
                    if missing_nums:
                        target_rows.append((s_name, u_code, ", ".join(map(str, sorted(missing_nums))), u_date))

            if target_rows:
                summary_student_counts = {}
                all_target_full_codes = []
                
                for s_name, u_code, nums_txt, u_date in target_rows:
                    parsed_s = parse_numbers(nums_txt)
                    if parsed_s:
                        summary_student_counts[s_name] = summary_student_counts.get(s_name, 0) + len(parsed_s)
                        for n in parsed_s:
                            all_target_full_codes.append(f"{u_code}{n:03d}".upper())
                
                unique_codes = list(set(all_target_full_codes))
                batch_link_cache = get_batch_problem_link_info(unique_codes)
                search_missing_total = sum(1 for f_code in unique_codes if not batch_link_cache.get(f_code, ("", ""))[0])

                with st.container(border=True):
                    total_sum_all = sum(summary_student_counts.values())
                    st.markdown(
                        f"""
                        <div style="font-size: 14px; font-weight: bold; margin-bottom: 6px;">📈 현재 검색 조건 통계 요약</div>
                        <div style="font-size: 13px; margin-bottom: 8px;">
                            🚨 해설 링크 누락(빨간색): <b style="color: #EF4444;">{search_missing_total}개</b> &nbsp;|&nbsp; 
                            📚 전체 오답 문제: <b style="color: #0284C7;">{total_sum_all}개</b>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    if summary_student_counts:
                        st.markdown("<div style='font-size: 12px; color: gray; margin-bottom: 4px;'>👤 학생별 총 오답 문제 수</div>", unsafe_allow_html=True)
                        st.markdown(" | ".join([f"`{s}`: **{c}개**" for s, c in summary_student_counts.items()]))
                st.markdown("---")

                for s_name, u_code, nums_txt, u_date in target_rows:
                    parsed_s = parse_numbers(nums_txt)
                    if parsed_s:
                        with st.container(border=True):
                            st.markdown(f"##### 👤 **{s_name}** | 📖 단원코드: `{u_code}` <span style='font-size:12px; color:gray;'>(등록일: {u_date})</span>", unsafe_allow_html=True)
                            
                            colored_num_tags = []
                            for n in sorted(list(parsed_s)):
                                f_code = f"{u_code}{n:03d}".upper()
                                v_url, _ = batch_link_cache.get(f_code, ("", ""))
                                if v_url and v_url.strip():
                                    colored_num_tags.append(f"<span style='color: #0284C7; font-weight: bold;'>{n:03d}</span>")
                                else:
                                    colored_num_tags.append(f"<span style='color: #DC2626; font-weight: bold;'>{n:03d}</span>")

                            st.markdown(f"<div style='padding: 10px; border-radius: 6px; font-family: monospace; font-size: 15px; border:1px solid rgba(128,128,128,0.3);'>{u_code}_({', '.join(colored_num_tags)})</div>", unsafe_allow_html=True)
            else:
                st.info("조건에 일치하는 오답노트 기록이 없습니다.")
        else:
            st.warning("등록된 학생이 없습니다.")

    with t_cfg_matrix:
        st.markdown("#### 📊 전체 학생 숙제 현황 및 통합 관리")
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, "SELECT DISTINCT hw_date FROM student_homework ORDER BY hw_date DESC")
        all_hw_dates = [r[0] for r in c.fetchall()]
        
        if all_hw_dates and student_list:
            selected_matrix_date = st.selectbox("확인할 숙제 날짜 선택", all_hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
            all_students_hw_map = get_all_students_homework_map(selected_matrix_date)
            entire_hw_prog = get_entire_homework_progress_map()
            active_hw_students = [s_name for s_name in student_list if all_students_hw_map.get(s_name)]

            if active_hw_students:
                for s_idx_main, s_name in enumerate(active_hw_students):
                    hws = all_students_hw_map.get(s_name, [])
                    with st.expander(f"👤 {s_name} 학생 숙제 현황 (총 {len(hws)}개 항목)", expanded=False):
                        initial_mat_text = "\n".join([hw[1] for hw in hws])
                        for h_idx, hw_tuple in enumerate(hws):
                            h_id = hw_tuple[0]
                            title = hw_tuple[1]
                            due_date = hw_tuple[2] if len(hw_tuple) > 2 else ""

                            if title.startswith("💬 [선생님 메시지]:"):
                                st.info(f"💬 **선생님 한마디**: {title.replace('💬 [선생님 메시지]:', '').strip()}")
                            else:
                                is_done = entire_hw_prog.get((s_name, h_id), False)
                                chk_key = f"mat_{s_idx_main}_{selected_matrix_date}_{h_id}_{h_idx}"
                                
                                date_suffix = ""
                                if due_date and due_date.strip():
                                    short_wday = get_weekday_short_kr(due_date)
                                    wday_str = f" ({short_wday})" if short_wday else ""
                                    date_suffix = f" (마감: {due_date}{wday_str})"

                                if st.checkbox(f"📌 {title}{date_suffix}", value=is_done, key=chk_key) != is_done:
                                    save_single_homework_progress(s_name, h_id, st.session_state[chk_key])
                                    st.rerun()
                        with st.popover("✏️ 이 날짜 숙제 수정 / 편집"):
                            with st.form(f"matrix_bulk_edit_form_{s_idx_main}_{selected_matrix_date}"):
                                edited_bulk_hw_text = st.text_area("숙제 내용 편집", value=initial_mat_text, height=120)
                                if st.form_submit_button("💾 수정 저장", type="primary"):
                                    update_student_homework_by_date(s_name, selected_matrix_date, edited_bulk_hw_text.strip())
                                    st.success("수정 완료!")
                                    st.rerun()
            else:
                st.info("해당 날짜에 배정된 숙제가 없습니다.")

    with t_cfg_links:
        st.markdown("#### 🎥 문제별 풀이해설 링크 통합 관리")
        col_link_tab1, col_link_tab2 = st.tabs(["➕ 개별 및 일괄 링크 등록", "📋 단원별 드롭다운 및 검색 관리"])
        
        with col_link_tab1:
            with st.form("add_problem_link_form"):
                col_pl1, col_pl2 = st.columns([1, 2])
                with col_pl1: f_code_in = st.text_input("문제 번호 (예: B1353015)")
                with col_pl2: v_url_in = st.text_input("네이버 카페 URL")
                if st.form_submit_button("➕ 개별 등록", type="primary"):
                    if f_code_in.strip() and v_url_in.strip():
                        if save_problem_link(f_code_in.strip(), v_url_in.strip()):
                            st.toast("🎥 해설 링크가 안전하게 등록되었습니다!", icon="✅")
                            st.success("저장되었습니다!")
                            st.rerun()
                        else:
                            st.error("등록 실패: 문제 번호가 4자리 이상인지 확인해 주세요.")
                    else:
                        st.warning("모두 입력해 주세요.")
            
            with st.form("bulk_problem_link_form"):
                bulk_txt = st.text_area("일괄 등록 (줄바꿈 입력)", placeholder="B1353015 https://cafe.naver.com/.../123")
                if st.form_submit_button("📥 일괄 등록 실행", type="primary"):
                    if bulk_txt.strip():
                        s_cnt, f_cnt = bulk_save_problem_links(bulk_txt)
                        st.toast(f"🎥 성공 {s_cnt}개 등록됨! (실패: {f_cnt}개)", icon="✅")
                        st.success(f"성공 {s_cnt}개 등록됨! (실패: {f_cnt}개)")
                        st.rerun()

        with col_link_tab2:
            st.markdown("##### 📂 단원별 드롭다운 선택 또는 직접 검색")
            unit_summaries = get_unit_code_summary_list()
            dropdown_options = ["-- 단원을 선택하세요 (등록된 링크 개수 표시) --"] + [f"{u_code} (총 {cnt}개 해설 링크)" for u_code, cnt in unit_summaries]
            unit_count_map = {f"{u_code} (총 {cnt}개 해설 링크)": u_code for u_code, cnt in unit_summaries}
            
            col_dd, col_sc = st.columns(2)
            with col_dd:
                selected_dropdown_item = st.selectbox("📌 단원별 드롭다운 셀렉트", dropdown_options)
            with col_sc:
                search_link_input = st.text_input("🔍 직접 검색 (단원코드 또는 문제번호)", placeholder="예: B1353").strip()
            
            target_filter = search_link_input if search_link_input else (unit_count_map.get(selected_dropdown_item, "") if selected_dropdown_item != "-- 단원을 선택하세요 (등록된 링크 개수 표시) --" else "")

            if target_filter:
                searched_links, search_cnt = get_all_problem_links_searched(target_filter)
                st.markdown(f"**📂 검색/선택 결과: 총 {search_cnt}개**")
                
                if searched_links:
                    st.markdown("💡 *삭제할 링크들을 선택하신 후 하단의 **'선택한 해설 링크 일괄 삭제하기'** 버튼을 누르세요!*")
                    
                    if "select_all_links_flag" not in st.session_state:
                        st.session_state["select_all_links_flag"] = False

                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        if st.button("☑️ 전체 선택 / 해제 반전", use_container_width=True):
                            st.session_state["select_all_links_flag"] = not st.session_state["select_all_links_flag"]
                            for l_id, _, _, _ in searched_links:
                                st.session_state[f"chk_link_del_{l_id}"] = st.session_state["select_all_links_flag"]
                            st.rerun()
                    
                    st.markdown("---")

                    links_to_delete = []
                    for l_id, f_code, v_url, u_code in searched_links:
                        if f"chk_link_del_{l_id}" not in st.session_state:
                            st.session_state[f"chk_link_del_{l_id}"] = st.session_state["select_all_links_flag"]
                        
                        chk_label = f"📌 [{f_code}] ({v_url})"
                        is_checked = st.checkbox(chk_label, key=f"chk_link_del_{l_id}")
                        if is_checked:
                            links_to_delete.append(l_id)
                    
                    st.markdown("---")
                    if st.button("🗑️ 선택한 해설 링크 일괄 삭제하기", type="primary", use_container_width=True):
                        if links_to_delete:
                            conn, _ = get_db_connection()
                            c = conn.cursor()
                            for l_id in links_to_delete:
                                q(c, "DELETE FROM problem_links WHERE id = ?", (l_id,))
                            conn.commit()
                            st.cache_data.clear()
                            
                            st.session_state["select_all_links_flag"] = False
                            for l_id in links_to_delete:
                                session_key = f"chk_link_del_{l_id}"
                                if session_key in st.session_state:
                                    del st.session_state[session_key]
                                    
                            st.success(f"🎉 총 {len(links_to_delete)}개의 해설 링크가 삭제되었습니다!")
                            st.rerun()
                        else:
                            st.warning("삭제할 링크를 체크박스에서 선택해 주세요.")
                else:
                    st.info("해당 조건에 일치하는 해설 링크가 없습니다.")
            else:
                st.info("💡 단원을 선택하시거나 검색어를 입력해 주세요.")

    with t_cfg_stats:
        st.markdown("#### 📈 실시간 학습 참여 현황")
        today_active_cnt, total_visits, s_summary, daily_logs = get_visitor_stats()
        col_st1, col_st2 = st.columns(2)
        with col_st1: st.metric(label="📌 오늘 접속 학생 현황", value=f"{today_active_cnt}명")
        with col_st2: st.metric(label="📈 누적 방문 횟수", value=f"{total_visits}회")
        st.markdown("---")
        if s_summary:
            for s_name, last_time, v_count in s_summary:
                with st.container(border=True):
                    st.markdown(f"👤 **{s_name}** | 🕒 최근: {last_time} | **총 {v_count}회**")

    with t_cfg_tests:
        st.markdown("#### 📋 학생 온라인 테스트 제출 결과 조회 (테스트별 요약)")
        
        conn_sub, _ = get_db_connection()
        c_sub = conn_sub.cursor()
        try:
            q(c_sub, """
                SELECT 
                    student_name, 
                    test_title, 
                    MAX(submitted_at) AS submitted_at, 
                    COUNT(*) AS total_cnt, 
                    SUM(COALESCE(is_checked, 0)) AS correct_cnt
                FROM student_test_submissions
                GROUP BY student_name, test_title
                ORDER BY MAX(submitted_at) DESC
            """)
            summary_rows = c_sub.fetchall()
        except Exception:
            summary_rows = []

        if summary_rows:
            filter_stu = st.selectbox("학생별 필터링", ["전체 학생 보기"] + student_list, key="filter_sub_stu")
            filtered_summaries = summary_rows if filter_stu == "전체 학생 보기" else [r for r in summary_rows if r[0] == filter_stu]

            st.markdown(f"**총 응시 테스트 내역: {len(filtered_summaries)}건**")
            st.markdown("---")

            for idx, (s_name, t_title, sub_at, total_cnt, correct_cnt) in enumerate(filtered_summaries):
                correct_cnt = int(correct_cnt) if correct_cnt is not None else 0
                wrong_cnt = total_cnt - correct_cnt
                score_pct = int((correct_cnt / total_cnt) * 100) if total_cnt > 0 else 0

                with st.container(border=True):
                    st.markdown(f"👤 **학생**: `{s_name}` &nbsp;|&nbsp; 📝 **테스트명**: **{t_title}**")
                    st.markdown(
                        f"📊 **채점 결과**: 총 **{total_cnt}문항** 중 "
                        f"<span style='color:#10B981; font-weight:bold;'>정답 {correct_cnt}개</span> / "
                        f"<span style='color:#EF4444; font-weight:bold;'>오답 {wrong_cnt}개</span> "
                        f"(`{score_pct}%`) &nbsp;|&nbsp; 🕒 **제출일시**: {sub_at}",
                        unsafe_allow_html=True
                    )

                    with st.expander(f"🔍 문항별 상세 답안 보기 ({total_cnt}문항)", expanded=False):
                        q(c_sub, """
                            SELECT problem_id, student_answer, is_checked 
                            FROM student_test_submissions 
                            WHERE student_name = ? AND test_title = ?
                            ORDER BY id ASC
                        """, (s_name, t_title))
                        detail_items = c_sub.fetchall()

                        for p_id, s_ans, is_corr in detail_items:
                            corr_badge = "🟢 정답" if is_corr == 1 else "🔴 오답"
                            ans_txt = s_ans if (s_ans and str(s_ans).strip()) else "미입력"
                            st.markdown(f"- 📌 `{p_id}` : 학생 답안 **`{ans_txt}`** ({corr_badge})")
        else:
            st.info("아직 학생들이 제출한 온라인 테스트 결과가 없습니다.")

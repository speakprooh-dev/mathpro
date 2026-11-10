import streamlit as st
import sqlite3
from datetime import datetime, date, timedelta, timezone
import calendar
import re
import pandas as pd
import io
import os

st.set_page_config(page_title="MathPro 학생 맞춤 학습 로드맵", page_icon="📐", layout="centered")

if "teacher_authenticated" not in st.session_state:
    st.session_state["teacher_authenticated"] = False

# 🟢 [수정] URL 파라미터 key('db')를 일치시켜 F5 새로고침 시에도 모드 완전 유지
if "db" in st.query_params:
    st.session_state["db_mode_override"] = st.query_params["db"]
elif "db_mode_override" not in st.session_state:
    st.session_state["db_mode_override"] = "supabase"

# ==========================================
# ☁️ Supabase URL 방식 연동 설정 (버튼 토글 연동)
# ==========================================
try:
    import psycopg2
    from urllib.parse import urlparse
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

@st.cache_resource(show_spinner=False)
def get_persistent_postgres_connection(conn_url):
    """클라우드 DB 연결을 한 번만 맺고 메모리에 유지하여 속도를 로컬 수준으로 끌어올립니다."""
    conn = psycopg2.connect(conn_url, connect_timeout=5)
    conn.autocommit = True
    return conn

def get_db_connection():
    # 🟢 사용자가 앱 내에서 'supabase' 모드를 켰을 때만 작동
    if st.session_state["db_mode_override"] == "supabase" and SUPABASE_AVAILABLE and "supabase" in st.secrets:
        try:
            sec = st.secrets["supabase"]
            conn_url = sec.get("url", "postgresql://postgres.qfpclacalaaxbhhheosw:MathPro2026@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres")
            
            conn = get_persistent_postgres_connection(conn_url)
            
            if conn.closed != 0:
                st.cache_resource.clear()
                conn = get_persistent_postgres_connection(conn_url)
                
            return conn, "postgres"
        except Exception as e:
            pass
    
    # 기본값 또는 'local' 모드 선택 시 SQLite 파일 사용
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

# ==========================================
# 🚀 딜레이를 없애기 위한 초고속 일괄 캐시 함수들
# ==========================================
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

@st.cache_data(ttl=30)
def get_batch_problem_link_info(full_codes):
    """⚡ 여러 문제의 해설 링크 정보를 단 1회의 쿼리로 일괄 조회"""
    if not full_codes:
        return {}
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        placeholders = ', '.join(['%s' if db_type == "postgres" else '?'] * len(full_codes))
        query = f"SELECT full_code, video_url, updated_at FROM problem_links WHERE full_code IN ({placeholders})"
        q(c, query, tuple(full_codes))
        rows = c.fetchall()
        return {r[0].upper(): (r[1], r[2] if r[2] else "") for r in rows}
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_all_homework_progress_map(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT student_hw_id, is_checked FROM student_homework_progress WHERE student_name = ?", (student_name,))
        return {r[0]: bool(r[1]) for r in c.fetchall()}
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
def get_all_routine_logs_map(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT routine_id, log_date, is_checked FROM daily_routine_logs WHERE student_name = ?", (student_name,))
        return {(str(r[0]), r[1]): bool(r[2]) for r in c.fetchall()}
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_entire_daily_routines_map():
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT student_name, id, title FROM daily_routines ORDER BY id")
        rows = c.fetchall()
        routines_map = {}
        for s_name, r_id, title in rows:
            routines_map.setdefault(s_name, []).append((r_id, title))
        return routines_map
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_entire_daily_routine_logs_map(target_date_str):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT student_name, routine_id, is_checked FROM daily_routine_logs WHERE log_date = ?", (target_date_str,))
        rows = c.fetchall()
        logs_map = {}
        for s_name, r_id, is_chk in rows:
            logs_map[(s_name, str(r_id))] = bool(is_chk)
        return logs_map
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_all_students_homework_map(hw_date):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, "SELECT id, student_name, title FROM student_homework WHERE hw_date = %s ORDER BY student_name, id", (hw_date,))
        else:
            q(c, "SELECT id, student_name, title FROM student_homework WHERE hw_date = ? ORDER BY student_name, id", (hw_date,))
        rows = c.fetchall()
        hw_map = {}
        for h_id, s_name, title in rows:
            hw_map.setdefault(s_name, []).append((h_id, title))
        return hw_map
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
        
        q(c, """
            SELECT student_name, MAX(visit_time), COUNT(*) 
            FROM visitor_logs 
            GROUP BY student_name 
            ORDER BY MAX(visit_time) DESC
        """, ())
        s_summary = c.fetchall()
        
        q(c, """
            SELECT visit_date, COUNT(DISTINCT student_name), COUNT(*) 
            FROM visitor_logs 
            GROUP BY visit_date 
            ORDER BY visit_date DESC 
            LIMIT 7
        """, ())
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
            "daily_routines", "daily_routine_logs", "notices", "visitor_logs"
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
            "daily_routines", "daily_routine_logs", "notices", "visitor_logs"
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
                            clean_row = []
                            for val in row:
                                if pd.isna(val):
                                    clean_row.append(None)
                                elif isinstance(val, str):
                                    clean_row.append(val.strip())
                                else:
                                    clean_row.append(val)
                            data_tuples.append(tuple(clean_row))
                        
                        if target_table == "students" and "name" in cols:
                            non_key_cols = [col for col in cols if col != "name"]
                            if non_key_cols:
                                set_str = ", ".join([f"{col} = EXCLUDED.{col}" for col in non_key_cols])
                                insert_query = f"INSERT INTO {target_table} ({col_str}) VALUES %s ON CONFLICT (name) DO UPDATE SET {set_str}"
                            else:
                                insert_query = f"INSERT INTO {target_table} ({col_str}) VALUES %s ON CONFLICT (name) DO NOTHING"
                        elif target_table == "problem_links" and "full_code" in cols:
                            non_key_cols = [col for col in cols if col != "full_code"]
                            if non_key_cols:
                                set_str = ", ".join([f"{col} = EXCLUDED.{col}" for col in non_key_cols])
                                insert_query = f"INSERT INTO {target_table} ({col_str}) VALUES %s ON CONFLICT (full_code) DO UPDATE SET {set_str}"
                            else:
                                insert_query = f"INSERT INTO {target_table} ({col_str}) VALUES %s ON CONFLICT (full_code) DO NOTHING"
                        else:
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
        
        for key in list(st.session_state.keys()):
            if "student" in key or "df" in key or "conn" in key:
                try:
                    del st.session_state[key]
                except:
                    pass
        return True, f"🎉 복구 완료된 시트 목록:\n- " + ",\n- ".join(restored_sheets)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, f"복구 중 오류 발생: {str(e)}"

def migrate_local_to_supabase():
    try:
        import sqlite3
        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mathpro_roadmap.db")
        local_conn = sqlite3.connect(DB_PATH)
        local_cursor = local_conn.cursor()
        
        sec = st.secrets["supabase"]
        conn_url = sec.get("url", "postgresql://postgres.qfpclacalaaxbhhheosw:MathPro2026@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres")
        cloud_conn = psycopg2.connect(conn_url, connect_timeout=5)
        cloud_conn.autocommit = True
        cloud_cursor = cloud_conn.cursor()
        
        local_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in local_cursor.fetchall()]
        migrated_tables = []
        for table in tables:
            if table in ["sqlite_sequence", "backup_info"]:
                continue
            local_cursor.execute(f"SELECT * FROM {table}")
            rows = local_cursor.fetchall()
            if not rows:
                continue
            col_names = [description[0] for description in local_cursor.description]
            col_str = ", ".join(col_names)
            placeholders = ", ".join(["%s"] * len(col_names))
            try:
                cloud_cursor.execute(f"DELETE FROM {table}")
            except Exception:
                cloud_conn.rollback()
            insert_query = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})"
            try:
                cloud_cursor.executemany(insert_query, rows)
                cloud_conn.commit()
                migrated_tables.append(f"{table}({len(rows)}건)")
            except Exception as e:
                cloud_conn.rollback()
        local_conn.close()
        cloud_conn.close()
        return True, f"클라우드 전송 완료된 테이블: {', '.join(migrated_tables)}"
    except Exception as e:
        return False, f"동기화 중 오류 발생: {str(e)}"

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

def init_db():
    try:
        conn, db_type = get_db_connection()
        c = conn.cursor()
        if db_type == "postgres":
            c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY, drive_url TEXT DEFAULT \'\');')
            c.execute('CREATE TABLE IF NOT EXISTS subjects (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS chapters (id SERIAL PRIMARY KEY, subject TEXT NOT NULL, name TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS chapter_types (id SERIAL PRIMARY KEY, chapter_id INTEGER NOT NULL, name TEXT NOT NULL, video_url TEXT DEFAULT \'\');')
            c.execute('CREATE TABLE IF NOT EXISTS milestones (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, subject TEXT NOT NULL, chapter TEXT NOT NULL, type_name TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS homework (id SERIAL PRIMARY KEY, hw_date TEXT NOT NULL, title TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS student_homework (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, hw_date TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL);')
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
            conn.commit()
        else:
            c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY, drive_url TEXT DEFAULT \'\')')
            c.execute('CREATE TABLE IF NOT EXISTS subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS chapters (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, name TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS chapter_types (id INTEGER PRIMARY KEY AUTOINCREMENT, chapter_id INTEGER NOT NULL, name TEXT NOT NULL, video_url TEXT DEFAULT \'\')')
            c.execute('CREATE TABLE IF NOT EXISTS milestones (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, subject TEXT NOT NULL, chapter TEXT NOT NULL, type_name TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS homework (id INTEGER PRIMARY KEY AUTOINCREMENT, hw_date TEXT NOT NULL, title TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS student_homework (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, hw_date TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL)')
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
            conn.commit()

        try:
            c.execute("ALTER TABLE problem_links ADD COLUMN updated_at TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass

        try:
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_student_hw_prog_unique ON student_homework_progress (student_name, student_hw_id)')
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_routine_logs_unique ON daily_routine_logs (student_name, routine_id, log_date)')
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_student_wrong_unique ON student_wrong_entries (student_name, unit_code)')
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_problem_links_unique ON problem_links (full_code)')
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_student_wrong_solved_unique ON student_wrong_solved (student_name, full_code)')
            conn.commit()
        except Exception:
            pass

        q(c, "SELECT COUNT(*) FROM subjects")
        if c.fetchone()[0] == 0:
            default_subjects = ["수학(상)", "수학(하)", "수학Ⅰ", "수학Ⅱ", "미적분", "확률과 통계"]
            for sub in default_subjects:
                try:
                    if db_type == "postgres":
                        q(c, "INSERT INTO subjects (name) VALUES (%s) ON CONFLICT DO NOTHING", (sub,))
                    else:
                        q(c, "INSERT INTO subjects (name) VALUES (?)", (sub,))
                except Exception:
                    pass
            conn.commit()

        try:
            c.execute("DELETE FROM student_wrong_logs")
            c.execute("SELECT student_name, unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE numbers_text != ''")
            existing_wrong_rows = c.fetchall()
            today_default_str = str(get_korean_today())
            now_default_str = get_korean_now_str()
            
            for s_name, u_code, nums_txt, u_date in existing_wrong_rows:
                reg_date = u_date if u_date and len(u_date) >= 10 else today_default_str
                for num in parse_numbers(nums_txt):
                    if db_type == "sqlite":
                        c.execute('''
                            INSERT OR IGNORE INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (s_name, u_code, int(num), reg_date, now_default_str))
                    else:
                        c.execute('''
                            INSERT INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (student_name, unit_code, prob_num, registered_date) DO NOTHING
                        ''', (s_name, u_code, int(num), reg_date, now_default_str))
            conn.commit()
        except Exception as e:
            print(f"오답 로그 강제 동기화 예외: {e}")

    except Exception as e:
        print(f"DB 초기화 중 예외 발생: {e}")

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

@st.cache_data(ttl=30)
def get_students():
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, "SELECT name FROM students ORDER BY name")
        rows = c.fetchall()
        return [r[0] for r in rows]
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
        try:
            conn.rollback()
        except:
            pass
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
    q(c, "DELETE FROM student_wrong_solved WHERE student_name = ?", (name,))
    q(c, "DELETE FROM daily_routines WHERE student_name = ?", (name,))
    q(c, "DELETE FROM daily_routine_logs WHERE student_name = ?", (name,))
    q(c, "DELETE FROM notices WHERE student_name = ?", (name,))
    q(c, "DELETE FROM visitor_logs WHERE student_name = ?", (name,))
    conn.commit()
    st.cache_data.clear()

@st.cache_data(ttl=60)
def get_subjects():
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT id, name FROM subjects ORDER BY id")
    rows = c.fetchall()
    return rows

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
        try:
            conn.rollback()
        except:
            pass
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
            q(c, '''
                INSERT INTO problem_links (full_code, unit_code, prob_num, video_url, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (full_code, unit_code, prob_num, video_url, now_str))
        else:
            q(c, '''
                INSERT INTO problem_links (full_code, unit_code, prob_num, video_url, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(full_code) DO UPDATE SET video_url = ?, updated_at = ?
            ''', (full_code, unit_code, prob_num, video_url, now_str, video_url, now_str))
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
                        q(c, '''
                            INSERT INTO problem_links (full_code, unit_code, prob_num, video_url, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (full_code, unit_code, prob_num, video_url, now_str))
                    else:
                        q(c, '''
                            INSERT INTO problem_links (full_code, unit_code, prob_num, video_url, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(full_code) DO UPDATE SET video_url = ?, updated_at = ?
                        ''', (full_code, unit_code, prob_num, video_url, now_str, video_url, now_str))
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
        
        try:
            q(c, "SELECT id, full_code, video_url, unit_code FROM problem_links WHERE full_code LIKE ? OR unit_code LIKE ? ORDER BY unit_code, full_code", (search_val, search_val))
        except Exception:
            q(c, "SELECT 0, full_code, video_url, unit_code FROM problem_links WHERE full_code LIKE ? OR unit_code LIKE ? ORDER BY unit_code, full_code", (search_val, search_val))
            
        rows = c.fetchall()
        return rows, len(rows)
    except Exception as e:
        print(f"문제 링크 검색 예외: {e}")
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

def save_single_routine_log(student_name, routine_id_str, log_date_str, val):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, '''
        INSERT INTO daily_routine_logs (student_name, routine_id, log_date, is_checked)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(student_name, routine_id, log_date) DO UPDATE SET is_checked = ?
    ''', (student_name, str(routine_id_str), log_date_str, int(val), int(val)))
    conn.commit()
    st.cache_data.clear()

def save_daily_routine_logs(student_name, log_date, routine_checked_dict):
    conn, _ = get_db_connection()
    c = conn.cursor()
    for routine_id_str, val in routine_checked_dict.items():
        q(c, '''
            INSERT INTO daily_routine_logs (student_name, routine_id, log_date, is_checked)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_name, routine_id, log_date) DO UPDATE SET is_checked = ?
        ''', (student_name, str(routine_id_str), log_date, int(val), int(val)))
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
    
    q(c, """
        SELECT COUNT(*) FROM daily_routine_logs 
        WHERE student_name = ? AND log_date >= ? AND log_date <= ? AND is_checked = 1
    """, (student_name, start_date_str, today_str))
    completed_count = c.fetchone()[0]
    rate = int((completed_count / total_expected) * 100) if total_expected > 0 else 0
    return rate, completed_count, total_expected

@st.cache_data(ttl=30)
def get_student_routine_streak(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT COUNT(*) FROM daily_routines WHERE student_name = ?", (student_name,))
    total_routines = c.fetchone()[0]
    if total_routines == 0:
        return 0
    
    streak = 0
    check_date = get_korean_today()
    while True:
        d_str = str(check_date)
        q(c, "SELECT COUNT(*) FROM daily_routines WHERE student_name = ?", (student_name,))
        r_cnt = c.fetchone()[0]
        if r_cnt == 0:
            break
        
        q(c, """
            SELECT COUNT(*) FROM daily_routine_logs 
            WHERE student_name = ? AND log_date = ? AND is_checked = 1
        """, (student_name, d_str))
        done_cnt = c.fetchone()[0]
        
        if done_cnt >= r_cnt:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            if check_date == get_korean_today():
                check_date -= timedelta(days=1)
                continue
            else:
                break
    return streak

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
            q(c, """
                SELECT m.id, m.subject, m.chapter, m.type_name, 
                       COALESCE((SELECT t.video_url FROM chapter_types t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.name = m.chapter AND t.name = m.type_name LIMIT 1), '') as video_url
                FROM milestones m WHERE m.student_name = %s
            """, (student_name,))
        else:
            q(c, """
                SELECT m.id, m.subject, m.chapter, m.type_name, 
                       COALESCE((SELECT t.video_url FROM chapter_types t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.name = m.chapter AND t.name = m.type_name LIMIT 1), '') as video_url
                FROM milestones m WHERE m.student_name = ?
            """, (student_name,))
        return c.fetchall()
    except Exception:
        try:
            conn.rollback()
        except:
            pass
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
    if db_type == "postgres":
        q(c, "SELECT id, title FROM student_homework WHERE student_name = %s AND hw_date = %s ORDER BY id", (student_name, hw_date))
    else:
        q(c, "SELECT id, title FROM student_homework WHERE student_name = ? AND hw_date = ? ORDER BY id", (student_name, hw_date))
    return c.fetchall()

@st.cache_data(ttl=30)
def get_all_student_homework(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT id, hw_date, title FROM student_homework WHERE student_name = ? ORDER BY hw_date DESC, id DESC", (student_name,))
    return c.fetchall()

def bulk_insert_student_homework(student_name, hw_date, text_data, message_text=""):
    conn, _ = get_db_connection()
    c = conn.cursor()
    if message_text.strip():
        msg_header = f"💬 [선생님 메시지]: {message_text.strip()}"
        q(c, "INSERT INTO student_homework (student_name, hw_date, title, parent_id) VALUES (?, ?, ?, NULL)", (student_name, hw_date, msg_header))
    lines = text_data.strip().split('\n')
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        q(c, "INSERT INTO student_homework (student_name, hw_date, title, parent_id) VALUES (?, ?, ?, NULL)", (student_name, hw_date, line_str))
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
        rows = c.fetchall()
        return {r[0]: bool(r[1]) for r in rows}
    except Exception:
        return {}

@st.cache_data(ttl=30)
def get_student_homework_progress(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT student_hw_id, is_checked FROM student_homework_progress WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    return {r[0]: bool(r[1]) for r in rows}

def save_single_milestone_progress(student_name, milestone_id, val):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "sqlite":
            q(c, "DELETE FROM milestone_progress WHERE student_name = ? AND milestone_id = ?", (student_name, milestone_id))
            q(c, "INSERT INTO milestone_progress (student_name, milestone_id, is_checked) VALUES (?, ?, ?)", (student_name, milestone_id, int(val)))
        else:
            q(c, '''
                INSERT INTO milestone_progress (student_name, milestone_id, is_checked)
                VALUES (?, ?, ?)
                ON CONFLICT(student_name, milestone_id) DO UPDATE SET is_checked = ?
            ''', (student_name, milestone_id, int(val), int(val)))
        conn.commit()
        st.cache_data.clear()
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
            q(c, '''
                INSERT INTO student_homework_progress (student_name, student_hw_id, is_checked)
                VALUES (?, ?, ?)
                ON CONFLICT(student_name, student_hw_id) DO UPDATE SET is_checked = ?
            ''', (student_name, student_hw_id, int(val), int(val)))
        conn.commit()
        st.cache_data.clear()
    except Exception:
        pass

@st.cache_data(ttl=30)
def get_student_wrong_entry(student_name, unit_code):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT numbers_text FROM student_wrong_entries WHERE student_name = ? AND unit_code = ?", (student_name, unit_code))
    row = c.fetchone()
    return row[0] if row else ""

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
            q(c, '''
                INSERT INTO student_wrong_entries (student_name, unit_code, numbers_text, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(student_name, unit_code) DO UPDATE SET numbers_text = ?, updated_at = ?
            ''', (student_name, unit_code, numbers_text, today_str, numbers_text, today_str))
        
        parsed_nums = parse_numbers(numbers_text)
        for num in parsed_nums:
            if db_type == "sqlite":
                q(c, '''
                    INSERT OR IGNORE INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (student_name, unit_code, int(num), today_str, now_str))
            else:
                c.execute('''
                    INSERT INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (student_name, unit_code, prob_num, registered_date) DO NOTHING
                ''', (student_name, unit_code, int(num), today_str, now_str))

        conn.commit()
        st.cache_data.clear()
    except Exception as e:
        print(f"오답 저장 중 예외: {e}")

@st.cache_data(ttl=30)
def get_student_wrong_solved_status(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT full_code, is_solved FROM student_wrong_solved WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    return {r[0]: bool(r[1]) for r in rows}

def save_single_wrong_solved_status(student_name, full_code, is_solved_val):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "sqlite":
            q(c, "DELETE FROM student_wrong_solved WHERE student_name = ? AND full_code = ?", (student_name, full_code))
            q(c, "INSERT INTO student_wrong_solved (student_name, full_code, is_solved) VALUES (?, ?, ?)", (student_name, full_code, int(is_solved_val)))
        else:
            q(c, '''
                INSERT INTO student_wrong_solved (student_name, full_code, is_solved)
                VALUES (?, ?, ?)
                ON CONFLICT(student_name, full_code) DO UPDATE SET is_solved = ?
            ''', (student_name, full_code, int(is_solved_val), int(is_solved_val)))
        conn.commit()
        st.cache_data.clear()
    except Exception:
        pass

def parse_numbers(text):
    if not text:
        return set()
    nums = re.findall(r'\d+', text)
    return set(int(n) for n in nums)

# ----------------------------------------------------
# 🖼️ 메인 화면 상단 로고 이미지 배치 및 타이틀
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
        st.success("👑 선생님 모드 활성화됨")
        
        # 🟢 [정돈 완료] DB 연동 모드 설정 버튼 (중복 없이 단 하나만 깔끔하게 배치)
        st.markdown("##### 🔀 DB 연동 모드 설정")
        current_mode = st.session_state["db_mode_override"]
        
        if current_mode == "supabase":
            st.markdown(
                '<div style="background-color: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; padding: 10px; border-radius: 8px; margin-bottom: 10px; font-size: 13px; font-weight: bold; color: #10B981; text-align: center;">'
                '☁️ 현재 Supabase 클라우드 연동 중'
                '</div>',
                unsafe_allow_html=True
            )
            if st.button("📁 로컬 모드로 전환 (SQLite)", use_container_width=True, key="btn_switch_to_local"):
                st.session_state["db_mode_override"] = "local"
                st.query_params["db"] = "local"
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()
        else:
            st.markdown(
                '<div style="background-color: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; padding: 10px; border-radius: 8px; margin-bottom: 10px; font-size: 13px; font-weight: bold; color: #F59E0B; text-align: center;">'
                '📁 현재 로컬 파일 모드 연동 중'
                '</div>',
                unsafe_allow_html=True
            )
            if st.button("☁️ Supabase 클라우드 모드로 전환", use_container_width=True, key="btn_switch_to_supabase"):
                st.session_state["db_mode_override"] = "supabase"
                st.query_params["db"] = "supabase"
                st.cache_resource.clear()
                st.cache_data.clear()
                st.rerun()

        st.divider()

        if st.button("로그아웃 (학생 모드로 전환)", use_container_width=True):
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
        
        with st.expander("🔄 엑셀 파일로 데이터 복구하기", expanded=True):
            uploaded_backup = st.file_uploader("백업 엑셀 파일(.xlsx) 선택", type=["xlsx"])
            if uploaded_backup is not None:
                if st.button("🚀 엑셀 데이터로 DB 복구 실행", type="primary", use_container_width=True):
                    with st.spinner("데이터를 복구 중입니다... 잠시만 기다려주세요."):
                        success, msg = restore_from_excel(uploaded_backup)
                        if success:
                            st.success(f"🎉 {msg}")
                            if st.button("🔄 화면 새로고침하기"):
                                st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                            
        st.markdown("---")
        if st.button("☁️ 로컬 데이터를 Supabase 클라우드로 업로드", use_container_width=True):
            with st.spinner("로컬 데이터를 클라우드로 전송 중입니다... 잠시만 기다려주세요."):
                success, msg = migrate_local_to_supabase()
                if success:
                    st.success(f"🎉 {msg}")
                else:
                    st.error(f"❌ {msg}")
        st.divider()

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
# 1. [학생 전용 모드 / 일반 사용자 화면]
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

        if unchecked_count > 0:
            st.markdown(
                f'<div style="background-color: rgba(239, 68, 68, 0.1); border-left: 4px solid #EF4444; padding: 12px; border-radius: 8px; margin-bottom: 15px;">'
                f'<div style="font-size: 14px; font-weight: bold; color: #EF4444;">🚨 오늘 아직 완료하지 않은 루틴 과제가 <u>{unchecked_count}개</u> 있습니다!</div>'
                f'<div style="font-size: 12px; margin-top: 4px; color: inherit;">"날짜별 숙제" 탭에서 오늘 루틴을 체크하고 완료해 주세요! 🔥</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            if routines_chk_list:
                st.markdown(
                    f'<div style="background-color: rgba(16, 185, 129, 0.1); border-left: 4px solid #10B981; padding: 12px; border-radius: 8px; margin-bottom: 15px;">'
                    f'<div style="font-size: 14px; font-weight: bold; color: #10B981;">🎉 완벽합니다! 오늘의 모든 루틴 과제를 완료하셨습니다!</div>'
                    f'<div style="font-size: 13px; margin-top: 4px;">🔥 현재 연속 스트릭: <b>{current_streak}일째</b> 진행 중! 계속 멋진 모습을 보여주세요!</div>'
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

        with st.expander("📖 💡 [어플 100% 활용 가이드] 꼭 읽어보세요!", expanded=False):
            st.markdown("""
            - **📘 개념 진도 탭**: 선생님이 배정해주신 단원별 개념 학습 현황을 확인하고, 학습이 완료되면 체크박스를 눌러주세요. `🎥 개념해설` 버튼을 통해 복습 영상도 언제든 시청할 수 있습니다.
            - **📚 날짜별 숙제 탭**: 날짜별로 부여된 숙제와 매일 반복 루틴 과제를 확인하고, **과제를 완료할 때마다 체크박스를 꾹 눌러 완료 상태로 기록**해 주세요!
            - **💬 오답·질문 관리 탭**: 틀린 문제의 번호나 단원코드를 입력해 나만의 오답 노트를 만들고, 콤팩트한 리스트에서 복습이 끝난 문제는 **[복습 완료]** 체크를 해두어 체계적으로 학습을 관리할 수 있습니다.
            """)

        milestones = get_student_milestones(selected_student)
        hw_dates = get_student_homework_dates(selected_student)
        m_progress = get_milestone_progress(selected_student)
        h_progress = get_student_homework_progress(selected_student)
        all_hws_flat = get_all_student_homework(selected_student)

        total_m = len(milestones)
        completed_m = sum(1 for m in milestones if m_progress.get(m[0], False))
        m_percent = int((completed_m / total_m) * 100) if total_m > 0 else 0

        actual_hws_flat = [h for h in all_hws_flat if not h[2].startswith("💬 [선생님 메시지]:")]
        total_h = len(actual_hws_flat)
        completed_h = sum(1 for h in actual_hws_flat if h_progress.get(h[0], False))
        h_percent = int((completed_h / total_h) * 100) if total_h > 0 else 0

        r_rate, r_completed, r_total = get_routine_completion_rate(selected_student, 7)

        conn_alert, _ = get_db_connection()
        c_alert = conn_alert.cursor()
        q(c_alert, "SELECT unit_code, numbers_text FROM student_wrong_entries WHERE student_name = ? AND numbers_text != ''", (selected_student,))
        user_wrong_rows = c_alert.fetchall()
        
        solved_map_alert = get_student_wrong_solved_status(selected_student)
        unsolved_total_count = 0
        new_video_count = 0
        now_datetime_alert = datetime.now()

        target_full_codes = []
        for u_code, nums_txt in user_wrong_rows:
            parsed_nums = parse_numbers(nums_txt)
            for n in parsed_nums:
                target_full_codes.append(f"{u_code}{n:03d}".upper())

        batch_link_info = get_batch_problem_link_info(target_full_codes)

        for f_code in target_full_codes:
            v_url, v_up_at = batch_link_info.get(f_code, ("", ""))
            is_solved = solved_map_alert.get(f_code, False)
            if v_url and not is_solved:
                unsolved_total_count += 1
                try:
                    up_dt = datetime.strptime(v_up_at, "%Y-%m-%d %H:%M:%S")
                    if (now_datetime_alert - up_dt).total_seconds() <= 86400:
                        new_video_count += 1
                except Exception:
                    pass

        if unsolved_total_count > 0:
            st.markdown(
                f'''
                <div style="
                    background-color: rgba(239, 68, 68, 0.1);
                    border-left: 4px solid #EF4444;
                    padding: 12px 14px;
                    border-radius: 8px;
                    margin-bottom: 15px;
                ">
                    <div style="font-size: 13.5px; color: #F87171; font-weight: bold;">
                        🔥 미복습 오답: <span style="color: #FFF;">{unsolved_total_count}개</span> (새해설 대기: <span style="color: #FBBF24;">{new_video_count}개</span>)
                    </div>
                    <div style="font-size: 12px; margin-top: 4px; color: inherit;">
                        "오답·질문 관리" 탭에서 해설을 시청하고 복습 완료를 체크해 주세요! 💡
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        st.markdown("##### 📊 나의 학습 성취도 대시보드")
        
        with st.container(border=True):
            st.markdown("🎯 **개념 진도**")
            cols_m = st.columns([4, 1])
            with cols_m[0]:
                st.progress(m_percent / 100 if total_m > 0 else 0)
            with cols_m[1]:
                st.markdown(f"<div style='text-align:right; font-weight:bold; color:#0284C7;'>{m_percent}%</div>", unsafe_allow_html=True)
            st.caption(f"완료: {completed_m} / 총 {total_m}개")

        with st.container(border=True):
            st.markdown("📚 **숙제 완료**")
            cols_h = st.columns([4, 1])
            with cols_h[0]:
                st.progress(h_percent / 100 if total_h > 0 else 0)
            with cols_h[1]:
                st.markdown(f"<div style='text-align:right; font-weight:bold; color:#10B981;'>{h_percent}%</div>", unsafe_allow_html=True)
            st.caption(f"완료: {completed_h} / 총 {total_h}개")

        with st.container(border=True):
            st.markdown(f"🔥 **루틴 연속 달성 (스트릭: {current_streak}일 연속!)**")
            r_progress_val = (r_rate / 100) if r_rate <= 100 else 1.0
            cols_r = st.columns([4, 1])
            with cols_r[0]:
                st.progress(r_progress_val)
            with cols_r[1]:
                st.markdown(f"<div style='text-align:right; font-weight:bold; color:#F59E0B;'>{r_rate}%</div>", unsafe_allow_html=True)
            st.caption(f"최근 7일 기준 완료: {r_completed} / 총 {r_total}개")

        st.divider()

        tab1, tab2, tab3 = st.tabs(["📘 개념 진도", "📚 날짜별 숙제", "💬 오답·질문 관리"])

        with tab1:
            st.markdown("### 📘 나의 개념 학습 목록")
            st.caption("체크박스를 연속으로 눌러도 렉 없이 빠르게 반영됩니다! 🔥")
            if milestones:
                grouped_s_milestones = {}
                for m_id, sub, ch, t_name, v_url in milestones:
                    key = (sub, ch)
                    grouped_s_milestones.setdefault(key, []).append((m_id, t_name, v_url))

                for (sub, ch), items in grouped_s_milestones.items():
                    done_cnt = sum(1 for m_id, _, _ in items if m_progress.get(m_id, False))
                    with st.container(border=True):
                        st.markdown(f"**[{sub}] {ch}** &nbsp; <span style='font-size:12px; color:#0284C7; font-weight:bold;'>(완료: {done_cnt}/{len(items)})</span>", unsafe_allow_html=True)
                        st.markdown("---")
                        for idx, (m_id, t_name, v_url) in enumerate(items):
                            default_val = m_progress.get(m_id, False)
                            cols = st.columns([4, 1])
                            with cols[0]:
                                val = st.checkbox(
                                    f"{t_name}", 
                                    value=default_val, 
                                    key=f"s_milestone_chk_{selected_student}_{ch}_{m_id}_{idx}"
                                )
                                if val != default_val:
                                    save_single_milestone_progress(selected_student, m_id, val)
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
            
            total_r_cnt = len(daily_routines_list)
            done_r_cnt = sum(1 for r_id, _ in daily_routines_list if current_day_logs.get((str(r_id), today_str), False))
            
            routine_status_text = f"🔥 오늘 루틴: {done_r_cnt} / {total_r_cnt}개 완료 " + ("(올클리어! 🎉)" if total_r_cnt > 0 and done_r_cnt == total_r_cnt else "(미완료! 🚨)")
            routine_color = "#10B981" if total_r_cnt > 0 and done_r_cnt == total_r_cnt else "#EF4444"

            st.markdown(
                f'<div style="background-color: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.3); padding: 14px; border-radius: 10px; margin-bottom: 15px;">'
                f'<div style="font-size: 15px; font-weight: bold; margin-bottom: 4px;">⚡ 오늘의 학습 시작 전 필수 체크!</div>'
                f'<div style="font-size: 13px; color: gray; margin-bottom: 8px;">매일 루틴과 날짜별 숙제를 완료하고 체크박스를 꼭 눌러주세요.</div>'
                f'<div style="font-size: 13px; font-weight: bold; color: {routine_color}; white-space: nowrap;">{routine_status_text}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            st.markdown("### 🔥 매일 반복 루틴 체크")
            st.caption("오늘 해야 할 루틴을 완료하고 체크박스를 눌러주세요.")

            if daily_routines_list:
                with st.container(border=True):
                    st.markdown(f"**오늘 ({today_str}) 루틴 항목**")
                    st.markdown("---")
                    daily_routine_checked_dict = {}
                    for r_id, r_title in daily_routines_list:
                        default_val = current_day_logs.get((str(r_id), today_str), False)
                        daily_routine_checked_dict[str(r_id)] = st.checkbox(f"{r_title}", value=default_val, key=f"s_daily_{selected_student}_{r_id}")
                        st.divider()
                if daily_routine_checked_dict:
                    save_daily_routine_logs(selected_student, today_str, daily_routine_checked_dict)

            if hw_dates:
                st.markdown("")
                st.markdown("---")
                st.markdown("### 📚 날짜별 개별 숙제")
                st.caption("선생님이 배정해주신 날짜별 숙제를 확인하고 완료 체크를 해보세요.")
                
                selected_date = st.selectbox("확인할 숙제 날짜 선택", hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
                hws = get_student_homework_by_date(selected_student, selected_date)
                
                total_hw_cnt = len([h for h in hws if not h[1].startswith("💬 [선생님 메시지]:")])
                done_hw_cnt = sum(1 for h_id, title in hws if not title.startswith("💬 [선생님 메시지]:") and h_progress.get(h_id, False))
                hw_status_text = f"📚 선택일 숙제: {done_hw_cnt} / {total_hw_cnt}개 완료 " + ("(올클리어! 🎉)" if total_hw_cnt > 0 and done_hw_cnt == total_hw_cnt else "(미완료! 🚨)")
                hw_color = "#10B981" if total_hw_cnt > 0 and done_hw_cnt == total_hw_cnt else "#EF4444"

                st.markdown(
                    f'<div style="background-color: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.2); padding: 10px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 13px; font-weight: bold; color: {hw_color}; white-space: nowrap;">{hw_status_text}</div>',
                    unsafe_allow_html=True
                )

                with st.container(border=True):
                    for h_idx, (h_id, title) in enumerate(hws):
                        if title.startswith("💬 [선생님 메시지]:"):
                            msg_content = title.replace("💬 [선생님 메시지]:", "").strip()
                            st.info(f"📌 **선생님의 한마디**: {msg_content}")
                        else:
                            default_val = h_progress.get(h_id, False)
                            chk_key = f"s_hw_{selected_student}_{selected_date}_{h_id}_{h_idx}"
                            if st.checkbox(f"{title}", value=default_val, key=chk_key) != default_val:
                                save_single_homework_progress(selected_student, h_id, st.session_state[chk_key])
                                st.rerun()

        with tab3:
            st.markdown("### 💬 오답 및 질문 관리")
            with st.container(border=True):
                st.markdown("##### 📝 1. 나의 오답 및 질문 번호 저장/수정")
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
                        st.toast("🎉 오답 노트가 안전하게 저장되었습니다!", icon="✅")
                        st.success("저장되었습니다!")
                        st.rerun()
                    else:
                        st.warning("단원코드를 먼저 입력해 주세요.")

            st.markdown("")
            with st.container(border=True):
                st.markdown("##### 📝 2. 나의 오답노트 및 해설 바로가기")
                st.caption("저장된 단원을 선택하여 틀린 문제들의 복습 상태를 체크하고 해설 영상 바로 시청하세요.")

                conn, _ = get_db_connection()
                c = conn.cursor()
                q(c, "SELECT unit_code, numbers_text FROM student_wrong_entries WHERE student_name = ? AND numbers_text != '' ORDER BY unit_code", (selected_student,))
                saved_rows = c.fetchall()
                saved_units_list = [r[0] for r in saved_rows]
                
                solved_map_chk = get_student_wrong_solved_status(selected_student)
                now_datetime_chk = datetime.now()
                
                unit_display_options = ["-- 저장된 단원을 선택하세요 --"]
                unit_map_dict = {}
                
                all_saved_full_codes = []
                for u_code in saved_units_list:
                    entry_txt = get_student_wrong_entry(selected_student, u_code)
                    for n in parse_numbers(entry_txt):
                        all_saved_full_codes.append(f"{u_code}{n:03d}".upper())
                batch_saved_link_info = get_batch_problem_link_info(all_saved_full_codes)

                for u_code in saved_units_list:
                    entry_txt = get_student_wrong_entry(selected_student, u_code)
                    p_nums = parse_numbers(entry_txt)
                    has_new_unsolved = False
                    for n in p_nums:
                        f_code = f"{u_code}{n:03d}".upper()
                        v_url, v_up_at = batch_saved_link_info.get(f_code, ("", ""))
                        is_solved = solved_map_chk.get(f_code, False)
                        if v_url and not is_solved:
                            try:
                                up_dt = datetime.strptime(v_up_at, "%Y-%m-%d %H:%M:%S")
                                if (now_datetime_chk - up_dt).total_seconds() <= 86400:
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
                    existing_wrong = get_student_wrong_entry(selected_student, view_target_code)
                    if existing_wrong:
                        st.markdown("---")
                        st.markdown(f"**📌 `{view_target_code}` 단원 오답 목록**")
                        parsed_nums = parse_numbers(existing_wrong)
                        solved_map = get_student_wrong_solved_status(selected_student)
                        now_datetime = datetime.now()
                        
                        if parsed_nums:
                            query_params = st.query_params
                            for n in sorted(list(parsed_nums)):
                                full_code = f"{view_target_code}{n:03d}".upper()
                                v_url, v_updated_at = batch_saved_link_info.get(full_code, ("", ""))
                                is_solved = solved_map.get(full_code, False)
                                
                                is_new_alert = False
                                if v_url and v_updated_at:
                                    try:
                                        up_dt = datetime.strptime(v_updated_at, "%Y-%m-%d %H:%M:%S")
                                        if (now_datetime - up_dt).total_seconds() <= 86400:
                                            is_new_alert = True
                                    except Exception:
                                        pass

                                action_key = f"toggle_solved_{selected_student}_{full_code}"
                                if query_params.get(action_key) == "true":
                                    new_state = not is_solved
                                    save_single_wrong_solved_status(selected_student, full_code, new_state)
                                    query_params.pop(action_key, None)
                                    st.rerun()

                                badge_html = ' <span style="background-color:#EF4444; color:white; padding:1px 4px; border-radius:3px; font-size:10px; font-weight:bold;">🔥 새해설</span>' if is_new_alert else (' <span style="color:#DC2626; font-size:11px;">(링크 누락)</span>' if not v_url else '')
                                text_style = "text-decoration: line-through; color: gray;" if is_solved else "font-weight: bold;"
                                checkbox_checked_attr = "checked" if is_solved else ""
                                
                                html_row_content = f'''
                                <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; margin-bottom: 6px; padding: 4px 0;">
                                    <div style="display: flex; align-items: center; gap: 8px; overflow: hidden;">
                                        <input type="checkbox" {checkbox_checked_attr} 
                                            onchange="window.location.href='/?student={selected_student}&{action_key}=true'" 
                                            style="width: 18px; height: 18px; cursor: pointer; accent-color: #0284C7; flex-shrink: 0;">
                                        <div style="{text_style} font-size: 14px; white-space: nowrap;">복습 완료 ({full_code}){badge_html}</div>
                                    </div>
                                    <div style="flex-shrink: 0; margin-left: 10px;">
                                        {"<a href='" + v_url + "' target='_blank' style='padding:4px 10px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold; background-color:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.3); color:inherit;'>🎥 해설 영상</a>" if v_url else "<span style='font-size:11px; color:gray;'>준비중</span>"}
                                    </div>
                                </div>
                                '''
                                st.markdown(html_row_content, unsafe_allow_html=True)
                                st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid rgba(128,128,128,0.15);'>", unsafe_allow_html=True)
                    else:
                        st.info("현재 등록된 오답이 없습니다.")

            st.markdown("")
            with st.container(border=True):
                st.markdown("##### 🔍 3. 해설 영상 즉시 검색하기")
                st.caption("궁금한 문제 번호 전체 또는 단원코드만 입력하면 즉시 해설 영상으로 이동합니다.")
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
    else:
        st.info("👋 전용 URL로 접속한 학생 프로필이 선택되지 않았습니다. 링크를 확인해 주세요.")

# ====================================================
# 2. [선생님 전용 관리 모드 화면]
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
    
    t_cfg_student, t_cfg_notice, t_cfg_hw, t_cfg_curriculum, t_cfg_wrong, t_cfg_matrix, t_cfg_links, t_cfg_stats = st.tabs([
        "👤 1. [개별] 학생 진도 관리", 
        "📢 2. 공지사항 관리",
        "📅 3. 개별 과제 관리", 
        "📚 4. 커리큘럼 진도 배정", 
        "🔍 5. 오답노트 모아보기",
        "📊 6. 전체 숙제 매트릭스",
        "🎥 7. 해설 링크 관리",
        "📈 8. 실시간 학습 참여 현황"
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
                    with st.container(border=True):
                        st.markdown(f"**[{sub}] {ch}**", unsafe_allow_html=True)
                        st.markdown("---")
                        for idx, (m_id, t_name, v_url) in enumerate(items):
                            is_done = s_m_progress.get(m_id, False)
                            chk_key = f"t_milestone_{selected_student}_{ch}_{m_id}_{idx}"
                            if st.checkbox(f"{t_name}", value=is_done, key=chk_key) != is_done:
                                save_single_milestone_progress(selected_student, m_id, st.session_state[chk_key])
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
                        st.markdown(f"**{badge_str} {n_title}** <span style='font-size:12px; color:gray;'>(작성일: {n_date})</span>", unsafe_allow_html=True)
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
            
            with st.expander("🔥 학생별 [매일 반복 루틴 과제] 설정 및 다중 날짜 소급 매트릭스", expanded=False):
                with st.form("add_teacher_routine_form"):
                    st.markdown("##### ➕ 루틴 과제 항목 추가")
                    new_routine_txt = st.text_area("루틴 과제 항목 입력 (줄바꿈으로 여러 개 입력 가능)", placeholder="- 오답노트 오답 정리\n- 영어 단어 20개 암기")
                    if st.form_submit_button("➕ 루틴 과제 일괄 등록", type="primary"):
                        if new_routine_txt.strip():
                            bulk_insert_daily_routines(selected_hw_student, new_routine_txt)
                            st.success("루틴 과제가 등록되었습니다!")
                            st.rerun()
                
                current_routines = get_student_daily_routines(selected_hw_student)
                if current_routines:
                    st.markdown("---")
                    st.markdown("##### 📋 현재 등록된 루틴 과제 목록 (삭제할 항목 선택)")
                    routines_to_delete = []
                    for r_id, r_title in current_routines:
                        if st.checkbox(f"📌 {r_title}", key=f"chk_del_routine_{r_id}"):
                            routines_to_delete.append(r_id)
                    
                    if st.button("🗑️ 선택한 루틴 과제 삭제하기", type="primary"):
                        if routines_to_delete:
                            for r_id in routines_to_delete:
                                delete_daily_routine(r_id)
                            st.success("선택한 루틴 과제가 삭제되었습니다!")
                            st.rerun()
                        else:
                            st.warning("삭제할 루틴 과제를 체크박스에서 먼저 선택해 주세요.")

                    st.markdown("---")
                    st.markdown("##### 📊 최근 7일 루틴 수행 한눈에 소급 체크 (일괄 캐시 적용)")
                    st.caption("체크박스를 누르는 즉시 해당 날짜의 기록이 자동으로 저장됩니다.")
                    
                    today_obj = get_korean_today()
                    date_columns = [str(today_obj - timedelta(days=i)) for i in range(6, -1, -1)]
                    batch_routine_logs = get_all_routine_logs_map(selected_hw_student)

                    for r_id, r_title in current_routines:
                        st.markdown(f"**📌 {r_title}**")
                        cols = st.columns(7)
                        for idx, d_str in enumerate(date_columns):
                            with cols[idx]:
                                day_name = get_weekday_kr(d_str)[:1]
                                short_date = d_str[5:]
                                st.caption(f"{short_date}({day_name})")
                                def_val = batch_routine_logs.get((str(r_id), d_str), False)
                                chk_key = f"auto_mat_routine_{selected_hw_student}_{r_id}_{d_str}"
                                new_val = st.checkbox("체크", value=def_val, key=chk_key, label_visibility="collapsed")
                                if new_val != def_val:
                                    save_single_routine_log(selected_hw_student, r_id, d_str, new_val)
                                    st.rerun()
                        st.markdown("")

            st.markdown("---")
            st.markdown("##### 📝 날짜별 과제 부여 및 수정/삭제")
            existing_hw_dates = get_student_homework_dates(selected_hw_student)
            if existing_hw_dates:
                with st.expander("✏️ 등록된 날짜별 숙제 내용 통째로 수정 및 삭제하기", expanded=False):
                    chosen_edit_date = st.selectbox("수정할 숙제 날짜 선택", existing_hw_dates, format_func=lambda d: f"{d} ({get_weekday_kr(d)})", key="select_date_to_edit_bulk")
                    date_hws = get_student_homework_by_date(selected_hw_student, chosen_edit_date)
                    combined_titles = [h_title for _, h_title in date_hws]
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
                        st.session_state["hw_text_area_input"] = (current_val + "\n" + chosen) if current_val.strip() else chosen

                st.selectbox("📌 템플릿 선택", template_options, key="select_hw_template_box", on_change=on_template_change)

            with st.form("add_student_hw_form"):
                hw_date_input = st.date_input("과제 제출일", value=get_korean_today())
                teacher_msg_input = st.text_input("💬 학생에게 전하는 메시지 / 학습 지침 (선택)", placeholder="예: 개념 노트 복습 먼저 하고 풀어보자! 화이팅 🔥")
                hw_text_area = st.text_area("날짜별 과제 내용 입력", key="hw_text_area_input", placeholder="[진도 교재]\n  - p.12~15 문제 풀이", height=150)
                col_sub_btn1, col_sub_btn2 = st.columns(2)
                with col_sub_btn1:
                    submit_hw_btn = st.form_submit_button("과제 등록", type="primary")
                with col_sub_btn2:
                    save_as_tpl_btn = st.form_submit_button("💾 현재 내용을 템플릿으로 저장")
                
                if submit_hw_btn:
                    if hw_text_area.strip():
                        bulk_insert_student_homework(selected_hw_student, str(hw_date_input), hw_text_area, teacher_msg_input)
                        st.success("과제 및 메시지가 성공적으로 등록되었습니다!")
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
            if st.form_submit_button("과목 등록", type="primary"):
                if new_sub_input.strip() and add_subject(new_sub_input.strip()):
                    st.success("과목이 등록되었습니다!")
                    st.rerun()
        
        subjects_data = get_subjects()
        if subjects_data:
            st.markdown("---")
            st.markdown("##### 📂 단원 및 세부 유형 등록")
            with st.form("add_chapter_and_type_form"):
                target_subject = st.selectbox("과목 선택", [s[1] for s in subjects_data], key="manage_chapter_sub_sel")
                new_ch_name = st.text_input("새 단원 이름 (예: 6. 함수)", placeholder="예: 6. 함수")
                new_types_txt = st.text_area("세부 유형 항목 (줄바꿈으로 여러 개 입력)", placeholder="- 개념 정리\n- 대표 유형\n- 심화 문제")
                if st.form_submit_button("➕ 단원 및 세부 유형 일괄 등록", type="primary"):
                    if new_ch_name.strip():
                        conn, _ = get_db_connection()
                        c = conn.cursor()
                        try:
                            q(c, "INSERT INTO chapters (subject, name) VALUES (?, ?)", (target_subject, new_ch_name.strip()))
                            ch_id = c.lastrowid
                            types_list = [t.strip() for t in new_types_txt.split('\n') if t.strip()] or ["단원 기본 학습"]
                            for t_name in types_list:
                                clean_t_name = t_name.lstrip('-•*└\t ').strip()
                                if clean_t_name:
                                    q(c, "INSERT INTO chapter_types (chapter_id, name, video_url) VALUES (?, ?, ?)", (ch_id, clean_t_name, ""))
                            conn.commit()
                            st.cache_data.clear()
                            st.success("단원과 세부 유형이 성공적으로 등록되었습니다!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"등록 중 오류 발생: {str(e)}")
                    else:
                        st.warning("단원 이름을 입력해 주세요.")

            st.markdown("---")
            st.markdown("##### ✏️ 등록된 단원별 세부 유형 및 해설 링크 관리 (수정/삭제)")
            selected_manage_sub = st.selectbox("관리할 과목 선택", [s[1] for s in subjects_data], key="manage_edit_sub_sel")
            all_chapters = get_chapters()
            sub_chapters = [ch for ch in all_chapters if ch[1] == selected_manage_sub]
            
            if sub_chapters:
                ch_options = {ch[0]: ch[2] for ch in sub_chapters}
                selected_ch_id = st.selectbox("관리할 단원 선택", options=list(ch_options.keys()), format_func=lambda x: ch_options[x], key="manage_edit_ch_sel")
                if selected_ch_id:
                    col_ch_del1, col_ch_del2 = st.columns([4, 1])
                    with col_ch_del2:
                        if st.button("🗑️ 단원 삭제", key=f"del_chapter_btn_{selected_ch_id}", type="secondary"):
                            conn, _ = get_db_connection()
                            c = conn.cursor()
                            q(c, "DELETE FROM chapter_types WHERE chapter_id = ?", (selected_ch_id,))
                            q(c, "DELETE FROM chapters WHERE id = ?", (selected_ch_id,))
                            conn.commit()
                            st.cache_data.clear()
                            st.success("단원이 삭제되었습니다!")
                            st.rerun()
                    
                    types_rows = get_chapter_types(selected_ch_id)
                    if types_rows:
                        with st.expander("📌 하위 세부 유형 목록 및 해설 링크 설정", expanded=False):
                            for t_id, t_name, t_vurl in types_rows:
                                with st.container(border=True):
                                    with st.form(f"edit_type_form_{t_id}"):
                                        col_t1, col_t2 = st.columns([2, 3])
                                        with col_t1:
                                            edited_t_name = st.text_input("유형 이름", value=t_name, key=f"t_name_{t_id}")
                                        with col_t2:
                                            edited_t_url = st.text_input("해설 영상 링크 (URL)", value=t_vurl, key=f"t_url_{t_id}", placeholder="https://...")
                                        col_b1, col_b2 = st.columns(2)
                                        with col_b1:
                                            if st.form_submit_button("💾 유형 정보 수정 저장", type="primary"):
                                                conn, _ = get_db_connection()
                                                c = conn.cursor()
                                                q(c, "UPDATE chapter_types SET name = ?, video_url = ? WHERE id = ?", (edited_t_name.strip(), edited_t_url.strip(), t_id))
                                                conn.commit()
                                                st.cache_data.clear()
                                                st.success("수정 완료!")
                                                st.rerun()
                                        with col_b2:
                                            if st.form_submit_button("🗑️ 해당 유형 삭제"):
                                                conn, _ = get_db_connection()
                                                c = conn.cursor()
                                                q(c, "DELETE FROM chapter_types WHERE id = ?", (t_id,))
                                                conn.commit()
                                                st.cache_data.clear()
                                                st.success("삭제 완료!")
                                                st.rerun()
                    else:
                        st.info("등록된 세부 유형이 없습니다.")
            else:
                st.info("해당 과목에 등록된 단원이 없습니다.")

        if subjects_data and student_list:
            st.divider()
            st.markdown("##### 🎯 학생별 커리큘럼 단원 일괄 배정")
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
                                if st.checkbox(f"{ch_name}", value=ch_name in assigned_chapters, key=f"assign_ch_chk_{selected_assign_student}_{ch_id}"):
                                    selected_ch_ids.append(ch_id)
                if st.form_submit_button("선택한 단원 일괄 배정하기", type="primary"):
                    if selected_ch_ids:
                        assign_chapters_to_student(selected_assign_student, selected_ch_ids)
                        st.success("배정되었습니다!")
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
                conn_check, db_type_check = get_db_connection()
                c_check = conn_check.cursor()
                
                q(c_check, "SELECT COUNT(*) FROM student_wrong_logs", ())
                if c_check.fetchone()[0] == 0:
                    try:
                        q(c_check, "SELECT student_name, unit_code, numbers_text, updated_at FROM student_wrong_entries WHERE numbers_text != ''", ())
                        existing_wrong_rows = c_check.fetchall()
                        today_default_str = str(get_korean_today())
                        now_default_str = get_korean_now_str()
                        
                        for s_name, u_code, nums_txt, u_date in existing_wrong_rows:
                            reg_date = u_date if u_date and len(u_date) >= 10 else today_default_str
                            for num in parse_numbers(nums_txt):
                                if db_type_check == "sqlite":
                                    c_check.execute('''
                                        INSERT OR IGNORE INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at)
                                        VALUES (?, ?, ?, ?, ?)
                                    ''', (s_name, u_code, int(num), reg_date, now_default_str))
                                else:
                                    c_check.execute('''
                                        INSERT INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at)
                                        VALUES (%s, %s, %s, %s, %s)
                                        ON CONFLICT (student_name, unit_code, prob_num, registered_date) DO NOTHING
                                    ''', (s_name, u_code, int(num), reg_date, now_default_str))
                        conn_check.commit()
                        st.cache_data.clear()
                    except Exception:
                        pass

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
                target_rows = c.fetchall()

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
                if wrong_view_mode not in ["📅 날짜별 보기", "📆 주간별(월~일) 한 주 모아보기"]:
                    st.info("저장된 오답이 없습니다.")
        else:
            st.warning("등록된 학생이 없습니다.")

    with t_cfg_matrix:
        st.markdown("#### 📊 전체 학생 숙제 현황 및 통합 관리")
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, "SELECT DISTINCT hw_date FROM student_homework ORDER BY hw_date DESC")
        all_hw_dates = [r[0] for r in c.fetchall()]
        
        if all_hw_dates and student_list:
            selected_matrix_date = st.selectbox("확인할 숙제 날짜 선택", all_hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})", key="matrix_date_selectbox")
            
            today_str_box = str(get_korean_today())
            
            routines_map = get_entire_daily_routines_map()
            logs_map = get_entire_daily_routine_logs_map(today_str_box)
            
            unchecked_students_today = []
            for s_item in student_list:
                r_list_s = routines_map.get(s_item, [])
                if r_list_s:
                    done_all = all(logs_map.get((s_item, str(r[0])), False) for r in r_list_s)
                    if not done_all:
                        unchecked_students_today.append(s_item)

            if unchecked_students_today:
                st.markdown(
                    f'<div style="background-color: rgba(239, 68, 68, 0.1); border: 1px solid #EF4444; padding: 10px; border-radius: 8px; margin-bottom: 15px;">'
                    f'<div style="font-size: 13px; font-weight: bold; color: #EF4444;">🚨 오늘 루틴 미체크 학생 목록: <b>{", ".join(unchecked_students_today)}</b></div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div style="background-color: rgba(16, 185, 129, 0.1); border: 1px solid #10B981; padding: 10px; border-radius: 8px; margin-bottom: 15px;">'
                    f'<div style="font-size: 13px; font-weight: bold; color: #10B981;">🎉 오늘 모든 학생들이 루틴 과제를 완료했습니다!</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            all_students_hw_map = get_all_students_homework_map(selected_matrix_date)
            entire_hw_prog = get_entire_homework_progress_map()

            active_hw_students = [s_name for s_name in student_list if all_students_hw_map.get(s_name)]

            if active_hw_students:
                st.markdown(f"📌 **{selected_matrix_date} 숙제 배정 학생 (총 {len(active_hw_students)}명)**")
                
                for s_idx_main, s_name in enumerate(active_hw_students):
                    hws = all_students_hw_map.get(s_name, [])
                    
                    expander_label = f"👤 {s_name} 학생 숙제 현황 (총 {len(hws)}개 항목)"
                    with st.expander(expander_label, expanded=False):
                        combined_titles_mat = [title for _, title in hws]
                        initial_mat_text = "\n".join(combined_titles_mat)
                        
                        for h_idx, (h_id, title) in enumerate(hws):
                            if title.startswith("💬 [선생님 메시지]:"):
                                msg_content = title.replace("💬 [선생님 메시지]:", "").strip()
                                st.info(f"💬 **선생님의 한마디**: {msg_content}")
                            else:
                                is_done = entire_hw_prog.get((s_name, h_id), False)
                                chk_key = f"mat_{s_idx_main}_{selected_matrix_date}_{h_id}_{h_idx}"
                                if st.checkbox(f"📌 {title}", value=is_done, key=chk_key) != is_done:
                                    save_single_homework_progress(s_name, h_id, st.session_state[chk_key])
                                    st.rerun()

                        with st.popover("✏️ 이 날짜 숙제 전체 수정 / 편집하기"):
                            with st.form(f"matrix_bulk_edit_form_{s_idx_main}_{selected_matrix_date}"):
                                st.markdown(f"##### 📝 {s_name} 학생 ({selected_matrix_date}) 숙제 전체 편집")
                                edited_bulk_hw_text = st.text_area("줄바꿈으로 숙제 항목들을 수정하세요", value=initial_mat_text, height=120, key=f"mat_text_area_{s_idx_main}_{selected_matrix_date}")
                                
                                col_mb1, col_mb2 = st.columns(2)
                                with col_mb1:
                                    save_mb_btn = st.form_submit_button("💾 일괄 수정 저장", type="primary")
                                with col_mb2:
                                    del_mb_btn = st.form_submit_button("🗑️ 이 날짜 숙제 전체 삭제")
                                    
                                if save_mb_btn:
                                    if edited_bulk_hw_text.strip():
                                        update_student_homework_by_date(s_name, selected_matrix_date, edited_bulk_hw_text.strip())
                                        st.success("숙제가 성공적으로 수정되었습니다!")
                                        st.rerun()
                                if del_mb_btn:
                                    delete_student_homework_date(s_name, selected_matrix_date)
                                    st.success("숙제가 전체 삭제되었습니다!")
                                    st.rerun()
            else:
                st.info(f"선택하신 {selected_matrix_date}에 숙제가 배정된 학생이 없습니다.")
        else:
            st.info("등록된 숙제 날짜나 학생이 없습니다.")

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
                    cols = st.columns(2)
                    for item_idx, (l_id, f_code, v_url, u_code) in enumerate(searched_links):
                        target_col = cols[item_idx % 2]
                        with target_col:
                            c_code, c_btn = st.columns([5, 1])
                            
                            with c_code:
                                st.markdown(f"📌 **[{f_code}]({v_url})** <span style='font-size:11px; color:gray;'>🔗 해설연결</span>", unsafe_allow_html=True)
                            
                            with c_btn:
                                if st.button("🗑️", key=f"del_link_item_{l_id}_{item_idx}", help="삭제"):
                                    delete_problem_link(l_id)
                                    st.rerun()
                            
                            st.markdown("<hr style='margin: 4px 0px 8px 0px; border: 0; border-top: 1px solid rgba(128,128,128,0.2);'>", unsafe_allow_html=True)
                else:
                    st.info("해당 조건에 일치하는 해설 링크가 없습니다.")
            else:
                st.info("💡 단원을 선택하시거나 검색어를 입력해 주세요.")

    with t_cfg_stats:
        st.markdown("#### 📈 실시간 학습 참여 현황")
        today_active_cnt, total_visits, s_summary, daily_logs = get_visitor_stats()
        
        col_st1, col_st2 = st.columns(2)
        with col_st1:
            st.metric(label="📌 오늘 접속한 학생 수", value=f"{today_active_cnt}명")
        with col_st2:
            st.metric(label="📈 누적 총 접속 횟수", value=f"{total_visits}회")
        st.markdown("---")
        
        st.markdown("##### 👤 학생별 최근 접속 일시 및 누적 횟수")
        if s_summary:
            for s_name, last_time, v_count in s_summary:
                with st.container(border=True):
                    col_ss1, col_ss2 = st.columns([3, 1])
                    with col_ss1:
                        st.markdown(f"👤 **{s_name}**")
                        st.caption(f"🕒 최근 접속: {last_time}")
                    with col_ss2:
                        st.markdown(f"<div style='text-align:right; margin-top:8px;'><b>총 {v_count}회 접속</b></div>", unsafe_allow_html=True)
        else:
            st.info("아직 저장된 학생 접속 기록이 없습니다.")
            
        if daily_logs:
            st.markdown("---")
            st.markdown("##### 📅 최근 7일 일자별 접속 요약")
            st.dataframe(pd.DataFrame(daily_logs, columns=["날짜", "접속 학생 수 (명)", "총 방문 횟수 (회)"]), use_container_width=True, hide_index=True)

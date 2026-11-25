import streamlit as st
import streamlit.components.v1 as components
import sqlite3
from datetime import datetime, date, timedelta, timezone
import calendar
import re
import pandas as pd
import io
import os
import base64

st.set_page_config(page_title="MathPro 학생 맞춤 학습 로드맵", page_icon="📐", layout="centered")

# 💡 카드 외곽선, 체크박스-버튼 컴팩트 정렬 및 모바일 가로 넘침/잘림 방지 CSS 스타일
st.markdown("""
<style>
/* 전체 페이지 모바일 가로 넘침 방지 */
html, body, [data-testid="stAppViewContainer"], .main, .block-container {
    max-width: 100vw !important;
    overflow-x: hidden !important;
}

/* st.container(border=True) 카드 외곽선과 배경 */
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
    border: 4px solid rgba(56, 189, 248, 0.8) !important;
    background-color: rgba(30, 35, 45, 0.95) !important;
    border-radius: 16px !important;
    padding: 18px !important;
    margin-bottom: 16px !important;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.5) !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}

/* 개념 진도 및 오답 목록 컬럼 간격 및 상하 여백 압축 (콤팩트 정렬) */
div[data-testid="stHorizontalBlock"] {
    align-items: center !important;
    gap: 6px !important;
    max-width: 100% !important;
}
div[data-testid="stCheckbox"] {
    display: flex !important;
    align-items: center !important;
    margin-top: -4px !important;
    margin-bottom: -4px !important;
    max-width: 100% !important;
}
div[data-testid="stCheckbox"] label {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    max-width: 100% !important;
}
div[data-testid="stCheckbox"] label p {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 13px !important;
}

/* 모바일 화면 가로 넘침 및 오른쪽 잘림 방지 */
@media (max-width: 640px) {
    .block-container {
        padding-left: 10px !important;
        padding-right: 10px !important;
    }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
        padding: 12px 10px !important;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: wrap !important;
        align-items: center !important;
        gap: 6px !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        flex: 1 1 auto !important;
        min-width: 0 !important;
        max-width: 100% !important;
    }
    /* 주간 이동 버튼(이전 주 / 이번 주 / 다음 주) 모바일 컴팩트화 */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] button p {
        font-size: 12px !important;
        white-space: nowrap !important;
    }
}

/* PC 온라인 테스트 문제 이미지 크기 제한 */
@media (min-width: 641px) {
    div[data-testid="stImage"] img {
        max-width: 480px !important;
        max-height: 320px !important;
        width: auto !important;
        height: auto !important;
        object-fit: contain !important;
        border-radius: 8px !important;
    }
}
@media (max-width: 640px) {
    div[data-testid="stForm"] div[data-testid="stImage"] img {
        max-width: 100% !important;
        max-height: none !important;
        width: auto !important;
        height: auto !important;
    }
}

/* 버튼 텍스트 왼쪽 정렬 설정 */
div.stButton > button {
    display: block !important;
    text-align: left !important;
    justify-content: flex-start !important;
    align-items: center !important;
    text-align-last: left !important;
}
div.stButton > button > div {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    text-align: left !important;
    width: 100% !important;
}
div.stButton > button > div > p {
    text-align: left !important;
    width: 100% !important;
}
</style>
""", unsafe_allow_html=True)

# URL 파라미터 확인 및 관리자 인증 상태 동기화
query_params = st.query_params
url_admin = query_params.get("admin", None)

if url_admin == "true":
    st.session_state["teacher_authenticated"] = True
elif "teacher_authenticated" not in st.session_state:
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

@st.cache_data(ttl=300, show_spinner=False)
def get_all_problem_link_set():
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT full_code FROM problem_links WHERE video_url IS NOT NULL AND trim(video_url) != ''")
        rows = c.fetchall()
        return {str(r[0]).upper() for r in rows}
    except Exception:
        return set()

@st.cache_data(ttl=300, show_spinner=False)
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

@st.cache_data(ttl=60, show_spinner=False)
def get_entire_homework_progress_map():
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT student_name, student_hw_id, is_checked FROM student_homework_progress")
        rows = c.fetchall()
        return {(r[0], r[1]): bool(r[2]) for r in rows}
    except Exception:
        return {}

@st.cache_data(ttl=300, show_spinner=False)
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

@st.cache_data(ttl=120, show_spinner=False)
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

@st.cache_data(ttl=120, show_spinner=False)
def get_cached_all_sessions():
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, "SELECT id, student_name, test_title, created_at, is_completed FROM online_test_sessions ORDER BY id DESC")
        return c.fetchall()
    except Exception:
        return []

@st.cache_data(ttl=120, show_spinner=False)
def get_cached_test_submission_summaries():
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, """
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
        return c.fetchall()
    except Exception:
        return []

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
            "student_test_submissions", "online_test_sessions", "online_test_items",
            "test_schedules"
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
            "student_test_submissions", "online_test_sessions", "online_test_items"
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

def cleanup_duplicate_wrong_logs():
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            c.execute("""
                DELETE FROM student_wrong_logs a
                USING student_wrong_logs b
                WHERE a.student_name = b.student_name
                  AND a.unit_code = b.unit_code
                  AND a.prob_num = b.prob_num
                  AND a.registered_date > b.registered_date
            """)
        else:
            q(c, """
                DELETE FROM student_wrong_logs
                WHERE id IN (
                    SELECT a.id
                    FROM student_wrong_logs a
                    WHERE EXISTS (
                        SELECT 1
                        FROM student_wrong_logs b
                        WHERE a.student_name = b.student_name
                          AND a.unit_code = b.unit_code
                          AND a.prob_num = b.prob_num
                          AND b.registered_date < a.registered_date
                    )
                )
            """)
        conn.commit()
        st.cache_data.clear()
        return True, "기존 중복 누적 로그 정리가 완료되었습니다!"
    except Exception as e:
        return False, f"로그 정리 중 오류 발생: {e}"

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

def get_week_range_str(date_str):
    try:
        d = date.fromisoformat(date_str[:10])
        start_week = d - timedelta(days=d.weekday())
        end_week = start_week + timedelta(days=6)
        return f"{start_week} ~ {end_week} (월~일)"
    except Exception:
        return "주간 미상"

def extract_test_date(title_str, fallback_str=None):
    m6 = re.search(r"\b(\d{2})(\d{2})(\d{2})\b", str(title_str or ""))
    if m6:
        try:
            yy, mm, dd = int(m6.group(1)), int(m6.group(2)), int(m6.group(3))
            return date(2000 + yy, mm, dd)
        except ValueError:
            pass
    m8 = re.search(r"(\d{4})[-./]?(\d{2})[-./]?(\d{2})", str(title_str or ""))
    if m8:
        try:
            return date(int(m8.group(1)), int(m8.group(2)), int(m8.group(3)))
        except ValueError:
            pass
    if fallback_str:
        try:
            return date.fromisoformat(str(fallback_str)[:10])
        except ValueError:
            pass
    return None

# ----------------------------------------------------
# 🗓️ 루틴 요일 지정 헬퍼 (0=월 ... 6=일)
# ----------------------------------------------------
ALL_WEEKDAYS = [0, 1, 2, 3, 4, 5, 6]
WEEKDAY_NAMES_KR = ["월", "화", "수", "목", "금", "토", "일"]
DEFAULT_ACTIVE_DAYS_STR = "0,1,2,3,4,5,6"

def parse_active_days(active_days_val):
    if active_days_val is None:
        return list(ALL_WEEKDAYS)
    raw = str(active_days_val).strip()
    if not raw:
        return []
    day_name_to_idx = {name: idx for idx, name in enumerate(WEEKDAY_NAMES_KR)}
    parsed = set()
    for token in re.split(r"[\s,·/|]+", raw):
        t = token.strip()
        if not t:
            continue
        if t.isdigit():
            val = int(t)
            if 0 <= val <= 6:
                parsed.add(val)
        elif t in day_name_to_idx:
            parsed.add(day_name_to_idx[t])
    return sorted(parsed) if parsed else list(ALL_WEEKDAYS)

def format_active_days_str(day_indices):
    clean_days = sorted({int(d) for d in (day_indices or []) if 0 <= int(d) <= 6})
    return ",".join(str(d) for d in clean_days)

def format_active_days_label(day_indices):
    days = parse_active_days(day_indices) if isinstance(day_indices, str) else sorted({int(d) for d in (day_indices or []) if 0 <= int(d) <= 6})
    if len(days) == 7:
        return "매일"
    if not days:
        return "휴식"
    return "·".join(WEEKDAY_NAMES_KR[d] for d in days)

@st.cache_resource(show_spinner=False)
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
            c.execute('CREATE TABLE IF NOT EXISTS daily_routines (id SERIAL PRIMARY KEY, student_name TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL, is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, active_days TEXT DEFAULT \'0,1,2,3,4,5,6\');')
            c.execute('CREATE TABLE IF NOT EXISTS homework_templates (id SERIAL PRIMARY KEY, title TEXT NOT NULL);')
            c.execute('CREATE TABLE IF NOT EXISTS milestone_progress (student_name TEXT, milestone_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, milestone_id));')
            c.execute('CREATE TABLE IF NOT EXISTS homework_progress (student_name TEXT, homework_id INTEGER, is_checked INTEGER, PRIMARY KEY (student_name, homework_id));')
            c.execute('CREATE TABLE IF NOT EXISTS student_homework_progress (student_name TEXT, student_hw_id INTEGER, is_checked INTEGER);')
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

            c.execute('''
                CREATE TABLE IF NOT EXISTS online_test_sessions (
                    id SERIAL PRIMARY KEY,
                    student_name TEXT NOT NULL,
                    test_title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_completed INTEGER DEFAULT 0
                );
            ''')

            c.execute('''
                CREATE TABLE IF NOT EXISTS online_test_items (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER,
                    problem_order INTEGER,
                    unit_code TEXT,
                    prob_num TEXT,
                    answer TEXT,
                    img_base64 TEXT,
                    solution_img_path TEXT,
                    wrong_noted INTEGER DEFAULT 0
                );
            ''')

            c.execute('''
                CREATE TABLE IF NOT EXISTS test_schedules (
                    id SERIAL PRIMARY KEY,
                    student_name TEXT NOT NULL,
                    test_date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    scope TEXT DEFAULT '',
                    test_type TEXT DEFAULT '정규 테스트',
                    status TEXT DEFAULT 'scheduled',
                    memo TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
            ''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_test_schedules_date_student ON test_schedules (test_date, student_name);')
            try:
                c.execute('ALTER TABLE online_test_items ADD COLUMN IF NOT EXISTS solution_img_path TEXT;')
                c.execute('ALTER TABLE online_test_items ADD COLUMN IF NOT EXISTS wrong_noted INTEGER DEFAULT 0;')
            except Exception:
                pass

            try:
                c.execute('ALTER TABLE student_homework ADD COLUMN IF NOT EXISTS due_date TEXT DEFAULT \'\';')
            except Exception:
                pass

            try:
                c.execute('ALTER TABLE daily_routines ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;')
                c.execute('ALTER TABLE daily_routines ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;')
                c.execute("ALTER TABLE daily_routines ADD COLUMN IF NOT EXISTS active_days TEXT DEFAULT '0,1,2,3,4,5,6';")
                c.execute('UPDATE daily_routines SET is_active = 1 WHERE is_active IS NULL;')
                c.execute('UPDATE daily_routines SET sort_order = id WHERE sort_order IS NULL OR sort_order = 0;')
                c.execute("UPDATE daily_routines SET active_days = '0,1,2,3,4,5,6' WHERE active_days IS NULL OR trim(active_days) = '';")
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
            c.execute('CREATE TABLE IF NOT EXISTS daily_routines (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT NOT NULL, title TEXT NOT NULL, parent_id INTEGER DEFAULT NULL, is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, active_days TEXT DEFAULT \'0,1,2,3,4,5,6\')')
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

            c.execute('''
                CREATE TABLE IF NOT EXISTS online_test_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_name TEXT NOT NULL,
                    test_title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_completed INTEGER DEFAULT 0
                );
            ''')

            c.execute('''
                CREATE TABLE IF NOT EXISTS online_test_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    problem_order INTEGER,
                    unit_code TEXT,
                    prob_num TEXT,
                    answer TEXT,
                    img_base64 TEXT,
                    solution_img_path TEXT,
                    wrong_noted INTEGER DEFAULT 0
                );
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS test_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_name TEXT NOT NULL,
                    test_date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    scope TEXT DEFAULT '',
                    test_type TEXT DEFAULT '정규 테스트',
                    status TEXT DEFAULT 'scheduled',
                    memo TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
            ''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_test_schedules_date_student ON test_schedules (test_date, student_name)')
            try:
                c.execute('ALTER TABLE online_test_items ADD COLUMN solution_img_path TEXT')
            except Exception:
                pass
            try:
                c.execute('ALTER TABLE online_test_items ADD COLUMN wrong_noted INTEGER DEFAULT 0')
            except Exception:
                pass

            try:
                c.execute('ALTER TABLE student_homework ADD COLUMN due_date TEXT DEFAULT \'\'')
            except Exception:
                pass

            try:
                c.execute("PRAGMA table_info(daily_routines)")
                existing_cols = [col[1] for col in c.fetchall()]
                if "is_active" not in existing_cols:
                    c.execute("ALTER TABLE daily_routines ADD COLUMN is_active INTEGER DEFAULT 1")
                if "sort_order" not in existing_cols:
                    c.execute("ALTER TABLE daily_routines ADD COLUMN sort_order INTEGER DEFAULT 0")
                if "active_days" not in existing_cols:
                    c.execute("ALTER TABLE daily_routines ADD COLUMN active_days TEXT DEFAULT '0,1,2,3,4,5,6'")
                c.execute("UPDATE daily_routines SET is_active = 1 WHERE is_active IS NULL")
                c.execute("UPDATE daily_routines SET sort_order = id WHERE sort_order IS NULL OR sort_order = 0")
                c.execute("UPDATE daily_routines SET active_days = '0,1,2,3,4,5,6' WHERE active_days IS NULL OR trim(active_days) = ''")
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        print(f"DB 초기화 예외: {e}")


@st.cache_data(ttl=60)
def get_test_schedules_by_range(start_date_str: str, end_date_str: str) -> pd.DataFrame:
    cols = ["id", "student_name", "test_date", "title", "scope", "test_type", "status", "memo", "created_at"]
    try:
        conn, db_type = get_db_connection()
        c = conn.cursor()
        ph = "%s" if db_type == "postgres" else "?"
        sql = f"""
            SELECT id, student_name, test_date, title, scope, test_type, status, memo, created_at
            FROM test_schedules
            WHERE test_date >= {ph} AND test_date <= {ph}
            ORDER BY test_date ASC, id ASC
        """
        c.execute(sql, (start_date_str, end_date_str))
        rows = c.fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame([dict(r) if hasattr(r, "keys") else dict(zip(cols, r)) for r in rows], columns=cols)
    except Exception:
        return pd.DataFrame(columns=cols)


def get_student_test_schedules(student_name: str, start_date_str: str = None, end_date_str: str = None) -> pd.DataFrame:
    cols = ["id", "student_name", "test_date", "title", "scope", "test_type", "status", "memo", "created_at"]
    try:
        conn, db_type = get_db_connection()
        c = conn.cursor()
        ph = "%s" if db_type == "postgres" else "?"
        if start_date_str and end_date_str:
            sql = f"""
                SELECT id, student_name, test_date, title, scope, test_type, status, memo, created_at
                FROM test_schedules
                WHERE (student_name = {ph} OR student_name = 'ALL')
                  AND test_date >= {ph} AND test_date <= {ph}
                ORDER BY test_date ASC, id ASC
            """
            c.execute(sql, (student_name, start_date_str, end_date_str))
        else:
            sql = f"""
                SELECT id, student_name, test_date, title, scope, test_type, status, memo, created_at
                FROM test_schedules
                WHERE (student_name = {ph} OR student_name = 'ALL')
                ORDER BY test_date ASC, id ASC
            """
            c.execute(sql, (student_name,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame([dict(r) if hasattr(r, "keys") else dict(zip(cols, r)) for r in rows], columns=cols)
    except Exception:
        return pd.DataFrame(columns=cols)


def clear_test_schedule_cache():
    try:
        get_test_schedules_by_range.clear()
    except Exception:
        pass


def _ts_weekday_short_kr(d_obj) -> str:
    return ["월", "화", "수", "목", "금", "토", "일"][d_obj.weekday()]


def _ts_week_range_str(monday_obj) -> str:
    sunday_obj = monday_obj + timedelta(days=6)
    return f"{monday_obj.strftime('%Y-%m-%d')} ({_ts_weekday_short_kr(monday_obj)}) ~ {sunday_obj.strftime('%Y-%m-%d')} ({_ts_weekday_short_kr(sunday_obj)})"


def add_test_schedule_entries(
    targets: list,
    test_dates: list,
    title: str,
    scope: str = "",
    test_type: str = "정규 테스트",
    status: str = "scheduled",
    memo: str = "",
) -> int:
    clean_title = (title or "").strip()
    if not clean_title or not targets or not test_dates:
        return 0
    now_str = get_korean_now_str() if "get_korean_now_str" in globals() else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    conn, db_type = get_db_connection()
    c = conn.cursor()
    ph = "%s" if db_type == "postgres" else "?"
    sql = f"""
        INSERT INTO test_schedules
        (student_name, test_date, title, scope, test_type, status, memo, created_at)
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
    """
    for target in targets:
        t_name = str(target).strip()
        if not t_name:
            continue
        for d_str in sorted(set(test_dates)):
            c.execute(sql, (t_name, d_str, clean_title, (scope or "").strip(), test_type, status, (memo or "").strip(), now_str))
            inserted += 1
    conn.commit()
    conn.close()
    clear_test_schedule_cache()
    return inserted


def update_test_schedule_item(
    schedule_id: int,
    test_date: str,
    title: str,
    scope: str,
    test_type: str,
    status: str,
    memo: str,
):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    ph = "%s" if db_type == "postgres" else "?"
    sql = f"""
        UPDATE test_schedules
        SET test_date = {ph}, title = {ph}, scope = {ph}, test_type = {ph}, status = {ph}, memo = {ph}
        WHERE id = {ph}
    """
    c.execute(sql, (test_date, title.strip(), scope.strip(), test_type, status, memo.strip(), int(schedule_id)))
    conn.commit()
    conn.close()
    clear_test_schedule_cache()


def delete_test_schedule_item(schedule_id: int):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    ph = "%s" if db_type == "postgres" else "?"
    c.execute(f"DELETE FROM test_schedules WHERE id = {ph}", (int(schedule_id),))
    conn.commit()
    conn.close()
    clear_test_schedule_cache()


def get_test_status_label(status: str) -> str:
    return {
        "scheduled": "예정",
        "completed": "완료",
        "retest": "재시험",
    }.get(status, "예정")

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

@st.cache_data(ttl=300, show_spinner=False)
def get_students():
    try:
        conn, _ = get_db_connection()
        c = conn.cursor()
        q(c, "SELECT name FROM students ORDER BY name")
        return [r[0] for r in c.fetchall()]
    except Exception:
        return []

@st.cache_data(ttl=300, show_spinner=False)
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
    q(c, "DELETE FROM online_test_items WHERE session_id IN (SELECT id FROM online_test_sessions WHERE student_name = ?)", (name,))
    q(c, "DELETE FROM online_test_sessions WHERE student_name = ?", (name,))
    conn.commit()
    st.cache_data.clear()

@st.cache_data(ttl=300, show_spinner=False)
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

@st.cache_data(ttl=300, show_spinner=False)
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

@st.cache_data(ttl=120, show_spinner=False)
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

@st.cache_data(ttl=300, show_spinner=False)
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
    st.cache_data.clear()

@st.cache_data(ttl=60, show_spinner=False)
def get_notices_for_student(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT id, title, content, created_at, student_name FROM notices WHERE student_name = '' OR student_name = ? ORDER BY id DESC", (student_name,))
    return c.fetchall()

@st.cache_data(ttl=60, show_spinner=False)
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
    st.cache_data.clear()

@st.cache_data(ttl=60, show_spinner=False)
def get_student_daily_routines(student_name, include_inactive=False):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if include_inactive:
            q(
                c,
                "SELECT id, title, COALESCE(is_active, 1), COALESCE(sort_order, id), COALESCE(active_days, '0,1,2,3,4,5,6') FROM daily_routines WHERE student_name = ? ORDER BY COALESCE(sort_order, id) ASC, id ASC",
                (student_name,)
            )
            rows = c.fetchall()
            return [(r[0], r[1], bool(r[2]), int(r[3]), parse_active_days(r[4])) for r in rows]
        else:
            q(
                c,
                "SELECT id, title, COALESCE(active_days, '0,1,2,3,4,5,6') FROM daily_routines WHERE student_name = ? AND COALESCE(is_active, 1) = 1 ORDER BY COALESCE(sort_order, id) ASC, id ASC",
                (student_name,)
            )
            return [(r[0], r[1], parse_active_days(r[2])) for r in c.fetchall()]
    except Exception:
        q(c, "SELECT id, title FROM daily_routines WHERE student_name = ? ORDER BY id ASC", (student_name,))
        rows = c.fetchall()
        if include_inactive:
            return [(r[0], r[1], True, idx + 1, list(ALL_WEEKDAYS)) for idx, r in enumerate(rows)]
        return [(r[0], r[1], list(ALL_WEEKDAYS)) for r in rows]

def bulk_insert_daily_routines(student_name, text_data, active_days=None):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT COALESCE(MAX(COALESCE(sort_order, id)), 0) FROM daily_routines WHERE student_name = ?", (student_name,))
    max_order_row = c.fetchone()
    next_sort_order = int(max_order_row[0]) if max_order_row and max_order_row[0] is not None else 0

    days_str = format_active_days_str(active_days if active_days is not None else ALL_WEEKDAYS)
    if not days_str:
        days_str = DEFAULT_ACTIVE_DAYS_STR

    lines = text_data.strip().split('\n')
    added_count = 0
    for line in lines:
        title = line.lstrip('-•*└\t ').strip()
        if not title:
            continue
        next_sort_order += 1
        try:
            q(
                c,
                "INSERT INTO daily_routines (student_name, title, is_active, sort_order, active_days) VALUES (?, ?, 1, ?, ?)",
                (student_name, title, next_sort_order, days_str)
            )
        except Exception:
            q(
                c,
                "INSERT INTO daily_routines (student_name, title, is_active, sort_order) VALUES (?, ?, 1, ?)",
                (student_name, title, next_sort_order)
            )
        added_count += 1
    conn.commit()
    st.cache_data.clear()
    return added_count

def update_routine_active_days(routine_id, day_indices):
    conn, _ = get_db_connection()
    c = conn.cursor()
    days_str = format_active_days_str(day_indices if day_indices else ALL_WEEKDAYS)
    if not days_str:
        days_str = DEFAULT_ACTIVE_DAYS_STR
    try:
        q(c, "UPDATE daily_routines SET active_days = ? WHERE id = ?", (days_str, routine_id))
        conn.commit()
        st.cache_data.clear()
    except Exception as e:
        print(f"루틴 요일 변경 중 예외: {e}")

def update_routine_order(student_name, routine_id, direction):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(
            c,
            "SELECT id, COALESCE(sort_order, id) FROM daily_routines WHERE student_name = ? ORDER BY COALESCE(sort_order, id) ASC, id ASC",
            (student_name,)
        )
        items = [(r[0], int(r[1])) for r in c.fetchall()]
        if not items:
            return

        normalized = []
        for idx, (r_id, _) in enumerate(items, start=1):
            normalized.append([r_id, idx])

        target_idx = next((i for i, (r_id, _) in enumerate(normalized) if r_id == routine_id), -1)
        if target_idx == -1:
            return

        if direction == "up" and target_idx > 0:
            normalized[target_idx - 1][1], normalized[target_idx][1] = normalized[target_idx][1], normalized[target_idx - 1][1]
        elif direction == "down" and target_idx < len(normalized) - 1:
            normalized[target_idx + 1][1], normalized[target_idx][1] = normalized[target_idx][1], normalized[target_idx + 1][1]
        else:
            return

        for r_id, s_order in normalized:
            q(c, "UPDATE daily_routines SET sort_order = ? WHERE id = ?", (s_order, r_id))
        conn.commit()
        st.cache_data.clear()
    except Exception as e:
        print(f"루틴 순서 변경 중 예외: {e}")

def toggle_routine_active(routine_id, new_active_bool):
    conn, _ = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "UPDATE daily_routines SET is_active = ? WHERE id = ?", (1 if new_active_bool else 0, routine_id))
        conn.commit()
        st.cache_data.clear()
    except Exception as e:
        print(f"루틴 활성 상태 변경 중 예외: {e}")

def delete_daily_routine(r_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM daily_routines WHERE id = ?", (r_id,))
    q(c, "DELETE FROM daily_routine_logs WHERE routine_id = ?", (str(r_id),))
    conn.commit()
    st.cache_data.clear()

@st.cache_data(ttl=60, show_spinner=False)
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

@st.cache_data(ttl=60, show_spinner=False)
def get_student_daily_logs_by_dates(student_name, date_strs):
    if not date_strs:
        return {}
    date_tuple = tuple(sorted(list(set(str(d) for d in date_strs))))
    conn, db_type = get_db_connection()
    c = conn.cursor()
    placeholders = ", ".join(["%s" if db_type == "postgres" else "?"] * len(date_tuple))
    q(
        c,
        f"SELECT routine_id, log_date, is_checked FROM daily_routine_logs WHERE student_name = ? AND log_date IN ({placeholders})",
        [student_name] + list(date_tuple)
    )
    rows = c.fetchall()
    return {(str(r_id), str(l_date)): bool(val) for r_id, l_date, val in rows}

@st.cache_data(ttl=60, show_spinner=False)
def get_routine_completion_rate(student_name, days_limit=7):
    conn, _ = get_db_connection()
    c = conn.cursor()
    today_obj = get_korean_today()
    start_date_obj = today_obj - timedelta(days=days_limit - 1)
    start_date_str = str(start_date_obj)
    today_str = str(today_obj)
    
    try:
        q(c, "SELECT id, COALESCE(active_days, '0,1,2,3,4,5,6') FROM daily_routines WHERE student_name = ? AND COALESCE(is_active, 1) = 1", (student_name,))
        active_rows = c.fetchall()
    except Exception:
        q(c, "SELECT id, '0,1,2,3,4,5,6' FROM daily_routines WHERE student_name = ?", (student_name,))
        active_rows = c.fetchall()

    if not active_rows:
        return 0, 0, 0

    active_days_by_id = {str(r[0]): set(parse_active_days(r[1])) for r in active_rows}
    date_list = [start_date_obj + timedelta(days=i) for i in range(days_limit)]
    date_weekday_map = {str(d): d.weekday() for d in date_list}

    total_expected = 0
    for r_id, a_days in active_days_by_id.items():
        total_expected += sum(1 for d in date_list if d.weekday() in a_days)

    if total_expected == 0:
        return 0, 0, 0

    q(c, "SELECT routine_id, log_date FROM daily_routine_logs WHERE student_name = ? AND log_date >= ? AND log_date <= ? AND is_checked = 1", (student_name, start_date_str, today_str))
    completed_count = 0
    for r_id, l_date in c.fetchall():
        r_key = str(r_id)
        d_key = str(l_date)
        if r_key in active_days_by_id and d_key in date_weekday_map:
            if date_weekday_map[d_key] in active_days_by_id[r_key]:
                completed_count += 1
    
    raw_rate = int((completed_count / total_expected) * 100) if total_expected > 0 else 0
    rate = min(100, max(0, raw_rate))
    
    return rate, completed_count, total_expected

@st.cache_data(ttl=60, show_spinner=False)
def get_student_routine_streak(student_name):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        q(c, "SELECT id, COALESCE(active_days, '0,1,2,3,4,5,6') FROM daily_routines WHERE student_name = ? AND COALESCE(is_active, 1) = 1", (student_name,))
        active_rows = c.fetchall()
    except Exception:
        q(c, "SELECT id, '0,1,2,3,4,5,6' FROM daily_routines WHERE student_name = ?", (student_name,))
        active_rows = c.fetchall()

    if not active_rows:
        return 0

    active_days_by_id = {str(r[0]): set(parse_active_days(r[1])) for r in active_rows}
    today_obj = get_korean_today()
    start_date_obj = today_obj - timedelta(days=60)
    if db_type == "postgres":
        q(c, "SELECT log_date, routine_id FROM daily_routine_logs WHERE student_name = %s AND log_date >= %s AND is_checked = 1", (student_name, str(start_date_obj)))
    else:
        q(c, "SELECT log_date, routine_id FROM daily_routine_logs WHERE student_name = ? AND log_date >= ? AND is_checked = 1", (student_name, str(start_date_obj)))
    rows = c.fetchall()

    completed_by_date = {}
    for l_date, r_id in rows:
        r_key = str(r_id)
        if r_key in active_days_by_id:
            completed_by_date.setdefault(str(l_date), set()).add(r_key)

    def is_day_completed(d_obj):
        required_ids = {r_id for r_id, a_days in active_days_by_id.items() if d_obj.weekday() in a_days}
        if not required_ids:
            return None
        done_ids = completed_by_date.get(str(d_obj), set())
        return required_ids.issubset(done_ids)

    streak = 0
    check_date = today_obj
    today_status = is_day_completed(check_date)
    if today_status is False:
        check_date -= timedelta(days=1)

    for _ in range(60):
        day_status = is_day_completed(check_date)
        if day_status is None:
            check_date -= timedelta(days=1)
            continue
        if day_status is True:
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
    get_student_daily_logs_by_dates.clear()
    get_routine_completion_rate.clear()
    get_student_routine_streak.clear()

def save_daily_routine_logs(student_name, log_date, routine_checked_dict):
    conn, _ = get_db_connection()
    c = conn.cursor()
    for routine_id_str, val in routine_checked_dict.items():
        q(c, "INSERT INTO daily_routine_logs (student_name, routine_id, log_date, is_checked) VALUES (?, ?, ?, ?) ON CONFLICT(student_name, routine_id, log_date) DO UPDATE SET is_checked = ?", (student_name, str(routine_id_str), log_date, int(val), int(val)))
    conn.commit()
    get_student_daily_logs_by_date.clear()
    get_student_daily_logs_by_dates.clear()
    get_routine_completion_rate.clear()
    get_student_routine_streak.clear()

@st.cache_data(ttl=300, show_spinner=False)
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
    st.cache_data.clear()

def delete_homework_template(t_id):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "DELETE FROM homework_templates WHERE id = ?", (t_id,))
    conn.commit()
    st.cache_data.clear()

@st.cache_data(ttl=60, show_spinner=False)
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

@st.cache_data(ttl=60, show_spinner=False)
def get_student_homework_dates(student_name):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    if db_type == "postgres":
        q(c, "SELECT DISTINCT hw_date FROM student_homework WHERE student_name = %s ORDER BY hw_date DESC", (student_name,))
    else:
        q(c, "SELECT DISTINCT hw_date FROM student_homework WHERE student_name = ? ORDER BY hw_date DESC", (student_name,))
    return [r[0] for r in c.fetchall()]

@st.cache_data(ttl=60, show_spinner=False)
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

@st.cache_data(ttl=60, show_spinner=False)
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

@st.cache_data(ttl=60, show_spinner=False)
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

@st.cache_data(ttl=60, show_spinner=False)
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

@st.cache_data(ttl=60, show_spinner=False)
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
            q(c, "INSERT INTO milestone_progress (student_name, milestone_id, is_checked) VALUES (%s, %s, %s) ON CONFLICT(student_name, milestone_id) DO UPDATE SET is_checked = ?", (student_name, milestone_id, int(val), int(val)))
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
            q(c, "INSERT INTO student_homework_progress (student_name, student_hw_id, is_checked) VALUES (%s, %s, %s) ON CONFLICT(student_name, student_hw_id) DO UPDATE SET is_checked = ?", (student_name, student_hw_id, int(val), int(val)))
        conn.commit()
        get_student_homework_progress.clear()
        get_entire_homework_progress_map.clear()
    except Exception:
        pass

@st.cache_data(ttl=60, show_spinner=False)
def get_student_wrong_entry(student_name, unit_code):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT numbers_text FROM student_wrong_entries WHERE student_name = ? AND unit_code = ?", (student_name, unit_code))
    row = c.fetchone()
    return row[0] if row else ""

@st.cache_data(ttl=60, show_spinner=False)
def get_all_student_wrong_entries(student_name):
    conn, _ = get_db_connection()
    c = conn.cursor()
    q(c, "SELECT unit_code, numbers_text FROM student_wrong_entries WHERE student_name = ? AND numbers_text != '' ORDER BY unit_code", (student_name,))
    return c.fetchall()

@st.cache_data(ttl=60, show_spinner=False)
def get_student_wrong_note_codes(student_name):
    if not student_name:
        return set()
    try:
        entries = get_all_student_wrong_entries(student_name)
        codes = set()
        for u_code, nums_txt in entries:
            u_clean = str(u_code or "").strip().upper()
            if not u_clean:
                continue
            for n in parse_numbers(nums_txt):
                codes.add(f"{u_clean}{int(n):03d}")
        return codes
    except Exception:
        return set()

@st.cache_data(ttl=60, show_spinner=False)
def get_student_wrong_repeat_counts(student_name):
    if not student_name:
        return {}
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, """
                SELECT UPPER(unit_code || LPAD(CAST(prob_num AS TEXT), 3, '0')) AS full_code,
                       COUNT(DISTINCT registered_date) AS reg_cnt
                FROM student_wrong_logs
                WHERE student_name = %s
                GROUP BY unit_code, prob_num
            """, (student_name,))
        else:
            q(c, """
                SELECT UPPER(unit_code || printf('%03d', CAST(prob_num AS INTEGER))) AS full_code,
                       COUNT(DISTINCT registered_date) AS reg_cnt
                FROM student_wrong_logs
                WHERE student_name = ?
                GROUP BY unit_code, prob_num
            """, (student_name,))
        return {str(r[0]).upper(): int(r[1]) for r in c.fetchall()}
    except Exception:
        return {}

@st.cache_data(ttl=60, show_spinner=False)
def get_all_students_wrong_repeat_counts():
    conn, db_type = get_db_connection()
    c = conn.cursor()
    try:
        if db_type == "postgres":
            q(c, """
                SELECT student_name,
                       UPPER(unit_code || LPAD(CAST(prob_num AS TEXT), 3, '0')) AS full_code,
                       COUNT(DISTINCT registered_date) AS reg_cnt
                FROM student_wrong_logs
                GROUP BY student_name, unit_code, prob_num
            """, ())
        else:
            q(c, """
                SELECT student_name,
                       UPPER(unit_code || printf('%03d', CAST(prob_num AS INTEGER))) AS full_code,
                       COUNT(DISTINCT registered_date) AS reg_cnt
                FROM student_wrong_logs
                GROUP BY student_name, unit_code, prob_num
            """, ())
        return {(str(r[0]), str(r[1]).upper()): int(r[2]) for r in c.fetchall()}
    except Exception:
        return {}

def format_repeat_badge_html(rep_cnt):
    try:
        cnt = int(rep_cnt)
    except Exception:
        cnt = 0
    if cnt >= 3:
        return f"<span style='background-color:rgba(239,68,68,0.18); color:#F87171; border:1px solid #EF4444; padding:1px 6px; border-radius:4px; font-size:11px; font-weight:bold; white-space:nowrap;'>⚠️ {cnt}회 반복</span>"
    elif cnt == 2:
        return "<span style='background-color:rgba(245,158,11,0.18); color:#FBBF24; border:1px solid #F59E0B; padding:1px 6px; border-radius:4px; font-size:11px; font-weight:bold; white-space:nowrap;'>🔁 2회 등록</span>"
    return ""

def save_student_wrong_entry(student_name, unit_code, numbers_text, target_nums_to_log=None):
    conn, db_type = get_db_connection()
    c = conn.cursor()
    today_str = str(get_korean_today())
    now_str = get_korean_now_str()
    try:
        new_total_nums = parse_numbers(numbers_text)

        if target_nums_to_log is not None:
            nums_to_log = sorted(list(set(int(n) for n in target_nums_to_log)))
        else:
            nums_to_log = sorted(list(new_total_nums))

        if db_type == "sqlite":
            q(c, "DELETE FROM student_wrong_entries WHERE student_name = ? AND unit_code = ?", (student_name, unit_code))
            q(c, "INSERT INTO student_wrong_entries (student_name, unit_code, numbers_text, updated_at) VALUES (?, ?, ?, ?)", (student_name, unit_code, numbers_text, today_str))
        else:
            q(c, "INSERT INTO student_wrong_entries (student_name, unit_code, numbers_text, updated_at) VALUES (%s, %s, %s, %s) ON CONFLICT(student_name, unit_code) DO UPDATE SET numbers_text = ?, updated_at = ?", (student_name, unit_code, numbers_text, today_str, numbers_text, today_str))
        
        for num in nums_to_log:
            if db_type == "sqlite":
                q(c, "INSERT OR IGNORE INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at) VALUES (?, ?, ?, ?, ?)", (student_name, unit_code, int(num), today_str, now_str))
            else:
                c.execute("INSERT INTO student_wrong_logs (student_name, unit_code, prob_num, registered_date, created_at) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (student_name, unit_code, prob_num, registered_date) DO NOTHING", (student_name, unit_code, int(num), today_str, now_str))

        conn.commit()
        st.cache_data.clear()
    except Exception as e:
        print(f"오답 저장 중 예외: {e}")

@st.cache_data(ttl=60, show_spinner=False)
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
            q(c, "INSERT INTO student_wrong_solved (student_name, full_code, is_solved) VALUES (%s, %s, %s) ON CONFLICT(student_name, full_code) DO UPDATE SET is_solved = ?", (student_name, full_code, int(is_solved_val), int(is_solved_val)))
        conn.commit()
        get_student_wrong_solved_status.clear()
    except Exception:
        pass

def parse_numbers(text):
    if not text:
        return set()
    return set(int(n) for n in re.findall(r'\d+', text))

def check_subjective_answer(user_ans, real_ans):
    if not user_ans or not real_ans:
        return False

    def normalize_text(t):
        t = str(t).strip().lower()
        t = re.sub(r'[−－—–]', '-', t)
        t = t.replace("×", "*").replace("÷", "/")
        t = t.replace("번", "").replace("제", "")
        t = re.sub(r'\s+', '', t)
        return t

    u_norm = normalize_text(user_ans)
    r_norm = normalize_text(real_ans)

    if u_norm == r_norm:
        return True

    if "," in u_norm and "," in r_norm:
        u_parts = sorted(p for p in u_norm.split(",") if p)
        r_parts = sorted(p for p in r_norm.split(",") if p)
        if u_parts and u_parts == r_parts:
            return True

    return False

def detect_multiple_choice(ans_str, filename_str):
    ans_clean = str(ans_str or "").strip()
    fn_clean = str(filename_str or "").strip()

    # 1. 명시적으로 주관식/서술형/단답인 경우 무조건 주관식
    is_explicit_subjective = (
        any(k in fn_clean for k in ["서술형", "주관식", "단답"])
        or any(k in ans_clean for k in ["서술형", "주관식", "단답"])
    )
    if is_explicit_subjective:
        return False

    # 2. 정답이 '-' 이거나 비어 있으면(셀프채점/서술형) 주관식/셀프채점 처리
    if not ans_clean or ans_clean == "-":
        return False

    # 3. 객관식 판별: 파일명에 '@'가 있거나, 원문자(①~⑤) 또는 '1번'~'5번' 형식인 경우만 객관식
    has_at_mark = ("@" in fn_clean) or ("@" in ans_clean)
    has_circle_num = any(c in ans_clean for c in ["①", "②", "③", "④", "⑤"])
    is_choice_num_label = ans_clean in ["1번", "2번", "3번", "4번", "5번"]

    return has_at_mark or has_circle_num or is_choice_num_label

def render_teacher_process_summary(prob_list, res_list, sess_id, s_name):
    quick_grade_map = st.session_state.get(f"quick_grade_map_{sess_id}", {})
    retry_res_map = st.session_state.get(f"retry_result_map_{sess_id}", {})
    wrong_note_codes = get_student_wrong_note_codes(s_name)

    init_wrong = []
    quick_fixed = []
    retry_ok = []
    still_wrong = []
    noted_orders = []

    for prob in prob_list:
        code = str(prob.get("full_code") or "").strip().upper()
        order = prob.get("order", code)

        if code and code in wrong_note_codes:
            noted_orders.append(order)

        orig_correct = next(
            (r.get("is_correct") for r in res_list if str(r.get("full_code") or "").strip().upper() == code),
            0
        ) == 1

        if orig_correct:
            continue

        init_wrong.append(order)

        if quick_grade_map.get(code) == "O":
            quick_fixed.append(order)
            continue

        if retry_res_map.get(code) == "correct":
            retry_ok.append(order)
        else:
            still_wrong.append(order)

    fixed_txt = ", ".join(f"{n}번" for n in quick_fixed) if quick_fixed else "없음"
    retry_ok_txt = ", ".join(f"{n}번" for n in retry_ok) if retry_ok else "없음"
    remain_txt = ", ".join(f"{n}번" for n in still_wrong) if still_wrong else "없음"
    noted_txt = ", ".join(f"{n}번" for n in noted_orders) if noted_orders else "없음"

    st.markdown(f"""
    <div style="background-color: var(--secondary-background-color); border: 1px solid #374151; padding: 12px 14px; border-radius: 10px; margin: 8px 0;">
        <div style="font-size: 14px; font-weight: bold; margin-bottom: 6px;">
            👩‍🏫 {s_name} — 채점·정정·다시풀기 한눈에 보기
        </div>
        <div style="font-size: 13px; line-height: 1.65;">
- <b>최초 오답 ({len(init_wrong)}문항):</b> {", ".join(f"{n}번" for n in init_wrong) if init_wrong else "없음"}<br>
- <span style="color:#38BDF8;"><b>빠른 확인 O 정정 ({len(quick_fixed)}문항):</b></span> {fixed_txt}<br>
- <span style="color:#10B981;"><b>다시풀기 정답 ({len(retry_ok)}문항):</b></span> {retry_ok_txt}<br>
- <span style="color:#EF4444;"><b>최종 남은 오답 ({len(still_wrong)}문항):</b></span> {remain_txt}<br>
- <span style="color:#F59E0B;"><b>오답노트 등록 ({len(noted_orders)}문항):</b></span> {noted_txt}
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_clipboard_copy_button(copy_text, key_suffix="default", btn_label="📋 전체복사"):
    escaped_text = (
        str(copy_text)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "")
        .replace("\n", "\\n")
    )
    btn_id = f"copyAllBtn_{key_suffix}"
    copy_btn_html = f"""
    <div style="display:flex; align-items:center; gap:10px; margin:0; padding:0;">
        <button id="{btn_id}" onclick="
            (function() {{
                var textToCopy = '{escaped_text}';
                var btn = document.getElementById('{btn_id}');
                function showDone() {{
                    btn.innerText = '✅ 전체 코드 복사 완료!';
                    btn.style.backgroundColor = '#2B8A3E';
                    setTimeout(function() {{
                        btn.innerText = '{btn_label}';
                        btn.style.backgroundColor = '#1864AB';
                    }}, 2000);
                }}
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(textToCopy).then(showDone).catch(function() {{
                        var ta = document.createElement('textarea');
                        ta.value = textToCopy;
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                        showDone();
                    }});
                }} else {{
                    var ta = document.createElement('textarea');
                    ta.value = textToCopy;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    showDone();
                }}
            }})();
        " style="
            background-color:#1864AB;
            color:white;
            border:none;
            border-radius:6px;
            padding:8px 16px;
            font-size:13.5px;
            font-weight:bold;
            cursor:pointer;
        ">{btn_label}</button>
        <span style="font-size:12px; color:#9CA3AF;">버튼을 누르면 아래 전체 문항 코드가 한 줄로 클립보드에 복사됩니다.</span>
    </div>
    """
    components.html(copy_btn_html, height=44)

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
            try:
                if "admin" in st.query_params:
                    del st.query_params["admin"]
            except Exception:
                pass
            st.rerun()
        st.divider()
        
        st.markdown("##### 📥/📤 데이터 백업 및 동기화")
        if st.button("📦 전체 데이터 엑셀 백업 준비하기", use_container_width=True, key="btn_prepare_excel_backup"):
            with st.spinner("엑셀 백업 파일을 생성하는 중..."):
                st.session_state["ready_excel_backup"] = create_excel_backup()
                st.session_state["ready_excel_backup_date"] = str(get_korean_today())
        if st.session_state.get("ready_excel_backup"):
            st.download_button(
                label="📥 준비된 엑셀 백업 다운로드",
                data=st.session_state["ready_excel_backup"],
                file_name=f"mathpro_backup_{st.session_state.get('ready_excel_backup_date', get_korean_today())}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="btn_download_excel_backup"
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
        with st.expander("🔒 선생님 전용 공간 (관리자 전환)", expanded=True):
            with st.form("sidebar_teacher_login_form"):
                teacher_pw_input = st.text_input("비밀번호 입력", type="password")
                if st.form_submit_button("선생님 모드 전환", type="primary"):
                    if teacher_pw_input == "1234":
                        st.session_state["teacher_authenticated"] = True
                        try:
                            st.query_params["admin"] = "true"
                        except Exception:
                            pass
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

        today_obj_check = get_korean_today()
        today_str_check = str(today_obj_check)
        today_weekday_idx = today_obj_check.weekday()
        routines_chk_list = get_student_daily_routines(selected_student, include_inactive=False)
        today_logs_chk = get_student_daily_logs_by_date(selected_student, today_str_check)
        unchecked_count = sum(
            1 for r_id, _, a_days in routines_chk_list
            if today_weekday_idx in a_days and not today_logs_chk.get((str(r_id), today_str_check), False)
        )
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
        repeat_count_map = get_student_wrong_repeat_counts(selected_student)
        
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

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📘 개념 진도", "📚 날짜별 숙제", "💬 오답·질문 관리", "📝 온라인 테스트", "🗓️ 테스트 일정"])

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
                            
                            def on_milestone_change(m_id=m_id, key=f"s_milestone_chk_{selected_student}_{ch}_{m_id}_{idx}"):
                                new_val = st.session_state[key]
                                save_single_milestone_progress(selected_student, m_id, new_val)

                            cols_m1, cols_m2 = st.columns([2.3, 1.7])
                            with cols_m1:
                                st.checkbox(
                                    f"{t_name}", 
                                    value=default_val, 
                                    key=f"s_milestone_chk_{selected_student}_{ch}_{m_id}_{idx}",
                                    on_change=on_milestone_change
                                )
                            with cols_m2:
                                if v_url and v_url.strip() != "":
                                    st.markdown(f'<div style="text-align: right; margin-top: 4px;"><a href="{v_url}" target="_blank" style="padding:3px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold; background-color:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.3); color:inherit; white-space: nowrap;">🎥 개념해설</a></div>', unsafe_allow_html=True)
                                else:
                                    st.markdown('<div style="text-align: right; margin-top: 4px; font-size:11px; color:gray;">준비중</div>', unsafe_allow_html=True)
                                        
                            st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid rgba(128,128,128,0.15);'>", unsafe_allow_html=True)
            else:
                st.info("아직 배정된 개념 학습 목록이 없습니다.")

        with tab2:
            today_obj = get_korean_today()
            today_str = str(today_obj)
            daily_routines_list = get_student_daily_routines(selected_student, include_inactive=False)

            sorted_hw_dates = sorted(list(set(hw_dates or [])), reverse=True)
            default_target_date = sorted_hw_dates[0] if sorted_hw_dates else today_str

            st.markdown("### 📚 날짜별 숙제 및 주간 루틴")

            if sorted_hw_dates:
                date_options = sorted_hw_dates if today_str in sorted_hw_dates else sorted_hw_dates + [today_str]
                default_idx = date_options.index(default_target_date) if default_target_date in date_options else 0

                selected_hw_date = st.selectbox(
                    "📅 확인할 숙제 날짜 선택 (최근 날짜 우선)",
                    options=date_options,
                    index=default_idx,
                    format_func=lambda d: f"{d} ({get_weekday_kr(d)})" + (" · 오늘" if d == today_str else (" · 최근 숙제" if d == sorted_hw_dates[0] else "")),
                    key=f"s_hw_date_sel_{selected_student}"
                )
            else:
                selected_hw_date = today_str
                st.caption(f"기준 날짜: {selected_hw_date} ({get_weekday_kr(selected_hw_date)})")

            target_date_str = str(selected_hw_date)
            target_hws = get_student_homework_by_date(selected_student, target_date_str)

            actual_target_hws = [h for h in target_hws if not h[1].startswith("💬 [선생님 메시지]:")]
            total_target_h = len(actual_target_hws)
            completed_target_h = sum(1 for h_item in actual_target_hws if h_progress.get(h_item[0], False))

            week_offset_key = f"routine_week_offset_{selected_student}"
            if week_offset_key not in st.session_state:
                st.session_state[week_offset_key] = 0

            base_d = today_obj
            current_week_start = base_d - timedelta(days=base_d.weekday())
            active_week_start = current_week_start + timedelta(weeks=st.session_state[week_offset_key])
            week_days = [(active_week_start + timedelta(days=i)) for i in range(7)]
            week_day_strs = [str(d) for d in week_days]

            week_log_map = get_student_daily_logs_by_dates(selected_student, week_day_strs)

            total_week_rt = sum(len(a_days) for _, _, a_days in daily_routines_list)
            completed_week_rt = sum(
                1 for r_id, _, a_days in daily_routines_list
                for d_obj in week_days
                if d_obj.weekday() in a_days and week_log_map.get((str(r_id), str(d_obj)), False)
            )

            with st.container(border=True):
                st.markdown(
                    f"<div style='font-size:13px; font-weight:bold; color:#0284C7; margin-bottom:6px;'>"
                    f"📝 {target_date_str} ({get_weekday_kr(target_date_str)}) 개별 숙제</div>",
                    unsafe_allow_html=True
                )
                if target_hws:
                    for h_idx, hw_tuple in enumerate(target_hws):
                        h_id = hw_tuple[0]
                        title = hw_tuple[1]
                        due_date = hw_tuple[2] if len(hw_tuple) > 2 else ""

                        if title.startswith("💬 [선생님 메시지]:"):
                            st.info(f"📌 **선생님의 한마디**: {title.replace('💬 [선생님 메시지]:', '').strip()}")
                        else:
                            default_val = h_progress.get(h_id, False)
                            chk_key = f"s_hw_{selected_student}_{target_date_str}_{h_id}_{h_idx}"

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
                                    st.markdown(
                                        f"<div style='text-align:right; margin-top:4px;'>"
                                        f"<span style='background-color:#FEF3C7; color:#D97706; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold;'>마감: {due_date}{wday_str}</span></div>",
                                        unsafe_allow_html=True
                                    )
                else:
                    st.caption("선택한 날짜에 등록된 개별 숙제가 없습니다.")

            @st.fragment
            def render_weekly_routine_grid():
                wk_offset = st.session_state.get(week_offset_key, 0)
                w_start = current_week_start + timedelta(weeks=wk_offset)
                w_days = [(w_start + timedelta(days=i)) for i in range(7)]
                w_day_strs = [str(d) for d in w_days]
                w_log_map = get_student_daily_logs_by_dates(selected_student, w_day_strs)

                with st.container(border=True):
                    st.markdown(
                        f"<div style='display:flex; justify-content:space-between; align-items:center; gap:6px; margin-bottom:6px; flex-wrap:wrap;'>"
                        f"<span style='font-size:13px; font-weight:bold; color:#F59E0B;'>🔁 주간 루틴 체크</span>"
                        f"<span style='font-size:11px; color:#94A3B8;'>{w_days[0].strftime('%m/%d')} ~ {w_days[-1].strftime('%m/%d')} (월~일)</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        """
                        <style>
                        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-btn_prev_wk_"]) {
                            display: flex !important;
                            flex-direction: row !important;
                            flex-wrap: nowrap !important;
                            align-items: center !important;
                            justify-content: space-between !important;
                            gap: 6px !important;
                            width: 100% !important;
                        }
                        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-btn_prev_wk_"]) > div[data-testid="stColumn"],
                        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-btn_prev_wk_"]) > div[data-testid="column"] {
                            flex: 0 0 calc((100% - 12px) / 3) !important;
                            width: calc((100% - 12px) / 3) !important;
                            min-width: 0 !important;
                            max-width: calc((100% - 12px) / 3) !important;
                        }
                        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-btn_prev_wk_"]) button {
                            min-height: 30px !important;
                            height: 30px !important;
                            padding: 2px 4px !important;
                            border-radius: 6px !important;
                            width: 100% !important;
                            min-width: 0 !important;
                        }
                        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-btn_prev_wk_"]) button > div {
                            display: flex !important;
                            justify-content: center !important;
                            align-items: center !important;
                            width: 100% !important;
                        }
                        div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-btn_prev_wk_"]) button p {
                            font-size: 11px !important;
                            line-height: 1.15 !important;
                            white-space: nowrap !important;
                            text-align: center !important;
                            width: auto !important;
                        }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )

                    col_nav1, col_nav2, col_nav3 = st.columns([1.15, 0.85, 1.15], gap="small")
                    with col_nav1:
                        if st.button("◀ 이전주", key=f"btn_prev_wk_{selected_student}", use_container_width=True):
                            st.session_state[week_offset_key] = wk_offset - 1
                            st.rerun(scope="fragment")
                    with col_nav2:
                        if st.button("이번주", key=f"btn_cur_wk_{selected_student}", use_container_width=True, disabled=(wk_offset == 0)):
                            st.session_state[week_offset_key] = 0
                            st.rerun(scope="fragment")
                    with col_nav3:
                        if st.button("다음주 ▶", key=f"btn_next_wk_{selected_student}", use_container_width=True):
                            st.session_state[week_offset_key] = wk_offset + 1
                            st.rerun(scope="fragment")

                    st.markdown("<hr style='margin: 6px 0 8px 0; border: none; border-top: 1px solid rgba(128,128,128,0.15);'>", unsafe_allow_html=True)

                    if not daily_routines_list:
                        st.caption("등록된 매일 반복 루틴이 없습니다.")
                        return

                    day_labels = ["월", "화", "수", "목", "금", "토", "일"]

                    st.markdown(
                        """
                        <style>
                        /* 주간 루틴 세로 1열 리스트 컴팩트 스타일 */
                        .weekly-vertical-list div[data-testid="stCheckbox"] {
                            margin-top: 2px !important;
                            margin-bottom: 2px !important;
                            padding: 2px 4px !important;
                        }
                        .weekly-vertical-list div[data-testid="stCheckbox"] label {
                            width: 100% !important;
                            gap: 8px !important;
                        }
                        .weekly-vertical-list div[data-testid="stCheckbox"] label p {
                            font-size: 13px !important;
                            white-space: normal !important;
                            overflow: visible !important;
                            text-overflow: clip !important;
                        }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )

                    for r_id, r_title, a_days in daily_routines_list:
                        active_day_set = set(a_days or ALL_WEEKDAYS)
                        target_cnt_week = len(active_day_set)
                        done_in_week = sum(
                            1 for d_obj in w_days
                            if d_obj.weekday() in active_day_set and w_log_map.get((str(r_id), str(d_obj)), False)
                        )
                        is_full_week = (target_cnt_week > 0 and done_in_week >= target_cnt_week)
                        badge_bg = "rgba(16,185,129,0.18)" if is_full_week else ("rgba(245,158,11,0.18)" if done_in_week > 0 else "rgba(148,163,184,0.15)")
                        badge_fg = "#34D399" if is_full_week else ("#FBBF24" if done_in_week > 0 else "#CBD5E1")
                        badge_bd = "#10B981" if is_full_week else ("#F59E0B" if done_in_week > 0 else "rgba(148,163,184,0.35)")

                        days_hint = ""
                        if 0 < len(active_day_set) < 7:
                            days_hint = f" <span style='font-size:11.5px; color:#94A3B8; font-weight:normal;'>({format_active_days_label(sorted(active_day_set))})</span>"

                        st.markdown(
                            f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; gap:8px; max-width:100%;'>"
                            f"<div style='font-size:13px; font-weight:bold; min-width:0; flex:1; word-break:break-word;'>• {r_title}{days_hint}</div>"
                            f"<span style='background-color:{badge_bg}; color:{badge_fg}; border:1px solid {badge_bd}; padding:2px 8px; border-radius:999px; font-size:11.5px; font-weight:bold; white-space:nowrap; flex-shrink:0;'>{done_in_week}/{target_cnt_week}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        st.markdown("<div class='weekly-vertical-list'>", unsafe_allow_html=True)

                        for idx_d, d_obj in enumerate(w_days):
                            d_str = str(d_obj)
                            is_today_mark = " 📍" if d_str == today_str else ""
                            is_day_active = (idx_d in active_day_set)

                            if is_day_active:
                                chk_default = w_log_map.get((str(r_id), d_str), False)
                                wk_key = f"wk_rt_{selected_student}_{r_id}_{d_str}"

                                def on_wk_routine_change(r_id=r_id, d_str=d_str, key=wk_key):
                                    save_single_routine_log(selected_student, str(r_id), d_str, st.session_state[key])

                                st.checkbox(
                                    f"{day_labels[idx_d]}({d_obj.day}일){is_today_mark}",
                                    value=chk_default,
                                    key=wk_key,
                                    on_change=on_wk_routine_change
                                )
                            else:
                                st.checkbox(
                                    f"{day_labels[idx_d]}({d_obj.day}일){is_today_mark} · 휴식",
                                    value=False,
                                    disabled=True,
                                    key=f"wk_rt_rest_{selected_student}_{r_id}_{d_str}"
                                )

                        st.markdown("</div>", unsafe_allow_html=True)
                        st.markdown("<hr style='margin: 10px 0; border: none; border-top: 1px solid rgba(128,128,128,0.15);'>", unsafe_allow_html=True)

            render_weekly_routine_grid()

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
                        added_nums = parse_numbers(add_txt)
                        deleted_nums = parse_numbers(del_txt)
                        final_nums = (saved_pre | added_nums) - deleted_nums
                        save_student_wrong_entry(
                            selected_student,
                            target_code,
                            ", ".join(map(str, sorted(list(final_nums)))),
                            target_nums_to_log=(added_nums - deleted_nums)
                        )
                        st.success("저장되었습니다!")
                        st.rerun()
                    else:
                        st.warning("단원코드를 먼저 입력해 주세요.")

            st.markdown("")
            
            with st.container(border=True):
                st.markdown("##### 📝 2. 나의 오답노트 및 해설 바로가기")
                st.caption("🔁 여러 날에 걸쳐 다시 등록된 문제는 복습이 필요한 반복 오답 신호입니다.")
                saved_units_list = [u_code for u_code, _ in saved_wrong_entries]
                solved_map_chk = get_student_wrong_solved_status(selected_student)
                now_datetime_chk = datetime.now()
                
                unit_display_options = ["-- 저장된 단원을 선택하세요 --"]
                unit_map_dict = {}

                for u_code in saved_units_list:
                    p_nums = parsed_entry_dict.get(u_code, set())
                    has_new_unsolved = False
                    has_repeat_item = False
                    for n in p_nums:
                        f_code = f"{u_code}{n:03d}".upper()
                        if repeat_count_map.get(f_code, 0) >= 2:
                            has_repeat_item = True
                        v_url, v_up_at = batch_link_info.get(f_code, ("", ""))
                        is_solved = solved_map_chk.get(f_code, False)
                        if v_url and not is_solved:
                            try:
                                up_dt = datetime.strptime(v_up_at, "%Y-%m-%d %H:%M:%S")
                                if (now_datetime_chk - up_dt).total_seconds() <= 30 * 86400:
                                    has_new_unsolved = True
                            except Exception:
                                pass
                    badges = []
                    if has_new_unsolved:
                        badges.append("🔥 [새해설 대기]")
                    if has_repeat_item:
                        badges.append("🔁 [반복 오답]")
                    display_name = f"{u_code} " + " ".join(badges) if badges else f"{u_code}"
                    unit_map_dict[display_name] = u_code
                    unit_display_options.append(display_name)

                selected_display_unit = st.selectbox("확인할 단원 선택", unit_display_options, key="saved_unit_select_box")
                view_target_code = unit_map_dict.get(selected_display_unit, "") if selected_display_unit != "-- 저장된 단원을 선택하세요 --" else ""

                if view_target_code:
                    parsed_nums = parsed_entry_dict.get(view_target_code, set())
                    if parsed_nums:
                        st.markdown("---")
                        
                        edit_mode_key = f"wrong_edit_mode_{selected_student}_{view_target_code}"
                        is_edit_mode = st.toggle("✏️ 오답 목록 편집 및 선택 삭제 모드 켜기", value=False, key=edit_mode_key)

                        st.markdown(f"**📌 `{view_target_code}` 단원 오답 목록**")
                        solved_map = get_student_wrong_solved_status(selected_student)
                        now_datetime = datetime.now()

                        @st.fragment
                        def render_wrong_edit_list():
                            if is_edit_mode:
                                flag_key = f"select_all_wrong_flag_{selected_student}_{view_target_code}"
                                if flag_key not in st.session_state:
                                    st.session_state[flag_key] = False

                                if st.button("☑️ 전체 선택 / 전체 해제 반전", use_container_width=True):
                                    st.session_state[flag_key] = not st.session_state[flag_key]
                                    for n_item in sorted(list(parsed_nums)):
                                        st.session_state[f"del_num_chk_{selected_student}_{view_target_code}_{n_item}"] = st.session_state[flag_key]
                                    st.rerun()
                                st.markdown("---")

                            for n in sorted(list(parsed_nums)):
                                full_code = f"{view_target_code}{n:03d}".upper()
                                v_url, v_updated_at = batch_link_info.get(full_code, ("", ""))
                                is_solved = solved_map.get(full_code, False)
                                rep_cnt = repeat_count_map.get(full_code, 0)
                                rep_badge = format_repeat_badge_html(rep_cnt)
                                
                                is_new_alert = False
                                if v_url and v_updated_at and not is_solved:
                                    try:
                                        up_dt = datetime.strptime(v_updated_at, "%Y-%m-%d %H:%M:%S")
                                        if (now_datetime - up_dt).total_seconds() <= 30 * 86400:
                                            is_new_alert = True
                                    except Exception:
                                        pass

                                if is_edit_mode:
                                    col_c1, col_c2 = st.columns([2.2, 1.8])
                                    with col_c1:
                                        st.checkbox(f"삭제 ({full_code})", value=False, key=f"del_num_chk_{selected_student}_{view_target_code}_{n}")
                                    with col_c2:
                                        right_parts = []
                                        if rep_badge:
                                            right_parts.append(rep_badge)
                                        if v_url and v_url.strip():
                                            if is_new_alert:
                                                right_parts.append(f"<a href='{v_url}' target='_blank' style='padding:3px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold; background-color:#EF4444; color:white; border:1px solid #DC2626; display:inline-block; white-space: nowrap;'>🔥 새해설</a>")
                                            else:
                                                right_parts.append(f"<a href='{v_url}' target='_blank' style='padding:3px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold; background-color:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.3); color:inherit; white-space: nowrap;'>🎥 해설</a>")
                                        else:
                                            right_parts.append("<span style='font-size:11px; color:gray;'>준비중</span>")
                                        st.markdown(f"<div style='text-align: right; margin-top: 4px; display:flex; justify-content:flex-end; align-items:center; gap:6px;'>{' '.join(right_parts)}</div>", unsafe_allow_html=True)
                                else:
                                    def on_wrong_solved_change(f_code=full_code, key=f"s_wrong_chk_{selected_student}_{full_code}"):
                                        new_val = st.session_state[key]
                                        save_single_wrong_solved_status(selected_student, f_code, new_val)

                                    col_c1, col_c2 = st.columns([2.2, 1.8])
                                    with col_c1:
                                        st.checkbox(
                                            f"복습 완료 ({full_code})", 
                                            value=is_solved, 
                                            key=f"s_wrong_chk_{selected_student}_{full_code}",
                                            on_change=on_wrong_solved_change
                                        )
                                    with col_c2:
                                        right_parts = []
                                        if rep_badge:
                                            right_parts.append(rep_badge)
                                        if v_url and v_url.strip():
                                            if is_new_alert:
                                                right_parts.append(f"<a href='{v_url}' target='_blank' style='padding:3px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold; background-color:#EF4444; color:white; border:1px solid #DC2626; display:inline-block; white-space: nowrap;'>🔥 새해설</a>")
                                            else:
                                                right_parts.append(f"<a href='{v_url}' target='_blank' style='padding:3px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold; background-color:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.3); color:inherit; white-space: nowrap;'>🎥 해설</a>")
                                        else:
                                            right_parts.append("<span style='font-size:11px; color:gray;'>준비중</span>")
                                        st.markdown(f"<div style='text-align: right; margin-top: 4px; display:flex; justify-content:flex-end; align-items:center; gap:6px;'>{' '.join(right_parts)}</div>", unsafe_allow_html=True)
                                        
                                st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid rgba(128,128,128,0.15);'>", unsafe_allow_html=True)

                            if is_edit_mode:
                                st.markdown("")
                                if st.button("🗑️ 선택한 오답 번호들 일괄 삭제하기", type="primary", use_container_width=True):
                                    actual_to_delete = []
                                    for n_item in sorted(list(parsed_nums)):
                                        if st.session_state.get(f"del_num_chk_{selected_student}_{view_target_code}_{n_item}", False):
                                            actual_to_delete.append(n_item)
                                            
                                    if actual_to_delete:
                                        current_nums = parse_numbers(get_student_wrong_entry(selected_student, view_target_code))
                                        updated_nums = current_nums - set(actual_to_delete)
                                        new_nums_text = ", ".join(map(str, sorted(list(updated_nums))))
                                        save_student_wrong_entry(selected_student, view_target_code, new_nums_text, target_nums_to_log=set())
                                        st.success("선택하신 오답 목록이 삭제되었습니다!")
                                        st.rerun()
                                    else:
                                        st.warning("삭제할 번호를 먼저 체크해 주세요.")

                        render_wrong_edit_list()
                    else:
                        st.info("현재 등록된 오답이 없습니다.")

            st.markdown("")
            
            with st.container(border=True):
                st.markdown("##### 🔍 3. 해설 영상 즉시 검색하기")
                search_prob_input = st.text_input("문제 번호 또는 단원코드 입력", placeholder="예: B1353015 또는 B1353").strip().upper()
                if search_prob_input:
                    if len(search_prob_input) >= 7:
                        matched_url, _ = get_problem_link_info(search_prob_input)
                        rep_cnt_search = repeat_count_map.get(search_prob_input, 0)
                        rep_badge_search = format_repeat_badge_html(rep_cnt_search)
                        if matched_url:
                            badge_line = f" &nbsp; {rep_badge_search}" if rep_badge_search else ""
                            st.markdown(f"<div style='background-color:rgba(16,185,129,0.12); border:1px solid #10B981; padding:10px 12px; border-radius:8px; margin-bottom:10px; font-size:13.5px;'>📌 <b>{search_prob_input}</b> 문제 해설 링크가 확인되었습니다!{badge_line}</div>", unsafe_allow_html=True)
                            st.markdown(f'<a href="{matched_url}" target="_blank" style="display:block; padding:12px; border-radius:8px; text-decoration:none; font-weight:bold; text-align:center; border:1px solid rgba(128,128,128,0.3);">🎥 풀이 영상 바로가기 ➔</a>', unsafe_allow_html=True)
                        else:
                            badge_line = f" &nbsp; {rep_badge_search}" if rep_badge_search else ""
                            st.markdown(f"<div style='background-color:rgba(245,158,11,0.12); border:1px solid #F59E0B; padding:10px 12px; border-radius:8px; font-size:13.5px;'>'{search_prob_input}'에 등록된 해설 링크가 없습니다.{badge_line}</div>", unsafe_allow_html=True)
                    else:
                        unit_results = get_problem_links_by_unit(search_prob_input)
                        if unit_results:
                            st.markdown(f"##### 📂 `{search_prob_input}` 단원 해설 목록 ({len(unit_results)}개)")
                            for f_code, v_url in unit_results:
                                f_code_u = str(f_code).upper()
                                rep_cnt_u = repeat_count_map.get(f_code_u, 0)
                                rep_badge_u = format_repeat_badge_html(rep_cnt_u)
                                badge_html = f" &nbsp;{rep_badge_u}" if rep_badge_u else ""
                                st.markdown(
                                    f'<div style="display:flex; justify-content:space-between; align-items:center; padding:10px; border-radius:6px; margin-bottom:6px; border:1px solid rgba(128,128,128,0.3);">'
                                    f'<div>📌 <b>{f_code_u}</b>{badge_html}</div>'
                                    f'<a href="{v_url}" target="_blank" style="text-decoration:none; font-weight:bold; color:#0284C7; white-space:nowrap;">🎥 해설 영상 ➔</a>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
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
                st.markdown("##### 📅 주간별 풀이할 테스트 목록 (월~일)")
                
                sessions_by_week = {}
                for s in sessions_list:
                    s_id, s_title, s_created, s_completed = s
                    parsed_d = extract_test_date(s_title, s_created)
                    ref_date_str = str(parsed_d) if parsed_d else s_created
                    week_key = get_week_range_str(ref_date_str) if ref_date_str else "기타 주간"
                    sessions_by_week.setdefault(week_key, []).append(s)

                sorted_weeks = sorted(sessions_by_week.keys(), reverse=True)
                
                selected_session_id = None
                
                for w_idx, w_key in enumerate(sorted_weeks):
                    def extract_title_date_key(session_tuple):
                        t_title = session_tuple[1]
                        match = re.search(r'(\d{6})', t_title)
                        if match:
                            return (0, match.group(1), t_title)
                        return (1, "999999", t_title)

                    week_sessions = sorted(sessions_by_week[w_key], key=extract_title_date_key)
                    wk_done_cnt = sum(1 for s in week_sessions if s[3] == 1)
                    wk_todo_cnt = len(week_sessions) - wk_done_cnt

                    with st.expander(
                        f"📆 [{w_key}] ({len(week_sessions)}개)",
                        expanded=False
                    ):
                        st.caption(f"✅ 완료 {wk_done_cnt} · 🆕 미제출 {wk_todo_cnt}")
                        prev_date_prefix = None
                        
                        for s_id, s_title, s_created, s_completed in week_sessions:
                            status_badge = "✅" if s_completed == 1 else "🆕"
                            
                            m_yymmdd = re.search(r"\b(\d{2})(\d{2})(\d{2})\b", str(s_title or ""))
                            date_prefix = f"{m_yymmdd.group(2)}/{m_yymmdd.group(3)}" if m_yymmdd else ""

                            if date_prefix and prev_date_prefix and date_prefix != prev_date_prefix:
                                st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
                            if date_prefix:
                                prev_date_prefix = date_prefix

                            formatted_title = str(s_title or "")
                            if m_yymmdd:
                                formatted_title = formatted_title.replace(
                                    m_yymmdd.group(0),
                                    f"{m_yymmdd.group(2)}/{m_yymmdd.group(3)}",
                                    1
                                )

                            if len(formatted_title) > 24:
                                formatted_title = formatted_title[:23] + "…"

                            btn_label = f"{status_badge} {formatted_title}"
                            
                            if st.button(btn_label, key=f"btn_sess_list_{s_id}", use_container_width=True):
                                st.session_state[f"active_sess_{selected_student}"] = s_id
                                st.rerun()

                if f"active_sess_{selected_student}" not in st.session_state and sessions_list:
                    st.session_state[f"active_sess_{selected_student}"] = sessions_list[0][0]
                
                selected_session_id = st.session_state.get(f"active_sess_{selected_student}", sessions_list[0][0])
                
                current_active_info = next((s for s in sessions_list if s[0] == selected_session_id), sessions_list[0])
                st.markdown(f"<div style='background-color:var(--secondary-background-color); padding:10px 14px; border-radius:8px; margin: 15px 0 15px 0; font-size:14px; font-weight:bold;'>🎯 현재 선택된 테스트: <span style='color:#0284C7;'>{current_active_info[1]}</span> ({current_active_info[2]})</div>", unsafe_allow_html=True)

                last_selected_sess = st.session_state.get("last_active_test_session_id", None)
                if last_selected_sess != selected_session_id:
                    st.session_state["last_active_test_session_id"] = selected_session_id
                    if f"submitted_{selected_session_id}" in st.session_state:
                        del st.session_state[f"submitted_{selected_session_id}"]
                    if f"all_results_{selected_session_id}" in st.session_state:
                        del st.session_state[f"all_results_{selected_session_id}"]
                    if f"retry_stage_{selected_session_id}" in st.session_state:
                        del st.session_state[f"retry_stage_{selected_session_id}"]
        
                cache_key_items = f"cached_items_form_{selected_session_id}"
                if st.session_state.get("active_form_session_id") != selected_session_id or cache_key_items not in st.session_state:
                    st.session_state["active_form_session_id"] = selected_session_id
                    
                    try:
                        q(c_test, "SELECT id, problem_order, unit_code, prob_num, answer, img_base64, solution_img_path, COALESCE(wrong_noted, 0) FROM online_test_items WHERE session_id = ? ORDER BY problem_order ASC", (selected_session_id,))
                        raw_items = c_test.fetchall()
                    except Exception:
                        q(c_test, "SELECT id, problem_order, unit_code, prob_num, answer, img_base64, solution_img_path FROM online_test_items WHERE session_id = ? ORDER BY problem_order ASC", (selected_session_id,))
                        raw_items = [(*r, 0) for r in c_test.fetchall()]
        
                    problem_list = []
                    for item_id, p_order, u_code, p_num, ans, img_b64, sol_path, w_noted in raw_items:
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
                            "filename": str(sol_path) if sol_path else "",
                            "wrong_noted": bool(w_noted)
                        })
                    st.session_state[cache_key_items] = problem_list
        
                problem_list = st.session_state.get(cache_key_items, [])
                selected_test_title = current_active_info[1]
                is_db_completed = (current_active_info[3] == 1)
        
                if not problem_list:
                    st.warning("이 테스트에 등록된 문항 데이터가 없습니다.")
                else:
                    forced_retest = st.session_state.get(f"force_retest_{selected_session_id}", False)
                    if (is_db_completed or st.session_state.get(f"submitted_{selected_session_id}", False)) and not forced_retest:
                        col_re1, col_re2 = st.columns([3, 1])
                        with col_re1:
                            st.info("✅ 이미 제출 완료된 테스트입니다. 아래에서 채점 결과를 확인하거나 다시 풀 수 있습니다.")
                        with col_re2:
                            if st.button("🔄 다시 풀기", use_container_width=True):
                                st.session_state[f"force_retest_{selected_session_id}"] = True
                                if f"submitted_{selected_session_id}" in st.session_state:
                                    del st.session_state[f"submitted_{selected_session_id}"]
                                if f"all_results_{selected_session_id}" in st.session_state:
                                    del st.session_state[f"all_results_{selected_session_id}"]
                                if f"retry_stage_{selected_session_id}" in st.session_state:
                                    del st.session_state[f"retry_stage_{selected_session_id}"]
                                st.rerun()

                    st.markdown("---")
        
                    @st.fragment
                    def render_problem_review_list(prob_list, res_list, sess_id, s_name, s_title):
                        correct_cnt = sum(1 for r in res_list if r.get("is_correct") == 1)
                        wrong_items = [
                            prob for prob in prob_list
                            if next((r.get("is_correct") for r in res_list if r["full_code"] == prob["full_code"]), 0) != 1
                        ]
                        wrong_cnt = len(wrong_items)

                        reolved_map_key = f"reolved_wrong_map_{sess_id}"
                        if reolved_map_key not in st.session_state:
                            st.session_state[reolved_map_key] = {}
                        reolved_map = st.session_state[reolved_map_key]

                        reolved_done_cnt = sum(
                            1 for w_prob in wrong_items
                            if reolved_map.get(w_prob["full_code"], False)
                        )

                        st.session_state[f"correct_count_{sess_id}"] = correct_cnt

                        st.markdown(f"""
                        <div style="background-color: var(--secondary-background-color); border: 2px solid #0284C7; padding: 18px; border-radius: 12px; text-align: center; margin-bottom: 16px;">
                            <h3 style="color: #0284C7; margin: 0 0 8px 0;">🎉 과제 제출 및 자동 채점 완료!</h3>
                            <p style="font-size: 16px; font-weight: bold; margin: 0;">
                                총 {len(prob_list)}문항 중 <span style="color: #10B981;">{correct_cnt}문항 정답</span> · <span style="color: #EF4444;">{wrong_cnt}문항 오답</span>
                            </p>
                            <p style="font-size: 13px; color: #F59E0B; font-weight: bold; margin-top: 8px; margin-bottom: 0;">
                                🔁 틀린 문제 재풀이: {reolved_done_cnt} / {wrong_cnt}문항 완료
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

                        only_wrong_key = f"only_wrong_filter_{sess_id}"
                        if wrong_cnt > 0:
                            only_wrong_mode = st.toggle(
                                f"🎯 틀린 문제만 모아 보기 ({wrong_cnt}문항)",
                                value=st.session_state.get(only_wrong_key, True),
                                key=only_wrong_key
                            )
                        else:
                            only_wrong_mode = False
                            st.success("👏 이번 테스트는 틀린 문제가 없어요! 전체 결과를 확인해 보세요.")

                        display_prob_list = wrong_items if (only_wrong_mode and wrong_items) else prob_list

                        st.markdown(f"### 📝 검토 문항 ({len(display_prob_list)}개)")

                        selected_wrong_notes = {}

                        all_f_codes = [prob["full_code"] for prob in display_prob_list]
                        batch_review_links = get_batch_problem_link_info(all_f_codes)

                        retry_res_map = st.session_state.get(f"retry_result_map_{sess_id}", {})

                        for prob in display_prob_list:
                            matched_res = next((r for r in res_list if r['full_code'] == prob['full_code']), None)

                            ans_str = str(prob.get("answer", "")).strip()
                            filename_str = str(prob.get("filename", "")).strip()

                            if matched_res:
                                u_ans_str = matched_res["user_ans"] if matched_res["user_ans"] else "미입력 (잘 모름)"
                                r_ans = matched_res["real_ans"]
                                is_cor = matched_res["is_correct"]
                                ox_mark = "O" if is_cor == 1 else "X"
                                ox_color = "#10B981" if is_cor == 1 else "#EF4444"
                            else:
                                u_ans_str = "미입력"
                                r_ans = prob["answer"]
                                is_cor = 0
                                ox_mark = "-"
                                ox_color = "gray"

                            v_url, _ = batch_review_links.get(prob["full_code"], ("", ""))
                            link_btn = (
                                f'<a href="{v_url}" target="_blank" style="background-color:#EF4444; color:white; padding:2px 8px; border-radius:4px; font-size:11px; text-decoration:none; font-weight:bold;">해설영상</a>'
                                if v_url
                                else '<span style="color:gray; font-size:11px;">해설 준비중</span>'
                            )

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
                                ans_display = f"<img src='{img_url}' style='height: 35px; width: auto; background: white; padding: 2px; border-radius: 4px; vertical-align: middle; border: 1px solid #ccc;' />"

                            is_multiple_choice_item = detect_multiple_choice(ans_str, filename_str)

                            re_status = retry_res_map.get(prob["full_code"])
                            retry_badge = ""
                            if re_status == "correct":
                                retry_badge = " <span style='background-color:rgba(16,185,129,0.18); color:#10B981; border:1px solid #10B981; padding:1px 6px; border-radius:4px; font-size:11px; font-weight:bold;'>🎯 재풀이 정답</span>"
                            elif re_status == "wrong":
                                retry_badge = " <span style='background-color:rgba(239,68,68,0.18); color:#EF4444; border:1px solid #EF4444; padding:1px 6px; border-radius:4px; font-size:11px; font-weight:bold;'>❌ 재풀이 오답</span>"

                            with st.container(border=True):
                                st.markdown(
                                    f"<div style='display: flex; align-items: center; justify-content: space-between; font-size: 13px; margin-bottom: 6px; padding: 5px 8px; background-color: var(--secondary-background-color); border-radius: 6px;'>"
                                    f"  <div>"
                                    f"    <b>{prob['order']}번 문제</b> "
                                    f"    <span style='color: #9CA3AF; font-size: 11px;'>(`{prob['full_code']}`)</span> "
                                    f"    <span style='color: {ox_color}; font-weight: bold; font-size: 14px;'>({ox_mark})</span>"
                                    f"    {retry_badge}"
                                    f"  </div>"
                                    f"  <div>{link_btn}</div>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                                img_exp_key = f"toggle_img_{sess_id}_{prob['item_id']}"
                                if img_exp_key not in st.session_state:
                                    st.session_state[img_exp_key] = False

                                is_img_open = st.session_state[img_exp_key]
                                if st.button(
                                    f"{'🖼️ 문제 사진 접기 ▲' if is_img_open else '🖼️ 문제 사진 보기 ▼'}",
                                    key=f"btn_top_img_{img_exp_key}",
                                    use_container_width=True
                                ):
                                    st.session_state[img_exp_key] = not is_img_open
                                    st.rerun(scope="fragment")

                                if st.session_state[img_exp_key]:
                                    with st.container(border=True):
                                        if prob["img_bytes"]:
                                            st.image(prob["img_bytes"], use_container_width=True)
                                        else:
                                            st.info("💡 등록된 문제 이미지가 없습니다.")

                                ans_exp_key = f"toggle_ans_{sess_id}_{prob['item_id']}"
                                if ans_exp_key not in st.session_state:
                                    st.session_state[ans_exp_key] = False

                                is_ans_open = st.session_state[ans_exp_key]
                                if st.button(
                                    f"{'🔍 정답 및 채점 확인 접기 ▲' if is_ans_open else '🔍 정답 및 채점 확인하기 ▼'}",
                                    key=f"btn_top_ans_{ans_exp_key}",
                                    use_container_width=True
                                ):
                                    st.session_state[ans_exp_key] = not is_ans_open
                                    st.rerun(scope="fragment")

                                if st.session_state[ans_exp_key]:
                                    with st.container(border=True):
                                        st.markdown(
                                            f"<div style='margin-bottom: 10px; font-size: 13px;'>"
                                            f"📌 <b>정답 확인:</b> {ans_display} &nbsp;|&nbsp; 내 답: <b style='color: {'#10B981' if is_cor == 1 else '#EF4444'};'>{u_ans_str}</b>"
                                            f"</div>",
                                            unsafe_allow_html=True
                                        )

                                        if not is_multiple_choice_item and matched_res is not None:
                                            current_self_val = 1 if is_cor == 1 else 0
                                            self_review_choice = st.radio(
                                                f"{prob['order']}번 셀프 채점 (오타나 형식 차이로 틀린 경우 여기서 변경하세요):",
                                                options=["❌ 틀림 (X)", "⭕ 정답 맞춤 (O)"],
                                                index=current_self_val,
                                                key=f"self_review_{sess_id}_{prob['item_id']}",
                                                horizontal=True
                                            )
                                            new_is_cor = 1 if "정답 맞춤" in self_review_choice else 0
                                            if new_is_cor != is_cor:
                                                matched_res["is_correct"] = new_is_cor
                                                is_postgres = "psycopg2" in str(type(conn_test))
                                                if is_postgres:
                                                    c_test.execute(
                                                        "UPDATE student_test_submissions SET is_checked = %s WHERE student_name = %s AND test_title = %s AND problem_id = %s",
                                                        (new_is_cor, s_name, s_title, prob['full_code'])
                                                    )
                                                else:
                                                    q(
                                                        c_test,
                                                        "UPDATE student_test_submissions SET is_checked = ? WHERE student_name = ? AND test_title = ? AND problem_id = ?",
                                                        (new_is_cor, s_name, s_title, prob['full_code'])
                                                    )
                                                conn_test.commit()
                                                st.rerun(scope="fragment")

                                if is_cor != 1:
                                    re_key = f"re_solve_chk_{sess_id}_{prob['full_code']}"
                                    prev_re_val = bool(reolved_map.get(prob["full_code"], False))
                                    re_checked = st.checkbox(
                                        f"🔁 {prob['order']}번 노트에 다시 풀어봄 (재풀이 완료)",
                                        value=prev_re_val,
                                        key=re_key
                                    )
                                    if re_checked != prev_re_val:
                                        reolved_map[prob["full_code"]] = re_checked
                                        st.rerun(scope="fragment")

                                is_item_saved = (
                                    bool(prob.get("wrong_noted", False))
                                    or st.session_state.get(f"item_saved_{sess_id}_{prob['item_id']}", False)
                                )

                                if is_item_saved:
                                    st.checkbox(
                                        f"✅ {prob['order']}번 오답노트 등록 완료됨",
                                        value=True,
                                        disabled=True,
                                        key=f"wrong_chk_disabled_{sess_id}_{prob['item_id']}"
                                    )
                                else:
                                    selected_wrong_notes[prob['item_id']] = st.checkbox(
                                        f"📌 {prob['order']}번 오답노트 담기",
                                        value=False,
                                        key=f"wrong_chk_{sess_id}_{prob['item_id']}"
                                    )

                        if st.button("📥 선택한 문제들을 오답노트에 등록하기", type="primary", use_container_width=True, key=f"btn_save_wrong_{sess_id}"):
                            manual_wrong_units = {}
                            current_checked_item_ids = []

                            for prob in display_prob_list:
                                if selected_wrong_notes.get(prob['item_id'], False):
                                    current_checked_item_ids.append(prob['item_id'])
                                    if prob["unit_code"] != "TEST":
                                        manual_wrong_units.setdefault(prob["unit_code"], set()).add(int(prob["prob_num"]))

                            if not current_checked_item_ids:
                                st.warning("오답노트에 담을 문제를 먼저 선택해 주세요.")
                            else:
                                try:
                                    for u_code, num_set in manual_wrong_units.items():
                                        existing_txt = get_student_wrong_entry(s_name, u_code)
                                        pre_nums = parse_numbers(existing_txt)
                                        merged_nums = pre_nums | num_set
                                        merged_txt = ", ".join(map(str, sorted(list(merged_nums))))
                                        save_student_wrong_entry(s_name, u_code, merged_txt, target_nums_to_log=num_set)

                                    for item_id_val in current_checked_item_ids:
                                        q(c_test, "UPDATE online_test_items SET wrong_noted = 1 WHERE id = ?", (item_id_val,))
                                        st.session_state[f"item_saved_{sess_id}_{item_id_val}"] = True
                                    conn_test.commit()

                                    for p_cached in st.session_state.get(f"cached_items_form_{sess_id}", []):
                                        if p_cached["item_id"] in current_checked_item_ids:
                                            p_cached["wrong_noted"] = True

                                    st.success("✨ 선택하신 문제들이 오답노트에 성공적으로 반영되었습니다!")
                                    st.rerun()

                                except Exception as e:
                                    st.error(f"⚠️ 오답노트 저장 중 오류 발생: {e}")

                    def evaluate_retry_answer(w_prob, raw_retry_ans):
                        u_ans = str(raw_retry_ans or "").strip()
                        ans_str = str(w_prob.get("answer", "")).strip()
                        fn_str = str(w_prob.get("filename", "")).strip()
                    
                        is_difficulty_empty = False
                        if "난이도" in fn_str:
                            parts_diff = fn_str.split("난이도")
                            if len(parts_diff) > 1:
                                after_diff = parts_diff[1]
                                if "@" not in after_diff and not any(c.isdigit() for c in after_diff.split(".")[0]):
                                    is_difficulty_empty = True
                    
                        if ans_str == "-" or not ans_str or is_difficulty_empty:
                            return "manual"
                    
                        if not u_ans:
                            return "wrong"
                    
                        real_ans = ans_str.replace("@", "").replace("번", "").strip()
                        return "correct" if check_subjective_answer(u_ans, real_ans) else "wrong"
                    
                    def _is_essay_or_subjective(prob):
                        ans_str = str(prob.get("answer", "")).strip()
                        fn_str = str(prob.get("filename", "")).strip()
                        return not detect_multiple_choice(ans_str, fn_str)
                    
                    def _is_essay_item(prob):
                        ans_str = str(prob.get("answer", "")).strip()
                        fn_str = str(prob.get("filename", "")).strip()
                        is_diff_empty = False
                        if "난이도" in fn_str:
                            parts_diff = fn_str.split("난이도")
                            if len(parts_diff) > 1:
                                after_diff = parts_diff[1]
                                if "@" not in after_diff and not any(c.isdigit() for c in after_diff.split(".")[0]):
                                    is_diff_empty = True
                        return (ans_str == "-" or not ans_str or is_diff_empty)

                    def _is_worth_quick_checking(prob, written_ans):
                        u_raw = str(written_ans or "").strip()
                        if not u_raw:
                            return False
                        if _is_essay_item(prob):
                            return True

                        r_raw = str(prob.get("answer") or "").replace("@", "").replace("번", "").strip()
                        if not r_raw or r_raw == "-":
                            return False

                        def _norm_compare(t):
                            t = str(t).strip().lower()
                            t = re.sub(r"[−－—–]", "-", t)
                            t = t.replace("×", "*").replace("÷", "/")
                            t = t.replace("제", "").replace("번", "")
                            t = re.sub(r"\s+", "", t)
                            return t

                        u_n = _norm_compare(u_raw)
                        r_n = _norm_compare(r_raw)
                        if not u_n or not r_n:
                            return False

                        u_has_alpha = bool(re.search(r"[a-z가-힣]", u_n))
                        r_has_alpha = bool(re.search(r"[a-z가-힣]", r_n))
                        if u_has_alpha != r_has_alpha:
                            u_nums = set(re.findall(r"\d+(?:\.\d+)?", u_n))
                            r_nums = set(re.findall(r"\d+(?:\.\d+)?", r_n))
                            if not (u_nums and r_nums and (u_nums & r_nums)):
                                return False

                        u_nums = set(re.findall(r"\d+(?:\.\d+)?", u_n))
                        r_nums = set(re.findall(r"\d+(?:\.\d+)?", r_n))
                        if u_nums and r_nums and not (u_nums & r_nums):
                            return False

                        if (u_n in r_n) or (r_n in u_n):
                            return True

                        u_tokens = set(re.findall(r"[a-z가-힣0-9]+", u_n))
                        r_tokens = set(re.findall(r"[a-z가-힣0-9]+", r_n))
                        if u_tokens and r_tokens and (u_tokens & r_tokens):
                            return True

                        return False
                    
                    def render_retry_then_review(prob_list, res_list, sess_id, s_name, s_title):
                        quick_grade_key = f"quick_grade_map_{sess_id}"
                        if quick_grade_key not in st.session_state:
                            st.session_state[quick_grade_key] = {}
                        quick_grade_map = st.session_state[quick_grade_key]
                    
                        wrong_items_for_retry = []
                        for prob in prob_list:
                            code = prob["full_code"]
                            orig_correct = next((r.get("is_correct") for r in res_list if r["full_code"] == code), 0) == 1
                            if orig_correct:
                                continue
                            if quick_grade_map.get(code) == "O":
                                continue
                            wrong_items_for_retry.append(prob)
                    
                        quick_check_targets = []
                        for prob in prob_list:
                            matched_r = next((r for r in res_list if r["full_code"] == prob["full_code"]), None)
                            if not matched_r or matched_r.get("is_correct") == 1:
                                continue
                            if not _is_essay_or_subjective(prob):
                                continue
                            written_ans = str(matched_r.get("user_ans") or "").strip()
                            if _is_worth_quick_checking(prob, written_ans):
                                quick_check_targets.append(prob)
                    
                        retry_stage_key = f"retry_stage_{sess_id}"
                        just_submitted_key = f"just_submitted_{sess_id}"
                    
                        if st.session_state.get(just_submitted_key, False):
                            if len(quick_check_targets) > 0:
                                st.session_state[retry_stage_key] = "quick_check"
                            elif len(wrong_items_for_retry) > 0:
                                st.session_state[retry_stage_key] = "retry"
                            else:
                                st.session_state[retry_stage_key] = "review"
                            st.session_state[just_submitted_key] = False
                    
                        if retry_stage_key not in st.session_state:
                            st.session_state[retry_stage_key] = "review"
                    
                        reolved_map_key = f"reolved_wrong_map_{sess_id}"
                        if reolved_map_key not in st.session_state:
                            st.session_state[reolved_map_key] = {}
                        reolved_map = st.session_state[reolved_map_key]
                    
                        retry_ans_key = f"retry_ans_map_{sess_id}"
                        if retry_ans_key not in st.session_state:
                            st.session_state[retry_ans_key] = {}
                        retry_ans_map = st.session_state[retry_ans_key]
                    
                        retry_res_key = f"retry_result_map_{sess_id}"
                        if retry_res_key not in st.session_state:
                            st.session_state[retry_res_key] = {}
                        retry_res_map = st.session_state[retry_res_key]
                    
                        def run_retry_grading_and_go_review():
                            graded_summary = {}
                            for w_item in wrong_items_for_retry:
                                code = w_item["full_code"]
                                ans_given = str(retry_ans_map.get(code, "")).strip()
                                status = evaluate_retry_answer(w_item, ans_given)
                                graded_summary[code] = status
                                reolved_map[code] = (ans_given != "")
                            st.session_state[retry_res_key] = graded_summary
                            st.session_state[retry_stage_key] = "review"
                    
                        if st.session_state[retry_stage_key] == "quick_check" and len(quick_check_targets) > 0:
                            st.markdown("""
                            <div style="background-color: var(--secondary-background-color); border: 2px solid #38BDF8; padding: 14px 16px; border-radius: 12px; margin-bottom: 14px;">
                                <h3 style="color: #38BDF8; margin: 0 0 6px 0;">⚡ 다시풀기 전 빠른 확인 (O/X 체크)</h3>
                                <p style="font-size: 13.5px; margin: 0 0 4px 0;">
                                    1. <b>표기·띄어쓰기 차이로 맞았거나 서술형을 맞힌 경우</b>만 <b>⭕ 정답 (O)</b>을 눌러주세요.
                                </p>
                                <p style="font-size: 13.5px; margin: 0; color: #9CA3AF;">
                                    2. 진짜 틀린 문제나 미입력 문항은 <b>❌ 오답 (X)</b> 그대로 두고, 아래 버튼으로 <b>다시풀기</b>를 진행합니다.
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                            for idx_q, q_prob in enumerate(quick_check_targets, start=1):
                                q_code = q_prob["full_code"]
                                matched_r = next((r for r in res_list if r["full_code"] == q_code), {})
                                raw_user_ans = str(matched_r.get("user_ans", "")).strip()
                                user_written = raw_user_ans if raw_user_ans else "미입력 (다시풀기 대상)"
                                real_answer_txt = str(matched_r.get("real_ans") or q_prob.get("answer") or "-").strip()
                                is_essay = _is_essay_item(q_prob)
                    
                                cur_ox = quick_grade_map.get(q_code, "X")
                                default_idx = 0 if cur_ox == "O" else 1
                    
                                with st.container(border=True):
                                    if is_essay:
                                        f_code = str(q_code).strip()
                                        u_part = f_code[:4] if len(f_code) > 4 else "A114"
                                        num_part = f_code[4:] if len(f_code) > 4 else f_code
                                        n_digits = "".join(filter(str.isdigit, num_part))
                                        project_id = "qfpclacalaaxbhhheosw"
                                        target_filename = f"{u_part}_ans_({n_digits}).png"
                                        ans_img_url = f"https://{project_id}.supabase.co/storage/v1/object/public/master_answer/{target_filename}"
                    
                                        st.markdown(f"**서술형 — {q_prob['order']}번 문제** <span style='color:#9CA3AF; font-size:12px;'>(연습장 풀이와 정답지 비교)</span>", unsafe_allow_html=True)
                                        st.markdown(
                                            f"<div style='margin: 4px 0 8px 0;'>"
                                            f"<span style='font-size: 13px; color: #9CA3AF;'>정답지:</span><br>"
                                            f"<img src='{ans_img_url}' onerror=\"this.style.display='none'; this.nextElementSibling.style.display='inline';\" "
                                            f"style='max-height: 90px; width: auto; background: white; padding: 4px 8px; border-radius: 6px; border: 1px solid #ddd; margin-top: 4px;' />"
                                            f"<span style='display: none; font-size: 13px; color: #9CA3AF;'>정답 이미지 없음 — 본인 풀이 기준 셀프채점</span>"
                                            f"</div>",
                                            unsafe_allow_html=True
                                        )
                                    else:
                                        st.markdown(f"**주관식 #{idx_q}** <span style='color:#9CA3AF; font-size:12px;'>(띄어쓰기·표기 차이만 정답 인정)</span>", unsafe_allow_html=True)
                                        st.markdown(f"- **정답:** `{real_answer_txt}`")
                                        st.markdown(f"- **내가 쓴 답:** `{user_written}`")
                    
                                    picked_ox = st.radio(
                                        "판정 선택",
                                        options=["⭕ 정답 (O)", "❌ 오답 (X)"],
                                        index=default_idx,
                                        key=f"quick_ox_{sess_id}_{q_code}",
                                        horizontal=True,
                                        label_visibility="collapsed"
                                    )
                                    quick_grade_map[q_code] = "O" if picked_ox.startswith("⭕") else "X"
                    
                            if st.button("✅ 확인 완료하고 틀린 문제 다시풀기", type="primary", use_container_width=True, key=f"btn_go_retry_after_quick_{sess_id}"):
                                remaining_wrong = [
                                    prob for prob in prob_list
                                    if next((r.get("is_correct") for r in res_list if r["full_code"] == prob["full_code"]), 0) != 1
                                    and quick_grade_map.get(prob["full_code"]) != "O"
                                ]
                                if len(remaining_wrong) > 0:
                                    st.session_state[retry_stage_key] = "retry"
                                else:
                                    st.session_state[retry_stage_key] = "review"
                                st.rerun()
                    
                        elif st.session_state[retry_stage_key] == "retry" and len(wrong_items_for_retry) > 0:
                            attempted_retry_cnt = sum(
                                1 for w_prob in wrong_items_for_retry
                                if str(retry_ans_map.get(w_prob["full_code"], "")).strip() != ""
                            )
                            wrong_nums_badge = ", ".join(f"{w['order']}번" for w in wrong_items_for_retry)
                            empty_warn_key = f"retry_empty_warn_{sess_id}"
                    
                            st.markdown(f"""
                            <div style="background-color: var(--secondary-background-color); border: 2px solid #F59E0B; padding: 14px 16px; border-radius: 12px; margin-bottom: 12px;">
                                <div style="font-size: 12px; font-weight: bold; color: #F59E0B; margin-bottom: 4px;">
                                    🔁 [2단계: 오답 다시풀기] 첫 화면으로 돌아간 게 아니에요!
                                </div>
                                <h3 style="margin: 0 0 6px 0; font-size: 18px;">틀린 문제만 골라 다시 풀기 ({len(wrong_items_for_retry)}문항)</h3>
                                <p style="font-size: 13px; margin: 0 0 6px 0; color: #D1D5DB;">
                                    방금 틀린 <b>{wrong_nums_badge}</b>를 노트에 다시 풀어보고 답을 적어주세요.
                                </p>
                                <p style="font-size: 12.5px; margin: 0; color: #FBBF24;">
                                    입력 완료: <b>{attempted_retry_cnt} / {len(wrong_items_for_retry)}문항</b>
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                            choice_options = ["1번", "2번", "3번", "4번", "5번", "잘 모름"]
                    
                            for idx_w, w_prob in enumerate(wrong_items_for_retry, start=1):
                                w_code = w_prob["full_code"]
                                w_ans_str = str(w_prob.get("answer", "")).strip()
                                w_fn_str = str(w_prob.get("filename", "")).strip()
                                is_mc = detect_multiple_choice(w_ans_str, w_fn_str)
                                prev_matched = next((r for r in res_list if r["full_code"] == w_code), {})
                                prev_given = str(prev_matched.get("user_ans") or "").strip()
                                prev_given_txt = prev_given if prev_given else "미입력"
                    
                                with st.container(border=True):
                                    type_badge = "객관식" if is_mc else "주관식/서술형"
                                    st.markdown(
                                        f"<div style='display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px; flex-wrap:wrap;'>"
                                        f"<div style='font-size: 14px; font-weight: bold;'>"
                                        f"🔁 재도전 {idx_w}/{len(wrong_items_for_retry)} · <b>{w_prob['order']}번 문제</b> "
                                        f"<span style='color: #38BDF8; font-size: 11px;'>[{type_badge}]</span>"
                                        f"</div>"
                                        f"<div style='font-size: 12px; color: #9CA3AF;'>직전 답: <b>{prev_given_txt}</b></div>"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                    
                                    if w_prob.get("img_bytes"):
                                        st.image(w_prob["img_bytes"], width=480)
                                    else:
                                        st.info("💡 등록된 문제 이미지가 없습니다.")
                    
                                    prev_re_val = retry_ans_map.get(w_code, "")
                    
                                    if is_mc:
                                        clean_prev = str(prev_re_val).replace("번", "").strip()
                                        default_radio_idx = choice_options.index(f"{clean_prev}번") if clean_prev in ["1", "2", "3", "4", "5"] else 5
                                        picked_choice = st.radio(
                                            f"{w_prob['order']}번 다시 풀어본 답 선택 (객관식):",
                                            options=choice_options,
                                            index=default_radio_idx,
                                            key=f"retry_radio_{sess_id}_{w_code}",
                                            horizontal=True
                                        )
                                        new_val = picked_choice.replace("번", "").strip() if picked_choice != "잘 모름" else ""
                                    else:
                                        new_val = st.text_input(
                                            f"{w_prob['order']}번 다시 풀어본 답 입력 (주관식):",
                                            value=prev_re_val,
                                            placeholder="다시 풀어본 답을 입력하세요",
                                            key=f"retry_input_{sess_id}_{w_code}"
                                        ).strip()
                    
                                    if new_val != prev_re_val:
                                        retry_ans_map[w_code] = new_val
                                        reolved_map[w_code] = (new_val != "")
                                        if new_val != "":
                                            st.session_state[empty_warn_key] = False
                                        st.rerun()
                    
                            if st.button("✅ 다시 풀기 마치고 재채점 보기", type="primary", use_container_width=True, key=f"btn_finish_retry_bottom_{sess_id}"):
                                if attempted_retry_cnt == 0:
                                    st.session_state[empty_warn_key] = True
                                else:
                                    st.session_state[empty_warn_key] = False
                                    run_retry_grading_and_go_review()
                                    st.rerun()

                            if st.session_state.get(empty_warn_key, False):
                                st.warning("다시풀기 하셨나요? 답을 입력한 뒤 재채점해 주세요!")
                    
                        else:
                            if len(quick_check_targets) > 0:
                                if st.button("⚡ 주관식/서술형 빠른 확인 다시 열기", use_container_width=True, key=f"btn_reopen_quick_{sess_id}"):
                                    st.session_state[retry_stage_key] = "quick_check"
                                    st.rerun()
                    
                            if len(wrong_items_for_retry) > 0:
                                if st.button(f"🔁 남은 오답 {len(wrong_items_for_retry)}문항 다시 풀기", type="primary", use_container_width=True, key=f"btn_reopen_retry_{sess_id}"):
                                    st.session_state[retry_stage_key] = "retry"
                                    st.rerun()
                    
                            if retry_res_map:
                                re_ok = sum(1 for v in retry_res_map.values() if v == "correct")
                                re_fail = sum(1 for v in retry_res_map.values() if v == "wrong")
                                st.markdown(f"""
                                <div style="background-color: rgba(16, 185, 129, 0.08); border: 1px solid #10B981; padding: 12px 14px; border-radius: 10px; margin-bottom: 12px; font-size: 13.5px;">
                                    🎯 <b>재풀이 채점 결과:</b> 다시 풀어본 문항 중 <b style="color:#10B981;">{re_ok}문항 정답</b> · <b style="color:#EF4444;">{re_fail}문항 재오답</b>
                                </div>
                                """, unsafe_allow_html=True)
                    
                            render_problem_review_list(prob_list, res_list, sess_id, s_name, s_title)

                    if (is_db_completed or st.session_state.get(f"submitted_{selected_session_id}", False)) and not st.session_state.get(f"force_retest_{selected_session_id}", False):
                        if f"all_results_{selected_session_id}" not in st.session_state:
                            is_postgres = "psycopg2" in str(type(conn_test))
                            if is_postgres:
                                c_test.execute("SELECT problem_id, student_answer, is_checked FROM student_test_submissions WHERE student_name = %s AND test_title = %s ORDER BY id ASC", (selected_student, selected_test_title))
                            else:
                                q(c_test, "SELECT problem_id, student_answer, is_checked FROM student_test_submissions WHERE student_name = ? AND test_title = ? ORDER BY id ASC", (selected_student, selected_test_title))
                            submitted_rows = c_test.fetchall()
                            sub_dict = {row[0]: {"user_ans": row[1], "is_checked": row[2]} for row in submitted_rows}
                            
                            restored_results = []
                            restored_correct_cnt = 0
                            for idx, prob in enumerate(problem_list):
                                f_code = prob['full_code']
                                info = sub_dict.get(f_code, {"user_ans": "", "is_checked": 0})
                                real_ans = prob["answer"]
                                is_cor = info["is_checked"]
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
                        render_retry_then_review(problem_list, all_results, selected_session_id, selected_student, selected_test_title)
        
                    else:
                        with st.form(key=f"test_form_{selected_session_id}"):
                            form_answers = {}
                            for idx, prob in enumerate(problem_list):
                                p_key = f"form_{selected_session_id}_{prob['item_id']}"
                                
                                st.markdown(f"#### **{idx + 1}번 문제** (`{prob['full_code']}`)")
                                if prob["img_bytes"]:
                                    st.image(prob["img_bytes"], width=480)
                                else:
                                    st.info("💡 등록된 문제 이미지가 없습니다.")
        
                                ans_str = str(prob.get("answer", "")).strip()
                                filename_str = str(prob.get("filename", "")).strip()
                                
                                is_difficulty_empty = False
                                if "난이도" in filename_str:
                                    parts_diff = filename_str.split("난이도")
                                    if len(parts_diff) > 1:
                                        after_diff = parts_diff[1]
                                        if "@" not in after_diff and not any(c.isdigit() for c in after_diff.split(".")[0]):
                                            is_difficulty_empty = True

                                is_self_check = (ans_str == "-" or is_difficulty_empty)

                                if is_self_check:
                                    st.markdown(
                                        "<div style='background-color: var(--secondary-background-color); border-left: 3px solid #0284C7; padding: 10px 12px; border-radius: 6px; font-size: 13px; color: #0284C7; margin-bottom: 10px;'>"
                                        "📝 <b>노트에 정답(풀이)을 적고 넘어가세요!</b><br>"
                                        "최종 제출 후 정답 해설을 확인하면서 셀프 채점(O/X)을 진행하게 됩니다."
                                        "</div>",
                                        unsafe_allow_html=True
                                    )
                                    user_ans = "셀프채점시대기"
                                else:
                                    is_multiple_choice = detect_multiple_choice(ans_str, filename_str)

                                    if is_multiple_choice:
                                        choice_options = ["1번", "2번", "3번", "4번", "5번", "잘 모름"]
                                        selected_choice = st.radio(
                                            f"{idx + 1}번 정답 선택 (객관식):",
                                            options=choice_options,
                                            index=5,
                                            key=f"radio_{p_key}",
                                            horizontal=True
                                        )
                                        user_ans = selected_choice.replace("번", "").strip() if selected_choice != "잘 모름" else ""
                                    else:
                                        user_ans = st.text_input(
                                            f"{idx + 1}번 정답 입력 (주관식 단답형):",
                                            value="",
                                            key=f"text_{p_key}",
                                            placeholder="정답을 입력하세요 (예: 제4사분면 또는 4사분면)"
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
                                ans_str = str(prob.get("answer", "")).strip()
                                filename_str = str(prob.get("filename", "")).strip()
                                
                                is_difficulty_empty = False
                                if "난이도" in filename_str:
                                    parts_diff = filename_str.split("난이도")
                                    if len(parts_diff) > 1:
                                        after_diff = parts_diff[1]
                                        if "@" not in after_diff and not any(c.isdigit() for c in after_diff.split(".")[0]):
                                            is_difficulty_empty = True

                                is_self_check = (ans_str == "-" or is_difficulty_empty)
                                u_ans = form_answers.get(p_key, "")

                                if is_self_check:
                                    is_correct = 0
                                    real_ans = "-"
                                else:
                                    real_ans = ans_str.replace("@", "").replace("번", "").strip()
                                    is_correct = 1 if (u_ans != "" and real_ans != "" and check_subjective_answer(u_ans, real_ans)) else 0

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
                                if is_postgres:
                                    c_test.execute(
                                        "DELETE FROM student_test_submissions WHERE student_name = %s AND test_title = %s",
                                        (selected_student, selected_test_title)
                                    )
                                else:
                                    q(c_test,
                                      "DELETE FROM student_test_submissions WHERE student_name = ? AND test_title = ?",
                                      (selected_student, selected_test_title))

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
                            st.session_state[f"just_submitted_{selected_session_id}"] = True
                            if f"force_retest_{selected_session_id}" in st.session_state:
                                del st.session_state[f"force_retest_{selected_session_id}"]
                            st.balloons()
                            st.rerun()

        with tab5:
            st.subheader("🗓️ 나의 테스트 일정 달력")
            st.caption("월간 달력에서 날짜를 선택하거나 주간 보기로 이번 주 테스트 일정을 확인하세요.")

            import calendar as py_calendar

            stu_target_name = selected_student if "selected_student" in locals() else ""
            today_kst = get_korean_today() if "get_korean_today" in globals() else datetime.now().date()
            if "stu_cal_year" not in st.session_state:
                st.session_state.stu_cal_year = today_kst.year
            if "stu_cal_month" not in st.session_state:
                st.session_state.stu_cal_month = today_kst.month
            if "stu_selected_date" not in st.session_state:
                st.session_state.stu_selected_date = today_kst.strftime("%Y-%m-%d")

            view_mode = st.radio(
                "보기 방식 선택",
                ["📅 월간 달력", "📆 주간 보기"],
                horizontal=True,
                key="stu_ts_view_mode",
            )

            if view_mode == "📅 월간 달력":
                from urllib.parse import urlencode

                # URL 쿼리 파라미터로 전달된 달력 날짜 선택 처리
                picked_cal_date = st.query_params.get("cal_date", None)
                if picked_cal_date:
                    try:
                        datetime.strptime(picked_cal_date, "%Y-%m-%d")
                        st.session_state.stu_selected_date = picked_cal_date
                    except ValueError:
                        pass
                    try:
                        del st.query_params["cal_date"]
                    except Exception:
                        pass

                yr = st.session_state.stu_cal_year
                mo = st.session_state.stu_cal_month

                m_prev, m_title, m_next = st.columns([1.25, 1.5, 1.25])
                with m_prev:
                    if st.button("◀ 이전", key="stu_cal_prev", use_container_width=True):
                        if mo == 1:
                            st.session_state.stu_cal_year = yr - 1
                            st.session_state.stu_cal_month = 12
                        else:
                            st.session_state.stu_cal_month = mo - 1
                        st.rerun()
                with m_title:
                    st.markdown(
                        f"<div style='text-align:center; font-weight:700; font-size:0.98rem; padding-top:7px; white-space:nowrap;'>"
                        f"{yr}.{mo:02d}</div>",
                        unsafe_allow_html=True,
                    )
                with m_next:
                    if st.button("다음 ▶", key="stu_cal_next", use_container_width=True):
                        if mo == 12:
                            st.session_state.stu_cal_year = yr + 1
                            st.session_state.stu_cal_month = 1
                        else:
                            st.session_state.stu_cal_month = mo + 1
                        st.rerun()

                last_day = py_calendar.monthrange(yr, mo)[1]
                m_start = f"{yr:04d}-{mo:02d}-01"
                m_end = f"{yr:04d}-{mo:02d}-{last_day:02d}"

                stu_ts_df = get_student_test_schedules(stu_target_name, m_start, m_end)
                date_to_rows = {}
                if not stu_ts_df.empty:
                    for _, r in stu_ts_df.iterrows():
                        date_to_rows.setdefault(str(r["test_date"]), []).append(r)

                st.caption("범례: 🔵 예정 · 🟢 완료 · 🔴 재시험 (날짜를 누르면 아래에 상세 일정이 표시됩니다)")

                current_student = st.query_params.get("student", None)

                cal_weeks = py_calendar.monthcalendar(yr, mo)
                grid_cells_html = []

                for d_lbl in ["월", "화", "수", "목", "금", "토", "일"]:
                    grid_cells_html.append(
                        f"<div style='text-align:center; font-size:12px; font-weight:700; color:#94A3B8; padding:4px 0;'>{d_lbl}</div>"
                    )

                for week in cal_weeks:
                    for day_num in week:
                        if day_num == 0:
                            grid_cells_html.append("<div style='min-height:48px;'></div>")
                        else:
                            d_str = f"{yr:04d}-{mo:02d}-{day_num:02d}"
                            day_items = date_to_rows.get(d_str, [])
                            badge_html = ""
                            if day_items:
                                statuses = [str(x["status"]) for x in day_items]
                                if "retest" in statuses:
                                    b_icon = "🔴"
                                elif "scheduled" in statuses:
                                    b_icon = "🔵"
                                else:
                                    b_icon = "🟢"
                                badge_html = f"<div style='font-size:10px; line-height:1.1; margin-top:2px;'>{b_icon}{len(day_items)}</div>"

                            is_sel = (st.session_state.stu_selected_date == d_str)
                            border_col = "#38BDF8" if is_sel else "rgba(148,163,184,0.25)"
                            bg_col = "rgba(2,132,199,0.28)" if is_sel else "rgba(15,23,42,0.55)"
                            text_col = "#FFFFFF" if is_sel else "#E2E8F0"

                            params_dict = {"cal_date": d_str}
                            if current_student:
                                params_dict["student"] = current_student
                            href_url = "?" + urlencode(params_dict)

                            cell_html = (
                                f"<a href='{href_url}' target='_self' style='"
                                f"display:flex; flex-direction:column; align-items:center; justify-content:center; "
                                f"min-height:48px; border-radius:8px; text-decoration:none; "
                                f"border:1.5px solid {border_col}; background-color:{bg_col}; color:{text_col}; "
                                f"box-sizing:border-box; padding:3px 2px;'>"
                                f"<span style='font-size:12.5px; font-weight:{'700' if is_sel else '500'}; line-height:1.15;'>{day_num}</span>"
                                f"{badge_html}"
                                f"</a>"
                            )
                            grid_cells_html.append(cell_html)

                st.markdown(
                    f"""
                    <div style="
                        display: grid;
                        grid-template-columns: repeat(7, minmax(0, 1fr));
                        gap: 4px;
                        width: 100%;
                        margin: 6px 0 10px 0;
                    ">
                        {''.join(grid_cells_html)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                sel_str = st.session_state.stu_selected_date
                try:
                    sel_obj = datetime.strptime(sel_str, "%Y-%m-%d").date()
                    sel_title = f"{sel_obj.month}월 {sel_obj.day}일 ({_ts_weekday_short_kr(sel_obj)}) 테스트 상세"
                except Exception:
                    sel_title = f"{sel_str} 테스트 상세"

                st.markdown("---")
                st.markdown(f"### 📌 {sel_title}")
                selected_items = date_to_rows.get(sel_str, [])
                if not selected_items:
                    st.info("선택한 날짜에 예정된 테스트 일정이 없습니다.")
                else:
                    for item in selected_items:
                        st_label = get_test_status_label(item["status"])
                        with st.container(border=True):
                            st.markdown(f"**[{st_label}] {item['title']}** · `{item['test_type']}`")
                            if item["scope"]:
                                st.write(f"**출제 범위:** {item['scope']}")
                            if item["memo"]:
                                st.caption(f"**안내 메모:** {item['memo']}")

            else:
                mon = today_kst - timedelta(days=today_kst.weekday())
                sun = mon + timedelta(days=6)
                st.info(f"📆 이번 주간: **{_ts_week_range_str(mon)}**")
                wk_df = get_student_test_schedules(stu_target_name, mon.strftime("%Y-%m-%d"), sun.strftime("%Y-%m-%d"))
                if wk_df.empty:
                    st.info("이번 주에 등록된 테스트 일정이 없습니다.")
                else:
                    for _, item in wk_df.iterrows():
                        d_obj = datetime.strptime(str(item["test_date"]), "%Y-%m-%d").date()
                        st_label = get_test_status_label(item["status"])
                        with st.container(border=True):
                            st.markdown(
                                f"**{d_obj.strftime('%m/%d')} ({_ts_weekday_short_kr(d_obj)}) · [{st_label}] {item['title']}**"
                            )
                            st.caption(f"구분: {item['test_type']}" + (f" | 범위: {item['scope']}" if item["scope"] else ""))
                            if item["memo"]:
                                st.caption(f"안내: {item['memo']}")


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

    t_cfg_student, t_cfg_notice, t_cfg_hw, t_cfg_curriculum, t_cfg_wrong, t_cfg_matrix, t_cfg_links, t_cfg_stats, t_cfg_tests, t_cfg_schedule = st.tabs([
        "👤 1. [개별] 학생 진도 관리", 
        "📢 2. 공지사항 관리",
        "📅 3. 개별 과제 관리", 
        "📚 4. 커리큘럼 진도 배정", 
        "🔍 5. 오답노트 모아보기",
        "📊 6. 전체 숙제 매트릭스",
        "🎥 7. 해설 링크 관리",
        "📈 8. 실시간 학습 참여 현황",
        "📋 9. 학생 제출물 및 풀이 검사",
        "🗓️ 10. 테스트 일정 관리"
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

                @st.fragment
                def render_teacher_milestone_list(stu_name, grouped_keys, grouped_map, prog_map):
                    open_exp_key = f"t_open_chapter_{stu_name}"
                    if open_exp_key not in st.session_state:
                        st.session_state[open_exp_key] = None

                    current_prog = dict(prog_map)

                    for (sub, ch) in grouped_keys:
                        items = grouped_map[(sub, ch)]
                        done_cnt = sum(1 for m_id, _, _ in items if current_prog.get(m_id, False))
                        chapter_tag = f"{sub}||{ch}"
                        is_expanded = (st.session_state[open_exp_key] == chapter_tag)

                        with st.expander(f"[{sub}] {ch}  (완료: {done_cnt}/{len(items)})", expanded=is_expanded):
                            st.session_state[open_exp_key] = chapter_tag
                            for idx, (m_id, t_name, v_url) in enumerate(items):
                                is_done = current_prog.get(m_id, False)
                                chk_key = f"t_milestone_{stu_name}_{ch}_{m_id}_{idx}"

                                def on_t_milestone_change(m_id_val=m_id, k=chk_key, tag=chapter_tag):
                                    st.session_state[open_exp_key] = tag
                                    save_single_milestone_progress(stu_name, m_id_val, st.session_state[k])

                                st.checkbox(
                                    f"{t_name}",
                                    value=is_done,
                                    key=chk_key,
                                    on_change=on_t_milestone_change
                                )

                render_teacher_milestone_list(selected_student, sorted_t_grouped_keys, grouped_t_milestones, s_m_progress)
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
            
            with st.expander("🔥 학생별 [루틴 과제 및 요일 지정] 설정", expanded=False):
                with st.form("add_teacher_routine_form"):
                    new_routine_txt = st.text_area("루틴 과제 항목 입력", placeholder="- 오답노트 정리\n- 영어 단어 암기")
                    new_routine_days = st.multiselect(
                        "진행 요일 선택 (미선택 시 매일)",
                        options=ALL_WEEKDAYS,
                        default=ALL_WEEKDAYS,
                        format_func=lambda idx: f"{WEEKDAY_NAMES_KR[idx]}요일",
                        key="new_routine_days_ms"
                    )
                    if st.form_submit_button("➕ 루틴 일괄 등록", type="primary"):
                        if new_routine_txt.strip():
                            bulk_insert_daily_routines(selected_hw_student, new_routine_txt, active_days=new_routine_days)
                            st.success("등록되었습니다!")
                            st.rerun()
                
                current_routines = get_student_daily_routines(selected_hw_student, include_inactive=True)
                if current_routines:
                    st.markdown("---")
                    st.caption("▲/▼로 순서를 변경하고, ⏸/▶로 일시 중단·재개(기존 기록 유지)하거나 요일·삭제를 관리하세요.")
                    routines_to_delete = []
                    total_rt_cnt = len(current_routines)

                    for r_idx, (r_id, r_title, r_active, r_order, r_days) in enumerate(current_routines):
                        row_c1, row_c2, row_c3, row_c4, row_c5 = st.columns([3.8, 0.7, 0.7, 1.3, 0.5])
                        days_badge_txt = format_active_days_label(r_days)
                        with row_c1:
                            status_prefix = "" if r_active else "⏸️ [일시중단] "
                            title_style = "" if r_active else "opacity: 0.65;"
                            st.markdown(
                                f"<div style='font-size:13px; font-weight:bold; padding-top:4px; {title_style}'>{status_prefix}📌 {r_title} <span style='font-size:11px; color:#38BDF8; font-weight:normal;'>[{days_badge_txt}]</span></div>",
                                unsafe_allow_html=True
                            )
                        with row_c2:
                            if st.button("▲", key=f"btn_rt_up_{selected_hw_student}_{r_id}", disabled=(r_idx == 0), use_container_width=True):
                                update_routine_order(selected_hw_student, r_id, "up")
                                st.rerun()
                        with row_c3:
                            if st.button("▼", key=f"btn_rt_dn_{selected_hw_student}_{r_id}", disabled=(r_idx == total_rt_cnt - 1), use_container_width=True):
                                update_routine_order(selected_hw_student, r_id, "down")
                                st.rerun()
                        with row_c4:
                            toggle_label = "⏸ 중단" if r_active else "▶ 재개"
                            if st.button(toggle_label, key=f"btn_rt_act_{selected_hw_student}_{r_id}", use_container_width=True):
                                toggle_routine_active(r_id, not r_active)
                                st.rerun()
                        with row_c5:
                            if st.checkbox("삭제", key=f"chk_del_routine_{r_id}", label_visibility="collapsed"):
                                routines_to_delete.append(r_id)

                        with st.popover(f"🗓️ '{r_title}' 요일 설정 ({days_badge_txt})"):
                            edited_days = st.multiselect(
                                "진행할 요일 선택",
                                options=ALL_WEEKDAYS,
                                default=r_days,
                                format_func=lambda idx: f"{WEEKDAY_NAMES_KR[idx]}요일",
                                key=f"edit_rt_days_{selected_hw_student}_{r_id}"
                            )
                            if st.button("💾 요일 저장", key=f"btn_save_rt_days_{selected_hw_student}_{r_id}", type="primary", use_container_width=True):
                                if edited_days:
                                    update_routine_active_days(r_id, edited_days)
                                    st.success("요일 설정이 저장되었습니다!")
                                    st.rerun()
                                else:
                                    st.warning("최소 1개 이상의 요일을 선택해 주세요.")

                        st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid rgba(128,128,128,0.12);'>", unsafe_allow_html=True)

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
            with st.expander("🧹 기존 중복 누적 로그 일괄 정리하기 (1회성 정리 도구)", expanded=False):
                st.caption("과거에 누적 저장되어 여러 날짜/주간에 중복 표시되는 이력을 최초 등록일 기준으로 깔끔하게 정리합니다.")
                if st.button("🧹 기존 중복 오답 로그 정리 실행", key="btn_cleanup_dup_wrong_logs", use_container_width=True):
                    ok_clean, msg_clean = cleanup_duplicate_wrong_logs()
                    if ok_clean:
                        st.success(msg_clean)
                        st.rerun()
                    else:
                        st.error(msg_clean)

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
                @st.cache_data(ttl=60, show_spinner=False)
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
                        def get_week_range_str_local(date_str):
                            try:
                                d = date.fromisoformat(date_str[:10])
                                start_week = d - timedelta(days=d.weekday())
                                end_week = start_week + timedelta(days=6)
                                return f"{start_week} ~ {end_week} (월~일)"
                            except Exception:
                                return "날짜 미상 주간"
                        
                        weeks_dict = {}
                        for s_name, u_code, p_num, reg_date in log_rows:
                            weeks_dict.setdefault(get_week_range_str_local(reg_date) if reg_date else "날짜 미상 주간", []).append((s_name, u_code, p_num, reg_date))
                        
                        sorted_weeks = sorted(weeks_dict.keys(), reverse=True)
                        selected_week = st.selectbox("📆 확인할 주간 선택 (월요일~일요일)", sorted_weeks)
                        filtered_logs = weeks_dict.get(selected_week, []) if selected_week else []

                        grouped_week_map = {}
                        for s_name, u_code, p_num, reg_date in filtered_logs:
                            key = (s_name, u_code)
                            if key not in grouped_week_map:
                                grouped_week_map[key] = {"nums": set(), "dates": []}
                            grouped_week_map[key]["nums"].add(int(p_num))
                            if reg_date:
                                grouped_week_map[key]["dates"].append(reg_date)
                        
                        for (s_name, u_code), info in grouped_week_map.items():
                            nums_txt = ", ".join(map(str, sorted(list(info["nums"]))))
                            date_span_str = f"{min(info['dates'])} ~ {max(info['dates'])}" if info["dates"] else (selected_week or "")
                            target_rows.append((s_name, u_code, nums_txt, date_span_str))
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
                all_rep_counts_map = get_all_students_wrong_repeat_counts()
                summary_student_counts = {}
                all_target_full_codes = []
                repeat_item_total = 0
                
                for s_name, u_code, nums_txt, u_date in target_rows:
                    parsed_s = parse_numbers(nums_txt)
                    if parsed_s:
                        summary_student_counts[s_name] = summary_student_counts.get(s_name, 0) + len(parsed_s)
                        for n in parsed_s:
                            f_code = f"{u_code}{n:03d}".upper()
                            all_target_full_codes.append(f_code)
                            if all_rep_counts_map.get((s_name, f_code), 0) >= 2:
                                repeat_item_total += 1
                
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
                            🔁 반복 오답(2회↑): <b style="color: #F59E0B;">{repeat_item_total}건</b> &nbsp;|&nbsp; 
                            📚 전체 오답 문제: <b style="color: #0284C7;">{total_sum_all}개</b>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    if summary_student_counts:
                        st.markdown("<div style='font-size: 12px; color: gray; margin-bottom: 4px;'>👤 학생별 총 오답 문제 수</div>", unsafe_allow_html=True)
                        st.markdown(" | ".join([f"`{s}`: **{c}개**" for s, c in summary_student_counts.items()]))

                # 📋 전체복사용 단원별 코드 문자열 수집 (예: A116_(027,101,...),116_(164,...))
                copy_chunks_all = []
                copy_chunks_by_student = {}
                for s_name, u_code, nums_txt, u_date in target_rows:
                    parsed_s = parse_numbers(nums_txt)
                    if parsed_s:
                        sorted_3digit = ",".join(f"{n:03d}" for n in sorted(list(parsed_s)))
                        chunk_str = f"{u_code}_({sorted_3digit})"
                        copy_chunks_all.append(chunk_str)
                        copy_chunks_by_student.setdefault(s_name, []).append(chunk_str)

                if copy_chunks_all:
                    with st.container(border=True):
                        st.markdown("##### 📋 단원별 오답 코드 전체복사")
                        if chk_student_choice == "전체 학생 (모두 보기)" and len(copy_chunks_by_student) > 1:
                            copy_target_opt = st.selectbox(
                                "복사 대상 선택",
                                ["전체 조회 결과 한 줄로 합치기"] + list(copy_chunks_by_student.keys()),
                                key="wrong_bulk_copy_target_sel"
                            )
                            if copy_target_opt == "전체 조회 결과 한 줄로 합치기":
                                full_copy_text = ",".join(copy_chunks_all)
                            else:
                                full_copy_text = ",".join(copy_chunks_by_student.get(copy_target_opt, []))
                        else:
                            full_copy_text = ",".join(copy_chunks_all)

                        render_clipboard_copy_button(
                            full_copy_text,
                            key_suffix=f"wrong_{chk_student_choice}_{wrong_view_mode}",
                            btn_label="📋 전체복사"
                        )
                        st.code(full_copy_text, language=None)

                st.markdown("---")

                for s_name, u_code, nums_txt, u_date in target_rows:
                    parsed_s = parse_numbers(nums_txt)
                    if parsed_s:
                        with st.container(border=True):
                            st.markdown(f"##### 👤 **{s_name}** | 📖 단원코드: `{u_code}` <span style='font-size:12px; color:gray;'>(등록일: {u_date})</span>", unsafe_allow_html=True)
                            
                            num_items_html = []
                            repeat_badges_html = []
                            for n in sorted(list(parsed_s)):
                                f_code = f"{u_code}{n:03d}".upper()
                                v_url, _ = batch_link_cache.get(f_code, ("", ""))
                                num_color = "#0284C7" if (v_url and v_url.strip()) else "#DC2626"
                                num_items_html.append(f"<span style='color: {num_color}; font-weight: bold;'>{n:03d}</span>")

                                rep_cnt_item = all_rep_counts_map.get((s_name, f_code), 0)
                                rep_badge_item = format_repeat_badge_html(rep_cnt_item)
                                if rep_badge_item:
                                    repeat_badges_html.append(f"<span style='display:inline-flex; align-items:center; gap:3px;'><span style='color:{num_color}; font-weight:bold; font-size:12px;'>{n:03d}</span>{rep_badge_item}</span>")

                            joined_nums_str = ",".join(num_items_html)
                            repeat_summary_html = (
                                f"<div style='margin-top: 6px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;'>{''.join(repeat_badges_html)}</div>"
                                if repeat_badges_html else ""
                            )

                            st.markdown(
                                f"<div style='padding: 10px; border-radius: 6px; font-family: monospace; font-size: 15px; border:1px solid rgba(128,128,128,0.3); line-height:1.6; user-select:text;'>"
                                f"<span>{u_code}_({joined_nums_str})</span>{repeat_summary_html}"
                                f"</div>",
                                unsafe_allow_html=True
                            )
            else:
                st.info("조건에 일치하는 오답노트 기록이 없습니다.")
        else:
            st.warning("등록된 학생이 없습니다.")

    with t_cfg_matrix:
        col_mat_title, col_mat_btn = st.columns([3.5, 1.5])
        with col_mat_title:
            st.markdown("#### 📊 전체 학생 숙제 현황 및 통합 관리")
        with col_mat_btn:
            if st.button("🔄 새로고침", key="btn_refresh_matrix", use_container_width=True):
                st.cache_data.clear()
                st.toast("최신 숙제 현황을 불러왔습니다!", icon="✅")
                st.rerun()

        @st.cache_data(ttl=30, show_spinner=False)
        def get_cached_hw_dates():
            conn_m, _ = get_db_connection()
            c_m = conn_m.cursor()
            q(c_m, "SELECT DISTINCT hw_date FROM student_homework ORDER BY hw_date DESC")
            return [r[0] for r in c_m.fetchall()]

        all_hw_dates = get_cached_hw_dates()
        
        if all_hw_dates and student_list:
            selected_matrix_date = st.selectbox("확인할 숙제 날짜 선택", all_hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
            
            @st.fragment
            def render_homework_matrix_section(sel_date, s_list):
                all_students_hw_map = get_all_students_homework_map(sel_date)
                entire_hw_prog = get_entire_homework_progress_map()
                active_hw_students = [s_name for s_name in s_list if all_students_hw_map.get(s_name)]

                if active_hw_students:
                    st.markdown(f"**📌 총 {len(active_hw_students)}명의 학생에게 숙제가 배정되어 있습니다.**")
                    st.markdown("---")

                    for s_idx_main, s_name in enumerate(active_hw_students):
                        hws = all_students_hw_map.get(s_name, [])
                        
                        done_count_mat = sum(1 for hw_item in hws if not hw_item[1].startswith("💬 [선생님 메시지]:") and entire_hw_prog.get((s_name, hw_item[0]), False))
                        total_count_mat = sum(1 for hw_item in hws if not hw_item[1].startswith("💬 [선생님 메시지]:"))
                        
                        with st.expander(f"👤 {s_name} 학생 숙제 현황 (완료: {done_count_mat} / {total_count_mat}개)", expanded=False):
                            initial_mat_text = "\n".join([hw[1] for hw in hws])
                            for h_idx, hw_tuple in enumerate(hws):
                                h_id = hw_tuple[0]
                                title = hw_tuple[1]
                                due_date = hw_tuple[2] if len(hw_tuple) > 2 else ""

                                if title.startswith("💬 [선생님 메시지]:"):
                                    st.info(f"💬 **선생님 한마디**: {title.replace('💬 [선생님 메시지]:', '').strip()}")
                                else:
                                    is_done = entire_hw_prog.get((s_name, h_id), False)
                                    chk_key = f"mat_{s_idx_main}_{sel_date}_{h_id}_{h_idx}"
                                    
                                    date_suffix = ""
                                    if due_date and due_date.strip():
                                        short_wday = get_weekday_short_kr(due_date)
                                        wday_str = f" ({short_wday})" if short_wday else ""
                                        date_suffix = f" (마감: {due_date}{wday_str})"

                                    def on_mat_hw_change(stu=s_name, hw_id_val=h_id, k=chk_key):
                                        save_single_homework_progress(stu, hw_id_val, st.session_state[k])

                                    st.checkbox(
                                        f"{title}{date_suffix}",
                                        value=is_done,
                                        key=chk_key,
                                        on_change=on_mat_hw_change
                                    )

                            with st.form(f"matrix_edit_form_{s_idx_main}_{sel_date}"):
                                edited_mat_text = st.text_area("이 학생의 숙제 일괄 편집", value=initial_mat_text, height=110)
                                col_m1, col_m2 = st.columns(2)
                                with col_m1:
                                    if st.form_submit_button("💾 수정 저장", type="primary"):
                                        update_student_homework_by_date(s_name, sel_date, edited_mat_text.strip())
                                        st.success("수정되었습니다!")
                                        st.rerun()
                                with col_m2:
                                    if st.form_submit_button("🗑️ 이 날 숙제 전체 삭제"):
                                        delete_student_homework_date(s_name, sel_date)
                                        st.success("삭제되었습니다!")
                                        st.rerun()
                else:
                    st.info("선택하신 날짜에 배정된 숙제가 있는 학생이 없습니다.")

            render_homework_matrix_section(selected_matrix_date, student_list)

    with t_cfg_links:
        st.markdown("#### 🎥 문제별 풀이 영상 링크 등록 및 관리")
        with st.form("single_prob_link_form"):
            col_l1, col_l2 = st.columns([1.5, 2.5])
            with col_l1: p_code_input = st.text_input("문제 코드", placeholder="B1353015")
            with col_l2: p_url_input = st.text_input("영상 URL", placeholder="https://cafe.naver.com/...")
            if st.form_submit_button("🔗 단일 등록", type="primary"):
                if p_code_input.strip() and p_url_input.strip():
                    if save_problem_link(p_code_input, p_url_input):
                        st.success("등록되었습니다!")
                        st.rerun()
        with st.form("bulk_prob_link_form"):
            bulk_links_txt = st.text_area("일괄 등록 (코드 링크 줄바꿈 입력)", height=150)
            if st.form_submit_button("🚀 일괄 등록", type="primary"):
                if bulk_links_txt.strip():
                    s_cnt, f_cnt = bulk_save_problem_links(bulk_links_txt)
                    st.success(f"완료: {s_cnt}건")
                    st.rerun()

        st.divider()
        st.markdown("#### 📊 등록된 단원코드별 문항 현황 요약")
        
        unit_summary_rows = get_unit_code_summary_list()
        if unit_summary_rows:
            total_links_count = sum(r[1] for r in unit_summary_rows)
            st.markdown(f"**📌 현재까지 총 `{len(unit_summary_rows)}개` 단원코드, `{total_links_count}개` 문항의 해설 링크가 등록되어 있습니다.**")
            
            with st.container(border=True):
                badges_html = ""
                for u_code, cnt in unit_summary_rows:
                    badges_html += (
                        f'<span style="display:inline-block; background-color:var(--secondary-background-color); '
                        f'border:1px solid rgba(128,128,128,0.4); border-radius:6px; padding:4px 10px; '
                        f'margin:4px; font-size:13px; font-family:monospace;">'
                        f'<b>{u_code}</b> : <span style="color:#0284C7; font-weight:bold;">{cnt}문항</span>'
                        f'</span>'
                    )
                st.markdown(badges_html, unsafe_allow_html=True)
        else:
            st.info("아직 등록된 해설 링크가 없습니다.")

        st.divider()
        st.markdown("#### 🔍 특정 단원코드 / 문제번호 상세 검색 및 수정·삭제")
        search_link_filter = st.text_input("검색어 입력 (단원코드 또는 문제번호)", placeholder="예: B1353 또는 B1353015", key="search_link_filter_box").strip().upper()
        
        if search_link_filter:
            searched_links, total_searched = get_all_problem_links_searched(search_link_filter)
            if searched_links:
                st.markdown(f"**🔎 검색 결과: `{search_link_filter}` 일치 항목 {total_searched}건**")
                for link_id, f_code, v_url, u_code in searched_links:
                    with st.container(border=True):
                        col_lk1, col_lk2, col_lk3 = st.columns([2, 4, 1])
                        with col_lk1:
                            st.markdown(f"**`{f_code}`**")
                        with col_lk2:
                            st.markdown(f"<a href='{v_url}' target='_blank' style='font-size:13px; color:#0284C7; text-decoration:none;'>🔗 {v_url}</a>", unsafe_allow_html=True)
                        with col_lk3:
                            if st.button("🗑️ 삭제", key=f"del_plink_{link_id}"):
                                delete_problem_link(link_id)
                                st.success("삭제되었습니다!")
                                st.rerun()
            else:
                st.warning(f"'{search_link_filter}'에 해당하는 등록된 링크가 없습니다.")
        else:
            st.caption("💡 전체 링크 목록을 한 번에 띄우지 않아 로딩 속도가 매우 빠릅니다. 확인이나 삭제가 필요한 단원코드만 입력해 주세요!")

    with t_cfg_stats:
        st.markdown("#### 📈 실시간 학습 참여 및 방문 통계")
        
        col_st_title, col_st_btn = st.columns([3.5, 1.5])
        with col_st_title:
            st.caption("학생들의 접속 로그 및 일일 과제·루틴 성취도를 한눈에 모니터링합니다.")
        with col_st_btn:
            if st.button("🔄 통계 새로고침", key="btn_refresh_stats", use_container_width=True):
                st.cache_data.clear()
                st.toast("최신 통계를 반영했습니다!", icon="📊")
                st.rerun()

        today_active_cnt, total_visits, s_summary, daily_logs = get_visitor_stats()

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("👤 전체 등록 학생 수", f"{len(student_list)}명")
        with col_m2:
            st.metric("🔥 오늘 학습실 방문 학생", f"{today_active_cnt}명")
        with col_m3:
            st.metric("📊 누적 총 방문 횟수", f"{total_visits}회")

        st.markdown("---")
        
        if student_list:
            st.markdown("##### 🎯 학생별 최근 접속 및 주간 루틴 달성률 요약")
            visit_map = {r[0]: (r[1], r[2]) for r in s_summary}
            
            for s_name in student_list:
                last_time, v_count = visit_map.get(s_name, ("방문 기록 없음", 0))
                r_rate, _, _ = get_routine_completion_rate(s_name, days_limit=7)
                streak_days = get_student_routine_streak(s_name)
                
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1.8, 2.5, 1.5, 1.5])
                    with c1:
                        st.markdown(f"**👤 {s_name}**")
                    with c2:
                        st.caption(f"최근 방문: `{last_time}` (총 {v_count}회)")
                    with c3:
                        st.markdown(f"루틴(7일): <b style='color:#F59E0B;'>{r_rate}%</b>", unsafe_allow_html=True)
                    with c4:
                        st.markdown(f"🔥 연속: <b>{streak_days}일</b>", unsafe_allow_html=True)

        st.markdown("---")
        if daily_logs:
            st.markdown("##### 📅 최근 7일 일자별 방문 통계")
            df_daily = pd.DataFrame(daily_logs, columns=["날짜", "방문 학생 수 (명)", "총 페이지 조회수 (회)"])
            st.dataframe(df_daily, use_container_width=True, hide_index=True)
        else:
            st.info("아직 기록된 일자별 방문 로그가 없습니다.")

    with t_cfg_tests:
        st.markdown("#### 📋 학생 온라인 테스트 제출 현황 및 답안 검사")
        
        col_ts_title, col_ts_btn = st.columns([3.5, 1.5])
        with col_ts_title:
            st.caption("학생들이 온라인으로 제출한 테스트 결과 및 정오답 여부를 확인·관리합니다.")
        with col_ts_btn:
            if st.button("🔄 제출 현황 새로고침", key="btn_refresh_tests", use_container_width=True):
                st.cache_data.clear()
                st.toast("제출 현황을 업데이트했습니다!", icon="✅")
                st.rerun()

        sub_summaries = get_cached_test_submission_summaries()
        all_sessions = get_cached_all_sessions()

        sub_view_mode = st.radio(
            "조회 방식 선택",
            ["📊 제출 완료된 테스트 채점 결과", "🗂️ 전체 출제된 온라인 테스트 세션 관리"],
            horizontal=True
        )

        if sub_view_mode == "📊 제출 완료된 테스트 채점 결과":
            if sub_summaries:
                filter_stu = st.selectbox("학생 필터", ["전체 학생"] + student_list, key="filter_test_sub_stu")
                filtered_subs = sub_summaries if filter_stu == "전체 학생" else [r for r in sub_summaries if r[0] == filter_stu]

                for s_name, t_title, sub_at, total_cnt, correct_cnt in filtered_subs:
                    correct_cnt = int(correct_cnt or 0)
                    total_cnt = int(total_cnt or 0)
                    wrong_cnt = total_cnt - correct_cnt
                    score_pct = int((correct_cnt / total_cnt) * 100) if total_cnt > 0 else 0

                    with st.expander(
                        f"👤 {s_name} | 📝 {t_title}  —  점수: {correct_cnt}/{total_cnt} ({score_pct}%)  [제출: {sub_at}]",
                        expanded=False
                    ):
                        conn_sub, _ = get_db_connection()
                        c_sub = conn_sub.cursor()
                        q(c_sub, """
                            SELECT problem_id, student_answer, is_checked 
                            FROM student_test_submissions 
                            WHERE student_name = ? AND test_title = ? 
                            ORDER BY id ASC
                        """, (s_name, t_title))
                        detail_rows = c_sub.fetchall()

                        if detail_rows:
                            df_details = pd.DataFrame(detail_rows, columns=["문항 코드", "학생 제출 답안", "정답 여부"])
                            df_details["정답 여부"] = df_details["정답 여부"].apply(lambda x: "⭕ 정답 (O)" if x == 1 else "❌ 오답 (X)")
                            st.dataframe(df_details, use_container_width=True, hide_index=True)

                            wrong_codes_only = [r[0] for r in detail_rows if r[2] != 1]
                            if wrong_codes_only:
                                st.markdown(f"<div style='color:#EF4444; font-size:13px; font-weight:bold; margin-top:6px;'>❌ 틀린 문항 코드 ({len(wrong_codes_only)}개): {', '.join(wrong_codes_only)}</div>", unsafe_allow_html=True)

                        if st.button("🗑️ 이 제출 기록 삭제", key=f"del_sub_rec_{s_name}_{t_title}_{sub_at}"):
                            q(c_sub, "DELETE FROM student_test_submissions WHERE student_name = ? AND test_title = ?", (s_name, t_title))
                            q(c_sub, "UPDATE online_test_sessions SET is_completed = 0 WHERE student_name = ? AND test_title = ?", (s_name, t_title))
                            conn_sub.commit()
                            st.cache_data.clear()
                            st.success("제출 기록이 삭제되고 미제출 상태로 복원되었습니다!")
                            st.rerun()
            else:
                st.info("아직 제출 완료된 온라인 테스트 기록이 없습니다.")

        else:
            if all_sessions:
                filter_sess_stu = st.selectbox("학생 선택", ["전체 학생"] + student_list, key="filter_all_sess_stu")
                filtered_sessions = all_sessions if filter_sess_stu == "전체 학생" else [s for s in all_sessions if s[1] == filter_sess_stu]

                for sess_id, s_name, t_title, c_at, is_comp in filtered_sessions:
                    badge_txt = "✅ 제출 완료" if is_comp == 1 else "🆕 미제출"
                    with st.container(border=True):
                        c_s1, c_s2 = st.columns([4.5, 1.5])
                        with c_s1:
                            st.markdown(f"**[{badge_txt}] 👤 {s_name} — {t_title}**")
                            st.caption(f"출제 일시: {c_at} (세션 ID: {sess_id})")
                        with c_s2:
                            if st.button("🗑️ 세션 삭제", key=f"del_sess_admin_{sess_id}", use_container_width=True):
                                conn_del, _ = get_db_connection()
                                c_del = conn_del.cursor()
                                q(c_del, "DELETE FROM online_test_items WHERE session_id = ?", (sess_id,))
                                q(c_del, "DELETE FROM online_test_sessions WHERE id = ?", (sess_id,))
                                conn_del.commit()
                                st.cache_data.clear()
                                st.success("테스트 세션이 삭제되었습니다!")
                                st.rerun()
            else:
                st.info("등록된 온라인 테스트 세션이 없습니다.")

    with t_cfg_schedule:
        st.subheader("🗓️ 학생별 테스트 일정 달력 · 주간 관리")
        st.caption("학생들의 주간·월간 테스트 일정을 한눈에 확인하고, 일괄 등록 및 상태(예정/완료/재시험)를 관리합니다.")

        import calendar as py_calendar

        today_kst = get_korean_today() if "get_korean_today" in globals() else datetime.now().date()
        all_students = get_students()

        # 1. 테스트 일정 등록 / 일괄 배정 폼
        with st.expander("➕ 새 테스트 일정 등록 / 여러 학생·날짜 일괄 배정", expanded=True):
            with st.form("teacher_add_test_schedule_form", clear_on_submit=True):
                c1, c2 = st.columns([2, 1])
                with c1:
                    ts_title = st.text_input("테스트 제목 *", placeholder="예: 11월 4주차 주간평가 / 수1 지수로그 단원평가")
                with c2:
                    ts_type = st.selectbox("테스트 구분", ["주간 테스트", "정규 테스트", "단원평가", "재시험", "모의고사"])

                ts_scope = st.text_input("출제 범위 (선택)", placeholder="예: 쎈 수학1 p.12 ~ p.35 / 오답 유사문항")

                c3, c4 = st.columns(2)
                with c3:
                    apply_all = st.checkbox("전체 학생(ALL) 공통 일정으로 등록", value=False)
                    selected_targets = st.multiselect(
                        "대상 학생 선택 (복수 선택 가능)",
                        options=all_students,
                        default=[],
                        help="위 '전체 학생(ALL)' 체크 시 개별 선택을 무시하고 전체 공통 일정으로 등록됩니다.",
                    )
                with c4:
                    base_date = st.date_input("기본 테스트 날짜 *", value=today_kst)
                    extra_dates_str = st.text_input(
                        "추가 반복 날짜 (선택, 쉼표 구분 YYYY-MM-DD)",
                        placeholder="예: 2026-12-02, 2026-12-09",
                    )

                c5, c6 = st.columns([1, 2])
                with c5:
                    ts_status = st.selectbox(
                        "초기 상태",
                        options=["scheduled", "completed", "retest"],
                        format_func=get_test_status_label,
                    )
                with c6:
                    ts_memo = st.text_input("선생님 메모 / 준비물 안내 (선택)", placeholder="예: 오답노트 지참, 통과 기준 80점")

                submitted_ts = st.form_submit_button("✅ 테스트 일정 등록하기", type="primary", use_container_width=True)
                if submitted_ts:
                    if not ts_title.strip():
                        st.error("테스트 제목을 입력해 주세요.")
                    else:
                        target_list = ["ALL"] if apply_all else selected_targets
                        if not target_list:
                            st.error("대상 학생을 선택하거나 '전체 학생(ALL)'을 체크해 주세요.")
                        else:
                            date_list = [base_date.strftime("%Y-%m-%d")]
                            invalid_dates = []
                            if extra_dates_str.strip():
                                for raw_d in extra_dates_str.split(","):
                                    s_d = raw_d.strip()
                                    if not s_d:
                                        continue
                                    try:
                                        datetime.strptime(s_d, "%Y-%m-%d")
                                        date_list.append(s_d)
                                    except ValueError:
                                        invalid_dates.append(s_d)
                            if invalid_dates:
                                st.error(f"날짜 형식이 올바르지 않습니다 (YYYY-MM-DD 필요): {', '.join(invalid_dates)}")
                            else:
                                cnt = add_test_schedule_entries(
                                    targets=target_list,
                                    test_dates=date_list,
                                    title=ts_title,
                                    scope=ts_scope,
                                    test_type=ts_type,
                                    status=ts_status,
                                    memo=ts_memo,
                                )
                                st.success(f"총 {cnt}건의 테스트 일정이 등록되었습니다.")
                                st.rerun()

        st.markdown("---")

        # 2. 필터 및 보기 방식 (월간 캘린더 / 주간 일정표 / 목록 관리)
        f1, f2, f3 = st.columns([1.4, 1.4, 1.2])
        with f1:
            t_view_mode = st.radio(
                "조회 보기",
                ["📅 월간 캘린더", "📆 주간 일정표", "📋 전체 목록·수정"],
                horizontal=True,
                key="t_ts_view_mode",
            )
        with f2:
            stu_filter_opts = ["전체 학생 보기", "전체 공통(ALL)만"] + all_students
            t_stu_filter = st.selectbox("학생 필터", stu_filter_opts, key="t_ts_stu_filter")
        with f3:
            t_status_filter = st.selectbox(
                "상태 필터",
                ["전체 상태", "scheduled", "completed", "retest"],
                format_func=lambda x: "전체 상태" if x == "전체 상태" else get_test_status_label(x),
                key="t_ts_status_filter",
            )

        def _filter_schedule_df(df: pd.DataFrame) -> pd.DataFrame:
            if df.empty:
                return df
            out = df.copy()
            if t_stu_filter == "전체 공통(ALL)만":
                out = out[out["student_name"] == "ALL"]
            elif t_stu_filter != "전체 학생 보기":
                out = out[(out["student_name"] == t_stu_filter) | (out["student_name"] == "ALL")]
            if t_status_filter != "전체 상태":
                out = out[out["status"] == t_status_filter]
            return out

        # --- 보기 1: 월간 캘린더 ---
        if t_view_mode == "📅 월간 캘린더":
            if "t_cal_year" not in st.session_state:
                st.session_state.t_cal_year = today_kst.year
            if "t_cal_month" not in st.session_state:
                st.session_state.t_cal_month = today_kst.month
            if "t_selected_date" not in st.session_state:
                st.session_state.t_selected_date = today_kst.strftime("%Y-%m-%d")

            nav1, nav2, nav3 = st.columns([1, 2, 1])
            with nav1:
                if st.button("◀ 이전 달", key="t_cal_prev", use_container_width=True):
                    if st.session_state.t_cal_month == 1:
                        st.session_state.t_cal_year -= 1
                        st.session_state.t_cal_month = 12
                    else:
                        st.session_state.t_cal_month -= 1
                    st.rerun()
            with nav2:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; font-size:1.1rem; padding-top:6px;'>"
                    f"{st.session_state.t_cal_year}년 {st.session_state.t_cal_month}월 테스트 캘린더</div>",
                    unsafe_allow_html=True,
                )
            with nav3:
                if st.button("다음 달 ▶", key="t_cal_next", use_container_width=True):
                    if st.session_state.t_cal_month == 12:
                        st.session_state.t_cal_year += 1
                        st.session_state.t_cal_month = 1
                    else:
                        st.session_state.t_cal_month += 1
                    st.rerun()

            yr = st.session_state.t_cal_year
            mo = st.session_state.t_cal_month
            last_day = py_calendar.monthrange(yr, mo)[1]
            m_start = f"{yr:04d}-{mo:02d}-01"
            m_end = f"{yr:04d}-{mo:02d}-{last_day:02d}"

            raw_month_df = get_test_schedules_by_range(m_start, m_end)
            month_df = _filter_schedule_df(raw_month_df)

            date_map = {}
            if not month_df.empty:
                for _, r in month_df.iterrows():
                    date_map.setdefault(str(r["test_date"]), []).append(r)

            st.caption("범례: 🔵 예정 · 🟢 완료 · 🔴 재시험 (날짜를 클릭하면 하단에서 즉시 수정·삭제할 수 있습니다)")

            st.markdown(
                """
                <style>
                .t-cal-grid-wrap div[data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns: repeat(7, minmax(0, 1fr)) !important;
                    gap: 4px !important;
                }
                .t-cal-grid-wrap div[data-testid="stHorizontalBlock"] > div {
                    width: 100% !important;
                    min-width: 0 !important;
                }
                .t-cal-grid-wrap button {
                    padding: 4px 2px !important;
                    min-height: 46px !important;
                    font-size: 0.78rem !important;
                    line-height: 1.15 !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<div class="t-cal-grid-wrap">', unsafe_allow_html=True)
            dow_cols = st.columns(7)
            for i, d_lbl in enumerate(["월", "화", "수", "목", "금", "토", "일"]):
                with dow_cols[i]:
                    st.markdown(
                        f"<div style='text-align:center; font-size:0.8rem; font-weight:700; color:#64748B;'>{d_lbl}</div>",
                        unsafe_allow_html=True,
                    )

            for week in py_calendar.monthcalendar(yr, mo):
                cols = st.columns(7)
                for d_idx, day_num in enumerate(week):
                    with cols[d_idx]:
                        if day_num == 0:
                            st.markdown("<div style='height:46px;'></div>", unsafe_allow_html=True)
                        else:
                            d_str = f"{yr:04d}-{mo:02d}-{day_num:02d}"
                            items = date_map.get(d_str, [])
                            badge = ""
                            if items:
                                sts = [str(x["status"]) for x in items]
                                if "retest" in sts:
                                    badge = f"\n🔴{len(items)}"
                                elif "scheduled" in sts:
                                    badge = f"\n🔵{len(items)}"
                                else:
                                    badge = f"\n🟢{len(items)}"
                            is_sel = (st.session_state.t_selected_date == d_str)
                            lbl = f"{'[' if is_sel else ''}{day_num}{']' if is_sel else ''}{badge}"
                            if st.button(
                                lbl,
                                key=f"t_cal_btn_{yr}_{mo}_{day_num}",
                                use_container_width=True,
                                type="primary" if is_sel else "secondary",
                            ):
                                st.session_state.t_selected_date = d_str
                                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            sel_d_str = st.session_state.t_selected_date
            st.markdown("---")
            st.markdown(f"### 📌 {sel_d_str} 등록된 테스트 일정 관리")
            day_list = date_map.get(sel_d_str, [])
            if not day_list:
                st.info("선택한 날짜에 등록된 테스트 일정이 없습니다.")
            else:
                for item in day_list:
                    sid = int(item["id"])
                    who = "🌐 전체 학생(ALL)" if item["student_name"] == "ALL" else f"👤 {item['student_name']}"
                    st_lbl = get_test_status_label(item["status"])
                    with st.expander(f"{who} · [{st_lbl}] {item['title']} ({item['test_type']})", expanded=True):
                        with st.form(f"edit_ts_day_{sid}"):
                            ec1, ec2, ec3 = st.columns([1.2, 1.5, 1])
                            with ec1:
                                new_d = st.text_input("날짜 (YYYY-MM-DD)", value=str(item["test_date"]))
                            with ec2:
                                new_t = st.text_input("제목", value=str(item["title"]))
                            with ec3:
                                status_opts = ["scheduled", "completed", "retest"]
                                cur_idx = status_opts.index(item["status"]) if item["status"] in status_opts else 0
                                new_st = st.selectbox("상태", status_opts, index=cur_idx, format_func=get_test_status_label)

                            ec4, ec5 = st.columns([1, 2])
                            with ec4:
                                type_opts = ["주간 테스트", "정규 테스트", "단원평가", "재시험", "모의고사"]
                                t_idx = type_opts.index(item["test_type"]) if item["test_type"] in type_opts else 0
                                new_tp = st.selectbox("구분", type_opts, index=t_idx)
                            with ec5:
                                new_sc = st.text_input("출제 범위", value=str(item["scope"] or ""))

                            new_mm = st.text_input("메모", value=str(item["memo"] or ""))

                            b1, b2 = st.columns([3, 1])
                            with b1:
                                if st.form_submit_button("💾 수정 저장", type="primary", use_container_width=True):
                                    update_test_schedule_item(sid, new_d, new_t, new_sc, new_tp, new_st, new_mm)
                                    st.success("수정되었습니다.")
                                    st.rerun()
                            with b2:
                                if st.form_submit_button("🗑️ 삭제", use_container_width=True):
                                    delete_test_schedule_item(sid)
                                    st.warning("삭제되었습니다.")
                                    st.rerun()

        # --- 보기 2: 주간 일정표 ---
        elif t_view_mode == "📆 주간 일정표":
            if "t_week_offset" not in st.session_state:
                st.session_state.t_week_offset = 0

            wnav1, wnav2, wnav3 = st.columns([1, 2, 1])
            with wnav1:
                if st.button("◀ 이전 주", key="t_wk_prev", use_container_width=True):
                    st.session_state.t_week_offset -= 1
                    st.rerun()
            with wnav2:
                if st.button("이번 주 기준", key="t_wk_today", use_container_width=True):
                    st.session_state.t_week_offset = 0
                    st.rerun()
            with wnav3:
                if st.button("다음 주 ▶", key="t_wk_next", use_container_width=True):
                    st.session_state.t_week_offset += 1
                    st.rerun()

            base_mon = today_kst - timedelta(days=today_kst.weekday()) + timedelta(weeks=st.session_state.t_week_offset)
            base_sun = base_mon + timedelta(days=6)
            st.info(f"📆 선택 주간: **{_ts_week_range_str(base_mon)}**")

            wk_raw = get_test_schedules_by_range(base_mon.strftime("%Y-%m-%d"), base_sun.strftime("%Y-%m-%d"))
            wk_df = _filter_schedule_df(wk_raw)

            for offset in range(7):
                d_cur = base_mon + timedelta(days=offset)
                d_str = d_cur.strftime("%Y-%m-%d")
                day_rows = wk_df[wk_df["test_date"] == d_str] if not wk_df.empty else pd.DataFrame()
                is_today_mark = " (오늘)" if d_cur == today_kst else ""
                with st.container(border=True):
                    st.markdown(f"**{d_cur.strftime('%m/%d')} ({_ts_weekday_short_kr(d_cur)}){is_today_mark}** — {len(day_rows)}건")
                    if day_rows.empty:
                        st.caption("등록된 일정 없음")
                    else:
                        for _, r in day_rows.iterrows():
                            who = "🌐 전체(ALL)" if r["student_name"] == "ALL" else f"👤 {r['student_name']}"
                            st_lbl = get_test_status_label(r["status"])
                            scope_txt = f" | 범위: {r['scope']}" if r["scope"] else ""
                            st.write(f"- **[{st_lbl}]** {who} · **{r['title']}** (`{r['test_type']}`){scope_txt}")

        # --- 보기 3: 전체 목록·수정 (최근 -30일 ~ +90일 범위) ---
        else:
            r_start = (today_kst - timedelta(days=30)).strftime("%Y-%m-%d")
            r_end = (today_kst + timedelta(days=90)).strftime("%Y-%m-%d")
            all_raw = get_test_schedules_by_range(r_start, r_end)
            list_df = _filter_schedule_df(all_raw)
            if list_df.empty:
                st.info("조회 기간(최근 30일 ~ 향후 90일) 내 등록된 테스트 일정이 없습니다.")
            else:
                disp = list_df[["id", "test_date", "student_name", "test_type", "title", "scope", "status", "memo"]].copy()
                disp["status"] = disp["status"].apply(get_test_status_label)
                disp.columns = ["ID", "날짜", "대상 학생", "구분", "테스트 제목", "출제 범위", "상태", "메모"]
                st.dataframe(disp, use_container_width=True, hide_index=True)

                del_id = st.number_input("빠른 삭제할 일정 ID 입력", min_value=0, step=1, value=0, key="t_ts_quick_del_id")
                if st.button("🗑️ 입력한 ID 일정 삭제", key="t_ts_quick_del_btn"):
                    if del_id > 0:
                        delete_test_schedule_item(int(del_id))
                        st.success(f"ID {del_id} 일정이 삭제되었습니다.")
                        st.rerun()

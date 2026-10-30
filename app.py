import streamlit as st
import sqlite3
from datetime import date
import re

# 페이지 기본 설정
st.set_page_config(page_title="MathPro 학생 맞춤 학습 로드맵", page_icon="📐", layout="centered")

# 한국어 요일 변환 함수
def get_weekday_kr(date_str):
    d = date.fromisoformat(date_str)
    weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    return weekdays[d.weekday()]

# 1. 데이터베이스 초기화 (해설 영상 URL 컬럼 포함)
def init_db():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    
    c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY)')
    
    # 과목 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # 단원 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    
    # 세부 유형 테이블 (해설 영상 URL video_url 추가)
    c.execute('''
        CREATE TABLE IF NOT EXISTS chapter_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            video_url TEXT DEFAULT ''
        )
    ''')
    
    # 기존 DB에 video_url 컬럼이 없을 경우를 대비한 안전 장치
    try:
        c.execute("ALTER TABLE chapter_types ADD COLUMN video_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    
    # 학생별 마일스톤
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
    
    # 학생 오답/질문 저장 테이블 (단원코드 + 저장된 번호 집합 문자열)
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_wrong_entries (
            student_name TEXT,
            unit_code TEXT,
            numbers_text TEXT,
            PRIMARY KEY (student_name, unit_code)
        )
    ''')
    
    # 초기 기본 과목 데이터
    c.execute("SELECT COUNT(*) FROM subjects")
    if c.fetchone()[0] == 0:
        default_subjects = ["수학(상)", "수학(하)", "수학Ⅰ", "수학Ⅱ", "미적분", "확률과 통계"]
        for sub in default_subjects:
            try:
                c.execute("INSERT INTO subjects (name) VALUES (?)", (sub,))
            except sqlite3.IntegrityError:
                pass
                
    # 초기 샘플 데이터
    c.execute("SELECT COUNT(*) FROM chapters")
    if c.fetchone()[0] == 0:
        default_data = [
            ("수학(상)", "01. 다항식의 연산과 인수분해", [("유형 01. 다항식의 연산", ""), ("유형 02. 나머지정리와 인수분해", "")]),
            ("수학(상)", "02. 복소수와 이차방정식", [("유형 01. 복소수의 연산", ""), ("유형 02. 이차방정식의 판별식과 근과 계수의 관계", "")]),
            ("수학(상)", "03. 이차함수의 그래프와 활용", [("유형 01. 이차함수의 그래프와 최대·최소", ""), ("유형 02. 이차함수 활용 문제", "")])
        ]
        for sub, ch_name, types in default_data:
            c.execute("INSERT INTO chapters (subject, name) VALUES (?, ?)", (sub, ch_name))
            ch_id = c.lastrowid
            for t_name, t_url in types:
                c.execute("INSERT INTO chapter_types (chapter_id, name, video_url) VALUES (?, ?, ?)", (ch_id, t_name, t_url))
            
    c.execute("SELECT COUNT(*) FROM homework")
    if c.fetchone()[0] == 0:
        today_str = str(date.today())
        default_hws = [
            (today_str, "쎈 수학(상) p.45~48 대표유형 풀이"),
            (today_str, "주간 오답노트 재시험 통과")
        ]
        for d, t in default_hws:
            c.execute("INSERT INTO homework (hw_date, title) VALUES (?, ?)", (d, t))
            
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

def add_student(name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO students (name) VALUES (?)", (name,))
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
    c.execute("DELETE FROM student_wrong_entries WHERE student_name = ?", (name,))
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
    c.execute("SELECT id, subject, name FROM chapters ORDER BY subject, name")
    rows = c.fetchall()
    conn.close()
    return rows

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

def get_student_milestones(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    # milestones에 해당하는 video_url도 함께 가져오기 위해 chapter_types와 조인하거나 매칭
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

def get_homework_dates():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT hw_date FROM homework ORDER BY hw_date DESC")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_homework_by_date(hw_date):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, title FROM homework WHERE hw_date = ?", (hw_date,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_homework():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, hw_date, title FROM homework ORDER BY hw_date DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def add_homework(hw_date, title):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("INSERT INTO homework (hw_date, title) VALUES (?, ?)", (hw_date, title))
    conn.commit()
    conn.close()

def bulk_insert_homework(hw_date, text_data):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    
    lines = text_data.strip().split('\n')
    added_count = 0
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        title = line_str.lstrip('-•* ').strip()
        if title:
            c.execute("INSERT INTO homework (hw_date, title) VALUES (?, ?)", (hw_date, title))
            added_count += 1
            
    conn.commit()
    conn.close()
    return added_count

def delete_homework(hw_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM homework WHERE id = ?", (hw_id,))
    c.execute("DELETE FROM homework_progress WHERE homework_id = ?", (hw_id,))
    conn.commit()
    conn.close()

def get_milestone_progress(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT milestone_id, is_checked FROM milestone_progress WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}

def get_homework_progress(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT homework_id, is_checked FROM homework_progress WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}

def save_progress(student_name, m_checked, h_checked):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    for m_id, val in m_checked.items():
        c.execute('''
            INSERT INTO milestone_progress (student_name, milestone_id, is_checked)
            VALUES (?, ?, ?)
            ON CONFLICT(student_name, milestone_id) DO UPDATE SET is_checked = ?
        ''', (student_name, m_id, int(val), int(val)))
    for h_id, val in h_checked.items():
        c.execute('''
            INSERT INTO homework_progress (student_name, homework_id, is_checked)
            VALUES (?, ?, ?)
            ON CONFLICT(student_name, homework_id) DO UPDATE SET is_checked = ?
        ''', (student_name, h_id, int(val), int(val)))
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
    c.execute('''
        INSERT INTO student_wrong_entries (student_name, unit_code, numbers_text)
        VALUES (?, ?, ?)
        ON CONFLICT(student_name, unit_code) DO UPDATE SET numbers_text = ?
    ''', (student_name, unit_code, numbers_text, numbers_text))
    conn.commit()
    conn.close()

def parse_numbers(text):
    if not text:
        return set()
    nums = re.findall(r'\d+', text)
    return set(int(n) for n in nums)

def format_numbers_list(num_set):
    if not num_set:
        return []
    sorted_nums = sorted(list(num_set))
    return [f"{n:03d}" for n in sorted_nums]

# --- 웹 UI 구성 ---
st.title("📐 MathPro 학생 맞춤 학습 로드맵")
st.caption("선생님과 함께하는 나의 고등 수학 학습 여정")
st.divider()

student_list = get_students()
query_params = st.query_params
url_student = query_params.get("student", None)

# 1. [학생 전용 모드]
if url_student and url_student in student_list:
    selected_student = url_student
    st.info(f"✨ **{selected_student}** 학생 전용 맞춤 페이지입니다.")
    
    milestones = get_student_milestones(selected_student)
    hw_dates = get_homework_dates()
    m_progress = get_milestone_progress(selected_student)
    h_progress = get_homework_progress(selected_student)
    all_hws_flat = get_all_homework()

    total_m = len(milestones)
    completed_m = sum(1 for m in milestones if m_progress.get(m[0], False))
    m_percent = int((completed_m / total_m) * 100) if total_m > 0 else 0

    total_h = len(all_hws_flat)
    completed_h = sum(1 for h in all_hws_flat if h_progress.get(h[0], False))
    h_percent = int((completed_h / total_h) * 100) if total_h > 0 else 0

    st.subheader(f"👋 {selected_student} 학생의 현재 학습 현황")
    
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.write(f"**🎯 진도 마일스톤 달성도: {m_percent}%** ({completed_m}/{total_m} 완료)")
        st.progress(m_percent / 100 if total_m > 0 else 0)
    with col_stat2:
        st.write(f"**📚 과제 달성도: {h_percent}%** ({completed_h}/{total_h} 완료)")
        st.progress(h_percent / 100 if total_h > 0 else 0)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["🚩 1. 맞춤 진도 마일스톤", "📚 2. 날짜별 과제함", "💬 3. 오답 및 질문 등록함"])

    with st.form("student_roadmap_form"):
        m_checked_results = {}
        h_checked_results = {}

        with tab1:
            st.markdown("### 📘 부여된 개념 단원 및 유형 마일스톤")
            st.info("💡 **안내:** 완료한 학습 항목의 체크박스에 체크하신 후, 하단의 **[내 학습 상태 저장하기]** 버튼을 꼭 눌러주세요!")
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
                            
                            # 체크박스와 해설 보기 버튼 레이아웃 분리
                            cols = st.columns([4, 1])
                            with cols[0]:
                                m_checked_results[m_id] = st.checkbox(f"{t_name}", value=default_val, key=f"s_milestone_{m_id}")
                            with cols[1]:
                                if v_url and v_url.strip() != "":
                                    st.markdown(
                                        f'<a href="{v_url}" target="_blank" style="display:inline-block; background-color:#03C75A; color:white; padding:4px 8px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; margin-top:4px;">🎥 해설보기</a>',
                                        unsafe_allow_html=True
                                    )
                                else:
                                    st.caption("영상 없음")
            else:
                st.info("아직 부여된 학습 마일스톤이 없습니다.")

        with tab2:
            st.markdown("### 📝 날짜별 과제함")
            st.info("💡 **안내:** 완료한 숙제 항목의 체크박스에 체크하신 후, 하단의 **[내 학습 상태 저장하기]** 버튼을 꼭 눌러주세요!")
            if hw_dates:
                selected_date = st.selectbox("확인할 과제 날짜를 선택하세요", hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
                st.markdown(f"#### 📌 [{selected_date} ({get_weekday_kr(selected_date)})] 부여된 숙제")
                target_hws = get_homework_by_date(selected_date)
                for h_id, title in target_hws:
                    default_val = h_progress.get(h_id, False)
                    h_checked_results[h_id] = st.checkbox(f"{title}", value=default_val, key=f"s_hw_{h_id}")
            else:
                st.info("등록된 날짜별 과제가 없습니다.")

        with tab3:
            st.markdown("### 💬 오답 및 질문 번호 관리함")
            st.info("💡 오늘 푼 교재의 **단원코드(예: A1351)**를 넣고, 새로 틀린 번호는 **[추가]**에, 맞았거나 잘못 넣은 번호는 **[삭제]**에 각각 적어주세요!\n\n*(작성 후 하단의 **[내 학습 상태 저장하기]** 버튼을 꼭 눌러주세요!)*")
            
            entered_unit_code = st.text_input("단원코드 입력", value="A1351").strip().upper()
            
            current_unit = entered_unit_code if entered_unit_code else "A1351"
            saved_text = get_student_wrong_entry(selected_student, current_unit)
            saved_nums = parse_numbers(saved_text)
            
            if saved_nums:
                formatted_saved = format_numbers_list(saved_nums)
                preview_str = ", ".join([f"{n}번" for n in formatted_saved])
                st.success(f"📋 **현재 저장된 오답 목록 (총 {len(saved_nums)}문제):** [{preview_str}]")
            else:
                st.info("📋 현재 저장된 오답 번호가 없습니다.")

            st.markdown("---")
            col_add, col_del = st.columns(2)
            with col_add:
                add_input_text = st.text_input("➕ 추가할 번호 입력 (예: 5, 12, 23)", placeholder="예: 5, 12")
            with col_del:
                del_input_text = st.text_input("➖ 삭제할 번호 입력 (예: 7, 10)", placeholder="예: 7")

        st.divider()
        submit_clicked = st.form_submit_button("내 학습 상태 저장하기", type="primary")
        if submit_clicked:
            save_progress(selected_student, m_checked_results, h_checked_results)
            if entered_unit_code:
                nums_to_add = parse_numbers(add_input_text)
                nums_to_del = parse_numbers(del_input_text)
                
                final_nums = (saved_nums | nums_to_add) - nums_to_del
                
                new_saved_text = ", ".join([str(n) for n in sorted(list(final_nums))])
                save_student_wrong_entry(selected_student, entered_unit_code, new_saved_text)
                
            st.success("학습 상태가 안전하게 저장되었습니다!")
            st.rerun()

# 2. [선생님 전용 관리 모드]
else:
    st.subheader("👥 학생 선택 및 관리 (선생님 전용 모드)")
    col_s1, col_s2, col_s3 = st.columns([2, 1, 1])

    with col_s1:
        if student_list:
            selected_student = st.selectbox("확인할 학생을 선택하세요", student_list)
        else:
            selected_student = None
            st.warning("등록된 학생이 없습니다. 아래에서 학생을 먼저 추가해 주세요!")

    with col_s2:
        with st.expander("➕ 학생 추가"):
            new_s_name = st.text_input("학생 이름 입력")
            if st.button("학생 등록"):
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
            with st.expander("🗑️ 학생 삭제"):
                st.write(f"**{selected_student}** 학생 삭제")
                with st.popover("학생 삭제 실행"):
                    st.warning(f"정말 **{selected_student}** 학생을 삭제하시겠습니까?")
                    if st.button("네, 삭제합니다", type="primary", key="pop_del_student"):
                        delete_student(selected_student)
                        st.success("삭제되었습니다!")
                        st.rerun()

    if student_list:
        with st.expander("🔗 [선생님 전용] 학생별 고유 링크(URL) 복사하기"):
            st.markdown("학생들에게 카카오톡으로 아래 링크를 보내주세요.")
            try:
                base_url = st.context.headers.get("Host", "")
                if base_url:
                    base_url = f"https://{base_url}"
                else:
                    base_url = "https://speakprooh-dev-mathpro-app-4byisa.streamlit.app"
            except:
                base_url = "https://speakprooh-dev-mathpro-app-4byisa.streamlit.app"

            for s in student_list:
                personal_link = f"{base_url}/?student={s}"
                st.text_input(f"📌 {s} 학생 고유 링크", value=personal_link, key=f"link_{s}")

    st.divider()

    st.markdown("### ⚙️ [선생님 전용] 커리큘럼 및 과제 통합 관리 설정")
    t_cfg1, t_cfg2, t_cfg3 = st.tabs(["📚 1. 커리큘럼 관리 및 진도", "📅 2. 날짜별 과제 관리", "🔍 3. 학생 오답노트 코드 취합"])

    with t_cfg1:
        subjects_data = get_subjects()
        subject_names = [s[1] for s in subjects_data]

        st.markdown("#### 📂 과목 / 단원 / 세부 유형 폴더형 통합 관리")

        with st.form("unified_sub_form"):
            col_u1, col_u2 = st.columns([3, 1])
            with col_u1:
                new_sub_input = st.text_input("새 과목 추가 (예: 수능 특강)")
            with col_u2:
                st.write("")
                st.write("")
                add_sub_submit = st.form_submit_button("과목 등록")
        if add_sub_submit:
            if new_sub_input.strip():
                if add_subject(new_sub_input.strip()):
                    st.success(f"'{new_sub_input.strip()}' 과목이 등록되었습니다!")
                    st.rerun()
                else:
                    st.warning("이미 존재하는 과목명입니다.")
            else:
                st.error("과목명을 입력하세요.")

        st.markdown("---")

        if subjects_data:
            for sub_id, sub_name in subjects_data:
                with st.expander(f"📚 [과목] {sub_name}", expanded=False):
                    col_h1, col_h2 = st.columns([1, 1])
                    with col_h1:
                        with st.popover("✏️ 과목명 수정"):
                            with st.form(f"edit_sub_{sub_id}"):
                                ed_sub = st.text_input("과목명 변경", value=sub_name, key=f"ed_sub_in_{sub_id}")
                                if st.form_submit_button("저장"):
                                    if ed_sub.strip():
                                        if update_subject(sub_id, sub_name, ed_sub.strip()):
                                            st.success("변경되었습니다!")
                                            st.rerun()
                                        else:
                                            st.warning("중복된 과목명입니다.")
                    with col_h2:
                        with st.popover("🗑️ 과목 삭제"):
                            st.warning(f"'{sub_name}' 과목을 삭제하시겠습니까?")
                            if st.button("삭제 확인", key=f"del_sub_confirm_{sub_id}", type="primary"):
                                delete_subject(sub_id)
                                st.success("삭제되었습니다.")
                                st.rerun()

                    st.markdown("---")

                    with st.form(f"add_ch_form_{sub_id}"):
                        col_ac1, col_ac2 = st.columns([3, 1])
                        with col_ac1:
                            new_ch_name = st.text_input(f"새 단원명 입력 (예: 01. 다항식의 연산)", key=f"ch_input_{sub_id}")
                        with col_ac2:
                            st.write("")
                            st.write("")
                            add_ch_submit = st.form_submit_button("단원 추가")
                    if add_ch_submit:
                        if new_ch_name.strip():
                            add_chapter(sub_name, new_ch_name.strip())
                            st.success("단원이 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error("단원명을 입력하세요.")

                    chapters_data = [ch for ch in get_chapters() if ch[1] == sub_name]
                    if chapters_data:
                        st.markdown("##### 📌 등록된 단원 및 세부 유형 목록")
                        for ch_id, ch_sub, ch_name in chapters_data:
                            with st.container(border=True):
                                c_box1, c_box2, c_box3 = st.columns([3, 1, 1])
                                with c_box1:
                                    st.write(f"▫️ **{ch_name}**")
                                with c_box2:
                                    with st.popover("✏️ 단원 수정"):
                                        with st.form(f"edit_ch_{ch_id}"):
                                            ed_ch_name = st.text_input("단원명 수정", value=ch_name, key=f"ed_ch_in_{ch_id}")
                                            if st.form_submit_button("저장"):
                                                if ed_ch_name.strip():
                                                    update_chapter(ch_id, sub_name, ed_ch_name.strip())
                                                    st.success("수정되었습니다!")
                                                    st.rerun()
                                                else:
                                                    st.error("단원명을 입력하세요.")
                                with c_box3:
                                    with st.popover("🗑️ 단원 삭제"):
                                        st.warning(f"'{ch_name}' 단원을 삭제하시겠습니까?")
                                        if st.button("삭제 확인", key=f"del_ch_confirm_{ch_id}", type="primary"):
                                            delete_chapter(ch_id)
                                            st.success("삭제되었습니다.")
                                            st.rerun()

                                with st.expander("📥 유형 일괄 등록 (복사 & 붙여넣기)"):
                                    st.caption("줄바꿈으로 구분하여 유형 이름들을 붙여넣으세요. (자동으로 '유형 01', '유형 02' 번호가 붙습니다)")
                                    with st.form(f"bulk_t_form_{ch_id}"):
                                        bulk_t_text = st.text_area("유형 목록 텍스트", key=f"bulk_t_area_{ch_id}", placeholder="- 다항식의 연산\n- 나머지정리")
                                        if st.form_submit_button("유형 일괄 등록 실행"):
                                            if bulk_t_text.strip():
                                                bulk_insert_types_for_chapter(ch_id, bulk_t_text)
                                                st.success("유형들이 성공적으로 일괄 등록되었습니다!")
                                                st.rerun()
                                            else:
                                                st.error("내용을 입력해주세요.")

                                types_list = get_chapter_types(ch_id)
                                with st.form(f"add_t_{ch_id}"):
                                    tc1, tc2 = st.columns([3, 1])
                                    with tc1:
                                        t_in = st.text_input("개별 유형 추가", key=f"t_in_{ch_id}", placeholder="예: 나머지정리 활용", label_visibility="collapsed")
                                    with tc2:
                                        if st.form_submit_button("유형 추가"):
                                            if t_in.strip():
                                                c_conn = sqlite3.connect("mathpro_roadmap.db")
                                                c_cur = c_conn.cursor()
                                                c_cur.execute("SELECT COUNT(*) FROM chapter_types WHERE chapter_id = ?", (ch_id,))
                                                cnt = c_cur.fetchone()[0] + 1
                                                c_conn.close()
                                                
                                                formatted_t = t_in.strip()
                                                if not formatted_t.startswith("유형"):
                                                    formatted_t = f"유형 {cnt:02d}. {formatted_t}"
                                                
                                                add_chapter_type(ch_id, formatted_t, "")
                                                st.rerun()
                                                
                                if types_list:
                                    with st.expander(f"속한 세부 유형 및 해설 영상 링크 관리 ({len(types_list)}개)"):
                                        for t_id, t_name, t_url in types_list:
                                            st.markdown(f"▪️ **{t_name}**")
                                            # 각 유형별 해설 영상 링크 입력 및 수정 폼
                                            with st.form(f"url_form_{t_id}"):
                                                u_col1, u_col2 = st.columns([3, 1])
                                                with u_col1:
                                                    new_url_input = st.text_input("네이버 카페 영상 URL", value=t_url, key=f"url_in_{t_id}", label_visibility="collapsed", placeholder="https://cafe.naver.com/...")
                                                with u_col2:
                                                    if st.form_submit_button("링크 저장"):
                                                        update_chapter_type_url(t_id, new_url_input.strip())
                                                        st.success("저장됨!")
                                                        st.rerun()
                                            
                                            # 삭제 버튼용 컬럼
                                            if st.button("유형 삭제", key=f"del_t_btn_{t_id}"):
                                                delete_chapter_type(t_id)
                                                st.rerun()
                                            st.divider()
                    else:
                        st.caption("등록된 단원이 없습니다.")
        else:
            st.info("등록된 과목이 없습니다. 위에서 과목을 추가해 주세요.")

        st.markdown("---")

        if selected_student:
            st.markdown(f"#### 🎯 [{selected_student}] 학생 맞춤 진도 계획 일괄 배정하기")
            st.info("과목별 폴더를 열어 **공부할 단원들을 체크한 뒤** 아래 버튼을 누르면 단원과 하위 유형이 학생에게 한 번에 배정됩니다!")
            
            all_chapters = get_chapters()
            subjects_data = get_subjects()
            
            if all_chapters and subjects_data:
                assigned_chapters = {m[2] for m in get_student_milestones(selected_student)}
                
                with st.form("assign_chapters_form"):
                    selected_ch_ids = []
                    for sub_id, sub_name in subjects_data:
                        sub_chapters = [ch for ch in all_chapters if ch[1] == sub_name]
                        if sub_chapters:
                            with st.expander(f"📚 [과목] {sub_name} (단원 {len(sub_chapters)}개)", expanded=False):
                                for ch_id, ch_sub, ch_name in sub_chapters:
                                    is_already_assigned = ch_name in assigned_chapters
                                    label_str = f"{ch_name} {' (이미 배정됨)' if is_already_assigned else ''}"
                                    if st.checkbox(label_str, key=f"assign_ch_chk_{ch_id}"):
                                            selected_ch_ids.append(ch_id)
                    
                    st.divider()
                    assign_submitted = st.form_submit_button("선택한 단원 및 유형을 학생에게 일괄 배정하기", type="primary")
                    if assign_submitted:
                        if selected_ch_ids:
                            cnt_added = assign_chapters_to_student(selected_student, selected_ch_ids)
                            st.success(f"총 {cnt_added}개의 마일스톤 유형이 {selected_student} 학생에게 성공적으로 배정되었습니다!")
                            st.rerun()
                        else:
                            st.warning("배정할 단원을 하나 이상 체크해주세요.")
            else:
                st.info("배정할 단원 데이터가 없습니다.")

    with t_cfg2:
        st.markdown("#### 📅 날짜별 과제 부여 및 관리")
        with st.form("add_hw_form"):
            hw_date_input = st.date_input("과제 수행(제출)일", value=date.today())
            hw_text_area = st.text_area("과제 내용 입력 (줄바꿈으로 여러 개 입력 가능)", placeholder="쎈 수학(상) p.45~48 대표유형 풀이\n주간 오답노트 재시험 통과")
            hw_submit = st.form_submit_button("과제 등록하기", type="primary")
            if hw_submit:
                if hw_text_area.strip():
                    date_str = str(hw_date_input)
                    added_c = bulk_insert_homework(date_str, hw_text_area)
                    st.success(f"총 {added_c}개의 과제가 {date_str} 자리에 등록되었습니다!")
                    st.rerun()
                else:
                    st.error("과제 내용을 입력해주세요.")

        st.markdown("---")
        st.markdown("##### 📋 등록된 과제 목록 및 삭제")
        all_hws = get_all_homework()
        if all_hws:
            for h_id, h_date, h_title in all_hws:
                col_h1, col_h2, col_h3 = st.columns([2, 5, 1])
                with col_h1:
                    st.write(f"📅 **{h_date}**")
                with col_h2:
                    st.write(f"📌 {h_title}")
                with col_h3:
                    if st.button("삭제", key=f"del_hw_{h_id}"):
                        delete_homework(h_id)
                        st.success("삭제되었습니다!")
                        st.rerun()
        else:
            st.info("등록된 과제가 없습니다.")

    with t_cfg3:
        st.markdown("#### 🔍 학생별 오답 및 질문 번호 코드 취합")
        st.info("학생들이 각 단원별로 입력한 오답/질문 번호들을 한눈에 모아서 확인하고 관리할 수 있습니다.")
        
        all_students = get_students()
        if all_students:
            chk_student = st.selectbox("조회할 학생 선택", all_students, key="chk_wrong_student")
            
            conn = sqlite3.connect("mathpro_roadmap.db")
            c = conn.cursor()
            c.execute("SELECT unit_code, numbers_text FROM student_wrong_entries WHERE student_name = ?", (chk_student,))
            wrong_rows = c.fetchall()
            conn.close()
            
            if wrong_rows:
                for u_code, nums_txt in wrong_rows:
                    with st.container(border=True):
                        st.markdown(f"##### 📖 단원코드: `{u_code}`")
                        parsed_s = parse_numbers(nums_txt)
                        formatted_s = format_numbers_list(parsed_s)
                        display_str = ", ".join([f"{n}번" for n in formatted_s]) if formatted_s else "없음"
                        st.write(f"**저장된 오답/질문 번호:** [{display_str}]")
            else:
                st.info(f"'{chk_student}' 학생이 등록한 오답/질문 내역이 없습니다.")
        else:
            st.info("등록된 학생이 없습니다.")

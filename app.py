import streamlit as st
import sqlite3
from datetime import date

# 페이지 기본 설정
st.set_page_config(page_title="MathPro 학생 맞춤 학습 로드맵", page_icon="📐", layout="centered")

# 한국어 요일 변환 함수
def get_weekday_kr(date_str):
    d = date.fromisoformat(date_str)
    weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    return weekdays[d.weekday()]

# 1. 데이터베이스 초기화
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
    
    # 세부 유형 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS chapter_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    
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
            ("수학(상)", "01. 다항식의 연산과 인수분해", ["유형 01. 다항식의 연산", "유형 02. 나머지정리와 인수분해"]),
            ("수학(상)", "02. 복소수와 이차방정식", ["유형 01. 복소수의 연산", "유형 02. 이차방정식의 판별식과 근과 계수의 관계"]),
            ("수학(상)", "03. 이차함수의 그래프와 활용", ["유형 01. 이차함수의 그래프와 최대·최소", "유형 02. 이차함수 활용 문제"])
        ]
        for sub, ch_name, types in default_data:
            c.execute("INSERT INTO chapters (subject, name) VALUES (?, ?)", (sub, ch_name))
            ch_id = c.lastrowid
            for t_name in types:
                c.execute("INSERT INTO chapter_types (chapter_id, name) VALUES (?, ?)", (ch_id, t_name))
            
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
    c.execute("SELECT id, name FROM chapter_types WHERE chapter_id = ?", (chapter_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def add_chapter_type(chapter_id, name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("INSERT INTO chapter_types (chapter_id, name) VALUES (?, ?)", (chapter_id, name))
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
            
            c.execute("INSERT INTO chapter_types (chapter_id, name) VALUES (?, ?)", (chapter_id, type_name))
            type_counter += 1
            
    conn.commit()
    conn.close()

def get_student_milestones(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, subject, chapter, type_name FROM milestones WHERE student_name = ?", (student_name,))
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

    # 진도 마일스톤 달성도 계산
    total_m = len(milestones)
    completed_m = sum(1 for m in milestones if m_progress.get(m[0], False))
    m_percent = int((completed_m / total_m) * 100) if total_m > 0 else 0

    # 과제 달성도 계산
    total_h = len(all_hws_flat)
    completed_h = sum(1 for h in all_hws_flat if h_progress.get(h[0], False))
    h_percent = int((completed_h / total_h) * 100) if total_h > 0 else 0

    st.subheader(f"👋 {selected_student} 학생의 현재 학습 현황")
    
    # 진도와 과제 달성도를 각각 독립된 프로그레스 바 영역으로 출력
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.write(f"**🎯 진도 마일스톤 달성도: {m_percent}%** ({completed_m}/{total_m} 완료)")
        st.progress(m_percent / 100 if total_m > 0 else 0)
    with col_stat2:
        st.write(f"**📚 과제 달성도: {h_percent}%** ({completed_h}/{total_h} 완료)")
        st.progress(h_percent / 100 if total_h > 0 else 0)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["🚩 1. 맞춤 진도 마일스톤", "📚 2. 날짜별 과제함", "💬 3. 코멘트 & 질문방"])

    with st.form("student_roadmap_form"):
        m_checked_results = {}
        h_checked_results = {}

        with tab1:
            st.markdown("### 📘 부여된 개념 단원 및 유형 마일스톤")
            if milestones:
                grouped_s_milestones = {}
                for m_id, sub, ch, t_name in milestones:
                    key = (sub, ch)
                    if key not in grouped_s_milestones:
                        grouped_s_milestones[key] = []
                    grouped_s_milestones[key].append((m_id, t_name))

                for (sub, ch), items in grouped_s_milestones.items():
                    done_cnt = sum(1 for m_id, _ in items if m_progress.get(m_id, False))
                    exp_label = f"[{sub}] {ch} (완료: {done_cnt}/{len(items)})"
                    
                    with st.expander(exp_label, expanded=False):
                        for m_id, t_name in items:
                            default_val = m_progress.get(m_id, False)
                            m_checked_results[m_id] = st.checkbox(t_name, value=default_val, key=f"s_milestone_{m_id}")
            else:
                st.info("아직 부여된 학습 마일스톤이 없습니다.")

        with tab2:
            st.markdown("### 📝 날짜별 과제함")
            if hw_dates:
                selected_date = st.selectbox("확인할 과제 날짜를 선택하세요", hw_dates, format_func=lambda x: f"{x} ({get_weekday_kr(x)})")
                st.markdown(f"#### 📌 [{selected_date} ({get_weekday_kr(selected_date)})] 부여된 숙제")
                target_hws = get_homework_by_date(selected_date)
                for h_id, title in target_hws:
                    default_val = h_progress.get(h_id, False)
                    h_checked_results[h_id] = st.checkbox(title, value=default_val, key=f"s_hw_{h_id}")
            else:
                st.info("등록된 날짜별 과제가 없습니다.")

        with tab3:
            st.markdown("### 💬 선생님의 1:1 맞춤 코멘트")
            st.info(f"**[{selected_student} 학생 맞춤 피드백]** 오늘도 꼼꼼하게 오답 정리하고 숙제 체크하기!")
            st.markdown("### ✏️ 오늘의 학습 다짐 / 질문하기")
            st.text_area("오늘 공부한 내용이나 궁금한 점을 적어보세요.")

        st.divider()
        if st.form_submit_button("내 체크상태 저장하기", type="primary"):
            save_progress(selected_student, m_checked_results, h_checked_results)
            st.success("학습 상태가 저장되었습니다!")
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
                if st.button("정말 삭제", type="primary"):
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
    t_cfg1, t_cfg2 = st.tabs(["📚 1. 커리큘럼 통합 관리 및 진도 배정", "📅 2. 날짜별 과제 관리"])

    with t_cfg1:
        subjects_data = get_subjects()
        subject_names = [s[1] for s in subjects_data]

        st.markdown("#### 📂 과목 / 단원 / 세부 유형 폴더형 통합 관리")

        # 새 과목 추가 영역
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

        # 과목별 접이식(Expander) 계층형 관리 화면
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
                        if st.button("🗑️ 과목 삭제", key=f"del_sub_{sub_id}"):
                            delete_subject(sub_id)
                            st.warning("과목이 삭제되었습니다.")
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
                                    if st.button("🗑️ 단원 삭제", key=f"del_ch_{ch_id}"):
                                        delete_chapter(ch_id)
                                        st.warning("단원이 삭제되었습니다.")
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
                                                    
                                                add_chapter_type(ch_id, formatted_t)
                                                st.rerun()
                                                
                                if types_list:
                                    with st.expander(f"속한 세부 유형 관리 ({len(types_list)}개)"):
                                        for t_id, t_name in types_list:
                                            tc1, tc2 = st.columns([4, 1])
                                            with tc1:
                                                st.write(f"▪️ {t_name}")
                                            with tc2:
                                                if st.button("유형 삭제", key=f"del_t_{t_id}"):
                                                    delete_chapter_type(t_id)
                                                    st.rerun()
                    else:
                        st.caption("등록된 단원이 없습니다.")
        else:
            st.info("등록된 과목이 없습니다. 위에서 과목을 추가해 주세요.")

        st.markdown("---")

        # 3. 학생별 진도 일괄 배정 영역
        if selected_student:
            st.markdown(f"#### 🎯 [{selected_student}] 학생 맞춤 진도 계획 일괄 배정하기")
            st.info("과목별 폴더를 열어 **공부할 단원들을 체크한 뒤** 아래 버튼을 누르면 단원과 하위 유형이 학생에게 한 번에 배정됩니다!")
            
            all_chapters = get_chapters()
            subjects_data = get_subjects()
            
            if all_chapters and subjects_data:
                assigned_chapters = {m[2] for m in get_student_milestones(selected_student)}
                
                selected_ch_ids = []
                for sub_id, sub_name in subjects_data:
                    sub_chapters = [ch for ch in all_chapters if ch[1] == sub_name]
                    if sub_chapters:
                        with st.expander(f"📚 [과목] {sub_name} (단원 {len(sub_chapters)}개)", expanded=False):
                            for ch_id, ch_sub, ch_name in sub_chapters:
                                is_already = ch_name in assigned_chapters
                                label = f"{ch_name}" + (" (이미 부여된 단원)" if is_already else "")
                                if st.checkbox(label, value=False, key=f"batch_chk_{ch_id}"):
                                    selected_ch_ids.append(ch_id)
                
                st.write("")
                if st.button("📥 선택한 단원들 일괄 부여하기", type="primary"):
                    if selected_ch_ids:
                        added_cnt = assign_chapters_to_student(selected_student, selected_ch_ids)
                        st.success(f"'{selected_student}' 학생에게 총 {added_cnt}개의 학습 항목이 성공적으로 배정되었습니다!")
                        st.rerun()
                    else:
                        st.warning("선택된 단원이 없습니다.")
            else:
                st.info("배정할 단원이 없습니다.")

            st.markdown("---")
            st.markdown(f"#### 📋 현재 [{selected_student}] 학생에게 부여된 학습 항목 목록")
            student_ms = get_student_milestones(selected_student)
            
            if student_ms:
                grouped_milestones = {}
                for m_id, sub, ch, t_name in student_ms:
                    key = (sub, ch)
                    if key not in grouped_milestones:
                        grouped_milestones[key] = []
                    grouped_milestones[key].append((m_id, t_name))

                for (sub, ch), items in grouped_milestones.items():
                    with st.expander(f"📁 [{sub}] {ch} (총 {len(items)}개 유형 부여됨)"):
                        for m_id, t_name in items:
                            col_m1, col_m2 = st.columns([4, 1])
                            with col_m1:
                                st.write(f"✔️ {t_name}")
                            with col_m2:
                                if st.button("부여 취소", key=f"del_ms_{m_id}"):
                                    delete_student_milestone(m_id)
                                    st.warning("제외되었습니다.")
                                    st.rerun()
            else:
                st.info("이 학생에게 부여된 학습 항목이 아직 없습니다.")
        else:
            st.warning("⚠️ 상단에서 진도를 계획할 **학생을 먼저 선택**해 주세요.")

    with t_cfg2:
        st.markdown("#### 📅 새로운 날짜별 과제 등록하기")
        with st.form("hw_form"):
            col_h1, col_h2, col_h3 = st.columns([1, 2, 1])
            with col_h1:
                reg_date = st.date_input("과제 날짜 선택", value=date.today())
            with col_h2:
                reg_title = st.text_input("과제 내용 입력 (예: 쎈 B단계 100~110번)")
            with col_h3:
                st.write("")
                st.write("")
                add_hw_btn = st.form_submit_button("과제 추가하기")

        if add_hw_btn:
            if reg_title.strip():
                add_homework(str(reg_date), reg_title.strip())
                st.success(f"[{reg_date}] 과제가 성공적으로 등록되었습니다!")
                st.rerun()
            else:
                st.error("과제 내용을 입력해주세요.")

        st.markdown("---")
        st.markdown("#### 📋 등록된 날짜별 과제 목록 (삭제 관리)")
        current_hws = get_all_homework()
        if current_hws:
            for h_id, hw_date, title in current_hws:
                weekday_str = get_weekday_kr(hw_date)
                c1, c2, c3 = st.columns([2, 3, 1])
                with c1:
                    st.write(f"**[{hw_date} ({weekday_str})]**")
                with c2:
                    st.write(title)
                with c3:
                    if st.button("삭제", key=f"del_hw_{h_id}"):
                        delete_homework(h_id)
                        st.warning("과제가 삭제되었습니다.")
                        st.rerun()
        else:
            st.info("등록된 과제가 없습니다.")

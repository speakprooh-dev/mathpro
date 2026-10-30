import streamlit as st
import sqlite3
from datetime import date

# 페이지 기본 설정
st.set_page_config(page_title="MathPro 학습 로드맵", page_icon="📐", layout="centered")

# 한국어 요일 변환 함수
def get_weekday_kr(date_str):
    d = date.fromisoformat(date_str)
    weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    return weekdays[d.weekday()]

# 1. 데이터베이스 초기화 (커리큘럼 풀 테이블 추가)
def init_db():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    
    c.execute('CREATE TABLE IF NOT EXISTS students (name TEXT PRIMARY KEY)')
    
    # 미리 등록해두는 전체 커리큘럼 풀 (과목, 단원, 유형)
    c.execute('''
        CREATE TABLE IF NOT EXISTS curriculum_pool (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            chapter TEXT NOT NULL,
            topic TEXT NOT NULL
        )
    ''')
    
    # 학생별로 부여된 맞춤 마일스톤
    c.execute('''
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            chapter TEXT NOT NULL,
            topic TEXT NOT NULL
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
    
    # 초기 커리큘럼 풀 샘플 데이터
    c.execute("SELECT COUNT(*) FROM curriculum_pool")
    if c.fetchone()[0] == 0:
        default_pool = [
            ("수학(상)", "01. 다항식", "다항식의 연산과 나머지정리"),
            ("수학(상)", "01. 다항식", "인수분해의 활용"),
            ("수학(상)", "02. 방정식과 부등식", "복소수와 이차방정식"),
            ("수학(상)", "02. 방정식과 부등식", "이차함수의 그래프와 최대·최소"),
            ("수학(상)", "03. 도형의 방정식", "평면좌표와 직선의 방정식"),
            ("수학(상)", "03. 도형의 방정식", "원의 방정식과 도형의 이동")
        ]
        for sub, ch, top in default_pool:
            c.execute("INSERT INTO curriculum_pool (subject, chapter, topic) VALUES (?, ?, ?)", (sub, ch, top))
            
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

# 커리큘럼 풀 관리
def get_curriculum_pool():
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, subject, chapter, topic FROM curriculum_pool ORDER BY subject, chapter")
    rows = c.fetchall()
    conn.close()
    return rows

def add_curriculum_pool(subject, chapter, topic):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("INSERT INTO curriculum_pool (subject, chapter, topic) VALUES (?, ?, ?)", (subject, chapter, topic))
    conn.commit()
    conn.close()

def delete_curriculum_pool(pool_id):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("DELETE FROM curriculum_pool WHERE id = ?", (pool_id,))
    conn.commit()
    conn.close()

# 학생별 맞춤 마일스톤 관리
def get_student_milestones(student_name):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("SELECT id, subject, chapter, topic FROM milestones WHERE student_name = ?", (student_name,))
    rows = c.fetchall()
    conn.close()
    return rows

def add_student_milestone(student_name, subject, chapter, topic):
    conn = sqlite3.connect("mathpro_roadmap.db")
    c = conn.cursor()
    c.execute("INSERT INTO milestones (student_name, subject, chapter, topic) VALUES (?, ?, ?, ?)", (student_name, subject, chapter, topic))
    conn.commit()
    conn.close()

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
    total_tasks = len(milestones) + len(all_hws_flat)
    completed_m = sum(1 for m_id, _, _, _, _ in milestones if m_progress.get(m_id, False))
    completed_h = sum(1 for h_id, _, _ in all_hws_flat if h_progress.get(h_id, False))
    total_completed = completed_m + completed_h
    progress_val = int((total_completed / total_tasks) * 100) if total_tasks > 0 else 0

    st.subheader(f"👋 {selected_student} 학생의 현재 학습 현황")
    st.write(f"**전체 커리큘럼 및 과제 달성도: {progress_val}%** ({total_completed}/{total_tasks} 완료)")
    st.progress(progress_val / 100 if total_tasks > 0 else 0)
    st.divider()

    tab1, tab2, tab3 = st.tabs(["🚩 1. 개념 완성 마일스톤", "📚 2. 날짜별 과제함", "💬 3. 코멘트 & 질문방"])

    with st.form("student_roadmap_form"):
        m_checked_results = {}
        h_checked_results = {}

        with tab1:
            st.markdown("### 📘 수학 핵심 개념 마일스톤")
            if milestones:
                for m_id, sub, ch, top in milestones:
                    label = f"[{sub}] {ch} - {top}"
                    default_val = m_progress.get(m_id, False)
                    m_checked_results[m_id] = st.checkbox(label, value=default_val, key=f"s_milestone_{m_id}")
            else:
                st.info("아직 부여된 마일스톤 항목이 없습니다.")

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

    # 고유 링크 복사 상자
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

    # 선생님 전용 관리 설정 영역
    st.markdown("### ⚙️ [선생님 전용] 커리큘럼 및 과제 통합 관리 설정")
    
    # 탭으로 과목/단원 관리와 과제 관리를 분리
    t_cfg1, t_cfg2 = st.tabs(["📚 1. 마스터 커리큘럼 및 학생별 마일스톤 부여", "📅 2. 날짜별 과제 관리"])

    with t_cfg1:
        st.markdown("#### 🛠️ 전체 커리큘럼 라이브러리(과목/단원/유형) 관리")
        with st.form("pool_form"):
            col_p1, col_p2, col_p3, col_p4 = st.columns([1.5, 2, 2, 1])
            with col_p1:
                p_sub = st.selectbox("과목", ["수학(상)", "수학(하)", "수학Ⅰ", "수학Ⅱ", "미적분", "확률과 통계"])
            with col_p2:
                p_ch = st.text_input("단원명 (예: 01. 다항식)")
            with col_p3:
                p_top = st.text_input("유형/소단원 (예: 나머지정리의 활용)")
            with col_p4:
                st.write("")
                st.write("")
                add_pool_btn = st.form_submit_button("라이브러리에 추가")
        
        if add_pool_btn:
            if p_ch.strip() and p_top.strip():
                add_curriculum_pool(p_sub, p_ch.strip(), p_top.strip())
                st.success("커리큘럼 라이브러리에 등록되었습니다!")
                st.rerun()
            else:
                st.error("단원명과 유형을 모두 입력해주세요.")

        st.markdown("---")
        st.markdown(f"#### 🎯 [{selected_student}] 학생 맞춤 마일스톤 부여 및 관리" if selected_student else "🎯 학생을 먼저 선택해주세요.")
        
        if selected_student:
            pool_items = get_curriculum_pool()
            if pool_items:
                st.markdown("원하는 항목을 선택하여 해당 학생의 로드맵에 추가하세요:")
                for p_id, p_sub, p_ch, p_top in pool_items:
                    col_i1, col_i2 = st.columns([4, 1])
                    with col_i1:
                        st.write(f"▪️ **[{p_sub}]** {p_ch} ➔ {p_top}")
                    with col_i2:
                        if st.button("학생에게 추가", key=f"assign_{p_id}"):
                            add_student_milestone(selected_student, p_sub, p_ch, p_top)
                            st.success(f"'{selected_student}' 학생에게 추가되었습니다!")
                            st.rerun()
            else:
                st.info("등록된 커리큘럼 라이브러리가 없습니다. 위에서 먼저 등록해 주세요.")

            st.markdown("---")
            st.markdown(f"#### 📋 현재 [{selected_student}] 학생에게 부여된 마일스톤 목록 (삭제 관리)")
            student_ms = get_student_milestones(selected_student)
            if student_ms:
                for m_id, sub, ch, top in student_ms:
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.write(f"✔️ **[{sub}]** {ch} - {top}")
                    with c2:
                        if st.button("부여 취소", key=f"del_ms_{m_id}"):
                            delete_student_milestone(m_id)
                            st.warning("제외되었습니다.")
                            st.rerun()
            else:
                st.info("이 학생에게 부여된 마일스톤이 아직 없습니다.")

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
            st.write("등록된 과제가 없습니다.")

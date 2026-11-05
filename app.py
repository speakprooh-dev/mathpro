import os
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="MathPro 고등 수학 학습 관리",
    page_icon="📐",
    layout="centered"
)

# ----------------------------------------------------
# 세션 상태 초기화 (관리자 모드 및 학생 선택용)
# ----------------------------------------------------
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

if "selected_student" not in st.session_state:
    st.session_state["selected_student"] = "노수연"  # 예시 학생

# ----------------------------------------------------
# 사이드바 구성 (메뉴 및 하단 숨김 관리자 로그인)
# ----------------------------------------------------
with st.sidebar:
    st.markdown("### 🧭 학습 메뉴")
    
    # 일반 학생용 / 기본 메뉴 영역
    st.markdown("---")
    
    # 🔒 사이드바 맨 하단에 숨겨둔 선생님 전용 공간 (비밀번호: 1234)
    with st.expander("🔒 선생님 전용 공간"):
        admin_password_input = st.text_input("비밀번호 입력", type="password", key="sidebar_admin_pw")
        if st.button("선생님 모드 전환"):
            if admin_password_input == "1234":
                st.session_state["is_admin"] = True
                st.success("선생님 모드로 진입했습니다!")
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
                
    if st.session_state["is_admin"]:
        if st.button("학생 모드로 돌아가기"):
            st.session_state["is_admin"] = False
            st.rerun()

# ----------------------------------------------------
# 메인 화면 구성
# ----------------------------------------------------

# 🖼️ 메인 화면 상단 로고 이미지 배치
if os.path.exists("mathpro_logo.png"):
    st.image("mathpro_logo.png", use_container_width=True)

# 💡 크기와 여백을 깔끔하게 잡은 메인 타이틀
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
st.markdown("---")

# 📁 온라인 학습실 (Google Drive) 바로가기 버튼 예시
student_drive = "https://drive.google.com"  # 실제 학생별 드라이브 주소 연동 함수 사용
if student_drive and student_drive.strip() != "":
    st.markdown(
        f'<a href="{student_drive}" target="_blank" style="display:block; background-color:#2563EB; color:#FFFFFF; padding:12px 16px; border-radius:8px; font-size:15px; text-decoration:none; font-weight:bold; text-align:center; margin-bottom:15px;">📁 온라인 학습실 (Google Drive) 바로가기 ➔</a>',
        unsafe_allow_html=True
    )

# 관리자 모드일 때 추가로 노출되는 기능들 예시
if st.session_state["is_admin"]:
    st.info("🛡️ 현재 [선생님 모드]로 접속 중입니다. 학생 관리 기능을 이용하실 수 있습니다.")
else:
    st.success(f"👋 환영합니다! 열심히 실력을 키워나가는 중입니다.")

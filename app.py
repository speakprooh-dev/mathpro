import streamlit.components.v1 as components

# 1) 현재 화면에 출력되는 단원별 코드 문자열을 순서대로 수집
# (예: ["A116_(027,101,121,161,186,187,188,195)", "116_(164,171,173,185,186,190,191,195)", ...])
all_unit_code_chunks = []

for u_code, probs_in_unit in grouped_units:  # 기존 단원별 카드 생성 루프
    nums_str = ",".join(str(p_num).zfill(3) for p_num in sorted_prob_nums)
    chunk_str = f"{u_code}_({nums_str})"
    all_unit_code_chunks.append(chunk_str)

# 2) 전체복사용 한 줄 문자열 생성
full_copy_text = ",".join(all_unit_code_chunks)

# 3) 화면 상단('현재 검색 조건 통계 요약' 아래)에 전체복사 버튼 + 코드박스 출력
if full_copy_text:
    st.markdown("#### 📋 단원별 오답 코드 전체복사")

    # 원클릭 클립보드 복사 HTML 버튼 (클릭 시 '✅ 복사 완료!' 표시)
    escaped_text = (
        full_copy_text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
    )
    copy_btn_html = f"""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
        <button id="copyAllBtn" onclick="
            navigator.clipboard.writeText('{escaped_text}').then(function() {{
                var btn = document.getElementById('copyAllBtn');
                btn.innerText = '✅ 전체 코드 복사 완료!';
                btn.style.backgroundColor = '#2B8A3E';
                setTimeout(function() {{
                    btn.innerText = '📋 전체복사';
                    btn.style.backgroundColor = '#1864AB';
                }}, 2000);
            }});
        " style="
            background-color:#1864AB;
            color:white;
            border:none;
            border-radius:6px;
            padding:8px 16px;
            font-size:14px;
            font-weight:bold;
            cursor:pointer;
        ">📋 전체복사</button>
        <span style="font-size:12px; color:#666;">클릭하면 아래 전체 문항 코드가 한 줄로 복사됩니다.</span>
    </div>
    """
    components.html(copy_btn_html, height=46)

    # Streamlit 기본 우측 상단 복사 아이콘도 함께 제공
    st.code(full_copy_text, language=None)

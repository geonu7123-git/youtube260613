
import streamlit as st
import pandas as pd
import re
import os
import requests
from googleapiclient.discovery import build
from konlpy.tag import Okt
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# 1. 한글 폰트 다운로드 함수 (Streamlit Cloud 환경 대응)
@st.cache_data
def download_font():
    font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
    font_path = "NanumGothic-Bold.ttf"
    if not os.path.exists(font_path):
        response = requests.get(font_url)
        with open(font_path, "wb") as f:
            f.write(response.content)
    return font_path

FONT_PATH = download_font()

# 2. 유튜브 URL에서 Video ID 추출 함수
def extract_video_id(url):
    pattern = r'(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/|e\/|watch\?v%3D|watch\?feature=player_embedded&v=)([^#\&\?]*微?)'
    match = re.search(pattern, url)
    if match and len(match.group(1)) == 11:
        return match.group(1)
    return None

# 3. 유튜브 댓글 수집 함수
def get_youtube_comments(api_key, video_id, max_results=200):
    youtube = build('youtube', 'v3', developerKey=api_key)
    comments = []
    
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100),
            textFormat="plainText"
        )
        
        while request and len(comments) < max_results:
            response = request.execute()
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment)
                if len(comments) >= max_results:
                    break
            
            # 다음 페이지가 있으면 계속 수집
            if 'nextPageToken' in response and len(comments) < max_results:
                request = youtube.commentThreads().list_next(request, response)
            else:
                break
    except Exception as e:
        st.error(f"유튜브 API 호출 중 오류가 발생했습니다: {e}")
        return []
        
    return comments

# 4. 한글 형태소 분석 및 명사 추출 함수
def process_korean_text(comments):
    okt = Okt()
    all_nouns = []
    
    for comment in comments:
        # 한글, 영문, 공백 제외한 특수문자 제거
        cleaned = re.sub(r'[^가-힣a-zA-Z\s]', '', comment)
        # 명사 추출
        nouns = okt.nouns(cleaned)
        # 2글자 이상인 단어 및 분석에 무의미한 단어 필터링
        stop_words = ['유튜브', '영상', '동영상', '진짜', '정말', '완전', '보고', '댓글']
        nouns = [n for n in nouns if len(n) > 1 and n not in stop_words]
        all_nouns.extend(nouns)
        
    return all_nouns

# --- 스트림릿 UI 시작 ---
st.set_page_config(page_title="유튜브 댓글 심층 분석기", layout="wide")

st.title("📊 유튜브 댓글 심층 분석 및 워드 클라우드")
st.markdown("유튜브 링크와 API 키를 입력하여 대중의 반응을 실시간으로 분석해 보세요.")

# 사이드바 설정
st.sidebar.header("🔑 설정 및 인증")
api_key = st.sidebar.text_input("YouTube API Key를 입력하세요", type="password")
youtube_url = st.text_input("분석할 유튜브 동영상 링크(URL)를 입력하세요", placeholder="https://www.youtube.com/watch?v=...")
max_comments = st.sidebar.slider("수집할 최대 댓글 수", min_value=50, max_value=500, value=200, step=50)

if st.button("🚀 댓글 수집 및 심층 분석 시작"):
    if not api_key:
        st.warning("사이드바에 YouTube API Key를 입력해 주세요.")
    elif not youtube_url:
        st.warning("유튜브 동영상 링크를 입력해 주세요.")
    else:
        video_id = extract_video_id(youtube_url)
        
        if not video_id:
            st.error("유효한 유튜브 URL 형식이 아닙니다. 주소를 다시 확인해 주세요.")
        else:
            with st.spinner("유튜브 서버에서 댓글을 가져오는 중입니다..."):
                comments = get_youtube_comments(api_key, video_id, max_results=max_comments)
                
            if not comments:
                st.info("가져온 댓글이 없거나, 댓글 기능이 꺼져 있는 영상입니다.")
            else:
                st.success(f"총 {len(comments)}개의 댓글을 성공적으로 수집했습니다!")
                
                # 데이터 프레임 변환 및 노출
                with st.expander("📥 수집된 원본 댓글 보기"):
                    df = pd.DataFrame(comments, columns=["댓글 내용"])
                    st.dataframe(df, use_container_width=True)
                
                # 데이터 가공
                with st.spinner("한글 형태소 분석 및 자연어 처리 중..."):
                    nouns = process_korean_text(comments)
                    word_counts = Counter(nouns)
                    top_words = word_counts.most_common(30)
                
                if not nouns:
                    st.warning("분석할 수 있는 한글 명사 키워드가 부족합니다.")
                else:
                    # 레이아웃 나누기 (2열 구성)
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("☁️ 핵심 키워드 워드 클라우드")
                        # 워드클라우드 생성
                        wc = WordCloud(
                            font_path=FONT_PATH,
                            background_color="white",
                            width=800,
                            height=600,
                            max_words=100
                        ).generate_from_frequencies(word_counts)
                        
                        # 시각화 표현
                        fig, ax = plt.subplots(figsize=(10, 8))
                        ax.imshow(wc, interpolation='bilinear')
                        ax.axis("off")
                        st.pyplot(fig)
                        
                    with col2:
                        st.subheader("📈 많이 언급된 단어 Top 15")
                        if top_words:
                            df_words = pd.DataFrame(top_words[:15], columns=["단어", "빈도수"])
                            
                            # 바 차트 시각화
                            st.bar_chart(data=df_words, x="단어", y="빈도수", color="#FF4B4B")
                            
                            # 표 데이터
                            st.dataframe(df_words, use_container_width=True, hide_index=True)

                    # 간단한 요약 인사이트 분석 플러그인 공간
                    st.markdown("---")
                    st.subheader("💡 댓글 분석 인사이트")
                    
                    # 간단한 규칙 기반 감성 어조 필터 예시
                    positive_keywords = ['좋다', '최고', '유익', '대박', '감사', '재미', '존경', '추천', '응원', '사랑']
                    negative_keywords = ['실망', '노잼', '최악', '불편', '부족', '아쉽', '시간낭비', '삭제', '광고']
                    
                    pos_count = sum(1 for c in comments if any(p in c for p in positive_keywords))
                    neg_count = sum(1 for c in comments if any(n in c for n in negative_keywords))
                    
                    col_p, col_n, col_n_total = st.columns(3)
                    col_p.metric(label="긍정적 어조 감지", value=f"{pos_count}건")
                    col_n.metric(label="우려/아쉬움 어조 감지", value=f"{neg_count}건")
                    col_n_total.metric(label="가장 핵심적인 단어", value=f"'{top_words[0][0]}'")

import os
import requests
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# =========================
# ENV
# =========================
load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# =========================
# Spotify OAuth Client
# =========================
def get_spotify_client():
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="playlist-modify-private playlist-modify-public",
            cache_path=".spotifycache",
            show_dialog=True
        )
    )

# =========================
# Weather
# =========================
def get_weather(city):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "kr"
    }
    try:
        r = requests.get(url, params=params)
        return r.json()
    except:
        return None

def weather_to_keyword(weather):
    desc = weather["weather"][0]["main"].lower()
    mapping = {
        "clear": "happy pop bright",
        "clouds": "indie chill",
        "rain": "lofi rainy chill",
        "snow": "cozy acoustic",
        "thunderstorm": "dark edm"
    }
    return mapping.get(desc, "chill mood")

# =========================
# Spotify Search (App Token)
# =========================
def get_app_token():
    url = "https://accounts.spotify.com/api/token"
    data = {"grant_type": "client_credentials"}
    r = requests.post(url, data=data, auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET))
    return r.json().get("access_token")

APP_TOKEN = get_app_token()
HEADERS = {"Authorization": f"Bearer {APP_TOKEN}"} if APP_TOKEN else {}

def search_tracks(query, limit=20):
    url = "https://api.spotify.com/v1/search"
    params = {"q": query, "type": "track", "limit": limit}
    try:
        r = requests.get(url, headers=HEADERS, params=params)
        return r.json()["tracks"]["items"]
    except:
        return []

def get_audio_features(ids):
    url = "https://api.spotify.com/v1/audio-features"
    try:
        r = requests.get(url, headers=HEADERS, params={"ids": ",".join(ids)})
        return r.json()["audio_features"]
    except:
        return []

# =========================
# Recommendation Modes
# =========================
def generate_basic(weather, track_limit):
    kw = weather_to_keyword(weather)
    return search_tracks(kw, track_limit)

def generate_tempo(weather, min_bpm, track_limit):
    kw = weather_to_keyword(weather)
    base = search_tracks(f"{kw} upbeat dance", track_limit * 3)

    ids = [t["id"] for t in base]
    feats = get_audio_features(ids)
    fmap = {f["id"]: f for f in feats if f}

    result = []
    for t in base:
        f = fmap.get(t["id"])
        if f and f.get("tempo", 0) >= min_bpm:
            result.append(t)

    if not result:
        return base[:track_limit]

    return result[:track_limit]

def generate_custom(weather, user_kw, track_limit):
    kw = weather_to_keyword(weather)
    return search_tracks(f"{kw} {user_kw}", track_limit)

# =========================
# ✅ REAL Playlist Creation (OAuth)
# =========================
def create_playlist_auto(city, ids):
    sp = get_spotify_client()
    user_id = sp.me()["id"]

    playlist = sp.user_playlist_create(
        user=user_id,
        name=f"Weather Mix - {city} ({datetime.now().strftime('%m/%d %H:%M')})",
        public=False,
        description="날씨 기반 자동 추천 플레이리스트"
    )

    sp.playlist_add_items(playlist["id"], ids)
    return playlist["external_urls"]["spotify"]

# =========================
# UI
# =========================
st.set_page_config(layout="wide")
st.title("🎧 Weather → Spotify")

city = st.text_input("도시명", "Seoul")
mode = st.selectbox("추천 모드", ["Basic", "Tempo", "Custom"])

# ✅ 추천 곡 수 선택
track_limit = st.slider("추천 곡 수 선택", min_value=5, max_value=30, value=15, step=1)

# ✅ 모드 설명
st.markdown("### 🔍 추천 모드 설명")

if mode == "Basic":
    st.info("☀️ **Basic 모드**는 현재 날씨를 기반으로 가장 어울리는 분위기의 음악을 자동 추천합니다.")
elif mode == "Tempo":
    st.warning("🔥 **Tempo 모드**는 날씨 + 설정한 최소 BPM을 기준으로 빠르고 에너지 있는 곡만 추천합니다.")
elif mode == "Custom":
    st.success("🎨 **Custom 모드**는 날씨 + 입력한 여러 키워드를 반영해 가장 개인화된 추천을 제공합니다.")

if mode == "Tempo":
    min_bpm = st.slider("최소 BPM", 60, 180, 110)

elif mode == "Custom":
    user_kw = st.text_input("키워드 입력 (여러 개 가능, 예: pop happy summer)")

make_playlist = st.checkbox("추천 결과를 실제 Spotify 플레이리스트로 생성")

# =========================
# 실행
# =========================
if st.button("🎵 추천 시작"):

    weather = get_weather(city)
    if not weather or weather.get("cod") != 200:
        st.error("날씨 정보를 찾을 수 없습니다.")
        st.stop()

    st.success(f"{city} 현재 날씨: {weather['weather'][0]['description']} / {weather['main']['temp']}°C")

    if mode == "Basic":
        tracks = generate_basic(weather, track_limit)

    elif mode == "Tempo":
        tracks = generate_tempo(weather, min_bpm, track_limit)

    else:
        tracks = generate_custom(weather, user_kw, track_limit)

    if not tracks:
        st.warning("추천 결과가 없습니다.")
        st.stop()

    st.subheader("🎶 추천 트랙")
    cols = st.columns(3)
    ids = []

    for i, t in enumerate(tracks):
        with cols[i % 3]:
            st.image(t["album"]["images"][0]["url"], use_container_width=True)
            st.markdown(f"**{t['name']}**")
            st.caption(", ".join(a["name"] for a in t["artists"]))
            st.link_button("🎧 Spotify에서 듣기", t["external_urls"]["spotify"])
            ids.append(t["uri"])

    if make_playlist:
        st.markdown("## 📀 Spotify 플레이리스트 생성 중...")
        try:
            link = create_playlist_auto(city, ids)
            st.success("✅ 플레이리스트 생성 완료!")
            st.link_button("🎶 Spotify에서 열기", link)
        except Exception as e:
            st.error(f"플레이리스트 생성 실패: {str(e)}")
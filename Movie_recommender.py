import streamlit as st
import pickle
import pandas as pd
import os
import requests
import time
import ast
import random
import urllib.parse
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# =========================================================
# MONGODB ATLAS AUTHENTICATION & WATCHLIST HELPERS
# =========================================================

def get_users_collection():
    """Retrieve MongoDB Atlas users collection using secrets or environment variable."""
    mongo_uri = None
    try:
        if "MONGODB_URI" in st.secrets:
            mongo_uri = st.secrets["MONGODB_URI"]
    except Exception:
        pass

    if not mongo_uri:
        mongo_uri = os.getenv("MONGODB_URI")

    if not mongo_uri:
        return None

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        db = client.get_default_database("movie_recommender_db")
        return db["users"]
    except Exception:
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            db = client["movie_recommender_db"]
            return db["users"]
        except Exception:
            return None

def register_user(email, password, confirm_password):
    """Register a new user in MongoDB Atlas."""
    if not email or not password:
        return False, "Email and password are required."
    if password != confirm_password:
        return False, "Passwords do not match."

    users_collection = get_users_collection()
    if users_collection is None:
        return False, "MongoDB connection error. Check your MONGODB_URI in secrets.toml or .env."

    try:
        existing_user = users_collection.find_one({"email": email})
        if existing_user:
            return False, "An account with this email already exists."

        user_doc = {
            "email": email,
            "password": password,
            "movies": []
        }
        users_collection.insert_one(user_doc)
        return True, "Account created successfully! Please log in."
    except Exception as e:
        return False, f"Database error: {str(e)}"

def login_user(email, password):
    """Authenticate user strictly using email and password."""
    if not email or not password:
        return False, "Email and password are required."

    users_collection = get_users_collection()
    if users_collection is None:
        return False, "MongoDB connection error. Check MONGODB_URI."

    try:
        user = users_collection.find_one({
            "email": email,
            "password": password
        })

        if user:
            st.session_state.logged_in = True
            st.session_state.user_email = email
            return True, "Logged in successfully!"
        else:
            return False, "Invalid email or password."
    except Exception as e:
        return False, f"Login error: {str(e)}"

def add_movie_to_user_list(email, movie_id, title):
    """Add movie to logged-in user's movies array with session fallback."""
    if "guest_watchlist" not in st.session_state:
        st.session_state.guest_watchlist = []

    try:
        m_id = int(movie_id) if movie_id is not None else 0
    except (ValueError, TypeError):
        m_id = movie_id

    movie_obj = {
        "movie_id": m_id,
        "title": title
    }

    # Always sync to local session state
    if not any(item.get("title") == title or (m_id is not None and m_id != 0 and item.get("movie_id") == m_id) for item in st.session_state.guest_watchlist):
        st.session_state.guest_watchlist.append(movie_obj)

    if email:
        users_collection = get_users_collection()
        if users_collection is not None:
            try:
                users_collection.update_one(
                    {"email": email},
                    {"$addToSet": {"movies": movie_obj}}
                )
            except Exception:
                pass
    return True, "Movie added to your watchlist!"

def remove_movie_from_user_list(email, movie_id, title=None):
    """Remove movie from logged-in user's movies array with session fallback."""
    try:
        m_id = int(movie_id) if movie_id is not None else movie_id
    except (ValueError, TypeError):
        m_id = movie_id

    if "guest_watchlist" in st.session_state:
        st.session_state.guest_watchlist = [
            item for item in st.session_state.guest_watchlist
            if not (item.get("title") == title or (m_id is not None and m_id != 0 and item.get("movie_id") == m_id))
        ]

    if email:
        users_collection = get_users_collection()
        if users_collection is not None:
            try:
                if m_id is not None and m_id != 0:
                    users_collection.update_one(
                        {"email": email},
                        {"$pull": {"movies": {"movie_id": m_id}}}
                    )
                if title:
                    users_collection.update_one(
                        {"email": email},
                        {"$pull": {"movies": {"title": title}}}
                    )
            except Exception:
                pass
    return True, "Movie removed from your watchlist!"

def get_user_movies_from_db(email):
    """Fetch movies array for logged-in user."""
    if not email or not st.session_state.get("logged_in"):
        return []

    users_collection = get_users_collection()
    if users_collection is None:
        return st.session_state.get("guest_watchlist", [])

    try:
        user = users_collection.find_one({"email": email})
        if user and "movies" in user and isinstance(user["movies"], list):
            return user["movies"]
    except Exception:
        pass
    return st.session_state.get("guest_watchlist", [])

@st.dialog("🔐 Account Login / Register")
def show_auth_dialog():
    st.write("Log in or create an account to manage your personal watchlist.")
    tab_login, tab_register = st.tabs(["🔑 Log In", "📝 Register"])

    with tab_login:
        email = st.text_input("Email Address", key="dlg_login_email")
        password = st.text_input("Password", type="password", key="dlg_login_pass")
        if st.button("Log In", key="dlg_login_btn", use_container_width=True):
            success, msg = login_user(email, password)
            if success:
                st.success(msg)
                if st.session_state.get("pending_movie"):
                    pm = st.session_state.pending_movie
                    add_movie_to_user_list(email, pm.get("movie_id"), pm.get("title"))
                    st.session_state.pending_movie = None
                    st.toast(f"Added '{pm.get('title')}' to My List!", icon="✅")
                time.sleep(0.4)
                st.rerun()
            else:
                st.error(msg)

    with tab_register:
        reg_email = st.text_input("Email Address", key="dlg_reg_email")
        reg_pass = st.text_input("Password", type="password", key="dlg_reg_pass")
        reg_confirm = st.text_input("Confirm Password", type="password", key="dlg_reg_confirm")
        if st.button("Create Account", key="dlg_reg_btn", use_container_width=True):
            success, msg = register_user(reg_email, reg_pass, reg_confirm)
            if success:
                st.success(msg)
            else:
                st.error(msg)

def trigger_add_to_list(movie):
    """Helper to handle 'Add to My List' action with loading spinner."""
    title = movie.get("title", "Movie")
    if not st.session_state.get("logged_in"):
        st.session_state.pending_movie = movie
        st.toast("🔒 Please log in or create an account first to save movies to your list.", icon="🔐")
        show_auth_dialog()
    else:
        show_loading_circle(f"🍿 Adding '{title}' to your watchlist...")
        m_id = movie.get("movie_id")
        if m_id is None and 'df' in globals() and df is not None:
            match = df[df["title"] == title]
            if not match.empty:
                m_id = match.iloc[0].get("id", match.iloc[0].get("movie_id"))
        add_movie_to_user_list(st.session_state.user_email, m_id, title)
        st.toast(f"Added '{title}' to My List!", icon="✅")
        st.rerun()

def trigger_remove_from_list(movie_id, title="Movie"):
    """Helper to handle 'Remove from My List' action with loading spinner."""
    show_loading_circle(f"🗑️ Removing '{title}' from your watchlist...")
    remove_movie_from_user_list(st.session_state.get("user_email", ""), movie_id, title)
    st.toast(f"Removed '{title}' from your watchlist.")
    st.rerun()

def is_movie_in_user_list(movie):
    """Check if movie is already in logged-in user's list."""
    if not st.session_state.get("logged_in"):
        return False
    user_movies = get_user_movies_from_db(st.session_state.get("user_email", ""))
    m_id = movie.get("movie_id")
    title = movie.get("title")
    for item in user_movies:
        if item.get("title") == title:
            return True
        if m_id is not None and m_id != 0 and item.get("movie_id") == m_id:
            return True
    return False

# Load Dataset & Pickle Models
movie_dict = pickle.load(open('movie_dict.pkl','rb'))
movies = pd.DataFrame(movie_dict)
similarity = pickle.load(open('similarity.pkl','rb'))

session = requests.session()
PLACEHOLDER_IMAGE = "https://placehold.co/300x450/111827/F8FAFC?text=Poster+Unavailable"
SUPABASE_POSTER_URL = "https://lfkyggfvcmcdqmgjvlfj.supabase.co/storage/v1/object/public/movie-posters"

@st.cache_data
def fetch_poster(movie_id):
    try:
        poster_url = f"{SUPABASE_POSTER_URL}/{movie_id}.jpg"
        return poster_url
    except Exception:
        pass
    return PLACEHOLDER_IMAGE

def recommend(movie, n):
    rnd = random.randint(1, 10)
    matches = movies[movies['title'] == movie].index
    if len(matches) == 0:
        return []
    movie_index = matches[0]
    distance = similarity[movie_index]
    movie_list = sorted(list(enumerate(distance)), reverse=True, key=lambda x: x[1])[rnd+1:rnd+n+1]
    
    recommended = []
    recommended_movie_poster = []

    for i in movie_list:
        movie_id = movies.iloc[i[0]].movie_id
        recommended.append(movies.iloc[i[0]].title)
        recommended_movie_poster.append(fetch_poster(movie_id))
    return recommended, recommended_movie_poster

def recommend_genres(genre, n):
    if 'df' not in globals() or df is None:
        return []
        
    if genre == "All":
        filtered_df = df.copy()
    elif genre == "Top Rated":
        filtered_df = df[df["vote_average"] >= 8]
    else:
        genre_aliases = {
            "Sci-Fi": "Science Fiction",
            "Anime": "Animation"
        }
        dataset_genre = genre_aliases.get(genre, genre)
        filtered_df = df[
            df["genres_list"].apply(
                lambda genres: dataset_genre.replace("-", " ").lower()
                in {g.replace("-", " ").lower() for g in genres} if isinstance(genres, list) else False
            )
        ]
        
    if filtered_df.empty:
        return []
        
    sampled_df = filtered_df.sort_values(by="popularity", ascending=False).head(n)
    
    recommendations = []
    for rank_idx, (_, row) in enumerate(sampled_df.iterrows(), 1):
        m_id = row.get('id', row.get('movie_id'))
        genre_str = row['genres_list'][0] if ('genres_list' in row and isinstance(row['genres_list'], list) and len(row['genres_list']) > 0) else "Unknown"
        actor_str = row['actors'][0] if ('actors' in row and isinstance(row['actors'], list) and len(row['actors']) > 0) else "Unknown"
        rating_str = f"★ {row['vote_average']:.1f}" if ('vote_average' in row and pd.notnull(row['vote_average'])) else "★ N/A"
        
        recommendations.append({
            "rank": rank_idx,
            "title": row['title'],
            "img": fetch_poster(m_id),
            "genre": genre_str,
            "rating": rating_str,
            "actor": actor_str,
            "movie_id": m_id
        })
    return recommendations

st.set_page_config(
    page_title="MoviX | Premium Movie Recommender & Watchlist",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data
def load_data():
    credits = pd.read_csv("tmdb_5000_credits.csv")
    movies_file = pd.read_csv("tmdb_5000_movies.csv")

    df = movies_file.merge(credits[["movie_id", "cast"]], left_on="id", right_on="movie_id")

    def get_actors(cast_str, limit=3):
        try:
            cast_list = ast.literal_eval(cast_str)
            return [actor["name"].strip() for actor in cast_list[:limit] if actor.get("name")]
        except (ValueError, SyntaxError, TypeError):
            return []

    df["actors"] = df["cast"].apply(get_actors)

    def get_genres(genre_str):
        try:
            genre_list = ast.literal_eval(genre_str)
            return [genre["name"] for genre in genre_list if genre.get("name")]
        except (ValueError, SyntaxError, TypeError):
            return []

    df["genres_list"] = df["genres"].apply(get_genres)

    unique_actors = sorted(
        list({actor for sublist in df["actors"] for actor in sublist if actor})
    )

    return df, unique_actors

df, unique_actors = load_data()

def show_loading_circle(text="Analyzing similarity matrix & fetching recommendations..."):
    """Render animated amber circular spinner before displaying results."""
    placeholder = st.empty()
    placeholder.markdown(f"""
    <div class="loading-circle-box">
        <div class="loading-circle"></div>
        <div class="loading-text">{text}</div>
    </div>
    """, unsafe_allow_html=True)
    time.sleep(0.4)
    placeholder.empty()

def get_movie_full_info(identifier):
    """Retrieve comprehensive movie metadata for details modal."""
    m_id = None
    title = None
    
    if isinstance(identifier, dict):
        m_id = identifier.get("movie_id") or identifier.get("id")
        title = identifier.get("title")
    elif isinstance(identifier, (int, float)):
        m_id = int(identifier)
    elif isinstance(identifier, str):
        title = identifier

    row = None
    if m_id is not None and 'df' in globals() and df is not None:
        try:
            m_id_num = int(m_id)
            match = df[df['id'] == m_id_num]
            if not match.empty:
                row = match.iloc[0]
        except Exception:
            pass

    if row is None and title is not None and 'df' in globals() and df is not None:
        match = df[df['title'].str.lower() == str(title).lower()]
        if not match.empty:
            row = match.iloc[0]

    if row is not None:
        movie_id = int(row['id'])
        title_str = str(row['title'])
        tagline = str(row['tagline']) if pd.notnull(row.get('tagline')) and str(row.get('tagline')).strip() != "nan" else ""
        overview = str(row['overview']) if pd.notnull(row.get('overview')) and str(row.get('overview')).strip() != "nan" else "No overview plot summary available for this movie."
        release_date = str(row['release_date']) if pd.notnull(row.get('release_date')) else "N/A"
        year = release_date.split("-")[0] if "-" in release_date else release_date
        
        runtime = row.get('runtime', 0)
        if pd.notnull(runtime) and float(runtime) > 0:
            hrs = int(float(runtime) // 60)
            mins = int(float(runtime) % 60)
            runtime_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
        else:
            runtime_str = "N/A"

        vote_avg = row.get('vote_average', 0)
        rating_str = f"★ {float(vote_avg):.1f}" if pd.notnull(vote_avg) else "★ N/A"
        vote_count = int(row.get('vote_count', 0)) if pd.notnull(row.get('vote_count')) else 0
        popularity = float(row.get('popularity', 0)) if pd.notnull(row.get('popularity')) else 0.0

        genres_list = row.get('genres_list', [])
        if not isinstance(genres_list, list) or not genres_list:
            genres_list = ["Movie"]
        
        actors = row.get('actors', [])
        if not isinstance(actors, list):
            actors = []

        homepage = str(row.get('homepage')) if pd.notnull(row.get('homepage')) and str(row.get('homepage')).startswith("http") else None
        budget = int(row.get('budget', 0)) if pd.notnull(row.get('budget')) else 0
        revenue = int(row.get('revenue', 0)) if pd.notnull(row.get('revenue')) else 0

        poster_url = fetch_poster(movie_id)
        trailer_query = urllib.parse.quote(f"{title_str} {year} official trailer")
        trailer_url = f"https://www.youtube.com/results?search_query={trailer_query}"

        return {
            "movie_id": movie_id,
            "title": title_str,
            "tagline": tagline,
            "overview": overview,
            "release_date": release_date,
            "year": year,
            "runtime_str": runtime_str,
            "rating_str": rating_str,
            "vote_average": vote_avg,
            "vote_count": vote_count,
            "popularity": popularity,
            "genres_list": genres_list,
            "actors": actors,
            "homepage": homepage,
            "budget": budget,
            "revenue": revenue,
            "poster_url": poster_url,
            "trailer_url": trailer_url
        }

    # Fallback
    safe_title = title or "Movie Details"
    return {
        "movie_id": m_id or 0,
        "title": safe_title,
        "tagline": "",
        "overview": "Detailed overview for this movie is currently loading.",
        "release_date": "N/A",
        "year": "N/A",
        "runtime_str": "N/A",
        "rating_str": "★ N/A",
        "vote_average": 0,
        "vote_count": 0,
        "popularity": 0,
        "genres_list": ["Movie"],
        "actors": [],
        "homepage": None,
        "budget": 0,
        "revenue": 0,
        "poster_url": fetch_poster(m_id) if m_id else PLACEHOLDER_IMAGE,
        "trailer_url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(safe_title + ' trailer')}"
    }

@st.dialog("🎬 Movie Details", width="large")
def show_movie_details_dialog(identifier):
    info = get_movie_full_info(identifier)
    
    col_img, col_info = st.columns([1, 2])
    with col_img:
        st.image(info["poster_url"], use_container_width=True)
        
        # YouTube Trailer Button
        st.markdown(f"""
        <a href="{info['trailer_url']}" target="_blank" style="text-decoration: none;">
            <div style="
                background: linear-gradient(135deg, #FF0000 0%, #C40000 100%);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 0.95rem;
                text-align: center;
                padding: 12px 16px;
                border-radius: 12px;
                margin-top: 12px;
                box-shadow: 0 4px 18px rgba(255, 0, 0, 0.4);
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                cursor: pointer;
            ">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                Watch Trailer on YouTube
            </div>
        </a>
        """, unsafe_allow_html=True)
        
        if info["homepage"]:
            st.markdown(f"""
            <a href="{info['homepage']}" target="_blank" style="text-decoration: none;">
                <div style="
                    background: rgba(255, 255, 255, 0.08);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    color: #E2E8F0;
                    font-weight: 600;
                    font-size: 0.88rem;
                    text-align: center;
                    padding: 8px 12px;
                    border-radius: 10px;
                    margin-top: 8px;
                ">
                    🌐 Visit Official Website
                </div>
            </a>
            """, unsafe_allow_html=True)

    with col_info:
        st.markdown(f"<h2 style='margin-bottom: 2px; font-weight: 800; color: #FFFFFF;'>{info['title']}</h2>", unsafe_allow_html=True)
        if info["tagline"]:
            st.markdown(f"<p style='color: #FF9F0A; font-style: italic; margin-bottom: 12px;'>\"{info['tagline']}\"</p>", unsafe_allow_html=True)

        genre_tags = " ".join([f'<span class="movie-genre" style="margin-right: 6px;">{g}</span>' for g in info["genres_list"]])
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px;">
            <span class="badge" style="font-size: 0.95rem; padding: 4px 12px;">{info['rating_str']} ({info['vote_count']:,} votes)</span>
            <span style="color: #CBD5E1; font-weight: 500;">📅 {info['year']}</span>
            <span style="color: #CBD5E1; font-weight: 500;">⏱️ {info['runtime_str']}</span>
        </div>
        <div style="margin-bottom: 16px;">{genre_tags}</div>
        """, unsafe_allow_html=True)

        st.markdown("#### 📖 Overview")
        st.write(info["overview"])

        if info["actors"]:
            st.markdown("#### 🎭 Top Cast")
            actors_html = " ".join([f'<span style="background: rgba(255, 159, 10, 0.15); color: #FF9F0A; border: 1px solid rgba(255, 159, 10, 0.3); padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; display: inline-block; margin-right: 6px; margin-bottom: 6px;">{a}</span>' for a in info["actors"]])
            st.markdown(f"<div>{actors_html}</div>", unsafe_allow_html=True)

        st.markdown("---")
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            is_in_list = is_movie_in_user_list(info)
            if is_in_list:
                if st.button("➖ Remove from List", key=f"dlg_rem_{info['movie_id']}", use_container_width=True):
                    trigger_remove_from_list(info["movie_id"], info["title"])
            else:
                if st.button("➕ Add to My List", key=f"dlg_add_{info['movie_id']}", use_container_width=True):
                    trigger_add_to_list(info)
        
        with col_act2:
            if st.button("✨ Similar Movies", key=f"dlg_rec_{info['movie_id']}", use_container_width=True):
                st.session_state.selected_movie = info["title"]
                st.session_state.active_recommendation = ("movie", info["title"])
                st.session_state.current_page = "Home"
                st.rerun()

# Custom CSS Styling: Premium Cinematic UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
        -webkit-font-smoothing: antialiased;
    }

    ::-webkit-scrollbar {
        width: 10px;
        background: #09090B;
    }
    ::-webkit-scrollbar-track {
        background: #09090B;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 159, 10, 0.3);
        border-radius: 10px;
        border: 2px solid #09090B;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 159, 10, 0.8);
    }

    .stApp {
        background: #09090B !important;
        color: #F8FAFC;
    }
    
    .stApp[data-test-script-state="running"],
    .stApp[data-test-script-state="running"] *,
    [data-test-script-state="running"] [data-testid="stAppViewContainer"],
    [data-test-script-state="running"] [data-testid="stMain"],
    [data-test-script-state="running"] [data-testid="stMainBlockContainer"],
    [data-test-script-state="running"] .block-container {
        opacity: 1 !important;
        filter: none !important;
        transition: none !important;
    }

    @keyframes floatOrb1 {
        0%, 100% { transform: translate(0, 0) scale(1); }
        33% { transform: translate(5vw, 10vh) scale(1.2); }
        66% { transform: translate(-5vw, -5vh) scale(0.9); }
    }

    @keyframes floatOrb2 {
        0%, 100% { transform: translate(0, 0) scale(1); }
        33% { transform: translate(-5vw, -10vh) scale(1.1); }
        66% { transform: translate(10vw, 5vh) scale(1.3); }
    }

    .bg-orb-1, .bg-orb-2 {
        position: fixed;
        border-radius: 50%;
        filter: blur(120px);
        z-index: 0;
        pointer-events: none;
    }

    .bg-orb-1 {
        top: -10%; left: -10%;
        width: 50vw; height: 50vw;
        background: radial-gradient(circle, rgba(255, 159, 10, 0.15) 0%, transparent 70%);
        animation: floatOrb1 25s infinite ease-in-out;
    }

    .bg-orb-2 {
        bottom: -10%; right: -10%;
        width: 60vw; height: 60vw;
        background: radial-gradient(circle, rgba(139, 92, 246, 0.1) 0%, transparent 70%);
        animation: floatOrb2 30s infinite ease-in-out reverse;
    }

    section[data-testid="stSidebar"] {
        background-color: rgba(18, 18, 22, 0.75) !important;
        backdrop-filter: blur(30px);
        -webkit-backdrop-filter: blur(30px);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 10px 0 30px rgba(0, 0, 0, 0.8);
    }

    .block-container {
        position: relative;
        z-index: 1;
        padding-top: 5.5rem !important;
        padding-bottom: 5rem !important;
    }

    .custom-navbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 70px;
        background: rgba(9, 9, 11, 0.88);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 180px 0 4.5rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
    }
    .nav-brand {
        font-size: 1.6rem;
        font-weight: 900;
        letter-spacing: -0.03em;
        color: #FFFFFF;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .brand-sq {
        width: 34px;
        height: 34px;
        background: linear-gradient(135deg, #FF9F0A 0%, #F59E0B 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 15px rgba(255, 159, 10, 0.4);
    }
    .brand-sq-inner {
        width: 14px;
        height: 14px;
        background: #FFFFFF;
        border-radius: 4px;
    }
    
    .nav-user-pill {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 25px;
        padding: 6px 16px;
        color: #FFFFFF;
        font-size: 0.88rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .section-title {
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        color: #FFFFFF;
        letter-spacing: -0.02em;
    }
    .section-subtitle {
        color: #8E8E93;
        font-size: 1rem;
        margin-bottom: 1.8rem;
        font-weight: 400;
    }

    /* NETFLIX STROKE RANK NUMBERS */
    .top10-container {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 240px;
        margin-bottom: 0.5rem;
        transition: transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .top10-container:hover {
        transform: scale(1.05) translateY(-5px);
    }

    .rank-number {
        position: absolute;
        right: calc(50% + 25px);
        bottom: 5px;
        font-size: 5.5rem;
        font-family: 'Outfit', sans-serif;
        font-weight: 900;
        line-height: 0.9;
        color: #09090B;
        -webkit-text-stroke: 2.5px #FF9F0A;
        user-select: none;
        z-index: 2;
        letter-spacing: -3px;
        transition: all 0.3s ease;
        filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.8));
    }
    .top10-container:hover .rank-number {
        -webkit-text-stroke: 2.5px #FFB800;
        text-shadow: 0 0 20px rgba(255, 159, 10, 0.6);
        transform: scale(1.08) translateX(-5px);
    }

    .rank-poster-box {
        position: relative;
        width: 180px;
        height: 210px;
        flex-shrink: 0;
        border-radius: 14px;
        overflow: hidden;
        z-index: 1;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.8);
        transition: all 0.3s ease;
        background: #141416;
    }
    .top10-container:hover .rank-poster-box {
        border-color: #FF9F0A;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.9), 0 0 30px rgba(255, 159, 10, 0.3);
    }
    .rank-poster-box img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 0.5s ease;
    }
    .top10-container:hover .rank-poster-box img {
        transform: scale(1.05);
    }

    .rec-card-details {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        width: 180px;
        margin: 0.8rem auto 0.5rem auto;
    }
    .rec-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #FFFFFF;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        width: 100%;
        text-align: center;
        transition: color 0.3s;
    }
    .top10-container:hover + .rec-card-details .rec-card-title {
        color: #FF9F0A;
    }
    .rec-card-meta {
        font-size: 0.85rem;
        color: #FF9F0A;
        margin-top: 0.2rem;
        font-weight: 600;
        text-align: center;
    }

    /* Standard Cards */
    .poster-card {
        background: #141416;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 1rem;
        transition: all 0.3s ease;
        margin-bottom: 0.8rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        display: flex;
        flex-direction: column;
    }
    .poster-card:hover {
        transform: translateY(-6px);
        background: #1C1C20;
        border-color: #FF9F0A;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(255, 159, 10, 0.2);
    }
    .movie-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-top: 0.8rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        transition: all 0.3s;
    }
    .poster-card:hover .movie-title {
        color: #FF9F0A;
    }
    .movie-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 0.6rem;
    }
    .movie-genre {
        font-size: 0.8rem;
        color: #E2E8F0;
        font-weight: 500;
        background: rgba(255, 255, 255, 0.08);
        padding: 4px 10px;
        border-radius: 20px;
    }
    .badge {
        background: rgba(255, 159, 10, 0.15);
        border: 1px solid rgba(255, 159, 10, 0.3);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        color: #FF9F0A;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    /* Buttons Styling */
    .stButton, div[data-testid="stButton"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
    }
    .stButton > button, div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #FF9F0A 0%, #D97706 100%);
        color: #000000 !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.65rem 1.4rem !important;
        box-shadow: 0 4px 18px rgba(255, 159, 10, 0.35) !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
        white-space: nowrap !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        color: #FFFFFF !important;
        background: #141416 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(255, 159, 10, 0.5);
        color: #000000;
    }

    div[data-baseweb="select"] > div {
        background-color: #141416;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        color: white;
    }

    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    div[data-testid="stDecoration"] { display: none !important; }

    header[data-testid="stHeader"] {
        background: transparent !important;
        z-index: 100000 !important;
    }

    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] {
        z-index: 100001 !important;
        color: #FF9F0A !important;
        background: rgba(20, 20, 25, 0.85) !important;
        border: 1px solid rgba(255, 159, 10, 0.4) !important;
        border-radius: 10px !important;
    }

    /* Custom Circular Loading Circle Animation */
    @keyframes spinRing {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .loading-circle-box {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem 1rem;
        gap: 16px;
        width: 100%;
        margin: 1.5rem 0;
    }

    .loading-circle {
        width: 52px;
        height: 52px;
        border: 4px solid rgba(255, 159, 10, 0.15);
        border-top: 4px solid #FF9F0A;
        border-right: 4px solid #FF9F0A;
        border-radius: 50%;
        animation: spinRing 0.75s linear infinite;
        box-shadow: 0 0 22px rgba(255, 159, 10, 0.45);
    }

    .loading-text {
        color: #FF9F0A;
        font-weight: 700;
        font-size: 1rem;
        letter-spacing: 0.02em;
    }

    /* Override Streamlit Spinner with Amber Theme */
    div[data-testid="stSpinner"] > div {
        border-top-color: #FF9F0A !important;
    }
    div[data-testid="stSpinner"] p {
        color: #FF9F0A !important;
        font-weight: 600 !important;
    }
</style>
<div class="bg-orb-1"></div>
<div class="bg-orb-2"></div>
""", unsafe_allow_html=True)

# Session State Initialization
if "selected_movie" not in st.session_state:
    st.session_state.selected_movie = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
if "selected_filter" not in st.session_state:
    st.session_state.selected_filter = "All"
if "active_recommendation" not in st.session_state:
    st.session_state.active_recommendation = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "pending_movie" not in st.session_state:
    st.session_state.pending_movie = None
if "guest_watchlist" not in st.session_state:
    st.session_state.guest_watchlist = []

RANDOM_FEATURED_MOVIES = [
    {
        "title": "Avatar",
        "genre": "Action",
        "actor": "SamWorthington",
        "rating": "★ 7.6",
        "img": fetch_poster(19995),
        "movie_id": 19995
    },
    {
        "title": "The Dark Knight",
        "genre": "Drama",
        "actor": "ChristianBale",
        "rating": "★ 8.5",
        "img": fetch_poster(155),
        "movie_id": 155
    },
    {
        "title": "Inception",
        "genre": "Action",
        "actor": "LeonardoDiCaprio",
        "rating": "★ 8.3",
        "img": fetch_poster(27205),
        "movie_id": 27205
    },
    {
        "title": "Interstellar",
        "genre": "Adventure",
        "actor": "MatthewMcConaughey",
        "rating": "★ 8.4",
        "img": fetch_poster(157336),
        "movie_id": 157336
    },
    {
        "title": "The Shawshank Redemption",
        "genre": "Drama",
        "actor": "TimRobbins",
        "rating": "★ 8.7",
        "img": fetch_poster(278),
        "movie_id": 278
    },
    {
        "title": "The Lord of the Rings: The Return of the King",
        "genre": "Adventure",
        "actor": "ElijahWood",
        "rating": "★ 8.4",
        "img": fetch_poster(122),
        "movie_id": 122
    },
    {
        "title": "Titanic",
        "genre": "Romance",
        "actor": "LeonardoDiCaprio",
        "rating": "★ 7.9",
        "img": fetch_poster(597),
        "movie_id": 597
    },
    {
        "title": "The Matrix",
        "genre": "Action",
        "actor": "KeanuReeves",
        "rating": "★ 8.1",
        "img": fetch_poster(603),
        "movie_id": 603
    }
]

FILTER_OPTIONS = [
    ("⚡", "Action"),
    ("🎭", "Comedy"),
    ("👻", "Horror"),
    ("🚀", "Sci-Fi"),
    ("♡", "Romance"),
    ("✦", "Anime"),
    ("🎬", "Thriller"),
    ("☆", "Top Rated")
]

# Sidebar Navigation & Controls
with st.sidebar:
    st.markdown("## 🧭 Navigation")
    if st.button("🏠 Home", use_container_width=True):
        show_loading_circle("🏠 Navigating to Home...")
        st.session_state.current_page = "Home"
        st.session_state.selected_movie = None
        st.session_state.active_recommendation = None
        st.rerun()

    user_movies_count = len(get_user_movies_from_db(st.session_state.user_email))
    if st.button(f"👤 My Profile & List ({user_movies_count})", use_container_width=True):
        show_loading_circle("👤 Navigating to Profile...")
        st.session_state.current_page = "Profile"
        st.rerun()

    if st.button(f"📌 Watchlist ({user_movies_count})", use_container_width=True):
        show_loading_circle("📌 Navigating to Watchlist...")
        st.session_state.current_page = "Watchlist"
        st.rerun()

    st.markdown("---")
    st.markdown("## 👤 Account")
    if st.session_state.get("logged_in"):
        st.markdown(f"**Logged in as:**\n`{st.session_state.user_email}`")
        if st.button("🚪 Log Out", use_container_width=True):
            show_loading_circle("🚪 Logging out...")
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.pending_movie = None
            st.toast("Logged out successfully.")
            st.rerun()
    else:
        st.info("Log in to sync your watchlist to the cloud.")
        if st.button("🔑 Log In / Register", use_container_width=True):
            show_auth_dialog()

    st.markdown("---")
    st.markdown("## ⚙️ Filter Options")
    if st.button("🔄 Reset Filters", use_container_width=True):
        show_loading_circle("🔄 Resetting filters...")
        st.session_state.selected_filter = "All"
        st.session_state.selected_movie = None
        st.session_state.active_recommendation = None
        st.rerun()

def get_filtered_movies(limit):
    selected_filter = st.session_state.selected_filter
    if selected_filter == "All":
        return RANDOM_FEATURED_MOVIES

    if selected_filter == "Top Rated":
        filtered_data = df[df["vote_average"] >= 8].sort_values(
            by="vote_average", ascending=False
        ).head(limit)
    else:
        genre_aliases = {
            "Sci-Fi": "Science Fiction",
            "Anime": "Animation"
        }
        dataset_genre = genre_aliases.get(selected_filter, selected_filter)
        filtered_data = df[
            df["genres_list"].apply(
                lambda genres: dataset_genre.replace("-", " ").lower()
                in {genre.replace("-", " ").lower() for genre in genres} if isinstance(genres, list) else False
            )
        ].sort_values(by="popularity", ascending=False).head(limit)

    return [
        {
            "title": row["title"],
            "genre": row["genres_list"][0] if ('genres_list' in row and isinstance(row['genres_list'], list) and row["genres_list"]) else "Unknown",
            "actor": row["actors"][0] if ('actors' in row and isinstance(row['actors'], list) and row["actors"]) else "Unknown",
            "rating": f"★ {row['vote_average']:.1f}" if pd.notnull(row.get('vote_average')) else "★ N/A",
            "img": fetch_poster(row["id"]),
            "movie_id": row["id"]
        }
        for _, row in filtered_data.iterrows()
    ]

def get_recommendations(target_title, n=5):
    res = recommend(target_title, n)
    if not res or not isinstance(res, (tuple, list)) or len(res) != 2:
        return []
    titles, posters = res
    recommendations = []
    for rank_idx, (title, poster) in enumerate(zip(titles, posters), 1):
        df_match = df[df['title'] == title] if 'df' in globals() and df is not None else pd.DataFrame()
        if not df_match.empty:
            row = df_match.iloc[0]
            genre_str = row['genres_list'][0] if ('genres_list' in row and isinstance(row['genres_list'], list) and len(row['genres_list']) > 0) else "Movie"
            actor_str = row['actors'][0] if ('actors' in row and isinstance(row['actors'], list) and len(row['actors']) > 0) else "Unknown"
            rating_str = f"★ {row['vote_average']:.1f}" if ('vote_average' in row and pd.notnull(row['vote_average'])) else "★ N/A"
            m_id = row.get('id', row.get('movie_id'))
        else:
            genre_str = "Movie"
            actor_str = "Unknown"
            rating_str = "★ N/A"
            m_id = None

        recommendations.append({
            "rank": rank_idx,
            "title": title,
            "img": poster,
            "genre": genre_str,
            "rating": rating_str,
            "actor": actor_str,
            "movie_id": m_id
        })
    return recommendations

# Top Navbar Rendering
st.markdown("""
<div class="custom-navbar">
    <div class="nav-brand">
        <div class="brand-sq"><div class="brand-sq-inner"></div></div>
        MoviX
    </div>
</div>
""", unsafe_allow_html=True)

# MAIN CONTENT ROUTING

# PAGE 1: PROFILE PAGE
if st.session_state.current_page == "Profile":
    user_email = st.session_state.get("user_email", "")
    is_logged = st.session_state.get("logged_in", False)
    display_email = user_email if is_logged else "Guest Cinephile"
    avatar_char = user_email[0].upper() if is_logged and user_email else "👤"

    db_movies = get_user_movies_from_db(user_email)
    total_movies_count = len(db_movies)

    # Calculate Watchlist Stats
    watchlist_full_info = [get_movie_full_info(m) for m in db_movies]
    valid_ratings = [m["vote_average"] for m in watchlist_full_info if m["vote_average"] > 0]
    avg_rating_val = sum(valid_ratings) / len(valid_ratings) if valid_ratings else 0.0
    avg_rating_str = f"★ {avg_rating_val:.1f}" if avg_rating_val > 0 else "★ N/A"

    # Calculate Top Genre
    all_saved_genres = [g for m in watchlist_full_info for g in m["genres_list"] if g != "Movie"]
    top_genre_str = max(set(all_saved_genres), key=all_saved_genres.count) if all_saved_genres else "Cinematic"

    # Profile Hero Banner
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(24, 24, 32, 0.95) 0%, rgba(12, 12, 18, 0.98) 100%);
        border: 1px solid rgba(255, 159, 10, 0.3);
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 1.5rem;
    ">
        <div style="display: flex; align-items: center; gap: 1.5rem;">
            <div style="
                width: 75px; height: 75px;
                border-radius: 50%;
                background: linear-gradient(135deg, #FF9F0A 0%, #D97706 100%);
                display: flex; align-items: center; justify-content: center;
                font-size: 2rem; font-weight: 800; color: #000000;
                box-shadow: 0 0 25px rgba(255, 159, 10, 0.4);
            ">
                {avatar_char}
            </div>
            <div>
                <h2 style="margin: 0; font-weight: 800; color: #FFFFFF; font-size: 1.8rem;">{display_email}</h2>
                <p style="margin: 4px 0 0 0; color: #94A3B8; font-size: 0.95rem;">Personal Cinephile Profile & Collection</p>
                <div style="display: flex; gap: 8px; margin-top: 8px;">
                    <span class="badge" style="background: rgba(255, 159, 10, 0.15); border-color: rgba(255, 159, 10, 0.4);">👑 Cinephile Member</span>
                    <span class="badge" style="background: rgba(99, 102, 241, 0.15); color: #818CF8; border-color: rgba(99, 102, 241, 0.4);">🎬 Active Curator</span>
                </div>
            </div>
        </div>
        <div style="display: flex; gap: 1.2rem; align-items: center; flex-wrap: wrap;">
            <div style="text-align: center; background: rgba(255, 255, 255, 0.04); padding: 12px 20px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.06);">
                <div style="font-size: 1.6rem; font-weight: 800; color: #FF9F0A;">{total_movies_count}</div>
                <div style="font-size: 0.78rem; color: #94A3B8; font-weight: 600;">SAVED MOVIES</div>
            </div>
            <div style="text-align: center; background: rgba(255, 255, 255, 0.04); padding: 12px 20px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.06);">
                <div style="font-size: 1.6rem; font-weight: 800; color: #10B981;">{avg_rating_str}</div>
                <div style="font-size: 0.78rem; color: #94A3B8; font-weight: 600;">AVG RATING</div>
            </div>
            <div style="text-align: center; background: rgba(255, 255, 255, 0.04); padding: 12px 20px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.06);">
                <div style="font-size: 1.6rem; font-weight: 800; color: #818CF8;">{top_genre_str}</div>
                <div style="font-size: 0.78rem; color: #94A3B8; font-weight: 600;">TOP GENRE</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_wl, tab_analytics, tab_acc = st.tabs(["🍿 My Watchlist", "📊 Cinephile Analytics", "⚙️ Account Settings"])

    with tab_wl:
        if not db_movies:
            st.info("🍿 Your watchlist is currently empty. Explore movies on the home page and click '➕ Add to List' to start your collection!")
            if st.button("🎬 Browse & Discover Movies", use_container_width=True):
                st.session_state.current_page = "Home"
                st.rerun()
        else:
            search_query = st.text_input("🔍 Search within Watchlist", placeholder="Filter saved movies by title...", key="wl_search_kw")
            filtered_wl = [m for m in watchlist_full_info if search_query.lower() in m["title"].lower()] if search_query else watchlist_full_info

            cols = st.columns(4)
            for idx, movie in enumerate(filtered_wl):
                col = cols[idx % 4]
                with col:
                    st.markdown(f"""
                    <div class="poster-card">
                        <img src="{movie['poster_url']}" style="width: 100%; border-radius: 12px; aspect-ratio: 2/3; object-fit: cover; margin-bottom: 0.5rem;" alt="{movie['title']}">
                        <div class="movie-title">{movie['title']}</div>
                        <div class="movie-meta">
                            <span class="movie-genre">{movie['genres_list'][0]}</span>
                            <span class="badge">{movie['rating_str']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("ℹ️ Details", key=f"prof_det_{idx}_{movie['movie_id']}", use_container_width=True):
                            show_movie_details_dialog(movie)
                    with c2:
                        if st.button("➖ Remove", key=f"prof_rem_{idx}_{movie['movie_id']}", use_container_width=True):
                            trigger_remove_from_list(movie['movie_id'], movie['title'])

    with tab_analytics:
        st.markdown("### 📊 Watchlist Insights")
        if not db_movies:
            st.info("Add movies to your watchlist to unlock genre and cinephile analytics.")
        else:
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.markdown("#### 🏷️ Genre Breakdown")
                genre_counts = pd.Series(all_saved_genres).value_counts()
                for genre_name, count in genre_counts.items():
                    pct = int((count / len(all_saved_genres)) * 100)
                    st.write(f"**{genre_name}** ({count} movies)")
                    st.progress(pct / 100.0)
            
            with col_a2:
                st.markdown("#### 🎭 Top Cast in Your Watchlist")
                all_actors = [a for m in watchlist_full_info for a in m["actors"]]
                if all_actors:
                    actor_counts = pd.Series(all_actors).value_counts().head(5)
                    for actor_name, a_count in actor_counts.items():
                        st.markdown(f"- **{actor_name}** ({a_count} appearances)")
                else:
                    st.write("Cast data sync complete.")

    with tab_acc:
        st.markdown("### 🔐 Account & Cloud Sync")
        if is_logged:
            st.success(f"Connected to Cloud Account: **{user_email}**")
            if st.button("🚪 Log Out", key="prof_logout_btn", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user_email = ""
                st.rerun()
        else:
            st.info("You are currently using Guest Mode. Log in or create an account to sync your watchlist across devices.")
            if st.button("🔑 Log In / Register Account", key="prof_login_btn", use_container_width=True):
                show_auth_dialog()

# PAGE 2: WATCHLIST DIRECT PAGE
elif st.session_state.current_page == "Watchlist":
    st.markdown('<div class="section-title">📌 My Watchlist</div>', unsafe_allow_html=True)
    db_movies = get_user_movies_from_db(st.session_state.get("user_email", ""))
    
    if not db_movies:
        st.info("Your list is currently empty. Go add some movies from the Home page!")
        if st.button("🎬 Browse Movies Now", use_container_width=True):
            st.session_state.current_page = "Home"
            st.rerun()
    else:
        cols = st.columns(4)
        for idx, movie in enumerate(db_movies):
            info = get_movie_full_info(movie)
            col = cols[idx % 4]
            with col:
                st.markdown(f"""
                <div class="poster-card">
                    <img src="{info['poster_url']}" style="width: 100%; border-radius: 12px; aspect-ratio: 2/3; object-fit: cover; margin-bottom: 0.5rem;" alt="{info['title']}">
                    <div class="movie-title">{info['title']}</div>
                    <div class="movie-meta">
                        <span class="movie-genre">{info['genres_list'][0]}</span>
                        <span class="badge">{info['rating_str']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("ℹ️ Details", key=f"wl_det_{idx}_{info['movie_id']}", use_container_width=True):
                        show_movie_details_dialog(info)
                with c2:
                    if st.button("➖ Remove", key=f"wl_rem_{idx}_{info['movie_id']}", use_container_width=True):
                        trigger_remove_from_list(info['movie_id'], info['title'])

# PAGE 3: HOME & RECOMMENDATIONS
elif st.session_state.selected_movie is None:
    if st.session_state.get("logged_in") and st.session_state.get("user_email"):
        st.markdown(f"""
        <div style="
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255, 159, 10, 0.12);
            border: 1px solid rgba(255, 159, 10, 0.35);
            border-radius: 20px;
            padding: 6px 16px;
            color: #FF9F0A;
            font-weight: 600;
            font-size: 0.92rem;
            margin-bottom: 0.8rem;
            box-shadow: 0 4px 15px rgba(255, 159, 10, 0.15);
        ">
            👤 Logged in as: <span style="color: #FFFFFF; font-weight: 700;">{st.session_state.user_email}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">🔍 Discover Your Next Watch</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Search for a title or pick from the list below to get instant personalized recommendations.</div>', unsafe_allow_html=True)

    all_titles = movies["title"].dropna().astype(str).tolist()
    search_selection = st.selectbox(
        "Search or select a movie:",
        ["-- Choose a Movie --"] + all_titles,
        label_visibility="collapsed"
    )

    n = st.slider("NO. Of Recommendation", min_value=3, max_value=10, value=5)
    
    col_rec1, col_rec2, col_rec3 = st.columns([1, 1.5, 1])
    with col_rec2:
        rec_movie_btn = st.button("🎬 Recommend by Movie", key="rec_movie_btn_main", use_container_width=True)

    st.markdown('<div class="section-title">Explore Movies By Genres</div>', unsafe_allow_html=True)
    category_columns = st.columns(4)
    for index, (icon, category) in enumerate(FILTER_OPTIONS):
        with category_columns[index % 4]:
            if st.button(f"{icon}  {category}", key=f"filter_{category}", use_container_width=True):
                st.session_state.selected_filter = category
                st.session_state.active_recommendation = ("genre", category)
                st.rerun()

    if rec_movie_btn:
        if search_selection != "-- Choose a Movie --":
            st.session_state.active_recommendation = ("movie", search_selection)
            st.rerun()
        else:
            st.info("No movie selected. Select a movie from the dropdown.")

    active_rec = st.session_state.get("active_recommendation")

    if active_rec and active_rec[0] == "movie":
        target_movie = active_rec[1]
        show_loading_circle(f"🎬 Finding top recommendations for '{target_movie}'...")
        recommendations = get_recommendations(target_movie, n)
        if recommendations:
            st.markdown(f"### 🎯 Recommendations for: **{target_movie}**")
            recommendation_cols = st.columns(3)
            for index, movie in enumerate(recommendations):
                with recommendation_cols[index % 3]:
                    st.markdown(f"""
                    <div class="top10-container">
                        <div class="rank-number">{movie['rank']}</div>
                        <div class="rank-poster-box">
                            <img src="{movie['img']}" alt="{movie['title']}">
                        </div>
                    </div>
                    <div class="rec-card-details">
                        <div class="rec-card-title">{movie['title']}</div>
                        <div class="rec-card-meta">{movie['genre']} • {movie['rating']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("ℹ️ Details", key=f"rec_search_det_{index}", use_container_width=True):
                            show_movie_details_dialog(movie)
                    with c2:
                        is_in_list = is_movie_in_user_list(movie)
                        btn_text = "✔ In List" if is_in_list else "➕ Add"
                        if st.button(btn_text, key=f"rec_search_add_{index}", use_container_width=True):
                            trigger_add_to_list(movie)
        else:
            st.info("No recommendations found for this movie.")

    elif active_rec and active_rec[0] == "genre":
        target_genre = active_rec[1]
        show_loading_circle(f"🏷️ Fetching top '{target_genre}' movies...")
        genre_recommendations = recommend_genres(target_genre, n)
        if genre_recommendations:
            st.markdown(f"### 🏷️ Top Recommendations in **{target_genre}** Genre")
            recommendation_cols = st.columns(3)
            for index, movie in enumerate(genre_recommendations):
                with recommendation_cols[index % 3]:
                    st.markdown(f"""
                    <div class="top10-container">
                        <div class="rank-number">{movie['rank']}</div>
                        <div class="rank-poster-box">
                            <img src="{movie['img']}" alt="{movie['title']}">
                        </div>
                    </div>
                    <div class="rec-card-details">
                        <div class="rec-card-title">{movie['title']}</div>
                        <div class="rec-card-meta">{movie['genre']} • {movie['rating']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("ℹ️ Details", key=f"rec_genre_det_{index}", use_container_width=True):
                            show_movie_details_dialog(movie)
                    with c2:
                        is_in_list = is_movie_in_user_list(movie)
                        btn_text = "✔ In List" if is_in_list else "➕ Add"
                        if st.button(btn_text, key=f"rec_genre_add_{index}", use_container_width=True):
                            trigger_add_to_list(movie)
        else:
            st.info(f"No recommendations found for genre '{target_genre}'.")

    else:
        # Initial Display: Popular Movies & Shows
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">🍿 Popular Movies & Shows</div>', unsafe_allow_html=True)

        show_loading_circle("🍿 Loading popular movies...")
        visible_movies = get_filtered_movies(n)

        if visible_movies:
            cols = st.columns(4)
            for idx, movie in enumerate(visible_movies):
                col = cols[idx % 4]
                with col:
                    st.markdown(f"""
                    <div class="poster-card">
                        <img src="{movie['img']}" style="width: 100%; border-radius: 12px; aspect-ratio: 2/3; object-fit: cover; margin-bottom: 0.5rem;" alt="{movie['title']}">
                        <div class="movie-title">{movie['title']}</div>
                        <div class="movie-meta">
                            <span class="movie-genre">{movie['genre']}</span>
                            <span class="badge">{movie['rating']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("ℹ️ Details", key=f"pop_det_{idx}", use_container_width=True):
                            show_movie_details_dialog(movie)
                    with c2:
                        is_in_list = is_movie_in_user_list(movie)
                        btn_text = "✔ List" if is_in_list else "➕ Add"
                        if st.button(btn_text, key=f"pop_add_{idx}", use_container_width=True):
                            trigger_add_to_list(movie)
        else:
            st.info("No movies match your current sidebar filters. Try resetting the filters.")

else:
    # RECOMMENDATIONS VIEW FOR SPECIFIC TARGET MOVIE
    target = st.session_state.selected_movie

    if st.button("← Back to Frontpage"):
        st.session_state.selected_movie = None
        st.rerun()

    st.markdown(f"""
    <div style="margin-top: 1.5rem; margin-bottom: 2rem;">
        <h2 style="font-size: 2.2rem; font-weight: 800; color: #FFFFFF;">Top Recommendations for: <span style="color: #FF9F0A;">{target}</span></h2>
        <p style="color: #94A3B8; font-size: 1rem;">Ranked picks based on content similarity algorithm.</p>
    </div>
    """, unsafe_allow_html=True)

    show_loading_circle(f"✨ Generating similarity recommendations for '{target}'...")
    recommendations = get_recommendations(target)

    if recommendations:
        rec_cols = st.columns(3)
        for idx, movie in enumerate(recommendations):
            with rec_cols[idx % 3]:
                st.markdown(f"""
                <div class="top10-container">
                    <div class="rank-number">{movie['rank']}</div>
                    <div class="rank-poster-box">
                        <img src="{movie['img']}" alt="{movie['title']}">
                    </div>
                </div>
                <div class="rec-card-details">
                    <div class="rec-card-title">{movie['title']}</div>
                    <div class="rec-card-meta">{movie['genre']} • {movie['rating']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("ℹ️ Details", key=f"target_rec_det_{idx}", use_container_width=True):
                        show_movie_details_dialog(movie)
                with c2:
                    is_in_list = is_movie_in_user_list(movie)
                    btn_text = "✔ In List" if is_in_list else "➕ Add"
                    if st.button(btn_text, key=f"target_rec_add_{idx}", use_container_width=True):
                        trigger_add_to_list(movie)
    else:
        st.info("No recommendations found for this movie.")
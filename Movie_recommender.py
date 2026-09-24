import streamlit as st
import pickle
import pandas as pd
import os
import requests
import time
import ast
import random
from dotenv import load_dotenv
from supabase import create_client
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
        client = MongoClient(mongo_uri)
        # Try getting default DB or specified DB name
        db = client.get_default_database("movie_recommender_db")
        return db["users"]
    except Exception:
        try:
            client = MongoClient(mongo_uri)
            db = client["movie_recommender_db"]
            return db["users"]
        except Exception:
            return None

def register_user(email, password, confirm_password):
    """Register a new user with plain text password in MongoDB Atlas."""
    if not email or not password:
        return False, "Email and password are required."
    if password != confirm_password:
        return False, "Passwords do not match."

    users_collection = get_users_collection()
    if users_collection is None:
        return False, "MongoDB connection string not configured. Please set MONGODB_URI in secrets.toml or .env."

    existing_user = users_collection.find_one({"email": email})
    if existing_user:
        return False, "An account with this email already exists."

    # Document schema for plain text password college demo requirement:
    # {
    #   "_id": ObjectId(...),
    #   "email": "user@example.com",
    #   "password": "user-entered-password",
    #   "movies": []
    # }
    user_doc = {
        "email": email,
        "password": password,
        "movies": []
    }
    users_collection.insert_one(user_doc)
    return True, "Account created successfully! Please log in."

def login_user(email, password):
    """Authenticate user strictly using email and plain text password query."""
    if not email or not password:
        return False, "Email and password are required."

    users_collection = get_users_collection()
    if users_collection is None:
        return False, "MongoDB connection string not configured. Please set MONGODB_URI in secrets.toml or .env."

    # Find user using both email and password as specified:
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

def add_movie_to_user_list(email, movie_id, title):
    """Add movie to logged-in user's movies array using $addToSet to prevent duplicates."""
    users_collection = get_users_collection()
    if users_collection is None:
        return False, "MongoDB connection error."

    try:
        m_id = int(movie_id) if movie_id is not None else 0
    except (ValueError, TypeError):
        m_id = movie_id

    # Movie item structure: { "movie_id": 123, "title": "Movie Name" }
    movie_obj = {
        "movie_id": m_id,
        "title": title
    }

    users_collection.update_one(
        {"email": email},
        {"$addToSet": {"movies": movie_obj}}
    )
    return True, "Movie added to your list!"

def remove_movie_from_user_list(email, movie_id, title=None):
    """Remove movie from logged-in user's movies array using $pull."""
    users_collection = get_users_collection()
    if users_collection is None:
        return False, "MongoDB connection error."

    try:
        m_id = int(movie_id) if movie_id is not None else movie_id
    except (ValueError, TypeError):
        m_id = movie_id

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
    return True, "Movie removed from your list!"

def get_user_movies_from_db(email):
    """Fetch movies array for the logged-in user from MongoDB Atlas."""
    if not email:
        return []

    users_collection = get_users_collection()
    if users_collection is None:
        return []

    user = users_collection.find_one({"email": email})
    if user and "movies" in user and isinstance(user["movies"], list):
        return user["movies"]
    return []

@st.dialog("🔐 Account Login / Register")
def show_auth_dialog():
    st.write("Log in or create a demo account to manage your personal watchlist.")
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
                time.sleep(0.5)
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
    """Helper to handle 'Add to My List' action with login popup if unauthenticated."""
    if not st.session_state.get("logged_in"):
        st.session_state.pending_movie = movie
        show_auth_dialog()
    else:
        m_id = movie.get("movie_id")
        title = movie.get("title")
        if m_id is None and 'df' in globals() and df is not None:
            match = df[df["title"] == title]
            if not match.empty:
                m_id = match.iloc[0].get("id", match.iloc[0].get("movie_id"))
        add_movie_to_user_list(st.session_state.user_email, m_id, title)
        st.toast(f"Added '{title}' to My List!", icon="✅")
        st.rerun()

def is_movie_in_user_list(movie):
    """Check if movie is already in logged-in user's list."""
    if not st.session_state.get("logged_in"):
        return False
    user_movies = get_user_movies_from_db(st.session_state.user_email)
    m_id = movie.get("movie_id")
    title = movie.get("title")
    for item in user_movies:
        if item.get("title") == title:
            return True
        if m_id is not None and item.get("movie_id") == m_id:
            return True
    return False

movie_dict = pickle.load(open('movie_dict.pkl','rb'))
movies = pd.DataFrame(movie_dict)
similarity = pickle.load(open('similarity.pkl','rb'))

session = requests.session()
PLACEHOLDER_IMAGE = "https://placehold.co/300x450/111827/F8FAFC?text=Poster+Unavailable"

SUPABASE_POSTER_URL = (
    "https://lfkyggfvcmcdqmgjvlfj.supabase.co"
    "/storage/v1/object/public/movie-posters"
)

@st.cache_data
def fetch_poster(movie_id):
    try:
        poster_url = (f"{SUPABASE_POSTER_URL}/{movie_id}.jpg")
        return poster_url
    except Exception:
        pass
    return PLACEHOLDER_IMAGE

def recommend(movie, n):
    rnd = random.randint(1,10)
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
    page_title="MoviX | Discover & Recommend Movies",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_data
def load_data():
    credits = pd.read_csv("tmdb_5000_credits.csv")
    movies_file = pd.read_csv("tmdb_5000_movies.csv")

    df = movies_file.merge(credits[["movie_id", "cast"]], left_on="id", right_on="movie_id")

    def get_actors(cast_str, limit=1):
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



# 1. Page Configuration

# 2. Custom CSS & HTML: Premium Cinematic UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    /* Custom Webkit Scrollbar */
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

    /* Base App Styling - Pitch Dark Flixet Theme */
    .stApp {
        background: #09090B !important;
        color: #F8FAFC;
    }
    /* Prevent screen dimming when rerunning / selecting dropdown option */
    .stApp[data-test-script-state="running"],
    .stApp[data-test-script-state="running"] *,
    [data-test-script-state="running"] [data-testid="stAppViewContainer"],
    [data-test-script-state="running"] [data-testid="stMain"],
    [data-test-script-state="running"] [data-testid="stMainBlockContainer"],
    [data-test-script-state="running"] .block-container,
    [data-test-script-state="running"] .element-container,
    div[data-test-script-state="running"] {
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
        background: radial-gradient(circle, rgba(245, 158, 11, 0.08) 0%, transparent 70%);
        animation: floatOrb2 30s infinite ease-in-out reverse;
    }

    /* Sidebar Dark Styling */
    section[data-testid="stSidebar"] {
        background-color: rgba(18, 18, 22, 0.7) !important;
        backdrop-filter: blur(30px);
        -webkit-backdrop-filter: blur(30px);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 10px 0 30px rgba(0, 0, 0, 0.8);
    }

    /* Streamlit Content Depth Positioning */
    .block-container {
        position: relative;
        z-index: 1;
        padding-top: 6rem !important;
        padding-bottom: 5rem !important;
    }

    /* Fixed Glass Navbar - Flixet Design */
    .custom-navbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 70px;
        background: rgba(9, 9, 11, 0.85);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 3rem 0 4.5rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
    }
    .nav-left-group {
        display: flex;
        align-items: center;
        gap: 2.5rem;
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
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, #FF9F0A 0%, #F59E0B 100%);
        border-radius: 9px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 15px rgba(255, 159, 10, 0.4);
    }
    .brand-sq-inner {
        width: 12px;
        height: 12px;
        background: #FFFFFF;
        border-radius: 3px;
    }
    .nav-pill-box {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        background: #141416;
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 4px 6px;
        border-radius: 30px;
    }
    .nav-item-link {
        font-size: 0.9rem;
        font-weight: 500;
        color: #94A3B8;
        padding: 6px 14px;
        border-radius: 20px;
        transition: all 0.3s;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .nav-item-link.active {
        background: rgba(255, 159, 10, 0.15);
        border: 1px solid #FF9F0A;
        color: #FF9F0A;
        font-weight: 700;
    }
    .nav-item-link:hover:not(.active) {
        color: #FFFFFF;
    }
    .nav-right-group {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .surprise-pill {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 6px 16px;
        color: #FFFFFF;
        font-size: 0.85rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
    }
    .search-pill-fake {
        background: #141416;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 6px 16px;
        color: #64748B;
        font-size: 0.85rem;
        display: flex;
        align-items: center;
        gap: 8px;
        width: 220px;
    }

    /* Section Header Flex Wrapper */
    .section-header-wrap {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 1.5rem;
    }
    .section-icon-badge {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        border: 1.5px solid rgba(255, 159, 10, 0.5);
        background: rgba(255, 159, 10, 0.1);
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .section-title-main {
        font-size: 1.6rem;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }
    .section-subtitle-main {
        font-size: 0.9rem;
        color: #8E8E93;
        font-weight: 400;
    }

    /* Typography */
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
        margin-bottom: 2rem;
        font-weight: 400;
    }

    /* ===================================================
       RECOMMENDED MOVIES - NETFLIX / FLIXET RANK STYLING
    =================================================== */
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

    /* Stroke Outline Number */
    .rank-number {
        position: absolute;
        right: calc(50% + 25px);
        bottom: 5px;
        font-size: 5.5rem;
        font-family: 'Outfit', 'Arial Black', Impact, sans-serif;
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

    /* Movie Poster Box */
    .rank-poster-box {
        position: relative;
        width: 180px;
        height: 210px;
        flex-shrink: 0;
        border-radius: 12px;
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
    .rank-poster-box::after {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(to top, rgba(255, 159, 10, 0.3), transparent 60%);
        opacity: 0;
        transition: opacity 0.4s;
        pointer-events: none;
    }
    .top10-container:hover .rank-poster-box::after {
        opacity: 1;
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

    /* Details Below Poster */
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

    /* Standard Frontpage Glass Cards */
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
    .movie-actor {
        font-size: 0.85rem;
        color: #8E8E93;
        margin-top: 0.8rem;
        display: flex;
        align-items: center;
        gap: 6px;
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

    /* Category Buttons (Browse by Genre) */
    div[data-testid="column"] .stButton > button {
        background: #141416;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        color: #FFFFFF;
        font-weight: 700;
        font-size: 1rem;
        padding: 1.2rem 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
    }
    div[data-testid="column"] .stButton > button:hover {
        background: #1C1C20;
        border-color: #FF9F0A;
        color: #FF9F0A;
        box-shadow: 0 8px 25px rgba(255, 159, 10, 0.25);
        transform: translateY(-3px);
    }

    /* Primary Buttons */
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
        font-size: 1rem !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.7rem 1.6rem !important;
        box-shadow: 0 4px 18px rgba(255, 159, 10, 0.35) !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
        max-width: 320px !important;
        margin: 0 auto !important;
        white-space: nowrap !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        max-width: 100% !important;
        color: #FFFFFF !important;
        background: #141416 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(255, 159, 10, 0.5);
        color: #000000;
        border: none;
    }
    .stButton > button:active {
        transform: translateY(1px);
    }
    
    /* Selectbox styling & dimming removal */
    div[data-baseweb="select"] {
        opacity: 1 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #141416;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        color: white;
        opacity: 1 !important;
    }
    div[data-baseweb="popover"],
    div[data-baseweb="menu"] {
        opacity: 1 !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
    }
    div[data-baseweb="backdrop"] {
        background: transparent !important;
        opacity: 0 !important;
        pointer-events: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
    }
    
    /* Header & Sidebar Toggle Controls (Ensures toggle button is visible on deployed app) */
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    div[data-testid="stDecoration"] { display: none !important; }

    header[data-testid="stHeader"], header {
        visibility: visible !important;
        background: transparent !important;
        z-index: 100000 !important;
        pointer-events: none !important;
    }

    header[data-testid="stHeader"] *, header * {
        pointer-events: auto !important;
    }

    /* Style sidebar toggle button (collapsed control & sidebar collapse button) */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    button[data-testid="baseButton-header"],
    button[data-testid="stSidebarCollapseButton"],
    button[aria-label="Expand sidebar"],
    button[aria-label="Collapse sidebar"] {
        visibility: visible !important;
        display: flex !important;
        z-index: 100001 !important;
        color: #FF9F0A !important;
        background: rgba(20, 20, 25, 0.85) !important;
        border: 1px solid rgba(255, 159, 10, 0.4) !important;
        border-radius: 10px !important;
        padding: 4px 8px !important;
        transition: all 0.3s ease !important;
    }

    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg,
    button[aria-label="Expand sidebar"] svg,
    button[aria-label="Collapse sidebar"] svg {
        fill: #FF9F0A !important;
        color: #FF9F0A !important;
        stroke: #FF9F0A !important;
    }

    [data-testid="collapsedControl"]:hover,
    [data-testid="stSidebarCollapseButton"]:hover {
        background: rgba(255, 159, 10, 0.25) !important;
        border-color: #FF9F0A !important;
        transform: scale(1.05);
        box-shadow: 0 0 12px rgba(255, 159, 10, 0.4) !important;
    }

    /* ===================================================
       RESPONSIVE MOBILE & TABLET STYLING
    =================================================== */
    @media (max-width: 768px) {
        .custom-navbar {
            padding: 0 1rem !important;
            height: 60px !important;
        }
        .nav-brand {
            font-size: 1.25rem !important;
        }
        .brand-sq {
            width: 26px !important;
            height: 26px !important;
        }
        .block-container {
            padding-top: 4.8rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            padding-bottom: 3rem !important;
        }
        .section-title {
            font-size: 1.35rem !important;
        }
        .section-subtitle {
            font-size: 0.88rem !important;
            margin-bottom: 1.2rem !important;
        }
        .stButton > button {
            max-width: 100% !important;
            width: 100% !important;
            font-size: 0.9rem !important;
            padding: 0.65rem 1rem !important;
        }
        div[data-testid="column"] .stButton > button {
            padding: 0.75rem 0.5rem !important;
            font-size: 0.85rem !important;
            border-radius: 12px !important;
        }
        .top10-container {
            height: 190px !important;
        }
        .rank-number {
            font-size: 3.8rem !important;
            right: calc(50% + 15px) !important;
            bottom: 2px !important;
            -webkit-text-stroke: 1.8px #FF9F0A !important;
        }
        .rank-poster-box {
            width: 130px !important;
            height: 165px !important;
            border-radius: 10px !important;
        }
        .rec-card-details {
            width: 130px !important;
            margin-top: 0.5rem !important;
        }
        .rec-card-title {
            font-size: 0.9rem !important;
        }
        .rec-card-meta {
            font-size: 0.75rem !important;
        }
        .poster-card {
            padding: 0.75rem !important;
            border-radius: 12px !important;
        }
        .movie-title {
            font-size: 0.95rem !important;
        }
        .movie-genre, .badge {
            font-size: 0.75rem !important;
            padding: 3px 8px !important;
        }
    }

    @media (max-width: 480px) {
        .custom-navbar {
            padding: 0 0.8rem !important;
        }
        .section-title {
            font-size: 1.2rem !important;
        }
        .rank-number {
            font-size: 3.2rem !important;
            right: calc(50% + 10px) !important;
        }
        .rank-poster-box, .rec-card-details {
            width: 115px !important;
        }
        .rank-poster-box {
            height: 145px !important;
        }
        div[data-testid="column"] {
            min-width: 100% !important;
        }
    }
</style>
<div class="bg-orb-1"></div>
<div class="bg-orb-2"></div>
""", unsafe_allow_html=True)

# 3. Session State Initialization
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

# 4. Sidebar Filters & Navigation
with st.sidebar:
    st.markdown("## 🧭 Navigation")
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.current_page = "Home"
        st.session_state.selected_movie = None
        st.session_state.active_recommendation = None
        st.rerun()

    # Count movies from MongoDB for logged-in user
    user_movies_count = len(get_user_movies_from_db(st.session_state.user_email)) if st.session_state.get("logged_in") else 0
    if st.button(f"📌 My List ({user_movies_count})", use_container_width=True):
        st.session_state.current_page = "My List"
        st.rerun()

    st.markdown("---")
    st.markdown("## 👤 Account")
    if st.session_state.get("logged_in"):
        st.markdown(f"**Logged in as:**\n`{st.session_state.user_email}`")
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.pending_movie = None
            st.toast("Logged out successfully.")
            st.rerun()
    else:
        st.info("Log in to save movies to your personal list.")
        if st.button("🔑 Log In / Register", use_container_width=True):
            show_auth_dialog()

    st.markdown("---")
    st.markdown("## ⚙️ Filter Options")
    if st.button("🔄 Reset Filters", use_container_width=True):
        st.session_state.selected_filter = "All"
        st.session_state.selected_movie = None
        st.session_state.active_recommendation = None
        st.rerun()

def filter_movies(movie_list):
    selected_filter = st.session_state.selected_filter
    if selected_filter == "All":
        return movie_list
    if selected_filter == "Top Rated":
        return [m for m in movie_list if float(m["rating"].replace("★", "").strip()) >= 8]
    return [m for m in movie_list if selected_filter.lower() in m["genre"].lower()]

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
                in {genre.replace("-", " ").lower() for genre in genres}
            )
        ].sort_values(by="popularity", ascending=False).head(limit)

    return [
        {
            "title": row["title"],
            "genre": row["genres_list"][0] if row["genres_list"] else "Unknown",
            "actor": row["actors"][0] if row["actors"] else "Unknown",
            "rating": f"★ {row['vote_average']:.1f}",
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

# 5. Header Bar (Fixed Navbar)
st.markdown("""
<div class="custom-navbar">
    <div class="nav-brand">
        MoviX
    </div>
</div>
""", unsafe_allow_html=True)

# 6. Main Content View
if st.session_state.current_page == "My List":
    st.markdown('<div class="section-title">📌 My Watchlist</div>', unsafe_allow_html=True)
    if not st.session_state.get("logged_in"):
        st.warning("🔒 Only logged-in users can access their personal movie list. Please log in or register.")
        if st.button("🔑 Log In / Register Now", use_container_width=True):
            show_auth_dialog()
    else:
        db_movies = get_user_movies_from_db(st.session_state.user_email)
        if not db_movies:
            st.info("Your list is currently empty. Go add some movies from the Home page!")
        else:
            cols = st.columns(4)
            for idx, movie in enumerate(db_movies):
                m_id = movie.get("movie_id")
                m_title = movie.get("title", "Movie")

                df_match = df[df['title'] == m_title] if 'df' in globals() and df is not None else pd.DataFrame()
                if df_match.empty and m_id:
                    df_match = df[df['id'] == m_id] if 'df' in globals() and df is not None else pd.DataFrame()

                if not df_match.empty:
                    row = df_match.iloc[0]
                    genre_str = row['genres_list'][0] if ('genres_list' in row and isinstance(row['genres_list'], list) and len(row['genres_list']) > 0) else "Movie"
                    rating_str = f"★ {row['vote_average']:.1f}" if ('vote_average' in row and pd.notnull(row['vote_average'])) else "★ N/A"
                    img_url = fetch_poster(row.get('id', m_id))
                else:
                    genre_str = "Movie"
                    rating_str = "★ N/A"
                    img_url = fetch_poster(m_id) if m_id else PLACEHOLDER_IMAGE

                col = cols[idx % 4]
                with col:
                    st.markdown(f"""
                    <div class="poster-card">
                        <img src="{img_url}" style="width: 100%; border-radius: 12px; aspect-ratio: 2/3; object-fit: cover; margin-bottom: 0.5rem;" alt="{m_title}">
                        <div class="movie-title">{m_title}</div>
                        <div class="movie-meta">
                            <span class="movie-genre">{genre_str}</span>
                            <span class="badge">{rating_str}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("➖ Remove", key=f"remove_db_{idx}", use_container_width=True):
                        remove_movie_from_user_list(st.session_state.user_email, m_id, m_title)
                        st.toast(f"Removed '{m_title}' from your list.")
                        st.rerun()

elif st.session_state.selected_movie is None:
    # --- FRONTPAGE VIEW ---
    st.markdown('<div class="section-title">🔍 Discover Your Next Watch</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Search for a title or pick from the list below to get instant personalized recommendations.</div>', unsafe_allow_html=True)

    all_titles = movies["title"].dropna().astype(str).tolist()
    search_selection = st.selectbox(
        "Search or select a movie:",
        ["-- Choose a Movie --"] + all_titles,
        label_visibility="collapsed"
    )

    n = st.slider("NO. Of Recommendation", min_value=3, max_value=10)
    
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
                    is_in_list = is_movie_in_user_list(movie)
                    btn_text = "✔ In List" if is_in_list else "➕ Add to List"
                    if st.button(btn_text, key=f"rec_search_add_{index}", use_container_width=True):
                        trigger_add_to_list(movie)
        else:
            st.info("No recommendations found for this movie.")

    elif active_rec and active_rec[0] == "genre":
        target_genre = active_rec[1]
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
                    is_in_list = is_movie_in_user_list(movie)
                    btn_text = "✔ In List" if is_in_list else "➕ Add to List"
                    if st.button(btn_text, key=f"rec_genre_add_{index}", use_container_width=True):
                        trigger_add_to_list(movie)
        else:
            st.info(f"No recommendations found for genre '{target_genre}'.")

    else:
        # Initial Display: Show Popular Movies & Shows
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">🍿 Popular Movies & Shows</div>', unsafe_allow_html=True)

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
                        <div class="movie-actor">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                            {movie['actor']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        if st.button("Recommend", key=f"grid_btn_{idx}", use_container_width=True):
                            st.session_state.selected_movie = movie["title"]
                            st.rerun()
                    with col2:
                        is_in_list = is_movie_in_user_list(movie)
                        btn_icon = "✔" if is_in_list else "➕"
                        if st.button(btn_icon, key=f"add_list_{idx}", use_container_width=True, help="Add to My List"):
                            trigger_add_to_list(movie)
        else:
            st.info("No movies match your current sidebar filters. Try resetting the filters.")

else:
    # --- RECOMMENDATIONS VIEW (NETFLIX STROKE RANK NUMBERS) ---
    target = st.session_state.selected_movie

    if st.button("← Back to Frontpage"):
        st.session_state.selected_movie = None
        st.rerun()

    st.markdown(f"""
    <div style="margin-top: 1.5rem; margin-bottom: 2rem;">
        <h2 style="font-size: 2.5rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.02em;">Top Recommendations for: <span style="background: linear-gradient(135deg, #A5B4FC 0%, #E0E7FF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{target}</span></h2>
        <p style="color: #94A3B8; font-size: 1.1rem;">Ranked picks based on your selected title.</p>
    </div>
    """, unsafe_allow_html=True)

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
                        <div class="recently-added-badge">Recently added</div>
                    </div>
                </div>
                <div class="rec-card-details">
                    <div class="rec-card-title">{movie['title']}</div>
                    <div class="rec-card-meta">{movie['genre']} • {movie['rating']}</div>
                </div>
                """, unsafe_allow_html=True)
                is_in_list = is_movie_in_user_list(movie)
                btn_text = "✔ In List" if is_in_list else "➕ Add to List"
                if st.button(btn_text, key=f"rec_add_list_{idx}", use_container_width=True):
                    trigger_add_to_list(movie)
    else:
        st.info("No recommendations found for this movie.")
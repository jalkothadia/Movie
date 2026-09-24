import streamlit as st


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="How Movie Recommendation Works",
    page_icon="🎬",
    layout="wide"
)


# =========================================================
# CUSTOM CSS: Pitch Dark Cinematic Flixet Theme
# =========================================================

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

    .block-container {
        position: relative;
        z-index: 1;
        padding-top: 3rem !important;
        padding-bottom: 5rem !important;
    }

    /* Typography & Titles */
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0.5rem;
        color: #FFFFFF;
        letter-spacing: -0.02em;
    }

    .subtitle {
        text-align: center;
        font-size: 1.1rem;
        color: #8E8E93;
        margin-bottom: 2.5rem;
        font-weight: 400;
    }

    h1, h2, h3, h4, h5, h6 {
        color: #FFFFFF !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
    }

    /* Step Cards Styling */
    .step-card {
        padding: 1.8rem;
        border-radius: 16px;
        background: #141416 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        margin-bottom: 1.5rem;
        color: #F8FAFC !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        transition: all 0.3s ease;
    }

    .step-card:hover {
        border-color: #FF9F0A !important;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.8), 0 0 20px rgba(255, 159, 10, 0.15);
        transform: translateY(-3px);
    }

    .step-number {
        font-size: 0.9rem;
        font-weight: 800;
        color: #FF9F0A;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        background: rgba(255, 159, 10, 0.15);
        border: 1px solid rgba(255, 159, 10, 0.3);
        padding: 4px 12px;
        border-radius: 20px;
        display: inline-block;
        margin-bottom: 0.8rem;
    }

    .step-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 0.8rem;
    }

    .step-text {
        font-size: 1.05rem;
        line-height: 1.7;
        color: #CBD5E1;
    }

    .step-text ul {
        margin-top: 0.5rem;
        padding-left: 1.2rem;
    }

    .step-text li {
        margin-bottom: 0.4rem;
        color: #E2E8F0;
    }

    /* Flow Diagrams & Code Boxes */
    .code-box {
        background: #141416 !important;
        border: 1px solid rgba(255, 159, 10, 0.3) !important;
        color: #FF9F0A !important;
        padding: 1.5rem;
        border-radius: 16px;
        font-family: 'Outfit', monospace;
        font-size: 1rem;
        line-height: 1.8;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }

    /* Tables */
    div[data-testid="stTable"] table {
        background-color: #141416 !important;
        color: #F8FAFC !important;
        border-radius: 12px !important;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
    }

    div[data-testid="stTable"] th {
        background-color: rgba(255, 159, 10, 0.15) !important;
        color: #FF9F0A !important;
        font-weight: 700 !important;
        border-bottom: 1px solid rgba(255, 159, 10, 0.3) !important;
    }

    div[data-testid="stTable"] td {
        border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
        color: #CBD5E1 !important;
    }

    /* Info & Code Containers */
    div[data-testid="stAlert"] {
        background: rgba(255, 159, 10, 0.1) !important;
        border: 1px solid rgba(255, 159, 10, 0.3) !important;
        color: #F8FAFC !important;
        border-radius: 12px !important;
    }

    div[data-testid="stCodeBlock"] {
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        background: #141416 !important;
    }

    /* Responsive Mobile Media Queries */
    @media (max-width: 768px) {
        .main-title {
            font-size: 1.8rem !important;
        }
        .subtitle {
            font-size: 0.95rem !important;
            margin-bottom: 1.8rem !important;
        }
        .step-card {
            padding: 1.2rem !important;
            border-radius: 12px !important;
        }
        .step-title {
            font-size: 1.2rem !important;
        }
        .step-text {
            font-size: 0.95rem !important;
        }
        .block-container {
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
    }

    /* Hide default Streamlit elements without hiding sidebar toggle button */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {
        background: transparent !important;
        z-index: 100001 !important;
        pointer-events: none !important;
    }
    [data-testid="stToolbar"] {
        visibility: hidden !important;
        pointer-events: none !important;
    }
    [data-testid="stHeaderCollapsedControl"],
    [data-testid="stSidebarCollapseButton"] {
        visibility: visible !important;
        display: flex !important;
        pointer-events: auto !important;
        z-index: 100002 !important;
    }
    [data-testid="stHeaderCollapsedControl"] button,
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stHeaderCollapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
        stroke: #FFFFFF !important;
    }
</style>
<div class="bg-orb-1"></div>
<div class="bg-orb-2"></div>
""", unsafe_allow_html=True)


# =========================================================
# TITLE
# =========================================================

st.markdown(
    '<div class="main-title">🎬 How Movie Recommendation Works</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Understanding the Machine Learning process behind this Movie Recommendation System'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# INTRODUCTION
# =========================================================

st.header("📌 What is a Movie Recommendation System?")

st.write("""
A Movie Recommendation System is a system that suggests movies
to users based on the characteristics or similarity of movies.

In this project, when the user selects a movie, the system finds
other movies that are most similar to the selected movie and
recommends them.
""")


# =========================================================
# COMPLETE FLOW
# =========================================================

st.header("🔄 Complete Recommendation Process")

st.markdown("""
<div class="code-box">

Movie Dataset
        ↓
Data Preprocessing
        ↓
Movie Features
        ↓
Feature Vectorization
        ↓
Similarity Calculation
        ↓
Similarity Matrix
        ↓
User Selects a Movie
        ↓
Find Selected Movie
        ↓
Compare Similarity Scores
        ↓
Sort Movies by Similarity
        ↓
Select Top N Movies
        ↓
Fetch Poster from Supabase
        ↓
Display Recommendations

</div>
""", unsafe_allow_html=True)


# =========================================================
# STEP 1
# =========================================================

st.header("1️⃣ Movie Dataset")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 1</div>

<div class="step-title">
📂 Movie Dataset
</div>

<div class="step-text">

The first step is collecting information about movies.

The dataset contains information such as:

<ul>
<li>Movie ID</li>
<li>Movie Title</li>
<li>Genres</li>
<li>Actors / Cast</li>
<li>Other movie-related information</li>
</ul>

This information is used to understand the characteristics
of each movie.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# STEP 2
# =========================================================

st.header("2️⃣ Data Preprocessing")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 2</div>

<div class="step-title">
🧹 Data Preprocessing
</div>

<div class="step-text">

Before applying the recommendation algorithm, the movie data
needs to be cleaned and prepared.

For example, information such as genres and cast is extracted
from the original dataset and converted into a format that can
be processed by the machine learning algorithm.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# STEP 3
# =========================================================

st.header("3️⃣ Movie Features")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 3</div>

<div class="step-title">
🏷️ Movie Features
</div>

<div class="step-text">

The system uses important information about each movie as its
features.

For example:

<br>

<b>Movie A</b>

<br>
Genre: Action, Adventure
<br>
Actors: Actor 1, Actor 2

<br><br>

These features help the system determine which movies have
similar characteristics.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# STEP 4
# =========================================================

st.header("4️⃣ Feature Vectorization")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 4</div>

<div class="step-title">
🔢 Convert Movie Information into Numbers
</div>

<div class="step-text">

Machine learning algorithms work with numerical data.

Therefore, the movie features are converted into numerical
representations called vectors.

Movies with similar features will have similar vector
representations.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# STEP 5
# =========================================================

st.header("5️⃣ Calculate Movie Similarity")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 5</div>

<div class="step-title">
📊 Similarity Matrix
</div>

<div class="step-text">

The system calculates a similarity score between movies.

The similarity matrix stores these scores.

A higher similarity score means that two movies are more similar
according to the features used by the recommendation model.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# SIMILARITY EXAMPLE
# =========================================================

st.subheader("Example of Similarity Scores")

similarity_data = {
    "Movie": [
        "Movie A",
        "Movie B",
        "Movie C",
        "Movie D",
        "Movie E"
    ],
    "Similarity Score": [
        1.00,
        0.91,
        0.82,
        0.65,
        0.42
    ]
}

st.table(similarity_data)

st.info("""
A higher similarity score means the movie is more similar
to the selected movie according to the recommendation model.
""")


# =========================================================
# STEP 6
# =========================================================

st.header("6️⃣ User Selects a Movie")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 6</div>

<div class="step-title">
🎯 User Input
</div>

<div class="step-text">

The user selects a movie from the application.

For example:

<br>

<b>Selected Movie:</b> Avatar

<br><br>

The system finds the position/index of Avatar in the movie
dataset.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# STEP 7
# =========================================================

st.header("7️⃣ Find Similar Movies")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 7</div>

<div class="step-title">
🔍 Compare Similarity Scores
</div>

<div class="step-text">

The system gets the similarity scores corresponding to the
selected movie.

It then compares the selected movie with all other movies.

The selected movie itself is removed from the recommendation
list.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# CODE EXAMPLE
# =========================================================

st.subheader("Core Recommendation Logic")

st.code("""
movie_index = matches[0]

distance = similarity[movie_index]

movie_list = sorted(
    list(enumerate(distance)),
    reverse=True,
    key=lambda x: x[1]
)[1:n+1]
""", language="python")

st.write("""
The code sorts the movies according to their similarity scores
and selects the top N similar movies.
""")


# =========================================================
# STEP 8
# =========================================================

st.header("8️⃣ Select Top Recommendations")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 8</div>

<div class="step-title">
🏆 Top N Movies
</div>

<div class="step-text">

After sorting the similarity scores, the system selects the
movies with the highest similarity scores.

For example, if the user asks for 5 recommendations, the
system returns the top 5 similar movies.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# STEP 9
# =========================================================

st.header("9️⃣ Fetch Movie Posters")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 9</div>

<div class="step-title">
🖼️ Supabase Poster Storage
</div>

<div class="step-text">

The movie posters are stored in Supabase Storage.

Each poster is stored using the movie ID.

For example:

<br><br>

<b>Movie ID:</b> 19995

<br>

<b>Poster:</b> 19995.jpg

<br><br>

When a recommendation is generated, the application creates
the Supabase URL using the movie ID and displays the poster.

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# SUPABASE FLOW
# =========================================================

st.code("""
Movie ID
   ↓
19995
   ↓
Supabase Storage
   ↓
movie-posters/19995.jpg
   ↓
Poster URL
   ↓
Streamlit
   ↓
Display Poster
""", language="text")


# =========================================================
# STEP 10
# =========================================================

st.header("🔟 Display Recommendations")

st.markdown("""
<div class="step-card">

<div class="step-number">STEP 10</div>

<div class="step-title">
🎬 Final Recommendations
</div>

<div class="step-text">

Finally, the application displays the recommended movies to
the user.

Each recommendation can contain:

<ul>
<li>Movie title</li>
<li>Movie poster</li>
<li>Genre</li>
<li>Rating</li>
<li>Cast information</li>
</ul>

</div>

</div>
""", unsafe_allow_html=True)


# =========================================================
# FINAL FLOW
# =========================================================

st.header("🚀 Final Working Flow")

st.markdown("""
<div class="code-box">

👤 User
   │
   ▼
🎬 Selects a Movie
   │
   ▼
🔍 Find Movie in Dataset
   │
   ▼
📊 Get Similarity Scores
   │
   ▼
↕️ Sort Similarity Scores
   │
   ▼
🏆 Select Top N Movies
   │
   ▼
🖼️ Get Posters from Supabase
   │
   ▼
🎬 Display Recommendations

</div>
""", unsafe_allow_html=True)


# =========================================================
# PROJECT SUMMARY
# =========================================================

st.header("📚 Project Summary")

st.success("""
This project uses a content-based movie recommendation approach.
The system analyzes movie information, calculates similarity
between movies, and recommends movies that are most similar to
the movie selected by the user.
""")
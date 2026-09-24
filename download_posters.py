import os
import time
import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm




# ============================================================
# 1. LOAD TMDB API KEY
# ============================================================

load_dotenv()

TMDB_API_KEY = os.getenv('TMDB_API_KEY')

if not TMDB_API_KEY:
    print("❌ ERROR: TMDB_API_KEY not found.")
    print("Please create a .env file and add:")
    print("TMDB_API_KEY")
    exit()


# ============================================================
# 2. SETTINGS
# ============================================================

CSV_FILE = "tmdb_5000_movies.csv"

POSTER_FOLDER = "posters"

TMDB_API_URL = "https://api.themoviedb.org/3/movie"

TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"


# ============================================================
# 3. CREATE POSTER FOLDER
# ============================================================

os.makedirs(POSTER_FOLDER, exist_ok=True)

print("📁 Poster folder:")
print(os.path.abspath(POSTER_FOLDER))


# ============================================================
# 4. LOAD CSV
# ============================================================

try:

    df = pd.read_csv(CSV_FILE)

except FileNotFoundError:

    print(f"\n❌ File not found: {CSV_FILE}")
    print("Make sure your CSV is in the same folder as this script.")
    exit()


print("\n========================================")
print("DATASET INFORMATION")
print("========================================")

print(f"Total movies: {len(df)}")


# ============================================================
# 5. CHECK ID COLUMN
# ============================================================

if "id" not in df.columns:

    print("\n❌ ERROR: 'id' column not found in CSV.")

    print("\nAvailable columns:")
    print(df.columns.tolist())

    exit()


# ============================================================
# 6. CREATE REQUEST SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "MovieRecommendationProject/1.0"
})


# ============================================================
# 7. DOWNLOAD POSTER FUNCTION
# ============================================================

def download_poster(movie_id):

    """
    Download one movie poster.

    Returns:
        downloaded
        already_exists
        no_poster
        api_error
        image_error
        network_error
        error
    """

    # --------------------------------------------------------
    # Local poster filename
    # --------------------------------------------------------

    local_file = os.path.join(
        POSTER_FOLDER,
        f"{movie_id}.jpg"
    )


    # --------------------------------------------------------
    # Check if poster already exists
    # --------------------------------------------------------

    if os.path.exists(local_file):

        return "already_exists"


    # --------------------------------------------------------
    # TMDB movie details API
    # --------------------------------------------------------

    api_url = (
        f"{TMDB_API_URL}/{movie_id}"
        f"?api_key={TMDB_API_KEY}"
    )


    try:

        # ----------------------------------------------------
        # Get movie information
        # ----------------------------------------------------

        response = session.get(
            api_url,
            timeout=10
        )


        # ----------------------------------------------------
        # Check API response
        # ----------------------------------------------------

        if response.status_code != 200:

            return "api_error"


        # ----------------------------------------------------
        # Convert response to JSON
        # ----------------------------------------------------

        data = response.json()


        # ----------------------------------------------------
        # Get poster path
        # ----------------------------------------------------

        poster_path = data.get("poster_path")


        # ----------------------------------------------------
        # Movie doesn't have a poster
        # ----------------------------------------------------

        if not poster_path:

            return "no_poster"


        # ----------------------------------------------------
        # Create poster URL
        # ----------------------------------------------------

        poster_url = (
            TMDB_IMAGE_URL
            + poster_path
        )


        # ----------------------------------------------------
        # Download poster image
        # ----------------------------------------------------

        poster_response = session.get(
            poster_url,
            timeout=10
        )


        # ----------------------------------------------------
        # Check image response
        # ----------------------------------------------------

        if poster_response.status_code != 200:

            return "image_error"


        # ----------------------------------------------------
        # Save image locally
        # ----------------------------------------------------

        with open(local_file, "wb") as file:

            file.write(
                poster_response.content
            )


        return "downloaded"


    # --------------------------------------------------------
    # Network error
    # --------------------------------------------------------

    except requests.exceptions.RequestException:

        return "network_error"


    # --------------------------------------------------------
    # Other error
    # --------------------------------------------------------

    except Exception as e:

        print(
            f"\nError downloading movie {movie_id}: {e}"
        )

        return "error"


# ============================================================
# 8. COUNTERS
# ============================================================

downloaded_count = 0

already_exists_count = 0

no_poster_count = 0

api_error_count = 0

image_error_count = 0

network_error_count = 0

other_error_count = 0


# ============================================================
# 9. DOWNLOAD ALL POSTERS
# ============================================================

print("\n========================================")
print("STARTING POSTER DOWNLOAD")
print("========================================")

print("This may take some time for the first run.\n")


for movie_id in tqdm(
    df["id"],
    desc="Downloading posters",
    unit="movie"
):

    # --------------------------------------------------------
    # Make sure ID is valid
    # --------------------------------------------------------

    if pd.isna(movie_id):

        continue


    try:

        movie_id = int(movie_id)

    except:

        continue


    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    result = download_poster(movie_id)


    # --------------------------------------------------------
    # Count result
    # --------------------------------------------------------

    if result == "downloaded":

        downloaded_count += 1


    elif result == "already_exists":

        already_exists_count += 1


    elif result == "no_poster":

        no_poster_count += 1


    elif result == "api_error":

        api_error_count += 1


    elif result == "image_error":

        image_error_count += 1


    elif result == "network_error":

        network_error_count += 1


    else:

        other_error_count += 1


    # --------------------------------------------------------
    # Small delay
    # --------------------------------------------------------

    time.sleep(0.1)


# ============================================================
# 10. FINAL SUMMARY
# ============================================================

print("\n")
print("========================================")
print("          DOWNLOAD COMPLETE")
print("========================================")

print(f"Total movies       : {len(df)}")

print(f"Downloaded         : {downloaded_count}")

print(f"Already existed    : {already_exists_count}")

print(f"No poster          : {no_poster_count}")

print(f"API errors         : {api_error_count}")

print(f"Image errors       : {image_error_count}")

print(f"Network errors     : {network_error_count}")

print(f"Other errors       : {other_error_count}")

print("----------------------------------------")

print("Posters location:")

print(
    os.path.abspath(POSTER_FOLDER)
)

print("========================================")
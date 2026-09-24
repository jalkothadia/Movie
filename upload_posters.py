import os
from supabase import create_client
from dotenv import load_dotenv


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# ==========================================
# SETTINGS
# ==========================================

BUCKET_NAME = "movie-posters"

POSTER_FOLDER = "posters"


# ==========================================
# CHECK SETTINGS
# ==========================================

if not SUPABASE_URL:
    print("❌ SUPABASE_URL not found in .env")
    exit()

if not SUPABASE_KEY:
    print("❌ SUPABASE_KEY not found in .env")
    exit()


# ==========================================
# CONNECT TO SUPABASE
# ==========================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ==========================================
# CHECK POSTER FOLDER
# ==========================================

if not os.path.exists(POSTER_FOLDER):

    print("❌ posters folder not found")

    exit()


# ==========================================
# GET FILES
# ==========================================

files = [
    file
    for file in os.listdir(POSTER_FOLDER)
    if file.lower().endswith(".jpg")
]


print("====================================")
print("SUPABASE POSTER UPLOAD")
print("====================================")

print(f"Posters found: {len(files)}")


# ==========================================
# UPLOAD
# ==========================================

uploaded = 0
failed = 0


for index, filename in enumerate(files, start=1):

    local_path = os.path.join(
        POSTER_FOLDER,
        filename
    )

    print(
        f"\n[{index}/{len(files)}] "
        f"{filename}"
    )

    try:

        with open(local_path, "rb") as file:

            supabase.storage \
                .from_(BUCKET_NAME) \
                .upload(
                    filename,
                    file,
                    file_options={
                        "content-type": "image/jpeg",
                        "upsert": False
                    }
                )

        uploaded += 1

        print("✅ Uploaded")

    except Exception as e:

        error_message = str(e)

        # File already exists
        if "already exists" in error_message.lower():

            print("⚠️ Already exists")

        else:

            print("❌ Failed")
            print(error_message)

            failed += 1


# ==========================================
# SUMMARY
# ==========================================

print("\n====================================")
print("UPLOAD COMPLETE")
print("====================================")

print(f"Total files : {len(files)}")
print(f"Uploaded    : {uploaded}")
print(f"Failed      : {failed}")

print("====================================")
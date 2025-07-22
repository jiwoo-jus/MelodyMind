import pymysql
import ast
import csv
from common_genres import COMMON_GENRES

# Connect to database
conn = pymysql.connect(
    host='localhost',
    user='root',
    password=("DB_PASSWORD"),
    database='musicoset'
)
cursor = conn.cursor(pymysql.cursors.DictCursor)

# Fetch all songs
cursor.execute("SELECT song_id, song_name, artists FROM songs")
songs = cursor.fetchall()

# Load artists into a dictionary for quick lookup
cursor.execute("SELECT artist_id, genres FROM artists WHERE artist_id IS NOT NULL AND genres IS NOT NULL")
artist_rows = cursor.fetchall()
artist_genre_map = {}

for artist in artist_rows:
    try:
        genres = ast.literal_eval(artist['genres'])  # convert from string to list
        artist_genre_map[artist['artist_id']] = [g.lower() for g in genres]
    except:
        artist_genre_map[artist['artist_id']] = []

# Helper function: map genres to umbrella genres
def map_to_common_genre(genres):
    for genre in genres:
        for umbrella, subgenres in COMMON_GENRES.items():
            if genre in subgenres:
                return umbrella
    return "Other"

# Process songs and assign genres
mapped_rows = []
for song in songs:
    try:
        artist_dict = ast.literal_eval(song['artists'])
        artist_ids = list(artist_dict.keys())

        all_artist_genres = []
        for aid in artist_ids:
            all_artist_genres.extend(artist_genre_map.get(aid, []))

        mapped_genre = map_to_common_genre(all_artist_genres)
    except Exception as e:
        print(f"Error processing song {song['song_name']}: {e}")
        mapped_genre = "Other"

    mapped_rows.append({
        "song_id": song['song_id'],
        "song_name": song['song_name'],
        "mapped_genre": mapped_genre
    })

# Save to CSV
with open("mapped_songs.csv", "w", newline='', encoding='utf-8') as csvfile:
    fieldnames = ["song_id", "song_name", "mapped_genre"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(mapped_rows)

print("Mapping complete! Results saved to mapped_songs.csv")

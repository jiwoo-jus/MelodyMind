import csv
import pymysql

# Connect to MySQL database
connection = pymysql.connect(
    host="localhost",
    user="root",
    password="Bday5292000",
    database="musicoset",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor
)

# Open CSV file
with open('mapped_songs.csv', newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    
    with connection.cursor() as cursor:
        for row in reader:
            song_id = row['song_id']
            mapped_genre = row['mapped_genre']
            
            cursor.execute("""
                UPDATE songs
                SET mapped_genre = %s
                WHERE song_id = %s
            """, (mapped_genre, song_id))
            
    connection.commit()
print("Successfully updated genres in 'songs' table.")

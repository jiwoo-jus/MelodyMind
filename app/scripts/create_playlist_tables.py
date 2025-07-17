#!/usr/bin/env python3
import os
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_tables():
    """Create playlist tables in MySQL database."""
    try:
        # Database connection
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME", "musicoset")
        )
        
        cursor = conn.cursor()
        
        # Read SQL file
        sql_file_path = os.path.join(os.path.dirname(__file__), "create_playlist_tables.sql")
        with open(sql_file_path, 'r') as file:
            sql_content = file.read()
        
        # Execute SQL commands
        for statement in sql_content.split(';'):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Playlist tables created successfully!")
        
    except mysql.connector.Error as e:
        print(f"❌ Error creating tables: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    create_tables()

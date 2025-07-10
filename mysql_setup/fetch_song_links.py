import os
import base64
import json
import mysql.connector
from requests import post, get
from dotenv import load_dotenv
import time
from urllib.parse import quote
import logging
from datetime import datetime
from ytmusicapi import YTMusic
#conda install conda-forge::ytmusicapi


load_dotenv()

# Configuration flags - Set these to control which services to fetch from
FETCH_SPOTIFY = False
FETCH_YOUTUBE_MUSIC = True

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'musicoset')
}

# Spotify API configuration
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('music_link_fetch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MusicLinkCollector:
    def __init__(self):
        self.spotify_token = None
        self.db_connection = None
        self.failed_fetches = []
        self.ytmusic = None
        
        # Initialize YouTube Music if enabled
        if FETCH_YOUTUBE_MUSIC:
            try:
                self.ytmusic = YTMusic()
                logger.info("YouTube Music API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize YouTube Music API: {e}")
                self.ytmusic = None
        
    def connect_to_database(self):
        """Connect to MySQL database"""
        try:
            self.db_connection = mysql.connector.connect(**DB_CONFIG)
            logger.info("Connected to database successfully")
        except mysql.connector.Error as err:
            logger.error(f"Database connection error: {err}")
            
    def get_spotify_token(self):
        """Get Spotify API access token"""
        if not FETCH_SPOTIFY:
            logger.info("Spotify fetching is disabled")
            return
            
        auth_string = SPOTIFY_CLIENT_ID + ":" + SPOTIFY_CLIENT_SECRET
        auth_bytes = auth_string.encode('utf-8')
        auth_base64 = str(base64.b64encode(auth_bytes), 'utf-8')

        url = "https://accounts.spotify.com/api/token"
        headers = {
            "Authorization": "Basic " + auth_base64,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}
        
        try:
            result = post(url, headers=headers, data=data)
            json_result = json.loads(result.content)
            self.spotify_token = json_result["access_token"]
            logger.info("Spotify token obtained successfully")
        except Exception as e:
            logger.error(f"Error getting Spotify token: {e}")
            
    def search_spotify_track(self, song_name, artist_name=None):
        """Search for track on Spotify with improved matching"""
        if not FETCH_SPOTIFY or not self.spotify_token:
            return None
            
        # Multiple search strategies for better matching
        search_queries = []
        
        if artist_name:
            # Strategy 1: Exact match with track and artist
            search_queries.append(f'track:"{song_name}" artist:"{artist_name}"')
            # Strategy 2: Less strict match
            search_queries.append(f"{song_name} {artist_name}")
        else:
            # Strategy 3: Track name only
            search_queries.append(f'track:"{song_name}"')
            search_queries.append(song_name)
            
        url = "https://api.spotify.com/v1/search"
        headers = {"Authorization": f"Bearer {self.spotify_token}"}
        
        for query in search_queries:
            params = {
                "q": query,
                "type": "track",
                "limit": 5  # Get multiple results to find best match
            }
            
            try:
                result = get(url, headers=headers, params=params)
                json_result = json.loads(result.content)
                
                if json_result["tracks"]["items"]:
                    tracks = json_result["tracks"]["items"]
                    
                    # Find best match
                    best_match = self._find_best_spotify_match(tracks, song_name, artist_name)
                    if best_match:
                        logger.info(f"Found Spotify match: {best_match['name']} by {', '.join([a['name'] for a in best_match['artists']])}")
                        return best_match["external_urls"]["spotify"]
                        
            except Exception as e:
                logger.error(f"Error searching Spotify with query '{query}': {e}")
                continue
                
        logger.warning(f"No Spotify match found for: {song_name} by {artist_name}")
        return None
    
    def _find_best_spotify_match(self, tracks, song_name, artist_name=None):
        """Find the best matching track from Spotify results"""
        song_name_lower = song_name.lower().strip()
        artist_name_lower = artist_name.lower().strip() if artist_name else None
        
        for track in tracks:
            track_name_lower = track['name'].lower().strip()
            track_artists = [artist['name'].lower().strip() for artist in track['artists']]
            
            # Check for exact song name match
            if song_name_lower == track_name_lower:
                if not artist_name_lower:
                    return track
                # Check if any artist matches
                if any(artist_name_lower in artist or artist in artist_name_lower for artist in track_artists):
                    return track
            
            # Check for partial song name match (for songs with features, remixes, etc.)
            if song_name_lower in track_name_lower or track_name_lower in song_name_lower:
                if not artist_name_lower:
                    return track
                if any(artist_name_lower in artist or artist in artist_name_lower for artist in track_artists):
                    return track
        
        # If no good match, return the first result (most popular)
        return tracks[0] if tracks else None
            
    def search_youtube_music(self, song_name, artist_name=None):
        """Search for track on YouTube Music using ytmusicapi"""
        if not FETCH_YOUTUBE_MUSIC or not self.ytmusic:
            return None
            
        search_query = f"{song_name} {artist_name}" if artist_name else song_name
        
        try:
            search_results = self.ytmusic.search(search_query, filter="songs", limit=5)
            
            if search_results:
                # Find best match
                best_match = self._find_best_youtube_match(search_results, song_name, artist_name)
                if best_match:
                    video_id = best_match['videoId']
                    artist_names = ', '.join([a['name'] for a in best_match.get('artists', [])])
                    logger.info(f"Found YouTube match: {best_match['title']} by {artist_names}")
                    return f"https://music.youtube.com/watch?v={video_id}"
                    
        except Exception as e:
            logger.error(f"YouTube Music search error: {e}")
        
        logger.warning(f"No YouTube Music match found for: {song_name} by {artist_name}")
        return None
    
    def _find_best_youtube_match(self, results, song_name, artist_name=None):
        """Find the best matching track from YouTube Music results"""
        song_name_lower = song_name.lower().strip()
        artist_name_lower = artist_name.lower().strip() if artist_name else None
        
        for result in results:
            if result.get('resultType') != 'song':
                continue
                
            title_lower = result['title'].lower().strip()
            result_artists = [artist['name'].lower().strip() for artist in result.get('artists', [])]
            
            # Check for exact song name match
            if song_name_lower == title_lower:
                if not artist_name_lower:
                    return result
                # Check if any artist matches
                if any(artist_name_lower in artist or artist in artist_name_lower for artist in result_artists):
                    return result
            
            # Check for partial match
            if song_name_lower in title_lower or title_lower in song_name_lower:
                if not artist_name_lower:
                    return result
                if any(artist_name_lower in artist or artist in artist_name_lower for artist in result_artists):
                    return result
        
        # Return first result if no perfect match
        return results[0] if results else None
        
    def get_songs_from_db(self, limit=None):
        """Get songs from database"""
        if not self.db_connection:
            return []
            
        cursor = self.db_connection.cursor(dictionary=True)
        query = "SELECT song_id, song_name, artists FROM songs"
        if limit:
            query += f" LIMIT {limit}"
            
        try:
            cursor.execute(query)
            songs = cursor.fetchall()
            cursor.close()
            logger.info(f"Retrieved {len(songs)} songs from database")
            return songs
        except mysql.connector.Error as err:
            logger.error(f"Error fetching songs: {err}")
            return []
            
    def save_links_to_db(self, song_id, spotify_url=None, youtube_music_url=None):
        """Save music links to database"""
        if not self.db_connection:
            return False

        cursor = self.db_connection.cursor()

        # Build dynamic query based on provided values
        query = """
        INSERT INTO melodymind_song_links (song_id, spotify_url, youtube_music_url)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        """
        updates = []
        params = [song_id, spotify_url, youtube_music_url]

        if spotify_url is not None:
            updates.append("spotify_url = VALUES(spotify_url)")
        if youtube_music_url is not None:
            updates.append("youtube_music_url = VALUES(youtube_music_url)")

        # Add updated_at timestamp
        updates.append("updated_at = CURRENT_TIMESTAMP")

        query += ", ".join(updates)

        try:
            cursor.execute(query, params)
            self.db_connection.commit()
            cursor.close()
            return True
        except mysql.connector.Error as err:
            logger.error(f"Error saving links for song_id {song_id}: {err}")
            return False
            
    def process_songs(self, limit=None):
        """Process songs and collect links"""
        songs = self.get_songs_from_db(limit)
        total_songs = len(songs)
        
        logger.info(f"Processing {total_songs} songs...")
        logger.info(f"Fetch settings - Spotify: {FETCH_SPOTIFY}, YouTube Music: {FETCH_YOUTUBE_MUSIC}")
        
        success_count = 0
        failed_count = 0
        
        for i, song in enumerate(songs, 1):
            # logger.info(f"Processing {i}/{total_songs}: {song['song_name']}")
            
            # Extract first artist name and clean it
            artist_name = None
            if song['artists']:
                # Split by comma and take first artist, remove any extra whitespace
                artist_name = song['artists'].split(',')[0].strip()
                # Remove any parenthetical information like "(feat. ...)"
                if '(' in artist_name:
                    artist_name = artist_name.split('(')[0].strip()
            
            # Initialize URLs
            spotify_url = None
            youtube_music_url = None
            
            logger.info(f"Processing {i}/{total_songs} : {song['song_name']} by {artist_name} | {song['song_id']} ")
            # Search Spotify if enabled
            if FETCH_SPOTIFY:
                spotify_url = self.search_spotify_track(song['song_name'], artist_name)
                if not spotify_url:
                    self.failed_fetches.append({
                        'song_id': song['song_id'],
                        'song_name': song['song_name'],
                        'artist': artist_name,
                        'service': 'Spotify',
                        'timestamp': datetime.now()
                    })
            
            # Search YouTube Music if enabled
            if FETCH_YOUTUBE_MUSIC:
                youtube_music_url = self.search_youtube_music(song['song_name'], artist_name)
                if not youtube_music_url:
                    self.failed_fetches.append({
                        'song_id': song['song_id'],
                        'song_name': song['song_name'],
                        'artist': artist_name,
                        'service': 'YouTube Music',
                        'timestamp': datetime.now()
                    })
            
            # Save to database
            success = self.save_links_to_db(song['song_id'], spotify_url, youtube_music_url)
            
            
            if success:
                success_count += 1
                links_found = []
                if spotify_url:
                    links_found.append("Spotify")
                if youtube_music_url:
                    links_found.append("YouTube Music")
                
                logger.info(f"✓ Saved ({', '.join(links_found) if links_found else 'No links found'})")
            else:
                failed_count += 1
                logger.error(f"✗ Failed to save links for: {song['song_name']}")
                
            # Add delay to respect API rate limits
            time.sleep(0.1)
        
        # Log summary
        logger.info(f"\n=== PROCESSING COMPLETE ===")
        logger.info(f"Total processed: {total_songs}")
        logger.info(f"Successful saves: {success_count}")
        logger.info(f"Failed saves: {failed_count}")
        logger.info(f"Failed fetches: {len(self.failed_fetches)}")
        
        # Log failed fetches
        if self.failed_fetches:
            logger.warning(f"\n=== FAILED FETCHES ===")
            for failure in self.failed_fetches:
                logger.warning(f"Failed to fetch {failure['service']} link for: {failure['song_name']} by {failure['artist']} (ID: {failure['song_id']})")
            
    def close_connections(self):
        """Close database connection"""
        if self.db_connection:
            self.db_connection.close()
            logger.info("Database connection closed")

def main():
    collector = MusicLinkCollector()
    
    try:
        # Initialize connections
        collector.connect_to_database()
        collector.get_spotify_token()
        
        # Process songs (start with a small batch for testing)
        # collector.process_songs(limit=10)  # Remove limit for all songs
        collector.process_songs()  # Remove limit for all songs
        
    except KeyboardInterrupt:
        logger.info("\n\nProcess interrupted by user")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        collector.close_connections()

if __name__ == "__main__":
    main()
    
#spotify results:
# === PROCESSING COMPLETE ===
# 2025-06-11 22:36:57,387 - INFO - Total processed: 20406
# 2025-06-11 22:36:57,388 - INFO - Successful saves: 20405
# 2025-06-11 22:36:57,388 - INFO - Failed saves: 0
# 2025-06-11 22:36:57,388 - INFO - Failed fetches: 9
# 2025-06-11 22:36:57,388 - WARNING - 
# === FAILED FETCHES ===
# 2025-06-11 22:36:57,390 - WARNING - Failed to fetch Spotify link for: Crackerbox Palace by Sweet Little Band (ID: 3YzRfaGVxZjYgWStlPhCaz)
# 2025-06-11 22:36:57,390 - WARNING - Failed to fetch Spotify link for: Darlin' Danielle Don't by Henry Lee Summer from 'Henry Lee Summer' (ID: 3tdFvLpFGSSjupu6VMvrNl)
# 2025-06-11 22:36:57,391 - WARNING - Failed to fetch Spotify link for: I'm Gonna Be Alright (feat. Nas) by Nas from 'This Is Me...Then' (ID: 3SHSWxOXqCrw55LiXAB8J1)
# 2025-06-11 22:36:57,391 - WARNING - Failed to fetch Spotify link for: Only Love Can Break A Heart by Bobby Vinton (ID: 5GlfyCpEDQ2AlZ6leIZN8u)
# 2025-06-11 22:36:57,391 - WARNING - Failed to fetch Spotify link for: I'll Be There for You (Theme from "Friends') by The Rembrandts from 'I'll Be There For You (Theme From FRIENDS) / Snippets: Don't Hide Your Love / End Of The Beginning / Lovin' Me Insane / Drowning In Your Tears / This House Is Not A Home / What Will It Take [Digital 45]' (ID: 1lfjTOtTRUDkzcmahA4lcs)
# 2025-06-11 22:36:57,391 - WARNING - Failed to fetch Spotify link for: Pinball Wizard by The Who from 'Tommy' (ID: 6LbbHFEajG9e4m0G3L47c4)
# 2025-06-11 22:36:57,391 - WARNING - Failed to fetch Spotify link for: Somewhere in America by Survivor (ID: 70dEBvY36k2QdwoLexpKOd)
# 2025-06-11 22:36:57,391 - WARNING - Failed to fetch Spotify link for: What U See Is What U Get by Xzibit from '40 Dayz & 40 Nightz (Explicit)' (ID: 4ezafcOuI5em8LoE2xxnpv)
# 2025-06-11 22:36:57,391 - WARNING - Failed to fetch Spotify link for: Sail On, Sailor by The Beach Boys from 'The Beach Boys Classics...Selected By Brian Wilson' (ID: 4LcJKxxmYF4DPajxfpPT60)
# 2025-06-11 22:36:57,405 - INFO - Database connecatch: Violet Hill by Col

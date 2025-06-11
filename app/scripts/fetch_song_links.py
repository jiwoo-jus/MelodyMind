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

# For whoever runs this script, ensure you should change the path to your .env file
load_dotenv("/Users/jiwoo/WorkSpace/MelodyMind/.env")

# Configuration flags - Set these to control which services to fetch from
FETCH_SPOTIFY = True
FETCH_YOUTUBE_MUSIC = False

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

print("Using Spotify Client ID:", SPOTIFY_CLIENT_ID)
print("Using Spotify Client Secret:", SPOTIFY_CLIENT_SECRET)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fetch_song_links.log'),
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
            self.spotify_token = None # Ensure token is None if fetching is disabled
            return
            
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            logger.error("Spotify credentials not found in environment variables. Cannot obtain token.")
            self.spotify_token = None # Explicitly set to None if credentials are not found
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
            result.raise_for_status()  # Raise exception for bad status codes
            json_result = json.loads(result.content)
            self.spotify_token = json_result["access_token"]
            logger.info("Spotify token obtained successfully")
        except Exception as e:
            logger.error(f"Error getting Spotify token: {e}")
            self.spotify_token = None
    
    def parse_artist_field(self, artists_field):
        """Parse the artists field from database which can be JSON string, dict, or plain string"""
        if not artists_field:
            return None
            
        try:
            # Convert to string first to handle any type
            artists_str = str(artists_field)
            
            # If it looks like a dictionary string {'id': 'name'}
            if '{' in artists_str and ':' in artists_str and '}' in artists_str:
                try:
                    # Try to parse as JSON first
                    parsed = json.loads(artists_str.replace("'", '"'))  # Replace single quotes with double quotes
                    if isinstance(parsed, dict):
                        # Extract artist names from dict values
                        artist_names = list(parsed.values())
                        return artist_names[0] if artist_names else None
                except (json.JSONDecodeError, ValueError):
                    # Manual parsing for {'id': 'name'} format
                    # Find the part after the colon
                    colon_parts = artists_str.split(':')
                    if len(colon_parts) > 1:
                        # Get the part after the last colon, clean it up
                        artist_part = colon_parts[-1].strip()
                        # Remove trailing braces, quotes, and whitespace
                        artist_part = artist_part.rstrip('}').strip().strip('\'"')
                        return artist_part if artist_part else None
            
            # If it's already a clean string or simple format
            if isinstance(artists_field, str):
                try:
                    # Try to parse as JSON
                    parsed = json.loads(artists_field)
                    if isinstance(parsed, dict):
                        artist_names = list(parsed.values())
                        return artist_names[0] if artist_names else None
                    elif isinstance(parsed, list):
                        return parsed[0] if parsed else None
                    else:
                        return str(parsed)
                except (json.JSONDecodeError, ValueError):
                    # If JSON parsing fails, treat as comma-separated string
                    return artists_field.split(',')[0].strip()
            
            # If it's already a dict
            elif isinstance(artists_field, dict):
                artist_names = list(artists_field.values())
                return artist_names[0] if artist_names else None
                
            # If it's a list
            elif isinstance(artists_field, list):
                return artists_field[0] if artists_field else None
                
            # Fallback
            return artists_str.split(',')[0].strip()
                
        except Exception as e:
            logger.warning(f"Error parsing artist field '{artists_field}': {e}")
            # Last resort fallback
            try:
                return str(artists_field).split(',')[0].strip()
            except:
                return None
            
    def search_spotify_track(self, song_name, artist_name=None, album_name=None):
        """Search for track on Spotify with improved matching including album"""
        if not FETCH_SPOTIFY or not self.spotify_token:
            return None
        
        # Skip if song_name is None or empty
        if not song_name or song_name.lower() == 'none':
            logger.warning("Skipping Spotify search: song_name is None or 'none'")
            return None
            
        # Multiple search strategies for better matching
        search_queries = []
        
        if artist_name and artist_name.lower() != 'none' and album_name and album_name.lower() != 'none':
            # Strategy 1: Complete match with track, artist, and album
            search_queries.append(f'track:"{song_name}" artist:"{artist_name}" album:"{album_name}"')
            # Strategy 2: Less strict with all fields
            search_queries.append(f"{song_name} {artist_name} {album_name}")
        elif artist_name and artist_name.lower() != 'none':
            # Strategy 3: Track and artist only (fallback)
            search_queries.append(f'track:"{song_name}" artist:"{artist_name}"')
            search_queries.append(f"{song_name} {artist_name}")
        elif album_name and album_name.lower() != 'none':
            # Strategy 4: Track and album only
            search_queries.append(f'track:"{song_name}" album:"{album_name}"')
            search_queries.append(f"{song_name} {album_name}")
        else:
            # Strategy 5: Track name only
            search_queries.append(f'track:"{song_name}"')
            search_queries.append(song_name)
            
        url = "https://api.spotify.com/v1/search"
        headers = {"Authorization": f"Bearer {self.spotify_token}"}
        
        for query in search_queries:
            params = {
                "q": query,
                "type": "track",
                "limit": 10  # Get more results when using album info
            }
            
            try:
                result = get(url, headers=headers, params=params)
                result.raise_for_status()  # Raise exception for bad status codes
                json_result = json.loads(result.content)
                
                if "tracks" in json_result and json_result["tracks"]["items"]:
                    tracks = json_result["tracks"]["items"]
                    
                    # Find best match
                    best_match = self._find_best_spotify_match(tracks, song_name, artist_name, album_name)
                    if best_match:
                        album_info = best_match.get('album', {}).get('name', 'Unknown Album')
                        logger.info(f"Found Spotify match: {best_match['name']} by {', '.join([a['name'] for a in best_match['artists']])} from '{album_info}'")
                        return best_match["external_urls"]["spotify"]
                        
            except Exception as e:
                logger.error(f"Error searching Spotify with query '{query}': {e}")
                # If we get rate limited, wait longer
                if "429" in str(e) or "Too Many Requests" in str(e):
                    logger.warning("Rate limited by Spotify, waiting 5 seconds...")
                    time.sleep(5)  # Increased delay for rate limiting
                # If we get an auth error, try to refresh token
                elif "401" in str(e) or "Unauthorized" in str(e):
                    logger.warning("Spotify token may be expired, attempting to refresh...")
                    self.get_spotify_token()
                    if not self.spotify_token:
                        logger.error("Failed to refresh Spotify token, skipping remaining Spotify searches")
                        return None
                continue
                
        logger.warning(f"No Spotify match found for: {song_name} by {artist_name} from album '{album_name}'")
        return None
    
    def _find_best_spotify_match(self, tracks, song_name, artist_name=None, album_name=None):
        """Find the best matching track from Spotify results"""
        song_name_lower = song_name.lower().strip()
        artist_name_lower = artist_name.lower().strip() if artist_name else None
        album_name_lower = album_name.lower().strip() if album_name else None
        
        # First priority: exact matches with album
        for track in tracks:
            track_name_lower = track['name'].lower().strip()
            track_artists = [artist['name'].lower().strip() for artist in track['artists']]
            track_album_lower = track.get('album', {}).get('name', '').lower().strip()
            
            # Check for exact song name match
            if song_name_lower == track_name_lower:
                artist_match = not artist_name_lower or any(artist_name_lower in artist or artist in artist_name_lower for artist in track_artists)
                album_match = not album_name_lower or album_name_lower in track_album_lower or track_album_lower in album_name_lower
                
                # Perfect match with all fields
                if artist_match and album_match:
                    return track
        
        # Second priority: partial matches with album
        for track in tracks:
            track_name_lower = track['name'].lower().strip()
            track_artists = [artist['name'].lower().strip() for artist in track['artists']]
            track_album_lower = track.get('album', {}).get('name', '').lower().strip()
            
            # Check for partial song name match
            if song_name_lower in track_name_lower or track_name_lower in song_name_lower:
                artist_match = not artist_name_lower or any(artist_name_lower in artist or artist in artist_name_lower for artist in track_artists)
                album_match = not album_name_lower or album_name_lower in track_album_lower or track_album_lower in album_name_lower
                
                if artist_match and album_match:
                    return track
        
        # Third priority: matches without considering album
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
            
    def search_youtube_music(self, song_name, artist_name=None, album_name=None):
        """Search for track on YouTube Music using ytmusicapi with album info"""
        if not FETCH_YOUTUBE_MUSIC or not self.ytmusic:
            return None
        
        # Skip if song_name is None or empty
        if not song_name or song_name.lower() == 'none':
            logger.warning("Skipping YouTube Music search: song_name is None or 'none'")
            return None
        
        # Create search query with available information
        search_parts = [song_name]
        if artist_name and artist_name.lower() != 'none':
            search_parts.append(artist_name)
        if album_name and album_name.lower() != 'none':
            search_parts.append(album_name)
        
        search_query = " ".join(search_parts)
        
        try:
            search_results = self.ytmusic.search(search_query, filter="songs", limit=10)
            
            if search_results:
                # Find best match
                best_match = self._find_best_youtube_match(search_results, song_name, artist_name, album_name)
                if best_match:
                    video_id = best_match['videoId']
                    artist_names = ', '.join([a['name'] for a in best_match.get('artists', [])])
                    album_info = best_match.get('album', {}).get('name', 'Unknown Album') if best_match.get('album') else 'Unknown Album'
                    logger.info(f"Found YouTube match: {best_match['title']} by {artist_names} from '{album_info}'")
                    return f"https://music.youtube.com/watch?v={video_id}"
                    
        except Exception as e:
            logger.error(f"YouTube Music search error: {e}")
        
        logger.warning(f"No YouTube Music match found for: {song_name} by {artist_name} from album '{album_name}'")
        return None
    
    def _find_best_youtube_match(self, results, song_name, artist_name=None, album_name=None):
        """Find the best matching track from YouTube Music results"""
        song_name_lower = song_name.lower().strip()
        artist_name_lower = artist_name.lower().strip() if artist_name else None
        album_name_lower = album_name.lower().strip() if album_name else None
        
        # First priority: exact matches with album consideration
        for result in results:
            if result.get('resultType') != 'song':
                continue
                
            title_lower = result['title'].lower().strip()
            result_artists = [artist['name'].lower().strip() for artist in result.get('artists', [])]
            result_album_lower = result.get('album', {}).get('name', '').lower().strip() if result.get('album') else ''
            
            # Check for exact song name match
            if song_name_lower == title_lower:
                artist_match = not artist_name_lower or any(artist_name_lower in artist or artist in artist_name_lower for artist in result_artists)
                album_match = not album_name_lower or (result_album_lower and (album_name_lower in result_album_lower or result_album_lower in album_name_lower))
                
                # Perfect match with available fields
                if artist_match and (not album_name_lower or album_match):
                    return result
        
        # Second priority: partial matches with album consideration
        for result in results:
            if result.get('resultType') != 'song':
                continue
                
            title_lower = result['title'].lower().strip()
            result_artists = [artist['name'].lower().strip() for artist in result.get('artists', [])]
            result_album_lower = result.get('album', {}).get('name', '').lower().strip() if result.get('album') else ''
            
            # Check for partial match
            if song_name_lower in title_lower or title_lower in song_name_lower:
                artist_match = not artist_name_lower or any(artist_name_lower in artist or artist in artist_name_lower for artist in result_artists)
                album_match = not album_name_lower or (result_album_lower and (album_name_lower in result_album_lower or result_album_lower in album_name_lower))
                
                if artist_match and (not album_name_lower or album_match):
                    return result
        
        # Third priority: matches without album consideration (fallback)
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
        """Get songs from database with album information"""
        if not self.db_connection:
            return []
            
        cursor = self.db_connection.cursor(dictionary=True)
        query = """
        SELECT 
            s.song_id, 
            s.song_name, 
            s.artists,
            a.name as album_name
        FROM songs s
        LEFT JOIN tracks t ON s.song_id = t.song_id
        LEFT JOIN albums a ON t.album_id = a.album_id
        """
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
        query = """
        INSERT INTO melodymind_song_links (song_id, spotify_url, youtube_music_url)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        spotify_url = VALUES(spotify_url),
        youtube_music_url = VALUES(youtube_music_url),
        updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            cursor.execute(query, (song_id, spotify_url, youtube_music_url))
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
            # Skip songs with no song_name or None values
            if not song.get('song_name') or song['song_name'] == 'None':
                logger.warning(f"Skipping song {i}/{total_songs}: song_name is None or 'None' | {song.get('song_id', 'Unknown ID')}")
                continue
                
            # Parse artist name and album name properly
            artist_name = self.parse_artist_field(song['artists'])
            album_name = song.get('album_name')
            
            # Clean artist name if it exists
            if artist_name:
                # Remove any parenthetical information like "(feat. ...)"
                if '(' in artist_name:
                    artist_name = artist_name.split('(')[0].strip()
                # Remove any extra whitespace
                artist_name = artist_name.strip()
            
            # Clean album name if it exists
            if album_name:
                album_name = album_name.strip()
            
            # Initialize URLs
            spotify_url = None
            youtube_music_url = None
            
            # Create display info
            album_info = f" from '{album_name}'" if album_name else ""
            logger.info(f"Processing {i}/{total_songs} : {song['song_name']} by {artist_name}{album_info} | {song['song_id']} ")
            
            # Search Spotify if enabled
            if FETCH_SPOTIFY:
                spotify_url = self.search_spotify_track(song['song_name'], artist_name, album_name)
                if not spotify_url:
                    self.failed_fetches.append({
                        'song_id': song['song_id'],
                        'song_name': song['song_name'],
                        'artist': artist_name,
                        'album': album_name,
                        'service': 'Spotify',
                        'timestamp': datetime.now()
                    })
            
            # Search YouTube Music if enabled
            if FETCH_YOUTUBE_MUSIC:
                youtube_music_url = self.search_youtube_music(song['song_name'], artist_name, album_name)
                if not youtube_music_url:
                    self.failed_fetches.append({
                        'song_id': song['song_id'],
                        'song_name': song['song_name'],
                        'artist': artist_name,
                        'album': album_name,
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
            time.sleep(1)  # Increased delay for rate limiting
        
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
                album_info = f" from '{failure['album']}'" if failure.get('album') else ""
                logger.warning(f"Failed to fetch {failure['service']} link for: {failure['song_name']} by {failure['artist']}{album_info} (ID: {failure['song_id']})")
            
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
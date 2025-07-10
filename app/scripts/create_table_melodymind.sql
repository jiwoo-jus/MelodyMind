CREATE TABLE melodymind_song_links (
    song_id VARCHAR(22) NOT NULL,
    spotify_url VARCHAR(500),
    youtube_music_url VARCHAR(500),
    apple_music_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (song_id)
);
/*
# spotify results:  
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

YouTube Music results:
# === PROCESSING COMPLETE ===
# 2025-06-12 22:32:54,498 - INFO - Total processed: 20406
# 2025-06-12 22:32:54,498 - INFO - Successful saves: 20405
# 2025-06-12 22:32:54,498 - INFO - Failed saves: 0
# 2025-06-12 22:32:54,499 - INFO - Failed fetches: 7
# 2025-06-12 22:32:54,499 - WARNING - 
# === FAILED FETCHES ===
# 2025-06-12 22:32:54,499 - WARNING - Failed to fetch YouTube Music link for: Come Join The Murder by 2014 Golden Cove (ID: 3T1BteAcIjKATAQ8wBLZT7)
# 2025-06-12 22:32:54,499 - WARNING - Failed to fetch YouTube Music link for: Ain't Love a Bitch by Flies on the Square Egg (ID: 2Ku4EmWMelrukSn8rICXo1)
# 2025-06-12 22:32:54,500 - WARNING - Failed to fetch YouTube Music link for: My Love (Paul McCartney And Wings Karaoke Tribute) by Blowjob Karaoke Explosion (ID: 6u1clHX8TT1JtCAy3Qy1ks)
# 2025-06-12 22:32:54,500 - WARNING - Failed to fetch YouTube Music link for: Wipeout by Fat Boys from 'All Meat No Filler: The Best of Fat Boys' (ID: 46ePNyvaDBKsxusDXDj7Wg)
# 2025-06-12 22:32:54,501 - WARNING - Failed to fetch YouTube Music link for: Ruby, Baby (Originally Performed by Billy "Crash" Craddock) [Karaoke Version] by Mega Tracks Karaoke Band (ID: 0Gwoky179lKmqm8HTTsdUK)
# 2025-06-12 22:32:54,501 - WARNING - Failed to fetch YouTube Music link for: I Can't Turn You Loose - Live by u"Edgar Winter's White Trash from 'WHITE TRASH ROADWORK' (ID: 5Np8Xbu2cMRReBOeT53fpX)
# 2025-06-12 22:32:54,502 - WARNING - Failed to fetch YouTube Music link for: Tie Your Mother Down - Remastered 2011 by Queen from 'A Day At The Races (Deluxe Edition 2011 Remaster)' (ID: 4mLKx7zsUdyT4Ax7rI7KXu)
# 2025-06-12 22:32:54,569 - INFO - Database connection closed
*/

SELECT 
    COUNT(*) AS total,
    SUM(spotify_url IS NULL) AS sp_null,
    ROUND(SUM(spotify_url IS NULL) / COUNT(*) * 100, 2) AS sp_null_pct,
    SUM(spotify_url IS NOT NULL) AS sp_not_null,
    ROUND(SUM(spotify_url IS NOT NULL) / COUNT(*) * 100, 2) AS sp_not_null_pct,
    SUM(youtube_music_url IS NULL) AS yt_null,
    ROUND(SUM(youtube_music_url IS NULL) / COUNT(*) * 100, 2) AS yt_null_pct,
    SUM(youtube_music_url IS NOT NULL) AS yt_not_null,
    ROUND(SUM(youtube_music_url IS NOT NULL) / COUNT(*) * 100, 2) AS yt_not_null_pct
FROM melodymind_song_links;

/*
+-------+---------+-------------+-------------+-----------------+---------+-------------+-------------+-----------------+
| total | sp_null | sp_null_pct | sp_not_null | sp_not_null_pct | yt_null | yt_null_pct | yt_not_null | yt_not_null_pct |
+-------+---------+-------------+-------------+-----------------+---------+-------------+-------------+-----------------+
| 20405 |       9 |        0.04 |       20396 |           99.96 |       7 |        0.03 |       20398 |           99.97 |
+-------+---------+-------------+-------------+-----------------+---------+-------------+-------------+-----------------+
*/

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/3YzRfaGVxZjYgWStlPhCaz'
WHERE song_id = '3YzRfaGVxZjYgWStlPhCaz';

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/3tdFvLpFGSSjupu6VMvrNl'
WHERE song_id = '3tdFvLpFGSSjupu6VMvrNl';

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/3SHSWxOXqCrw55LiXAB8J1'
WHERE song_id = '3SHSWxOXqCrw55LiXAB8J1';

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/5GlfyCpEDQ2AlZ6leIZN8u'
WHERE song_id = '5GlfyCpEDQ2AlZ6leIZN8u';

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/15tHagkk8z306XkyOHqiip'
WHERE song_id = '1lfjTOtTRUDkzcmahA4lcs';

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/6LbbHFEajG9e4m0G3L47c4'
WHERE song_id = '6LbbHFEajG9e4m0G3L47c4';

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/6PXWiezZ5R2zWv0GKExVLn'
WHERE song_id = '70dEBvY36k2QdwoLexpKOd';

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/4ezafcOuI5em8LoE2xxnpv'
WHERE song_id = '4ezafcOuI5em8LoE2xxnpv';

UPDATE melodymind_song_links
SET spotify_url = 'https://open.spotify.com/track/4LcJKxxmYF4DPajxfpPT60'
WHERE song_id = '4LcJKxxmYF4DPajxfpPT60';

-- Come Join The Murder – The White Buffalo & The Forest Rangers
UPDATE melodymind_song_links
SET youtube_music_url = 'https://music.youtube.com/watch?v=jXwgShqzVas'
WHERE song_id = '3T1BteAcIjKATAQ8wBLZT7';

-- Ain’t Love a Bitch – Flies on the Square Egg
UPDATE melodymind_song_links
SET youtube_music_url = 'https://music.youtube.com/watch?v=Z0Nk6MWL8FE'
WHERE song_id = '2Ku4EmWMelrukSn8rICXo1';

-- My Love (Paul McCartney And Wings Karaoke Tribute) – Blowjob Karaoke Explosion
UPDATE melodymind_song_links
SET youtube_music_url = 'https://music.youtube.com/watch?v=PA9XLa2ARfs'
WHERE song_id = '6u1clHX8TT1JtCAy3Qy1ks';

-- Wipeout – Fat Boys
UPDATE melodymind_song_links
SET youtube_music_url = 'https://music.youtube.com/watch?v=r-kAnNgqN9o'
WHERE song_id = '46ePNyvaDBKsxusDXDj7Wg';

-- Ruby, Baby (Originally Performed by Billy "Crash" Craddock) [Karaoke Version] – Mega Tracks Karaoke Band
UPDATE melodymind_song_links
SET youtube_music_url = 'https://music.youtube.com/watch?v=2yr9Ii5kGq4'
WHERE song_id = '0Gwoky179lKmqm8HTTsdUK';

-- I Can’t Turn You Loose – Edgar Winter’s White Trash
UPDATE melodymind_song_links
SET youtube_music_url = 'https://music.youtube.com/watch?v=gSOGqzzovaQ'
WHERE song_id = '5Np8Xbu2cMRReBOeT53fpX';

-- Tie Your Mother Down – Queen
UPDATE melodymind_song_links
SET youtube_music_url = 'https://music.youtube.com/watch?v=zl4M_X6Q4bM'
WHERE song_id = '4mLKx7zsUdyT4Ax7rI7KXu';

/*
+-------+---------+-------------+-------------+-----------------+---------+-------------+-------------+-----------------+
| total | sp_null | sp_null_pct | sp_not_null | sp_not_null_pct | yt_null | yt_null_pct | yt_not_null | yt_not_null_pct |
+-------+---------+-------------+-------------+-----------------+---------+-------------+-------------+-----------------+
| 20405 |       0 |        0.00 |       20405 |          100.00 |       0 |        0.00 |       20405 |          100.00 |
+-------+---------+-------------+-------------+-----------------+---------+-------------+-------------+-----------------+
*/
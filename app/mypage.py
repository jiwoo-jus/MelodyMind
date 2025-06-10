
from elasticsearch import Elasticsearch
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET")
jwt = JWTManager(app)

# Helper function for user operations
def get_user_profile(user_id):
    return es.get(index="user_profiles", id=user_id)["_source"]

es = Elasticsearch("http://localhost:9200")

# Create user profile index
user_index_mapping = {
    "mappings": {
        "properties": {
            "username": {"type": "keyword"},
            "email": {"type": "keyword"},
            "favorite_genres": {"type": "keyword"},
            "favorite_artists": {"type": "keyword"},
            "saved_tracks": {"type": "keyword"},
            "playlists": {
                "type": "nested",
                "properties": {
                    "name": {"type": "text"},
                    "tracks": {"type": "keyword"},
                    "created_at": {"type": "date"}
                }
            },
            "listening_history": {
                "type": "nested",
                "properties": {
                    "track_id": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "play_count": {"type": "integer"}
                }
            },
            "preferences": {
                "properties": {
                    "theme": {"type": "keyword"},
                    "audio_quality": {"type": "keyword"}
                }
            }
        }
    }
}

es.indices.create(index="user_profiles", body=user_index_mapping, ignore=400)

@app.route('/api/me/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user = get_jwt_identity()
    user_profile = get_user_profile(current_user)
    return jsonify(user_profile), 200

@app.route('/api/me/recommendations', methods=['GET'])
@jwt_required()
def get_recommendations():
    user_id = get_jwt_identity()
    user = get_user_profile(user_id)

    # Build recommendation query based on user preferences
    query = {
        "query": {
            "bool": {
                "should": [
                    {"terms": {"genres": user.get("favorite_genres", [])}},
                    {"terms": {"artist_id": user.get("favorite_artists", [])}},
                    {
                        "range": {
                            "danceability": {
                                "gte": 0.7 if "electronic" in user.get("favorite_genres", []) else 0.5,
                                "lte": 1.0
                            }
                        }
                    }
                ],
                "must_not": {
                    "terms": {
                        "track_id": [item["track_id"] for item in user.get("listening_history", [])]
                    }
                }
            }
        },
        "size": 10
    }

    recommendations = es.search(index="music_tracks", body=query)
    return jsonify([hit["_source"] for hit in recommendations["hits"]["hits"]]), 200

@app.route('/api/me/history', methods=['GET', 'POST'])
@jwt_required()
def listening_history():
    user_id = get_jwt_identity()

    if request.method == 'POST':
        track_id = request.json.get("track_id")
        if not track_id:
            return jsonify({"error": "track_id required"}), 400

        # Update listening history
        script = {
            "source": """
                if (ctx._source.listening_history == null) {
                    ctx._source.listening_history = [];
                }
                
                def found = false;
                for (item in ctx._source.listening_history) {
                    if (item.track_id == params.track_id) {
                        item.play_count++;
                        item.timestamp = params.timestamp;
                        found = true;
                        break;
                    }
                }
                
                if (!found) {
                    ctx._source.listening_history.add([
                        "track_id": params.track_id,
                        "timestamp": params.timestamp,
                        "play_count": 1
                    ]);
                }
            """,
            "params": {
                "track_id": track_id,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        }

        es.update(index="user_profiles", id=user_id, body={"script": script})
        return jsonify({"success": True}), 200

    # GET method - return history
    user = get_user_profile(user_id)
    history = sorted(user.get("listening_history", []),
                     key=lambda x: x["timestamp"],
                     reverse=True)[:20]
    return jsonify(history), 200

@app.route('/api/me/favorites', methods=['GET', 'POST', 'DELETE'])
@jwt_required()
def favorite_tracks():
    user_id = get_jwt_identity()

    if request.method == 'POST':
        track_id = request.json.get("track_id")
        if not track_id:
            return jsonify({"error": "track_id required"}), 400

        script = {
            "source": """
                if (ctx._source.saved_tracks == null) {
                    ctx._source.saved_tracks = new ArrayList();
                }
                if (!ctx._source.saved_tracks.contains(params.track_id)) {
                    ctx._source.saved_tracks.add(params.track_id);
                }
            """,
            "params": {
                "track_id": track_id
            }
        }

        es.update(index="user_profiles", id=user_id, body={"script": script})
        return jsonify({"success": True}), 200

    elif request.method == 'DELETE':
        track_id = request.json.get("track_id")
        if not track_id:
            return jsonify({"error": "track_id required"}), 400

        script = {
            "source": """
                if (ctx._source.saved_tracks != null) {
                    ctx._source.saved_tracks.removeIf(item -> item == params.track_id);
                }
            """,
            "params": {
                "track_id": track_id
            }
        }

        es.update(index="user_profiles", id=user_id, body={"script": script})
        return jsonify({"success": True}), 200

    # GET method - return favorites
    user = get_user_profile(user_id)
    favorites = user.get("saved_tracks", [])

    if favorites:
        tracks = es.search(index="music_tracks", body={
            "query": {
                "terms": {
                    "track_id": favorites
                }
            }
        })
        return jsonify([hit["_source"] for hit in tracks["hits"]["hits"]]), 200
    return jsonify([]), 200

@app.route('/api/me/playlists', methods=['GET', 'POST'])
@jwt_required()
def user_playlists():
    user_id = get_jwt_identity()

    if request.method == 'POST':
        playlist_name = request.json.get("name")
        track_ids = request.json.get("tracks", [])

        if not playlist_name:
            return jsonify({"error": "Playlist name required"}), 400

        new_playlist = {
            "name": playlist_name,
            "tracks": track_ids,
            "created_at": datetime.datetime.utcnow().isoformat()
        }

        script = {
            "source": """
                if (ctx._source.playlists == null) {
                    ctx._source.playlists = [];
                }
                ctx._source.playlists.add(params.playlist);
            """,
            "params": {
                "playlist": new_playlist
            }
        }

        es.update(index="user_profiles", id=user_id, body={"script": script})
        return jsonify({"success": True}), 201

    # GET method - return playlists
    user = get_user_profile(user_id)
    playlists = user.get("playlists", [])
    return jsonify(playlists), 200

@app.route('/api/me/preferences', methods=['GET', 'PUT'])
@jwt_required()
def user_preferences():
    user_id = get_jwt_identity()

    if request.method == 'PUT':
        preferences = request.json
        if not preferences:
            return jsonify({"error": "Preferences data required"}), 400

        es.update(
            index="user_profiles",
            id=user_id,
            body={"doc": {"preferences": preferences}}
        )
        return jsonify({"success": True}), 200

    # GET method
    user = get_user_profile(user_id)
    return jsonify(user.get("preferences", {})), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)




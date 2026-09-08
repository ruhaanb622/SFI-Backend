# imports from flask
from flask_socketio import SocketIO, send, emit
from flask import Flask

app = Flask(__name__)

socketio = SocketIO(app, cors_allowed_origins=[
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://open-coding-society.github.io",
    "https://pages.opencodingsociety.com",
])


players = []  # Keep a list of players and scores

@socketio.on("player_join")
def handle_player_join(data):
    name = data.get("name")
    if name:
        players.append({"name": name, "score": 0})
        emit("player_joined", {"name": name}, broadcast=True)

@socketio.on("player_score")
def handle_player_score(data):
    name = data.get("name")
    score = data.get("score", 0)
    for p in players:
        if p["name"] == name:
            p["score"] = score
            break
    # Sort and broadcast leaderboard
    leaderboard = sorted(players, key=lambda x: x["score"], reverse=True)
    emit("leaderboard_update", leaderboard, broadcast=True)

@socketio.on("clear_leaderboard")
def handle_clear_leaderboard():
    global players
    players = []
    emit("leaderboard_update", players, broadcast=True)

@socketio.on("get_leaderboard")
def handle_get_leaderboard():
    # Sort and emit current leaderboard
    leaderboard = sorted(players, key=lambda x: x["score"], reverse=True)
    emit("leaderboard_update", leaderboard)


# this runs the flask application on the development server
if __name__ == "__main__":
    # change name for testing
    socketio.run(app, debug=True, host="0.0.0.0", port=8500)

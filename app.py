from flask import Flask, render_template, request, redirect, url_for, abort, jsonify, session
import random
import secrets
import string
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key")

CARDS_PER_PLAYER = 24

CARD_POOL = [
    {"name": "王俊凯", "image": "wjk.jpg"},
    {"name": "王源", "image": "wy.jpg"},
    {"name": "易烊千玺", "image": "yyqx.jpg"},
    {"name": "马嘉祺", "image": "mjq.jpg"},
    {"name": "丁程鑫", "image": "dcx.jpg"},
    {"name": "宋亚轩", "image": "syx.jpg"},
    {"name": "刘耀文", "image": "lyw.jpg"},
    {"name": "张真源", "image": "zzy.jpg"},
    {"name": "严浩翔", "image": "yhx.jpg"},
    {"name": "贺峻霖", "image": "hjl.jpg"},
    {"name": "朱志鑫", "image": "22x.jpg"},
    {"name": "张泽禹", "image": "zack.jpg"},
    {"name": "张极", "image": "jeremy.jpg"},
    {"name": "左航", "image": "left.jpg"},
    {"name": "苏新皓", "image": "su.jpg"},
    {"name": "童禹坤", "image": "tyk.jpg"},
    {"name": "邓佳鑫", "image": "djx.jpg"},
    {"name": "穆祉丞", "image": "mzc.jpg"},
    {"name": "张子墨", "image": "zzm.jpg"},
    {"name": "黄朔", "image": "hs.jpg"},
    {"name": "余宇涵", "image": "yyh.jpg"},
    {"name": "张峻豪", "image": "zjh.jpg"},
    {"name": "官俊臣", "image": "gjc.jpg"},
    {"name": "张桂源", "image": "zgy.jpg"},
    {"name": "张函瑞", "image": "zhr.jpg"},
    {"name": "王橹杰", "image": "wlj.jpg"},
    {"name": "左奇函", "image": "zqh.jpg"},
    {"name": "陈奕恒", "image": "cyh.jpg"},
    {"name": "杨博文", "image": "ybw.jpg"},
    {"name": "杨涵博", "image": "yhb.jpg"},
    {"name": "张奕然", "image": "zyr.jpg"},
    {"name": "聂玮辰", "image": "nwc.jpg"},
    {"name": "陈思罕", "image": "csh.jpg"},
    {"name": "魏子宸", "image": "wzc.jpg"},
    {"name": "李煜东", "image": "lyd.jpg"},
    {"name": "陈浚铭", "image": "cjm.jpg"},
    {"name": "王烁然", "image": "wsr.jpg"}
]

GAMES = {}


def generate_room_code():
    chars = string.ascii_uppercase + string.digits

    while True:
        room_code = "".join(random.choices(chars, k=6))

        if room_code not in GAMES:
            return room_code


def make_game_state():
    if len(CARD_POOL) < CARDS_PER_PLAYER:
        raise ValueError("固定卡池人数不足，至少需要 24 人。")

    p1_board = random.sample(CARD_POOL, CARDS_PER_PLAYER)
    p2_board = random.sample(CARD_POOL, CARDS_PER_PLAYER)

    p1_secret = random.choice(p1_board)
    p2_secret = random.choice(p2_board)

    return {
        # 每一局的唯一编号，用来判断是否已经开启新局
        "match_id": secrets.token_hex(8),

        "players": {
            "p1": None,
            "p2": None,
        },
        "p1": {
            "board": p1_board,
            "secret": p1_secret,
            "eliminated": [],
        },
        "p2": {
            "board": p2_board,
            "secret": p2_secret,
            "eliminated": [],
        },

        # 当前轮次
        "round": 1,

        # 当前阶段
        "phase": "p1_ask",

        # 当前轮每个人的猜测 / 不猜记录
        "round_guesses": {
            "p1": None,
            "p2": None,
        },

        # 每个玩家累计猜错次数，达到 3 次直接判负
        "wrong_guesses": {
            "p1": 0,
            "p2": 0,
        },

        # 对局结束后，双方是否点击“再来一局”
        "rematch_ready": {
            "p1": False,
            "p2": False,
        },

        "questions": [],
        "guesses": [],
        "winner": None,
    }


def reset_game_for_rematch(game):
    old_players = game["players"]

    new_game = make_game_state()
    new_game["players"] = old_players

    game.clear()
    game.update(new_game)


def get_game(room_code):
    room_code = room_code.upper()
    game = GAMES.get(room_code)

    if game is None:
        abort(404)

    return game


def get_opponent(player):
    if player == "p1":
        return "p2"

    if player == "p2":
        return "p1"

    abort(404)


def is_started(game):
    return game["players"]["p1"] is not None and game["players"]["p2"] is not None


def get_asker_for_phase(phase):
    if phase == "p1_ask":
        return "p1"

    if phase == "p2_ask":
        return "p2"

    return None


def get_answerer_for_phase(phase):
    if phase == "p2_answer":
        return "p2"

    if phase == "p1_answer":
        return "p1"

    return None


def start_next_round(game):
    game["round"] += 1
    game["phase"] = "p1_ask"
    game["round_guesses"] = {
        "p1": None,
        "p2": None,
    }


def resolve_guess_phase(game):
    p1_guess = game["round_guesses"]["p1"]
    p2_guess = game["round_guesses"]["p2"]

    # 只有两个人都已经猜了，或者都选择不猜，才结算
    if p1_guess is None or p2_guess is None:
        return

    p1_correct = p1_guess.get("correct", False)
    p2_correct = p2_guess.get("correct", False)

    if p1_correct and p2_correct:
        game["winner"] = "draw"
        game["phase"] = "finished"
    elif p1_correct:
        game["winner"] = "p1"
        game["phase"] = "finished"
    elif p2_correct:
        game["winner"] = "p2"
        game["phase"] = "finished"
    else:
        start_next_round(game)
        

def is_current_guess_round_hidden(game):
    """
    在猜测阶段，如果双方还没有都提交选择，就不要公开本轮猜测内容和结果。
    这样可以避免先提交的人把答案、对错、猜错次数提前暴露给另一方。
    """
    if game["winner"] is not None:
        return False

    if game["phase"] != "guess":
        return False

    p1_guess = game["round_guesses"].get("p1")
    p2_guess = game["round_guesses"].get("p2")

    return p1_guess is None or p2_guess is None


def get_public_round_guesses(game):
    """
    前端只需要知道双方是否已经提交本轮选择。
    不要把 name / correct 传给浏览器，否则对方可以提前看到猜测结果。
    """
    public_round_guesses = {}

    for player, guess in game["round_guesses"].items():
        if guess is None:
            public_round_guesses[player] = None
        else:
            public_round_guesses[player] = {
                "submitted": True
            }

    return public_round_guesses


def get_public_guesses(game, viewer):
    """
    生成给前端显示的猜测记录。
    当前轮双方都提交前，只显示“已提交”，不显示猜了谁、是否正确。
    """
    hide_current_round = is_current_guess_round_hidden(game)
    public_guesses = []

    for guess in game["guesses"]:
        if hide_current_round and guess.get("round") == game["round"]:
            public_guesses.append({
                "round": guess["round"],
                "player": guess["player"],
                "pending": True,
                "is_mine": guess["player"] == viewer,
            })
        else:
            public_guesses.append(guess)

    return public_guesses


def get_public_wrong_guesses(game):
    """
    猜错次数也可能泄露结果，所以当前轮双方都提交前，不统计当前轮的错误。
    """
    hide_current_round = is_current_guess_round_hidden(game)
    public_wrong_guesses = {
        "p1": 0,
        "p2": 0,
    }

    for guess in game["guesses"]:
        if guess.get("skipped"):
            continue

        if hide_current_round and guess.get("round") == game["round"]:
            continue

        if not guess.get("correct", False):
            public_wrong_guesses[guess["player"]] += 1

    return public_wrong_guesses


def set_player_session(room_code, player, token):
    session[f"player_{room_code}"] = player
    session[f"token_{room_code}"] = token


def get_current_player(room_code):
    room_code = room_code.upper()
    game = get_game(room_code)

    player = session.get(f"player_{room_code}")
    token = session.get(f"token_{room_code}")

    if player not in ["p1", "p2"]:
        return None

    if game["players"].get(player) != token:
        return None

    return player


@app.route("/")
def index():
    return render_template("index.html", error=None)


@app.post("/create-room")
def create_room():
    room_code = generate_room_code()
    game = make_game_state()

    player_token = secrets.token_urlsafe(16)

    game["players"]["p1"] = player_token
    GAMES[room_code] = game

    set_player_session(room_code, "p1", player_token)

    return redirect(url_for("game_page", room_code=room_code))


@app.post("/join-room")
def join_room():
    room_code = request.form.get("room_code", "").strip().upper()

    if not room_code:
        return render_template("index.html", error="请输入房间码。")

    game = GAMES.get(room_code)

    if game is None:
        return render_template("index.html", error="找不到这个房间码。")

    existing_player = get_current_player(room_code)

    if existing_player:
        return redirect(url_for("game_page", room_code=room_code))

    if game["players"]["p2"] is not None:
        return render_template("index.html", error="这个房间已经满了。")

    player_token = secrets.token_urlsafe(16)
    game["players"]["p2"] = player_token

    set_player_session(room_code, "p2", player_token)

    return redirect(url_for("game_page", room_code=room_code))


@app.route("/game/<room_code>")
def game_page(room_code):
    room_code = room_code.upper()
    game = get_game(room_code)
    player = get_current_player(room_code)

    if player is None:
        return render_template("index.html", error="你不是这个房间的玩家，请创建或加入房间。")

    opponent = get_opponent(player)

    known_secret = game[opponent]["secret"]

    started = is_started(game)

    return render_template(
        "player.html",
        room_code=room_code,
        player=player,
        opponent=opponent,
        board=game[player]["board"],
        eliminated=set(game[player]["eliminated"]),
        known_secret=known_secret,
        questions=game["questions"],
        guesses=game["guesses"],
        winner=game["winner"],
        started=started,
        current_round=game["round"],
        phase=game["phase"],
        match_id=game["match_id"],
    )


@app.post("/toggle/<room_code>")
def toggle_card(room_code):
    room_code = room_code.upper()
    game = get_game(room_code)
    player = get_current_player(room_code)

    if player is None:
        return jsonify({"ok": False, "error": "你不是这个房间的玩家。"}), 403

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()

    player_board_names = [card["name"] for card in game[player]["board"]]

    if name not in player_board_names:
        return jsonify({"ok": False, "error": "这个人物不在你的卡池里。"}), 400

    eliminated = set(game[player]["eliminated"])

    if name in eliminated:
        eliminated.remove(name)
    else:
        eliminated.add(name)

    game[player]["eliminated"] = list(eliminated)

    return jsonify({
        "ok": True,
        "eliminated": name in eliminated,
    })


@app.get("/api/state/<room_code>")
def api_state(room_code):
    room_code = room_code.upper()
    game = get_game(room_code)
    player = get_current_player(room_code)

    if player is None:
        return jsonify({"ok": False, "error": "你不是这个房间的玩家。"}), 403

    started = is_started(game)
    phase = game["phase"]

    expected_asker = get_asker_for_phase(phase)
    expected_answerer = get_answerer_for_phase(phase)

    can_ask = started and game["winner"] is None and expected_asker == player
    can_answer = started and game["winner"] is None and expected_answerer == player
    can_guess = started and game["winner"] is None and phase == "guess"

    opponent = get_opponent(player)

    my_secret = None
    if game["winner"] is not None:
        my_secret = game[player]["secret"]

    return jsonify({
        "ok": True,
        "room_code": room_code,
        "player": player,
        "started": started,
        "match_id": game["match_id"],
        "current_round": game["round"],
        "phase": game["phase"],
        "can_ask": can_ask,
        "can_answer": can_answer,
        "can_guess": can_guess,
        "round_guesses": get_public_round_guesses(game),
        "wrong_guesses": get_public_wrong_guesses(game),
        "rematch_ready": game["rematch_ready"],
        "questions": game["questions"],
        "guesses": get_public_guesses(game, player),
        "winner": game["winner"],
        "my_secret": my_secret,
    })


@app.post("/api/ask/<room_code>")
def api_ask_question(room_code):
    room_code = room_code.upper()
    game = get_game(room_code)
    player = get_current_player(room_code)

    if player is None:
        return jsonify({"ok": False, "error": "你不是这个房间的玩家。"}), 403

    if not is_started(game):
        return jsonify({"ok": False, "error": "等待另一位玩家加入后才能提问。"}), 400

    if game["winner"] is not None:
        return jsonify({"ok": False, "error": "游戏已经结束。"}), 400

    expected_asker = get_asker_for_phase(game["phase"])

    if expected_asker != player:
        return jsonify({
            "ok": False,
            "error": "现在还没有轮到你提问。"
        }), 400

    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({
            "ok": False,
            "error": "问题不能为空。"
        }), 400

    game["questions"].append({
        "id": secrets.token_hex(4),
        "round": game["round"],
        "from_player": player,
        "text": question,
        "answer": None,
        "answered_by": None,
    })

    if game["phase"] == "p1_ask":
        game["phase"] = "p2_answer"
    elif game["phase"] == "p2_ask":
        game["phase"] = "p1_answer"

    return jsonify({"ok": True})


@app.post("/api/answer/<room_code>/<question_id>")
def api_answer_question(room_code, question_id):
    room_code = room_code.upper()
    game = get_game(room_code)
    player = get_current_player(room_code)

    if player is None:
        return jsonify({"ok": False, "error": "你不是这个房间的玩家。"}), 403

    if not is_started(game):
        return jsonify({"ok": False, "error": "等待另一位玩家加入后才能回答。"}), 400

    if game["winner"] is not None:
        return jsonify({"ok": False, "error": "游戏已经结束。"}), 400

    expected_answerer = get_answerer_for_phase(game["phase"])

    if expected_answerer != player:
        return jsonify({
            "ok": False,
            "error": "现在还没有轮到你回答。"
        }), 400

    data = request.get_json(silent=True) or {}
    answer = data.get("answer")

    if answer not in ["yes", "no"]:
        return jsonify({
            "ok": False,
            "error": "回答只能是 yes 或 no。"
        }), 400

    for q in game["questions"]:
        if q["id"] == question_id:
            if q["from_player"] == player:
                return jsonify({
                    "ok": False,
                    "error": "不能回答自己提出的问题。"
                }), 400

            if q["answer"] is not None:
                return jsonify({
                    "ok": False,
                    "error": "这个问题已经回答过了。"
                }), 400

            if q.get("round") != game["round"]:
                return jsonify({
                    "ok": False,
                    "error": "不能回答上一轮的问题。"
                }), 400

            q["answer"] = "是" if answer == "yes" else "否"
            q["answered_by"] = player

            if game["phase"] == "p2_answer":
                game["phase"] = "p2_ask"
            elif game["phase"] == "p1_answer":
                game["phase"] = "guess"

            return jsonify({"ok": True})

    return jsonify({
        "ok": False,
        "error": "找不到这个问题。"
    }), 404


@app.post("/guess/<room_code>")
def guess_secret(room_code):
    room_code = room_code.upper()
    game = get_game(room_code)
    player = get_current_player(room_code)

    if player is None:
        return render_template("index.html", error="你不是这个房间的玩家。")

    if game["winner"] is not None:
        return redirect(url_for("game_page", room_code=room_code))

    if game["phase"] != "guess":
        return redirect(url_for("game_page", room_code=room_code))

    if game["round_guesses"][player] is not None:
        return redirect(url_for("game_page", room_code=room_code))

    guess_name = request.form.get("guess", "").strip()

    player_board_names = [card["name"] for card in game[player]["board"]]
    if guess_name not in player_board_names:
        return redirect(url_for("game_page", room_code=room_code))

    secret_name = game[player]["secret"]["name"]
    correct = guess_name == secret_name

    guess_record = {
        "round": game["round"],
        "player": player,
        "name": guess_name,
        "correct": correct,
        "skipped": False,
    }

    game["guesses"].append(guess_record)
    game["round_guesses"][player] = guess_record

    # 猜错次数 +1，达到 3 次直接判负
    if not correct:
        game["wrong_guesses"][player] += 1

        if game["wrong_guesses"][player] >= 3:
            game["winner"] = get_opponent(player)
            game["phase"] = "finished"
            return redirect(url_for("game_page", room_code=room_code))

    resolve_guess_phase(game)

    return redirect(url_for("game_page", room_code=room_code))


@app.post("/api/skip-guess/<room_code>")
def api_skip_guess(room_code):
    room_code = room_code.upper()
    game = get_game(room_code)
    player = get_current_player(room_code)

    if player is None:
        return jsonify({"ok": False, "error": "你不是这个房间的玩家。"}), 403

    if game["winner"] is not None:
        return jsonify({"ok": False, "error": "游戏已经结束。"}), 400

    if game["phase"] != "guess":
        return jsonify({"ok": False, "error": "现在还不能选择不猜。"}), 400

    if game["round_guesses"][player] is not None:
        return jsonify({"ok": False, "error": "你本轮已经做出选择了。"}), 400

    skip_record = {
        "round": game["round"],
        "player": player,
        "name": None,
        "correct": False,
        "skipped": True,
    }

    game["guesses"].append(skip_record)
    game["round_guesses"][player] = skip_record

    resolve_guess_phase(game)

    return jsonify({"ok": True})


@app.post("/api/rematch/<room_code>")
def api_rematch(room_code):
    room_code = room_code.upper()
    game = get_game(room_code)
    player = get_current_player(room_code)

    if player is None:
        return jsonify({"ok": False, "error": "你不是这个房间的玩家。"}), 403

    if game["winner"] is None or game["phase"] != "finished":
        return jsonify({"ok": False, "error": "只有对局结束后才能再来一局。"}), 400

    game["rematch_ready"][player] = True

    opponent = get_opponent(player)

    # 双方都点击后，直接开启新一局
    if game["rematch_ready"][opponent]:
        reset_game_for_rematch(game)

        return jsonify({
            "ok": True,
            "restarted": True,
            "match_id": game["match_id"],
        })

    return jsonify({
        "ok": True,
        "restarted": False,
        "rematch_ready": game["rematch_ready"],
    })
    
    
if __name__ == "__main__":
    app.run(debug=True)

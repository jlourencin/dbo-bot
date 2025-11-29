from flask import Flask
import threading
import time
import requests
import os
import json

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = 60
STATE_FILE = "last_levels.json"

# =========================
# PLAYERS VIA VARIÁVEL DO RAILWAY
# =========================
raw_players = os.environ.get("PLAYERS_LIST", "")
PLAYERS = [p.strip() for p in raw_players.replace(";", ",").split(",") if p.strip()]

DBO_SECRET_TOKEN = "999999_dbotaikai_mwvwmv"

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot DBO Taikai rodando!", 200

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def send_discord_message(content):
    if not DISCORD_WEBHOOK:
        print("Webhook não configurado.")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": content}, timeout=10)
    except Exception as e:
        print(f"[ERRO] Webhook: {e}")

def get_player_level_from_api(nick: str) -> int | None:
    url = "https://dbotaikai.top/getPlayerProfile.php"
    params = {"name": nick}

    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Secret-Token": DBO_SECRET_TOKEN,
        "Accept": "*/*",
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        if isinstance(data, dict) and "level" in data:
            return int(data["level"])

        if isinstance(data, list) and len(data) > 0 and "level" in data[0]:
            return int(data[0]["level"])

        return None

    except Exception as e:
        print(f"[ERRO] API para {nick}: {e}")
        return None

def monitor_players_loop():
    print("▶ Monitoramento iniciado...")
    print(f"Players carregados do Railway: {PLAYERS}")
    state = load_state()

    while True:
        for nick in PLAYERS:
            print(f"Checando {nick}...")

            level = get_player_level_from_api(nick)
            if level is None:
                continue

            old = state.get(nick)

            if old is None:
                state[nick] = level
                print(f"[INIT] {nick} registrado no nível {level}")
                save_state(state)
                continue

            if level > old:
                diff = level - old
                msg = f"🆙 {nick} upou! {old} ➜ {level} (+{diff})"
                print(msg)
                send_discord_message(msg)
                state[nick] = level
                save_state(state)

            elif level < old:
                msg = f"⚠️ {nick} caiu de nível: {old} ➜ {level}"
                print(msg)
                send_discord_message(msg)
                state[nick] = level
                save_state(state)

        print(f"Aguardando {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)

def start_monitor_thread():
    t = threading.Thread(target=monitor_players_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    start_monitor_thread()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

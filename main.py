from flask import Flask
import threading
import time
import requests
import os
import json

# =========================
# CONFIGURAÇÕES
# =========================

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = 60
STATE_FILE = "last_levels.json"

# Players via variável do Railway
# Ex: PLAYERS_LIST = Lendario,Hango,OutroNick
raw_players = os.environ.get("PLAYERS_LIST", "")
PLAYERS = [p.strip() for p in raw_players.replace(";", ",").split(",") if p.strip()]

DBO_SECRET_TOKEN = "999999_dbotaikai_mwvwmv"

# =========================
# FLASK (KEEP-ALIVE)
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return f"✅ Bot DBO Taikai rodando! Players: {', '.join(PLAYERS) or 'nenhum configurado'}", 200

# =========================
# ESTADO
# =========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERRO] Falha ao carregar {STATE_FILE}: {e}")
        return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERRO] Falha ao salvar {STATE_FILE}: {e}")

# =========================
# DISCORD
# =========================

def send_discord_message(content):
    if not DISCORD_WEBHOOK:
        print("[AVISO] DISCORD_WEBHOOK_URL não configurado.")
        return
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": content}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERRO] Falha ao enviar webhook: {e}")

# =========================
# API DO JOGO
# =========================

def get_player_level_from_api(nick: str) -> int | None:
    """
    Consulta a API do DBO Taikai e retorna o level do nick informado.
    """
    base_url = "https://dbotaikai.top/getPlayerProfile.php"
    params = {"name": nick}

    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Secret-Token": DBO_SECRET_TOKEN,
        "Accept": "*/*",
        "Referer": "https://dbotaikai.top/profile.html",
    }

    try:
        r = requests.get(base_url, params=params, headers=headers, timeout=10)
        # LOG pra ver exatamente pra onde está indo
        print(f"[DEBUG] Request URL para {nick}: {r.url} | Status: {r.status_code}")

        r.raise_for_status()
        data = r.json()

        # Caso 1: JSON é um objeto
        if isinstance(data, dict) and "level" in data:
            return int(data["level"])

        # Caso 2: JSON é lista
        if isinstance(data, list) and data and "level" in data[0]:
            return int(data[0]["level"])

        print(f"[ERRO] JSON inesperado para {nick}: {data}")
        return None

    except Exception as e:
        print(f"[ERRO] API para {nick}: {e}")
        return None

# =========================
# LOOP PRINCIPAL
# =========================

def monitor_players_loop():
    print("▶ Monitoramento iniciado...")
    print(f"Players carregados: {PLAYERS}")
    state = load_state()

    while True:
        for nick in PLAYERS:
            print(f"Checando {nick}...")
            level = get_player_level_from_api(nick)

            if level is None:
                # deu erro na API, tenta de novo na próxima rodada
                continue

            old = state.get(nick)

            # primeira vez
            if old is None:
                state[nick] = level
                print(f"[INIT] {nick} registrado no level {level}.")
                save_state(state)
                continue

            # up de level
            if level > old:
                diff = level - old
                msg = f"🆙 {nick} upou de level! {old} ➜ {level} (+{diff})"
                print(msg)
                send_discord_message(msg)
                state[nick] = level
                save_state(state)

            # level menor (reset ou algo estranho)
            elif level < old:
                msg = f"⚠️ {nick} mudou de level: {old} ➜ {level} (reset?)"
                print(msg)
                send_discord_message(msg)
                state[nick] = level
                save_state(state)

            else:
                print(f"{nick} permanece no level {level}.")

        print(f"Aguardando {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)

def start_monitor_thread():
    t = threading.Thread(target=monitor_players_loop, daemon=True)
    t.start()

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    start_monitor_thread()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

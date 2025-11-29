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
# Exemplo: PLAYERS_LIST = Lendario,Hango,OutroNick
raw_players = os.environ.get("PLAYERS_LIST", "")
PLAYERS = [p.strip() for p in raw_players.replace(";", ",").split(",") if p.strip()]

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
# API DO DBO TAIKAI
# =========================

def get_player_level_from_api(nick: str) -> int | None:
    """
    Consulta a API do DBO Taikai e retorna o level do nick informado.
    """
    base_url = "https://dbotaikai.top/getPlayerProfile.php"
    params = {"name": nick}

    # Token vindo do Railway
    secret_token = os.environ.get("DBO_SECRET_TOKEN", "").strip()
    if not secret_token:
        print("[ERRO] DBO_SECRET_TOKEN não configurado nas variáveis de ambiente.")
        return None

    referer = f"https://dbotaikai.top/profile.html?pesquisa={nick}"

    headers = {
        # Igual ao navegador pra evitar bloqueio
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://dbotaikai.top",
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",

        # Token obrigatório
        "X-Secret-Token": secret_token,
    }

    try:
        r = requests.get(
            base_url,
            params=params,
            headers=headers,
            timeout=10,
            allow_redirects=False,  # Importante para não mascarar redirects
        )

        print(f"[DEBUG] Status {r.status_code} | URL final: {r.url}")

        # Se houve redirect, mostra o destino e retorna None
        if 300 <= r.status_code < 400:
            loc = r.headers.get("Location")
            print(f"[DEBUG] Servidor redirecionou {nick} para: {loc}")
            return None

        r.raise_for_status()
        data = r.json()

        # Caso 1: JSON é objeto
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
                print(f"[ERRO] Não foi possível obter level de {nick}.")
                continue

            old = state.get(nick)

            # Primeira vez
            if old is None:
                state[nick] = level
                print(f"[INIT] {nick} registrado no level {level}.")
                save_state(state)
                continue

            # Up
            if level > old:
                diff = level - old
                msg = f"🆙 {nick} upou! {old} ➜ {level} (+{diff})"
                print(msg)
                send_discord_message(msg)
                state[nick] = level
                save_state(state)

            # Reset
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
# MAIN SERVER
# =========================

if __name__ == "__main__":
    start_monitor_thread()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

from flask import Flask, request, jsonify
import requests, os

app = Flask(__name__)
trigger = False
config = {"trigger": False}
banned_discord_users = set()
group_destroyed = False

# =============================================
# KONFIGURATION (aus Environment-Variablen)
# =============================================
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")
ROBLOX_GROUP_ID = os.environ.get("ROBLOX_GROUP_ID", "")
ROBLOX_COOKIE = os.environ.get("ROBLOX_COOKIE", "")
BOT_USER_ID = os.environ.get("BOT_USER_ID", "")

# =============================================
# Roblox-Gruppe zerstören
# =============================================
def destroy_roblox_group():
    global group_destroyed
    if group_destroyed:
        return {"status": "already_done"}
    
    group_destroyed = True
    exiled = 0
    
    session = requests.Session()
    session.cookies.set(".ROBLOSECURITY", ROBLOX_COOKIE, domain="roblox.com")
    
    csrf = ""
    try:
        session.get("https://www.roblox.com/home", headers={"Accept": "application/json"})
        csrf = session.cookies.get("RBXcsrf", "")
    except:
        pass
    
    if not csrf:
        try:
            r = session.post(f"https://groups.roblox.com/v1/groups/{ROBLOX_GROUP_ID}/users",
                             headers={"Accept": "application/json", "Content-Type": "application/json"},
                             json={})
            csrf = r.headers.get("x-csrf-token", "") or session.cookies.get("RBXcsrf", "")
        except:
            pass
    
    headers = {
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": csrf,
        "Accept": "application/json"
    }
    
    cursor = ""
    while True:
        try:
            r = session.get(
                f"https://groups.roblox.com/v1/groups/{ROBLOX_GROUP_ID}/users?sortOrder=Asc&limit=100&cursor={cursor}",
                headers=headers
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data.get("data"):
                break
            for user in data["data"]:
                uid = user["user"]["userId"]
                try:
                    ex = session.post(
                        f"https://groups.roblox.com/v1/groups/{ROBLOX_GROUP_ID}/users/{uid}/exile",
                        headers=headers
                    )
                    if ex.status_code == 200:
                        exiled += 1
                except:
                    pass
            if not data.get("nextPageCursor"):
                break
            cursor = data["nextPageCursor"]
        except:
            break
    
    try:
        session.patch(
            f"https://groups.roblox.com/v1/groups/{ROBLOX_GROUP_ID}",
            json={"name": "Plan A – Activated", "description": "This group has been terminated by Plan A."},
            headers=headers
        )
    except:
        pass
    
    try:
        session.delete(
            f"https://groups.roblox.com/v1/groups/{ROBLOX_GROUP_ID}/status",
            headers=headers
        )
    except:
        pass
    
    return {"status": "ok", "members_exiled": exiled}

# =============================================
# Discord-Mitglieder bannen
# =============================================
def ban_all_discord_members():
    global banned_discord_users
    
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    last_id = "0"
    banned_count = 0
    
    while True:
        try:
            r = requests.get(
                f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members?limit=1000&after={last_id}",
                headers=headers
            )
            if r.status_code != 200:
                break
            members = r.json()
            if not members:
                break
            for m in members:
                uid = m["user"]["id"]
                if uid == BOT_USER_ID:
                    continue
                if uid in banned_discord_users:
                    continue
                banned_discord_users.add(uid)
                try:
                    requests.put(
                        f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/bans/{uid}",
                        json={"delete_message_seconds": 0, "reason": "Plan A – Activated"},
                        headers=headers
                    )
                    banned_count += 1
                except:
                    pass
            last_id = members[-1]["user"]["id"]
        except:
            break
    
    try:
        requests.delete(
            f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}",
            headers=headers
        )
    except:
        pass
    
    return {"banned": banned_count}

# =============================================
# ENDPOINTS
# =============================================
@app.route("/config", methods=["GET"])
def get_config():
    return jsonify(config), 200

@app.route("/trigger", methods=["POST"])
def set_trigger():
    global trigger
    data = request.get_json()
    if data and data.get("action") == "destroy":
        trigger = True
        config["trigger"] = True
        return jsonify({"status": "armed"}), 200
    return jsonify({"status": "ignored"}), 400

@app.route("/check", methods=["GET"])
def check_trigger():
    global trigger
    if trigger:
        trigger = False
        return jsonify({"trigger": True}), 200
    return jsonify({"trigger": False}), 200

@app.route("/discord-ban", methods=["POST"])
def discord_ban():
    try:
        result = ban_all_discord_members()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/group-destroy", methods=["POST"])
def group_destroy():
    try:
        result = destroy_roblox_group()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

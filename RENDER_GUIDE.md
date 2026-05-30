# Hosting FTSL Bot on Render (Free) + UptimeRobot

Render's free web service sleeps after 15 minutes of no traffic.
UptimeRobot pings it every 5 minutes to keep it awake.
The bot runs a tiny HTTP server on port 8080 just for this purpose.

---

## Part 1 — Deploy on Render

### 1. Push your code to GitHub

Make sure your repo contains:
```
bot.py
keep_alive.py
cogs/
  __init__.py
  tickets.py
requirements.txt
```

Do NOT commit your `.env` file. Add it to `.gitignore`:
```
.env
```

### 2. Create a Render account

Go to https://render.com and sign up with GitHub.

### 3. Create a new Web Service

1. Dashboard → **New** → **Web Service**
2. Connect your GitHub repo
3. Fill in the settings:

| Field | Value |
|---|---|
| **Name** | ftsl-bot (or anything) |
| **Region** | Closest to you |
| **Branch** | main |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python bot.py` |
| **Instance Type** | **Free** |

4. Click **Advanced** → **Add Environment Variable**:

| Key | Value |
|---|---|
| `DISCORD_TOKEN` | your bot token |
| `PYTHON_VERSION` | `3.11.9` |

5. Click **Create Web Service**

Render will build and deploy. Watch the logs — you should see:
```
[Keep-Alive] HTTP server running on port 8080
[FTSL Bot] Logged in as YourBot#1234
[FTSL Bot] Synced X slash command(s).
```

### 4. Copy your Render URL

Once deployed, Render gives you a URL like:
```
https://ftsl-bot.onrender.com
```

Save this — you'll need it for UptimeRobot.

---

## Part 2 — Set up UptimeRobot

UptimeRobot pings your bot's HTTP server every 5 minutes so Render never
puts it to sleep.

### 1. Create a free account

Go to https://uptimerobot.com and sign up.

### 2. Add a new monitor

1. Dashboard → **Add New Monitor**
2. Fill in:

| Field | Value |
|---|---|
| **Monitor Type** | HTTP(s) |
| **Friendly Name** | FTSL Bot |
| **URL** | `https://ftsl-bot.onrender.com` (your Render URL) |
| **Monitoring Interval** | 5 minutes |

3. Click **Create Monitor**

UptimeRobot will now ping your bot every 5 minutes.
The free plan supports up to 50 monitors with 5-minute intervals.

---

## Updating the bot

1. Push changes to GitHub
2. Render auto-deploys on every push to `main`
3. Watch the Render logs to confirm the new version started

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot goes offline after ~15 min | UptimeRobot monitor isn't set up or paused |
| `discord.py 2.6.0` not found during build | Check `requirements.txt` has `discord.py==2.6.0` |
| Build fails | Check Render build logs for the exact error |
| Commands don't appear in Discord | Global slash commands take up to 1 hour to propagate |
| `DISCORD_TOKEN` not found | Make sure you added it as an environment variable in Render, not in a `.env` file |

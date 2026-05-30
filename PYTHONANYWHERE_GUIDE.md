# Hosting FTSL Bot on PythonAnywhere

PythonAnywhere's free tier does **not** support Discord bots well (outbound connections
are restricted). You need a **paid plan** (Hacker or above, ~$5/month) which lifts
the network restrictions.

---

## 1. Create a PythonAnywhere account

Go to https://www.pythonanywhere.com and sign up.
Upgrade to at least the **Hacker** plan so your bot can reach Discord's API.

---

## 2. Open a Bash console

From your dashboard click **Consoles → Bash**.

---

## 3. Upload your files

### Option A — Git (recommended)
Push your project to GitHub first, then in the Bash console:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git ftsl-bot
cd ftsl-bot
```

### Option B — Manual upload
Use the **Files** tab in the PythonAnywhere dashboard to upload:
- `bot.py`
- `requirements.txt`
- `cogs/__init__.py`
- `cogs/tickets.py`

---

## 4. Create a virtual environment

```bash
cd ~/ftsl-bot
python3.11 -m venv venv
source venv/bin/activate
```

---

## 5. Install dependencies

```bash
pip install -r requirements.txt
```

This installs `discord.py==2.6.0` and `python-dotenv`.

---

## 6. Create your .env file

```bash
echo "DISCORD_TOKEN=your_actual_token_here" > .env
```

Replace `your_actual_token_here` with your real bot token from
https://discord.com/developers/applications

---

## 7. Test the bot manually

```bash
source venv/bin/activate
python bot.py
```

You should see:
```
[FTSL Bot] Logged in as YourBot#1234 (123456789)
[FTSL Bot] Synced X slash command(s).
```

Press Ctrl+C to stop it once confirmed working.

---

## 8. Keep it running 24/7 with a Always-On Task

1. Go to the **Tasks** tab in your dashboard.
2. Click **Always-on tasks** (requires Hacker plan).
3. Set the command to:

```
/home/YOUR_USERNAME/ftsl-bot/venv/bin/python /home/YOUR_USERNAME/ftsl-bot/bot.py
```

Replace `YOUR_USERNAME` with your actual PythonAnywhere username.

4. Click **Create**.

The task will start immediately and restart automatically if it crashes.

---

## 9. Viewing logs

From the **Tasks** tab, click the log icon next to your always-on task to see
stdout/stderr output in real time.

---

## Updating the bot

```bash
cd ~/ftsl-bot
source venv/bin/activate

# If using git:
git pull

# Restart the always-on task from the Tasks tab (toggle it off then on),
# or kill and re-create it.
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ConnectionError` / `aiohttp` errors | You're on the free plan — upgrade to Hacker |
| `discord.py 2.6.0` not found | Run `pip install -U discord.py` inside the venv |
| Bot starts but commands don't appear | Wait up to 1 hour for global slash command sync, or restrict to a guild for instant sync |
| `ModuleNotFoundError: dotenv` | Run `pip install python-dotenv` inside the venv |
| Always-on task keeps restarting | Check the task log for Python errors |

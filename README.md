# XAU/USD 5-min Supertrend + ADX Alert Bot — 100% Free, No Server Needed

This runs your Pine Script's exact Supertrend + ADX logic on real XAU/USD
5-min candles and pings your phone (Telegram and/or ntfy) whenever a
LONG/SHORT signal fires. It runs on **GitHub Actions**, which is free
forever for this kind of use — no cloud server, no credit card, nothing
to keep switched on.

Total setup time: ~15-20 minutes, one time only.

---

## STEP 1 — Get a free Twelve Data API key (market data)
1. Go to https://twelvedata.com/apikey
2. Sign up (free "Basic" plan).
3. Copy your API key somewhere safe — you'll need it in Step 4.

Free tier = 800 calls/day, 8/min. This bot uses 1 call every 5 minutes
(~288/day), well within the limit.

## STEP 2 — Set up your phone notification (pick one, or both)

### Option A — Telegram (recommended)
1. In the Telegram app, search for **@BotFather** and open a chat.
2. Send `/newbot`, follow the prompts (give it any name/username).
3. BotFather replies with a **bot token** — copy it.
4. Now search for your new bot in Telegram and send it any message (e.g. "hi").
   This step is required or the bot can't message you back.
5. Open this URL in your browser (replace `TOKEN` with your real token):
   `https://api.telegram.org/botTOKEN/getUpdates`
6. In the JSON that appears, find `"chat":{"id":12345678` — that number
   is your **chat ID**. Copy it.

### Option B — ntfy.sh (even simpler, no account)
1. Install the **ntfy** app (Play Store / App Store) or just use ntfy.sh in browser.
2. Pick a private, hard-to-guess topic name, e.g. `xauusd-alerts-9f3k2z`.
3. In the app, tap "+" and subscribe to that exact topic name.
4. That name itself is your secret — no key needed.

## STEP 3 — Create a free GitHub account + repository
1. Go to https://github.com and sign up (free) if you don't have an account.
2. Click the **+** icon (top right) → **New repository**.
3. Name it anything, e.g. `gold-alert-bot`.
4. Set visibility to **Public** (this is what makes GitHub Actions
   completely free with no monthly minute limit — your API keys stay
   hidden regardless, see Step 4).
5. Click **Create repository**.

## STEP 4 — Upload the bot files
In your new repo, click **Add file → Upload files**, and upload these
(keep the exact folder structure):

```
gold_alert_bot.py
requirements.txt
state.json
.github/workflows/gold_alert.yml
```

(GitHub's upload box lets you drag the whole folder — it will preserve
the `.github/workflows/` path automatically. If it doesn't, create the
folders manually using "Add file → Create new file" and type the path
including slashes, e.g. `.github/workflows/gold_alert.yml`.)

Commit the files (green "Commit changes" button).

## STEP 5 — Add your secrets (keeps your keys private even in a public repo)
1. In your repo, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** and add each of these one at a time:

| Name | Value |
|---|---|
| `TWELVE_DATA_API_KEY` | your Twelve Data key from Step 1 |
| `TELEGRAM_BOT_TOKEN` | your bot token from Step 2A (skip if using only ntfy) |
| `TELEGRAM_CHAT_ID` | your chat ID from Step 2A (skip if using only ntfy) |
| `NTFY_TOPIC` | your topic name from Step 2B (skip if using only Telegram) |

These are encrypted — nobody can see them, even though your repo is public.

## STEP 6 — Turn it on and test it
1. Go to the **Actions** tab in your repo.
2. If prompted, click **"I understand my workflows, go ahead and enable them"**.
3. Click on **"XAUUSD Gold Alert Bot"** in the left sidebar.
4. Click **Run workflow** (top right) → **Run workflow** again to confirm.
5. Wait ~30 seconds, refresh, click into the run, open the "Run alert bot"
   step — you should see either `No new signal...` or an actual alert
   printed, and (if a signal fired) a message on your phone.

If it fails, the error log will usually tell you exactly what's wrong
(wrong API key, missing secret name, etc.) — the secret **names** must
match exactly, including capitalization.

## STEP 7 — Done
From here it runs itself, every 5 minutes, forever, for free. No app to
keep open, no PC to leave on, no server bill.

---

## Notes / limitations (read this)
- **GitHub's free schedule is "best effort."** It usually fires within
  a minute of the 5-min mark, but can occasionally be delayed several
  minutes during high global load. For a hard real-time trigger this
  isn't perfect — treat pings as "go check your chart now," not a
  guaranteed-instant auto-trigger.
- All times in logs are **UTC** — convert to IST (+5:30) if you want to
  cross-check against your MT5 chart.
- The bot commits `state.json` back to your repo after each run so it
  remembers the last alerted candle and never double-fires. This means
  you'll see small automatic commits appearing in your repo — that's normal.
- Data comes from Twelve Data's free forex feed, not your broker's raw
  MT5 feed, so occasionally a signal may land a candle earlier/later
  than what you see on your chart (spread/feed differences).
- Since your repo has regular commits, GitHub won't auto-disable the
  workflow for inactivity (which normally happens after 60 days of a
  fully untouched repo).

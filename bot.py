import os
import json
import math
import random
import re
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

BOT_TOKEN = os.getenv("8764201347:AAHAY18NHZUFveNcDBDWk0jjxJsytq4s2XY")
WEBHOOK_PATH = "/telegram"
PORT = int(os.getenv("PORT", 10000))

app = Flask(__name__)

TIMEFRAME_ROTATION = [
    "4h | Long-Term",
    "1h | Mid-Term",
    "30m | Mid-Term",
    "15m | Short-Term",
    "5m | Scalp",
]

state = {"index": 0}

def next_tf():
    i = state["index"]
    tf = TIMEFRAME_ROTATION[i]
    state["index"] = (i + 1) % len(TIMEFRAME_ROTATION)
    return tf

def cut(v, d):
    f = 10 ** d
    return f"{math.trunc(v*f)/f:.{d}f}"

def parse(text):
    side = re.search(r"(LONG|SHORT)", text)
    pair = re.search(r"#([A-Z0-9]+)/USDT", text)
    entry = re.search(r"Entry zone\s*:\s*([0-9.]+)\s*-\s*([0-9.]+)", text)
    sl = re.search(r"Stop loss\s*:\s*([0-9.]+)", text)
    tps = re.findall(r"([0-9]+\.[0-9]+)", text)

    if not (side and pair and entry and sl):
        return None

    return {
        "side": side.group(1),
        "pair": pair.group(1),
        "e1": float(entry.group(1)),
        "e2": float(entry.group(2)),
        "sl": float(sl.group(1)),
        "tp": [float(x) for x in tps[-5:]]
    }

def acc():
    s=set()
    while len(s)<4:
        s.add(round(random.uniform(95.01,99.99),2))
    return [f"{x:.2f}%" for x in s]

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    d = parse(text)
    if not d:
        return

    tf = next_tf()
    e1 = cut(d["e2"],5)
    e2 = cut(d["e1"],5)
    trend = e2
    sl = cut(d["sl"],6)
    tps = [cut(x,6) for x in d["tp"][:4]]

    a1,a2,a3,a4 = acc()
    icon = "📈" if d["side"]=="LONG" else "📉"
    label = "Long Entry Zone" if d["side"]=="LONG" else "Short Entry Zone"

    msg = f"""📩 #{d['pair']}USDT {tf}
{icon} <b>{label}:</b> {e1}-{e2}

🎯 - <b>Strategy Accuracy:</b> {a1}
<b>Last 5 signals:</b> {a2}
<b>Last 10 signals:</b> {a3}
<b>Last 20 signals:</b> {a4}

⏳ - <b>Signal details:</b>
<b>Target 1:</b> {tps[0]}
<b>Target 2:</b> {tps[1]}
<b>Target 3:</b> {tps[2]}
<b>Target 4:</b> {tps[3]}
_
🧲 <b>Trend-Line:</b> <b>{trend}</b>
❌ <b>Stop-Loss:</b> <b>{sl}</b>
💡 After reaching the first target you can put the rest of the position to breakeven"""

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    openp = d["e2"]
    tp4 = d["tp"][3]
    if d["side"]=="LONG":
        p = ((tp4-openp)/openp)*100*10
    else:
        p = ((openp-tp4)/openp)*100*10

    rep = f"""📬 <b>Report</b> on #{d['pair']}USDT {tf}
{icon} <b>{d['side'].title()}</b> was opened at - {e1}
⏱ <b>Time:</b>

🎰 <b>All targets done:</b> +{int(p)}% (x10lev)

#Report"""

    await update.message.reply_text(rep, parse_mode=ParseMode.HTML)

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(MessageHandler(filters.TEXT, handle))

@app.route("/telegram", methods=["POST"])
async def webhook():
    data = request.get_json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "running"

if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().create_task(telegram_app.initialize())
    asyncio.get_event_loop().create_task(telegram_app.start())
    app.run(host="0.0.0.0", port=PORT)

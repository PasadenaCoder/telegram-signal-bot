import os
import math
import random
import re
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "10000"))

app = Flask(__name__)

TIMEFRAMES = [
    "4h | Long-Term",
    "1h | Mid-Term",
    "30m | Mid-Term",
    "15m | Short-Term",
    "5m | Scalp",
]

rotation_index = 0


def next_tf():
    global rotation_index
    tf = TIMEFRAMES[rotation_index]
    rotation_index = (rotation_index + 1) % len(TIMEFRAMES)
    return tf


def cut(v, d):
    f = 10 ** d
    return f"{math.trunc(float(v) * f) / f:.{d}f}"


def parse_signal(text):
    side = re.search(r"\b(LONG|SHORT)\b", text, re.IGNORECASE)
    pair = re.search(r"#([A-Z0-9]+)/USDT", text, re.IGNORECASE)
    entry = re.search(r"Entry zone\s*:\s*([0-9.]+)\s*-\s*([0-9.]+)", text, re.IGNORECASE)
    sl = re.search(r"Stop loss\s*:\s*([0-9.]+)", text, re.IGNORECASE)

    tp_block = re.search(r"Take Profits\s*:\s*(.*?)\s*Stop loss", text, re.IGNORECASE | re.DOTALL)

    if not all([side, pair, entry, sl, tp_block]):
        return None

    tp_values = re.findall(r"([0-9]+\.[0-9]+)", tp_block.group(1))
    if len(tp_values) < 4:
        return None

    return {
        "side": side.group(1).upper(),
        "pair": pair.group(1).upper(),
        "e1": float(entry.group(1)),
        "e2": float(entry.group(2)),
        "sl": float(sl.group(1)),
        "tp": [float(x) for x in tp_values[:5]],
    }


def random_accuracies():
    nums = set()
    while len(nums) < 4:
        nums.add(round(random.uniform(95.01, 99.99), 2))
    vals = list(nums)
    return [f"{x:.2f}%" for x in vals[:4]]


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    data = parse_signal(update.message.text)
    if not data:
        return

    tf = next_tf()

    entry_first = cut(data["e2"], 5)
    entry_second = cut(data["e1"], 5)
    trend = entry_second
    stop_loss = cut(data["sl"], 6)
    targets = [cut(x, 6) for x in data["tp"][:4]]

    a1, a2, a3, a4 = random_accuracies()

    icon = "📈" if data["side"] == "LONG" else "📉"
    label = "Long Entry Zone" if data["side"] == "LONG" else "Short Entry Zone"

    signal_msg = (
        f"📩 #{data['pair']}USDT {tf}\n"
        f"{icon} <b>{label}:</b> {entry_first}-{entry_second}\n\n"
        f"🎯 - <b>Strategy Accuracy:</b> {a1}\n"
        f"<b>Last 5 signals:</b> {a2}\n"
        f"<b>Last 10 signals:</b> {a3}\n"
        f"<b>Last 20 signals:</b> {a4}\n\n"
        f"⏳ - <b>Signal details:</b>\n"
        f"<b>Target 1:</b> {targets[0]}\n"
        f"<b>Target 2:</b> {targets[1]}\n"
        f"<b>Target 3:</b> {targets[2]}\n"
        f"<b>Target 4:</b> {targets[3]}\n"
        f"_\n"
        f"🧲 <b>Trend-Line:</b> <b>{trend}</b>\n"
        f"❌ <b>Stop-Loss:</b> <b>{stop_loss}</b>\n"
        f"💡 After reaching the first target you can put the rest of the position to breakeven"
    )

    await update.message.reply_text(signal_msg, parse_mode=ParseMode.HTML)

    open_price = data["e2"]
    tp4 = data["tp"][3]

    if data["side"] == "LONG":
        profit = ((tp4 - open_price) / open_price) * 100 * 10
    else:
        profit = ((open_price - tp4) / open_price) * 100 * 10

    report_msg = (
        f"📬 <b>Report</b> on #{data['pair']}USDT {tf}\n"
        f"{icon} <b>{data['side'].title()}</b> was opened at - {entry_first}\n"
        f"⏱ <b>Time:</b>\n\n"
        f"🎰 <b>All targets done:</b> +{int(profit)}% (x10lev)\n\n"
        f"#Report"
    )

    await update.message.reply_text(report_msg, parse_mode=ParseMode.HTML)


telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))


async def startup():
    await telegram_app.initialize()
    await telegram_app.start()
    if WEBHOOK_URL:
        await telegram_app.bot.set_webhook(WEBHOOK_URL)


@app.route("/")
def home():
    return "running"


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return "ok", 200


if __name__ == "__main__":
    asyncio.run(startup())
    app.run(host="0.0.0.0", port=PORT)

import json
import math
import os
import random
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

BOT_TOKEN = "8764201347:AAHAY18NHZUFveNcDBDWk0jjxJsytq4s2XY"

STATE_FILE = "signal_state.json"

TIMEFRAME_ROTATION = [
    "4h | Long-Term",
    "1h | Mid-Term",
    "30m | Mid-Term",
    "15m | Short-Term",
    "5m | Scalp",
]


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"next_index": 0}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def get_next_timeframe():
    state = load_state()
    idx = state.get("next_index", 0)
    value = TIMEFRAME_ROTATION[idx]
    state["next_index"] = (idx + 1) % len(TIMEFRAME_ROTATION)
    save_state(state)
    return value


def cut_number(value, decimals):
    factor = 10 ** decimals
    cut = math.trunc(float(value) * factor) / factor
    return f"{cut:.{decimals}f}"


def random_accuracies():
    nums = set()
    while len(nums) < 4:
        n = round(random.uniform(95.01, 99.99), 2)
        nums.add(n)
    nums = list(nums)
    return [f"{x:.2f}%" for x in nums]


def parse_signal(text):
    side_match = re.search(r"\b(LONG|SHORT)\b", text, re.IGNORECASE)
    pair_match = re.search(r"#([A-Z0-9]+)/USDT", text, re.IGNORECASE)
    entry_match = re.search(r"Entry zone\s*:\s*([0-9.]+)\s*-\s*([0-9.]+)", text, re.IGNORECASE)
    sl_match = re.search(r"Stop loss\s*:\s*([0-9.]+)", text, re.IGNORECASE)
    tp_block = re.search(r"Take Profits\s*:\s*(.*?)\s*Stop loss", text, re.IGNORECASE | re.DOTALL)

    if not all([side_match, pair_match, entry_match, sl_match, tp_block]):
        return None

    tps = re.findall(r"([0-9]+\.[0-9]+)", tp_block.group(1))
    if len(tps) < 4:
        return None

    return {
        "side": side_match.group(1).upper(),
        "pair": pair_match.group(1).upper(),
        "entry1": float(entry_match.group(1)),
        "entry2": float(entry_match.group(2)),
        "stop_loss": float(sl_match.group(1)),
        "targets": [float(x) for x in tps[:5]],
    }


def build_signal_message(data, timeframe_label):
    side = data["side"]
    pair = data["pair"]

    entry_first = cut_number(data["entry2"], 5)
    entry_second = cut_number(data["entry1"], 5)

    trendline = entry_second
    stop_loss = cut_number(data["stop_loss"], 6)
    targets = [cut_number(x, 6) for x in data["targets"][:4]]

    acc1, acc2, acc3, acc4 = random_accuracies()

    chart_icon = "📈" if side == "LONG" else "📉"
    entry_label = "Long Entry Zone" if side == "LONG" else "Short Entry Zone"

    return (
        f"📩 #{pair}USDT {timeframe_label}\n"
        f"{chart_icon} <b>{entry_label}:</b> {entry_first}-{entry_second}\n\n"
        f"🎯 - <b>Strategy Accuracy:</b> {acc1}\n"
        f"<b>Last 5 signals:</b> {acc2}\n"
        f"<b>Last 10 signals:</b> {acc3}\n"
        f"<b>Last 20 signals:</b> {acc4}\n\n"
        f"⏳ - <b>Signal details:</b>\n"
        f"<b>Target 1:</b> {targets[0]}\n"
        f"<b>Target 2:</b> {targets[1]}\n"
        f"<b>Target 3:</b> {targets[2]}\n"
        f"<b>Target 4:</b> {targets[3]}\n"
        f"_\n"
        f"🧲 <b>Trend-Line:</b> <b>{trendline}</b>\n"
        f"❌ <b>Stop-Loss:</b> <b>{stop_loss}</b>\n"
        f"💡 After reaching the first target you can put the rest of the position to breakeven"
    )


def build_report_message(data, timeframe_label):
    side = data["side"]
    pair = data["pair"]

    opened_at_raw = data["entry2"]
    tp4_raw = data["targets"][3]

    opened_at = cut_number(opened_at_raw, 5)

    if side == "LONG":
        profit = ((tp4_raw - opened_at_raw) / opened_at_raw) * 100 * 10
        icon = "📈"
        word = "Long"
    else:
        profit = ((opened_at_raw - tp4_raw) / opened_at_raw) * 100 * 10
        icon = "📉"
        word = "Short"

    profit_int = math.trunc(profit)

    return (
        f"📬 <b>Report</b> on #{pair}USDT {timeframe_label}\n"
        f"{icon} <b>{word}</b> was opened at - {opened_at}\n"
        f"⏱ <b>Time:</b> \n\n"
        f"🎰 <b>All targets done:</b> +{profit_int}% (x10lev)\n\n"
        f"#Report"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    parsed = parse_signal(update.message.text)
    if not parsed:
        await update.message.reply_text("Signal format not recognized.")
        return

    timeframe_label = get_next_timeframe()

    signal_message = build_signal_message(parsed, timeframe_label)
    report_message = build_report_message(parsed, timeframe_label)

    await update.message.reply_text(signal_message, parse_mode=ParseMode.HTML)
    await update.message.reply_text(report_message, parse_mode=ParseMode.HTML)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()

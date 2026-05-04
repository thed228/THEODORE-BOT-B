#!/usr/bin/env python3
"""Bot Telegram de Prediction Baccarat - Strategies: 1ere Carte +6"""
import asyncio, signal, sys
from datetime import datetime

def configure_console_encoding():
    """Force UTF-8 stdout/stderr on Windows terminals."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

configure_console_encoding()

try:
    from telegram import Update
    from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes
    from telegram.constants import ParseMode
    from telegram.error import Conflict
except ImportError:
    print("=" * 50)
    print("⭕️ Dependances manquantes !")
    print("Tape : pip install -r requirements.txt")
    print("=" * 50)
    sys.exit(1)

from strategies import StrategyManager, format_cards, calculate_hand_value
from utils import get_latest_results, get_live_game_number, update_history, save_history_to_file, load_history_from_file

TOKEN = "7992757444:AAFuZdtp6fw_BhEH0C4bX-XOQj4odi5Vo_w"
CHAT_IDS = ['-1002360476595']
ADMIN_IDS = [6621311234, 7992757444]

MSG = {
    "start": "🤖 <b>BOT PREDICTION BACCARAT</b>\n\n⭐ Priorite 1 : 1ere Carte +6\n⭐ Priorite 2 : Double Pattern\n\n/startbot - Demarrer\n/stopbot - Arreter\n/stats - Stats\n/last - Derniers jeux\n/strategy - Strategies\n/force - Forcer prediction",
    "bot_started": "✅ <b>BOT DEMARRE</b>\n🎯 1ere Carte +6 | Double Pattern\n⏱️ Verification 10s",
    "bot_stopped": "🛑 <b>BOT ARRETE</b>",
    "already_running": "⚠️ Deja en cours",
    "already_stopped": "⚠️ Deja arrete",
    "no_permission": "⛔ Acces refuse",
    "prediction": "{symbol}→#N{game}",
    "prediction_plus6": "{symbol}→#N{game}",
    "prediction_win": "{symbol}→#N{game} {index}✅",
    "prediction_loss": "{symbol}→#N{game} ❌",
    "skip": "⏭️ Pause {count} jeux\nReprise : #{end}",
    "stats": "📊 <b>STATS</b>\n🎯 Total : {total}\n✅ Reussites : {success}\n❌ Echecs : {failures}\n📈 Taux : {rate}%",
    "last_games": "🎮 <b>DERNIERS JEUX</b>{games}",
    "strategy_info": "🧠 <b>STRATEGIES</b>\n\n⭐ <b>1ere Carte +6</b>\n1. 1ere = X, 2eme = Y\n2. X et Y doivent etre DIFFERENTES\n3. Banquier sans X\n4. Prediction X au JEU+6\n\n⭐ <b>Double Pattern</b>\n2 memes couleurs → Meme couleur\nEx: ❤️❤️→❤️ | ♦️♦️→♦️ | ♠️♠️→♠️ | ♣️♣️→♣️"
}

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        print("⚠️ Telegram Conflict: une autre instance du bot est deja en cours. Arret propre.")
        await context.application.stop()
        return
    print(f"[Telegram Error] {err}")


class BaccaratBot:
    def __init__(self):
        self.running = False
        self.history = load_history_from_file()
        self.predictions = []
        self.skipped = []
        self.waiting_plus6 = None
        self.task = None
        self.strategy = StrategyManager()
        self.stats = {"total": 0, "success": 0, "failed": 0}
        self.start_game_number = None
        self.last_live_game_number = None
        print(f"💾 {len(self.history)} jeux charges")

    async def cmd_start(self, update, context):
        await update.message.reply_text(MSG["start"], parse_mode=ParseMode.HTML)

    async def cmd_startbot(self, update, context):
        if update.effective_user.id not in ADMIN_IDS: await update.message.reply_text(MSG["no_permission"]); return
        if self.running: await update.message.reply_text(MSG["already_running"]); return
        self.running = True
        print(f"\n[Bot] ▶️ DEMARRE")
        results = get_latest_results()
        self.history = {}
        if results:
            current_max = max(r["game_number"] for r in results)
            self.start_game_number = current_max
            filtered_results = [r for r in results if r["game_number"] >= self.start_game_number]
            self.history = update_history(filtered_results, {})
            self.last_live_game_number = get_live_game_number(results)
            print(f"💾 Jeu de demarrage: #{current_max}")
            if self.last_live_game_number:
                print(f"🎯 Jeu en direct detecte: #{self.last_live_game_number}")
        else:
            print("⚠️ Aucune donnees API au demarrage, historique vide")
        await update.message.reply_text(MSG["bot_started"], parse_mode=ParseMode.HTML)
        self.task = asyncio.create_task(self.loop(context))

    async def cmd_stopbot(self, update, context):
        if update.effective_user.id not in ADMIN_IDS: await update.message.reply_text(MSG["no_permission"]); return
        if not self.running: await update.message.reply_text(MSG["already_stopped"]); return
        self.running = False; save_history_to_file(self.history)
        if self.task: self.task.cancel()
        print(f"[Bot] ⏹️ ARRETE")
        await update.message.reply_text(MSG["bot_stopped"], parse_mode=ParseMode.HTML)

    async def cmd_stats(self, update, context):
        if update.effective_user.id not in ADMIN_IDS: return
        t, s = self.stats["total"], self.stats["success"]
        r = (s/t*100) if t>0 else 0
        await update.message.reply_text(MSG["stats"].format(total=t, success=s, failures=self.stats["failed"], rate=f"{r:.1f}"), parse_mode=ParseMode.HTML)

    async def cmd_last(self, update, context):
        if not self.history: await update.message.reply_text("❌ Pas de donnees"); return
        txt = ""
        for n in sorted(self.history.keys(), reverse=True)[:5]:
            g = self.history[n]
            p = format_cards(g.get("player_cards",[]))
            b = format_cards(g.get("banker_cards",[]))
            pv = calculate_hand_value(g.get("player_cards",[]))
            bv = calculate_hand_value(g.get("banker_cards",[]))
            s = "✅" if g.get("is_finished") else "🔄"
            txt += f"\n{s} <b>#{n}</b>\n👤 {p} ({pv})\n🏦 {b} ({bv})\n"
        await update.message.reply_text(MSG["last_games"].format(games=txt), parse_mode=ParseMode.HTML)

    async def cmd_strategy(self, update, context):
        await update.message.reply_text(MSG["strategy_info"], parse_mode=ParseMode.HTML)

    async def cmd_force(self, update, context):
        if not self.history: await update.message.reply_text("❌ Pas de donnees"); return
        pred = self.strategy.generate_prediction(self.history)
        if not pred: await update.message.reply_text("❌ Impossible"); return
        game_num = pred["game_number"]
        current_max = max(self.history.keys())
        wait = game_num - current_max
        if wait > 1:
            text = MSG["prediction_plus6"].format(game=game_num, symbol=pred["symbol"], strategy=pred.get("strategy_used",""), wait=wait)
        else:
            text = MSG["prediction"].format(game=game_num, symbol=pred["symbol"], strategy=pred.get("strategy_used",""))
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def loop(self, context):
        try:
            while self.running:
                try: await self.cycle(context)
                except Exception as e: print(f"[Loop] Erreur: {e}")
                await asyncio.sleep(10)
        except asyncio.CancelledError: save_history_to_file(self.history); raise

    async def cycle(self, context):
        results = get_latest_results()
        if not results: return
        if self.start_game_number is not None:
            results = [r for r in results if r["game_number"] >= self.start_game_number]
        self.history = update_history(results, self.history)
        if len(self.history) % 50 == 0: save_history_to_file(self.history)
        current_max = max(self.history.keys()) if self.history else 0
        current_live = get_live_game_number(results)
        if current_live != self.last_live_game_number:
            self.last_live_game_number = current_live
            if current_live:
                print(f"[Realtime] Nouveau jeu en direct detecte: #{current_live}")
            else:
                print("[Realtime] Aucun jeu en direct actuellement")
        if self.skipped:
            if max(self.skipped) in self.history and self.history[max(self.skipped)].get("is_finished"): self.skipped = []
            return
        if self.waiting_plus6:
            await self.check_plus6(context, current_max)
            if self.waiting_plus6: return
        if self.predictions: await self.check_predictions(context, results)
        if not self.predictions and not self.skipped and not self.waiting_plus6:
            await self.new_prediction(context, current_max)

    async def check_plus6(self, context, current_max):
        pred = self.waiting_plus6
        target = pred["game_number"]
        if current_max < target: return
        print(f"[+6] 🎯 Jeu #{target} arrive !")
        self.waiting_plus6 = None
        self.stats["total"] += 1
        text = MSG["prediction"].format(game=pred["game_number"], symbol=pred["symbol"], strategy=pred.get("strategy_used",""))
        for chat_id in CHAT_IDS:
            try:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
                self.predictions.append({"message_id": msg.message_id, "chat_id": chat_id, "data": pred})
                await asyncio.sleep(0.5)
            except Exception as e: print(f"[+6] Erreur: {e}")

    async def check_predictions(self, context, results):
        for p in self.predictions[:]:
            pred = p["data"]
            if pred["status"]: continue
            gn = pred["game_number"]
            rel = [g for g in results if gn <= g["game_number"] <= gn+2]
            if not rel: continue
            for g in rel:
                if g.get("is_finished") and self.strategy.verify_prediction(pred, g):
                    pred["status"] = "✅"; pred["result_game"] = g["game_number"]
                    self.stats["success"] += 1; self.strategy.notify_result(True)
                    diff = g["game_number"] - gn; sc = 3 if diff<=1 else 4
                    self.skipped = [g["game_number"]+i for i in range(1, sc+1)]
                    await self.send_skip(context, sc, max(self.skipped)); break
            if not pred["status"]:
                mg = gn+2
                if all(g.get("is_finished") for g in results if gn<=g["game_number"]<=mg):
                    pred["status"] = "❌"; self.stats["failed"] += 1; self.strategy.notify_result(False)
            if pred["status"]: await self.update_message(context, p); self.predictions.remove(p)

    async def new_prediction(self, context, current_max):
        pred = self.strategy.generate_prediction(self.history)
        if not pred: return
        game_num = pred["game_number"]
        wait = game_num - current_max
        if wait > 1:
            self.waiting_plus6 = pred
            text = MSG["prediction_plus6"].format(game=game_num, symbol=pred["symbol"], strategy=pred.get("strategy_used",""), wait=wait)
        else:
            self.stats["total"] += 1
            text = MSG["prediction"].format(game=game_num, symbol=pred["symbol"], strategy=pred.get("strategy_used",""))
        for chat_id in CHAT_IDS:
            try:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
                if wait <= 1: self.predictions.append({"message_id": msg.message_id, "chat_id": chat_id, "data": pred})
                await asyncio.sleep(0.5)
            except Exception as e: print(f"[Pred] Erreur: {e}")

    async def update_message(self, context, pred_msg):
        pred = pred_msg["data"]; idx = ""
        if pred["status"] == "✅":
            d = pred.get("result_game",0)-pred["game_number"]; idx = {0:"0️⃣",1:"1️⃣",2:"2️⃣"}.get(d,"")
        text = MSG["prediction_win" if pred["status"]=="✅" else "prediction_loss"].format(
            symbol=pred.get("symbol","🏦"),
            index=idx,
            game=pred.get("game_number", "?")
        )
        try: await context.bot.edit_message_text(chat_id=pred_msg["chat_id"], message_id=pred_msg["message_id"], text=text, parse_mode=ParseMode.HTML)
        except: pass

    async def send_skip(self, context, count, end):
        return

def main():
    print("="*40); print("🤖 BOT BACCARAT"); print("⭐ 1ere Carte +6 | Double Pattern"); print("="*40)
    bot = BaccaratBot()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_error_handler(on_error)
    for cmd, func in [("start", bot.cmd_start), ("startbot", bot.cmd_startbot), ("stopbot", bot.cmd_stopbot), ("stats", bot.cmd_stats), ("last", bot.cmd_last), ("strategy", bot.cmd_strategy), ("force", bot.cmd_force)]:
        app.add_handler(CommandHandler(cmd, func))
    def handle(sig, frame): save_history_to_file(bot.history); sys.exit(0)
    signal.signal(signal.SIGINT, handle); signal.signal(signal.SIGTERM, handle)
    print("✅ Pret ! /startbot dans Telegram"); print("="*40)
    app.run_polling()

if __name__ == "__main__": main()

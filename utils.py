import requests, ast, time, json

def get_latest_results(retries=3, delay=2):
    for attempt in range(retries):
        try:
            url = "https://1xbet.com/service-api/LiveFeed/GetChampZip?champ=2050671&lng=en&country=96&groupChamps=true"
            resp = requests.get(url, timeout=30); resp.raise_for_status()
            data = resp.json()
            if "Value" not in data or "G" not in data["Value"]: continue
            results = []
            for game in data["Value"]["G"]:
                try:
                    sc = game.get("SC",{})
                    is_finished = sc.get("I")=="Game finished" or sc.get("CPS")=="Match finished"
                    pc, bc = [], []
                    for s in sc.get("S",[]):
                        val = s.get("Value","[]")
                        if val and val!="[]":
                            try:
                                cards = ast.literal_eval(val)
                                if s["Key"]=="P": pc=cards
                                elif s["Key"]=="B": bc=cards
                            except: pass
                    results.append({"game_number":int(game.get("DI",0)),"player_cards":pc,"banker_cards":bc,"is_finished":is_finished})
                except: continue
            return results
        except: pass
        if attempt < retries-1: time.sleep(delay)
    return []

def get_live_game_number(results):
    live_games = [r["game_number"] for r in results if not r.get("is_finished")]
    return max(live_games) if live_games else None


def update_history(results, history):
    for r in results:
        n = r["game_number"]
        if n not in history: history[n] = r
        elif not history[n].get("is_finished") and r["is_finished"]: history[n].update(r)
    if len(history) > 200:
        for k in sorted(history.keys())[:-200]: del history[k]
    return history

def save_history_to_file(history, filename="history.json"):
    try:
        with open(filename,'w',encoding='utf-8') as f: json.dump({str(k):v for k,v in history.items()},f,ensure_ascii=False)
    except: pass

def load_history_from_file(filename="history.json"):
    try:
        with open(filename,'r',encoding='utf-8') as f: return {int(k):v for k,v in json.load(f).items()}
    except: return {}

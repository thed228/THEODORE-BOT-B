from random import choice
from collections import Counter
from typing import Dict, Optional, Any, List
import ast

symbol_to_number = {"♣️": 1, "♠️": 0, "❤️": 3, "♦️": 2}
number_to_symbol = {v: k for k, v in symbol_to_number.items()}

def get_card_value(card): return 0 if card.get("R",0)>9 else card.get("R",0)
def calculate_hand_value(cards): return sum(get_card_value(c) for c in cards)%10
def get_card_symbol(card): return number_to_symbol.get(card.get("S",-1),"?")
def get_card_rank(card):
    r=card.get("R",0); return {1:"A",11:"J",12:"Q",13:"K"}.get(r,str(r) if r<=10 else "?")
def format_cards(cards):
    if not cards: return "[]"
    return " ".join(f"{get_card_rank(c)}{get_card_symbol(c)}" for c in cards)

class StrategyManager:
    def __init__(self):
        self.consecutive_failures = 0; self.failed_attempts = 0
        self.last_predictions = []; self.prediction_history = []
        self.last_minus32_prediction_game = None

    def _get_last_finished(self, history, count=10):
        return sorted([n for n,g in history.items() if g.get("is_finished")], reverse=True)[:count]

    def _get_first_two_cards(self, game):
        cards = game.get("player_cards",[])
        if len(cards) < 2: return []
        return [get_card_symbol(c) for c in cards[:2] if get_card_symbol(c) != "?"]

    def _get_first_card(self, game):
        """Récupère la première carte du joueur"""
        cards = game.get("player_cards", [])
        if not cards: return None
        return get_card_symbol(cards[0])

    def detect_minus32(self, history, target_game_number):
        """
        Stratégie -32: Pour prédire le jeu N, on regarde le jeu N-32
        et on donne la première carte du joueur de ce jeu.
        """
        source_game = target_game_number - 32
        
        # Vérifier que le jeu source existe
        if source_game not in history:
            print(f"[Minus 32] ⚠️ Jeu source #{source_game} non trouvé dans l'historique")
            return None
        
        source_game_data = history[source_game]
        
        # Vérifier que le jeu source est terminé
        if not source_game_data.get("is_finished"):
            print(f"[Minus 32] ⚠️ Jeu source #{source_game} non terminé")
            return None
        
        # Récupérer la première carte du joueur du jeu source
        first_card = self._get_first_card(source_game_data)
        if first_card is None or first_card == "?":
            print(f"[Minus 32] ⚠️ Pas de première carte valide dans le jeu #{source_game}")
            return None
        
        # Éviter de répéter la même prédiction
        if self.last_minus32_prediction_game == target_game_number:
            return None
        
        self.last_minus32_prediction_game = target_game_number
        
        print(f"[Minus 32] 🎯 Prédiction jeu #{target_game_number}")
        print(f"[Minus 32] Source: jeu #{source_game} → Première carte: {first_card}")
        
        return {
            "symbol": first_card,
            "number": symbol_to_number.get(first_card),
            "game_number": target_game_number,
            "status": None,
            "result_game": None,
            "message_id": None,
            "strategy_used": f"🎯 Stratégie -32 (jeu #{source_game}): {first_card}",
            "bet_type": "minus32",
            "source_game": source_game
        }

    def generate_prediction(self, history):
        """Génère une prédiction pour le prochain jeu"""
        if not history:
            return None
        
        # Déterminer le numéro du prochain jeu
        next_game_number = max(history.keys()) + 1
        
        # Essayer la stratégie -32
        minus32 = self.detect_minus32(history, next_game_number)
        if minus32:
            self.last_predictions.append(minus32["symbol"])
            return minus32
        
        # Fallback: stratégie par défaut si -32 ne fonctionne pas
        finished = self._get_last_finished(history, 1)
        if not finished:
            return None
        
        game = history[finished[0]]
        cards = game.get("player_cards", [])
        if not cards:
            return None
        
        if self.consecutive_failures >= 2:
            last = get_card_symbol(cards[-1])
            pred = last if last != "?" else choice(list(symbol_to_number.keys()))
            strat = f"Suivi après échecs ({last}→{pred})"
        elif len(cards) == 2:
            pred = get_card_symbol(cards[-1])
            strat = f"Suivi ({pred})"
        elif len(cards) == 3:
            pred = Counter(get_card_symbol(c) for c in cards).most_common(1)[0][0]
            strat = f"Majorité ({pred})"
        else:
            pred = choice(list(symbol_to_number.keys()))
            strat = "Aléatoire"
        
        self.last_predictions.append(pred)
        return {
            "symbol": pred,
            "number": symbol_to_number.get(pred),
            "game_number": next_game_number,
            "status": None,
            "result_game": None,
            "message_id": None,
            "strategy_used": strat
        }

    def verify_prediction(self, pred, game):
        """Vérifie si la prédiction est correcte"""
        if pred.get("number") is None:
            return False
        return any(c.get("S") == pred["number"] for c in game.get("player_cards", []))

    def notify_result(self, success):
        """Notifie le résultat d'une prédiction"""
        if success:
            self.consecutive_failures = 0
            self.failed_attempts = max(0, self.failed_attempts - 1)
        else:
            self.consecutive_failures += 1
            self.failed_attempts += 1

    def get_stats(self):
        """Retourne les statistiques actuelles"""
        return {
            "consecutive_failures": self.consecutive_failures,
            "last_predictions": self.last_predictions[-5:] if self.last_predictions else []
        }
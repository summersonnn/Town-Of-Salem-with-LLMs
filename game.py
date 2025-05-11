import os
import random
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# your provided chat_completion; assumed to be on PYTHONPATH
from llm_call import chat_completion  


class Vampire_or_Peasant:
    def __init__(
        self,
        player_names: List[str],
        available_models: List[str],
        temperature: float = 0.9
    ):
        """
        player_names: list of human-readable names, e.g. ["John","Bob","Sarah"]
        available_models: list of model strings to assign uniquely, e.g.
                          ["openai/o4-mini-high","google/gemini-2.5-pro-preview",
                           "qwen/qwen3-235b-a22b","anthropic/claude-3.7-sonnet" ]
                          Must be at least as many models as players.
        """
        if len(available_models) < len(player_names):
            raise ValueError(
                "Not enough distinct models to assign uniquely to each player."
            )

        # Sample without replacement so every player gets a different base model
        shuffled = random.sample(available_models, len(player_names))
        # Append ":nitro" to each model name
        suffixed = [model + ":nitro" for model in shuffled]

        # Build the public mapping
        self.player_model_map: Dict[str, str] = dict(zip(player_names, suffixed))

        # Turn order
        self.turn_order: List[str] = player_names[:]
        self.current_index: int = 0
        self.temperature: float = temperature

        # Shared (public) chat history
        self.shared_history: List[Dict[str, Any]] = []

        # Private history per player (e.g., their secret role info)
        self.private_histories: Dict[str, List[Dict[str, Any]]] = {
            name: [] for name in player_names
        }

    def introduce_players(self) -> None:
        """Call once at start to announce who’s playing (system role)."""
        names = ", ".join(self.turn_order)
        system_msg = {"role": "system", "content": f"I am the moderator of this game. I introduce the players: {names}. \
                      I've already assigned roles. Let's begin."}
        self.shared_history.append(system_msg)

    def assign_roles(self, vampire_population: int = 1) -> None:
        """
        Randomly assigns `vampire_population` distinct Vampires and the rest Peasants.
        Appends a private system message to each player's history exactly once.

        Args:
            vampire_population: Number of players to assign as Vampire. Default is 1.
        """
        total_players = len(self.turn_order)
        if vampire_population < 1 or vampire_population > total_players:
            raise ValueError(
                f"vampire_population must be between 1 and {total_players}"
            )

        # Choose distinct vampires without replacement
        vampires = set(random.sample(self.turn_order, vampire_population))

        # Assign roles and notify privately
        for player in self.turn_order:
            # Inform player of their name first
            self.private_histories[player].append({
                "role": "system",
                "content": f"You are {player}."
            })
            # Then inform of their secret role
            role = "Vampire" if player in vampires else "Peasant"
            self.private_histories[player].append({
                "role": "system",
                "content": f"Your secret role is: {role}."
            })

    def _parse_direct_address(self) -> Optional[str]:
        """
        If last shared message ends with '->Name?' return that Name.
        """
        if not self.shared_history:
            return None
        last = self.shared_history[-1].get("content", "").strip()
        if last.endswith('?') and '->' in last:
            candidate = last.rsplit('->', 1)[-1].rstrip('?').strip()
            if candidate in self.player_model_map:
                return candidate
        return None

    def chat(self) -> List[Dict[str, Any]]:
        """
        Advance conversation:
          - Determine speaker (direct address or round-robin)
          - Build a structured message list with clear separators:
              1. game rules system prompt
              2. "Here is the chat between players so far:" system prompt + shared history
              3. "Here is your private chat history:" system prompt + private history
          - Call chat_completion, append to shared history
        Returns updated shared_history.
        """
        # Pick who speaks
        direct = self._parse_direct_address()
        if direct:
            speaker = direct
        else:
            speaker = self.turn_order[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.turn_order)

        # 1) Core game rules
        system_rules = {
            "role": "system",
            "content": (
                "You are playing Vampire or Peasant."
                "Speak only as your assigned player and do not reveal your model."
                "Game begins now. "
            )
        }
        # 2) Shared history with separator
        shared_sep = {"role": "system", "content": "Here is the chat between players so far:"}
        shared = self.shared_history.copy()

        # 3) Private history with separator
        private_sep = {"role": "system", "content": "Here is your private chat history:"}
        private = self.private_histories[speaker].copy()

        # Final message list
        messages = [system_rules, shared_sep] + shared + [private_sep] + private

        # Call the LLM
        response = chat_completion(
            chat_history=messages,
            temperature=self.temperature,
            player_name=speaker,
            player_model_map=self.player_model_map
        )

        # Build assistant message
        assistant_msg = {"role": "assistant", "name": speaker, "content": response}

        # Append to shared history only
        self.shared_history.append(assistant_msg)

        return self.shared_history
        

# ----------- example --------------
if __name__ == "__main__":
    load_dotenv()  # ensure LLM_BASE_URL & LLM_API_KEY are set

    players = ["John","Bob","Sarah", "Alice"]
    models  = [
        "openai/o4-mini-high", 
        "google/gemini-2.5-pro-preview", 
        "qwen/qwen3-235b-a22b",
        "anthropic/claude-3.7-sonnet"
    ]

    # Initialize game and announce players
    game = Vampire_or_Peasant(players, models)
    game.introduce_players()

    # Randomly assign 2 vampires and notify privately
    game.assign_roles(vampire_population=2)
    # Print each player's private role for demonstration
    for p in players:
        private_msgs = game.private_histories[p]
        print(f"[PRIVATE to {p}]: {private_msgs[0]['content']}")

    # 3 normal rounds
    for _ in range(3):
        hist = game.chat()
        msg = hist[-1]
        print(f"{msg['name']}: {msg['content']}")



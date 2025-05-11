import os
import random
from typing import List, Dict, Optional, Any, Tuple
from dotenv import load_dotenv

# your provided chat_completion; assumed to be on PYTHONPATH
from llm_call import chat_completion  

def sanitize_reply(reply: str) -> str:
    """
    Removes any preceding <|im_start|> text in the reply.
    Then, removes a single pair of surrounding double-quotation marks from the
    (potentially modified) reply if it starts and ends with a double-quote (").
    Otherwise, returns the (potentially modified) reply.
    """
    im_start_token = "<|im_start|>\n"

    # Step 1: Remove preceding <|im_start|> text, if present.
    # This handles "any preceding <|im_start|> text". If the token is there at the start,
    # it's removed. If not, the string remains unchanged.
    if reply.startswith(im_start_token):
        reply = reply[len(im_start_token):]

    # Step 2: Remove a single pair of surrounding double-quotation marks
    # from the (potentially modified) reply. This is the original functionality.
    if len(reply) >= 2 and reply.startswith('"') and reply.endswith('"'):
        return reply[1:-1]
    
    # If quotes were not removed (either not present or string too short),
    # return the reply, which might have had <|im_start|> removed or might be original.
    return reply

class Vampire_or_Peasant:
    def __init__(
        self,
        player_names: List[str],
        available_models: List[str],
        temperature: float = 0.9
    ):
        """
        player_names: list of human-readable names
        available_models: unique model strings to assign (must >= players)
        """
        if len(available_models) < len(player_names):
            raise ValueError("Not enough distinct models for each player.")

        # Assign unique models with :nitro suffix
        suffixed = [m + ":nitro" for m in random.sample(available_models, len(player_names))]
        self.player_model_map = dict(zip(player_names, suffixed))

        self.turn_order = player_names[:]    # fixed round-robin
        self.current_index = 0
        self.temperature = temperature

        # Histories
        self.shared_history = []             # public chat
        self.private_histories = {          # private per player
            name: [] for name in player_names
        }

        # Roles mapping
        self.roles: Dict[str, str] = {}

        # Game rules
        self.rules = {"role": "system", "content": (
                "You are playing Vampire or Peasant.  "
                "There are multiple human‐named players, each controlled by a different LLM.  "
                "You only know players by their human name.  "
                "Follow the turn order unless someone is directly addressed with “Name!”.  "
                "Do not reveal which LLM model you are running under.  "
                "Speak only as your assigned player."
                "Do not mix your shared and private histories. You should not reveal anything about your private history when speaking to others. "
                "You don't need to put your name at the beginning of your message. It will be added automatically. Just write your message. "
                "Do not repeat old messages in the chat history. Just output the new message. "
        )}

    def introduce_players(self) -> None:
        """Announce players once at game start."""
        names = ", ".join(self.turn_order)
        self.shared_history.append({
            "role": "system",
            "content": (
                "I am the moderator. Players: " + names + ". "
                "Roles assigned. Game begins now."
            )
        })

    def assign_roles(self, vampire_population: int = 1) -> None:
        """
        Randomly assign secret roles to each player.
        """
        n = len(self.turn_order)
        if not (1 <= vampire_population <= n):
            raise ValueError(f"vampire_population must be 1..{n}")

        vampires = set(random.sample(self.turn_order, vampire_population))
        for p in self.turn_order:
            # Notify private history
            self.private_histories[p].append({"role": "system", "content": f"You are {p}."})
            role = "Vampire" if p in vampires else "Peasant"
            self.private_histories[p].append({"role": "system", "content": f"Your secret role is: {role}."})
            # Store role
            self.roles[p] = role

    def chat(self, rounds: int = 1) -> List[Dict[str, Any]]:
        for _ in range(rounds):
            speaker = self.turn_order[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.turn_order)

            # Build conversation for this player
            shared_sep = {"role": "system", "content": "Here is the chat so far:"}
            private_sep = {"role": "system", "content": "Here is your private history:"}
            msgs = [self.rules, shared_sep] + self.shared_history + [private_sep] + self.private_histories[speaker]

            raw_reply = chat_completion(
                chat_history=msgs,
                temperature=self.temperature,
                player_name=speaker,
                player_model_map=self.player_model_map
            )

            reply = sanitize_reply(raw_reply)
            self.shared_history.append({"role": "assistant", "name": speaker, "content": reply})
            print(f"{speaker}: {reply}")
            print("---")
        return self.shared_history
    
        # Game stages stubs
    def vampires_chatting(self) -> None:
        pass

    def mod_announcing_updates(self) -> None:
        pass

    def update_player_list(self) -> None:
        pass

    def check_game_end(self) -> Tuple[bool, str]:
        """
        Evaluate win conditions:
        - If no vampires remain, peasants win.
        - If vampires >= peasants, vampires win.
        Returns (ended: bool, winner: str).
        """
        # Count roles among alive players
        alive = self.turn_order
        num_vampires = sum(1 for p in alive if self.roles.get(p) == "Vampire")
        num_peasants = sum(1 for p in alive if self.roles.get(p) == "Peasant")

        # Peasants win if no vampires remain
        if num_vampires == 0:
            return True, "Peasants"

        # Vampires win if they are equal or outnumber peasants
        if num_vampires > 0 and num_peasants <= num_vampires:
            return True, "Vampires"

        return False, ""

    def vote(self) -> str:
        pass

    def run_game(self) -> None:
        """
        Main game loop combining day and night stages until end state.
        """
        round_counter = 0
        while True:
            # Night: vampires choose a victim
            self.vampires_chatting()

            # Moderator announces results and updates about the night actions
            self.mod_announcing_updates()

            # Day: players discuss
            self.chat(rounds=len(self.turn_order)*2)

            # Vote for a player to kick out
            kicked_player = self.vote()

            # Update player list based on night actions
            self.update_player_list()

            # Moderator announces results and updates about the poll results
            self.mod_announcing_updates()

            finished, winner = self.check_game_end()
            if finished:
                print(f"Game over! {winner} wins!")
                break

# --- example ---
if __name__ == "__main__":
    load_dotenv()
    players = ["John","Bob","Sarah","Alice"]
    models = [
        "openai/o4-mini-high",
        "google/gemini-2.5-pro-preview",
        "qwen/qwen3-32b",
        "anthropic/claude-3.7-sonnet"
    ]

    game = Vampire_or_Peasant(players, models)
    game.introduce_players()
    game.assign_roles(vampire_population=1)

    # run the full game loop
    game.run_game()

import os
import random
from typing import List, Dict, Optional, Any
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
        """Randomly pick distinct vampires, notify each privately."""
        n = len(self.turn_order)
        if not (1 <= vampire_population <= n):
            raise ValueError(f"vampire_population must be 1..{n}")

        vampires = set(random.sample(self.turn_order, vampire_population))
        for p in self.turn_order:
            # name notice
            self.private_histories[p].append({
                "role": "system",
                "content": f"You are {p}."
            })
            role = "Vampire" if p in vampires else "Peasant"
            self.private_histories[p].append({
                "role": "system",
                "content": f"Your secret role is: {role}."
            })

    # def _parse_direct_address(self) -> Optional[str]:
    #     """Detect '->Name?' in last shared message."""
    #     if not self.shared_history:
    #         return None
    #     txt = self.shared_history[-1]["content"].strip()
    #     if txt.endswith('?') and '->' in txt:
    #         cand = txt.rsplit('->', 1)[-1].rstrip('?').strip()
    #         if cand in self.player_model_map:
    #             return cand
    #     return None

    def chat(self, rounds: int = 1) -> List[Dict[str, Any]]:
        """
        Run the conversation for `rounds` turns internally.
        Each turn:
          - Determine speaker (direct or round-robin)
          - Build message list: rules, shared, private
          - Call chat_completion
          - Append result to shared history
        Returns the updated shared_history after all turns.
        """
        for _ in range(rounds):
            # pick speaker
            # direct = self._parse_direct_address()
            # if direct:
            #     speaker = direct
            # else:
            #     speaker = self.turn_order[self.current_index]
            #     self.current_index = (self.current_index + 1) % len(self.turn_order)
            speaker = self.turn_order[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.turn_order)

            # prepare messages
            shared_sep = {"role": "system", "content": "Here is the chat so far:"}
            private_sep = {"role": "system", "content": "Here is your private history:"}

            msgs = [self.rules, shared_sep] + self.shared_history + [private_sep] + self.private_histories[speaker]

            # call LLM
            raw_reply = chat_completion(
                chat_history=msgs,
                temperature=self.temperature,
                player_name=speaker,
                player_model_map=self.player_model_map
            )

            # sanitize and append to shared
            reply = sanitize_reply(raw_reply)
            self.shared_history.append({
                "role": "assistant",
                "name": speaker,
                "content": reply
            })
            print(f"{speaker}: {reply}")
            print("---")
        return self.shared_history

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
    game.assign_roles(vampire_population=2)

    # run 5 turns internally
    history = game.chat(rounds=10)

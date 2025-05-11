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

    def public_chat(self, rounds: int = 1) -> List[Dict[str, Any]]:
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
    
    def vampires_voting(self) -> Optional[str]:
        """
        Ask each vampire to vote on a peasant to kill. Tally votes and return the chosen victim.
        Returns the name of the selected victim, or None if no valid vote.
        """
        # Identify alive vampires and peasants
        vampires = [p for p, role in self.roles.items() if role == "Vampire" and p in self.turn_order]
        peasants = [p for p, role in self.roles.items() if role == "Peasant" and p in self.turn_order]
        if not vampires or not peasants:
            return None

        # Collect votes
        votes: Dict[str, int] = {peasant: 0 for peasant in peasants}
        for vamp in vampires:
            prompt = [
                {"role": "system", "content": f"You are the vampire {vamp}."},
                {"role": "system", "content": "Choose one peasant to kill tonight."},
                {"role": "system", "content": "Choices: " + ", ".join(peasants)}
            ]
            raw = chat_completion(
                chat_history=prompt,
                temperature=self.temperature,
                player_name=vamp,
                player_model_map=self.player_model_map
            )
            choice = sanitize_reply(raw).strip()
            if choice not in peasants:
                choice = random.choice(peasants)
            votes[choice] += 1

        # Determine highest votes and resolve ties
        max_votes = max(votes.values())
        top_choices = [p for p, count in votes.items() if count == max_votes]
        victim = random.choice(top_choices) if len(top_choices) > 1 else top_choices[0]

        # Remove victim from game
        self.update_player_list(victim)
        return victim

    def mod_announcing_updates(self, day_or_night: str, subject: Optional[str]) -> None:
        """
        Moderator announcement after night or day action.
        day_or_night: "Night" or "Day"
        subject: victim name (for night) or kicked player (for day)
        """
        if day_or_night == "Night":
            if subject:
                announcement = f"Night has fallen. Vampires have killed {subject} tonight."
            else:
                announcement = "Night has fallen. No one was killed tonight."
        else:
            if subject:
                announcement = f"Day has dawned. The community has voted out {subject}."
            else:
                announcement = "Day has dawned. The vote was tied; no one was voted out."
        # Append to public history
        self.shared_history.append({"role": "system", "content": announcement})

    def mod_announcing_alive_players(self) -> None:
        """
        Announce currently living players to the public chat.
        """
        if not self.turn_order:
            return
        announcement = "Currently alive players: " + ", ".join(self.turn_order) + "."
        self.shared_history.append({"role": "system", "content": announcement})


    def update_player_list(self, removed_player: str) -> None:
        """
        Remove eliminated player from turn order, roles, and private history.
        Adjust current_index accordingly.
        """
        if removed_player not in self.turn_order:
            return
        idx = self.turn_order.index(removed_player)
        self.turn_order.remove(removed_player)
        # Adjust current index to account for removed player
        if idx < self.current_index:
            self.current_index -= 1
        # Clean up role and private history
        self.roles.pop(removed_player, None)
        self.private_histories.pop(removed_player, None)

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

    def vote(self) -> Optional[str]:
        """
        Real vote function: players can vote for someone to kick or pass.
        Returns the name of the kicked player, or None if tie or no votes.
        """
        if not self.turn_order:
            return None
        # Initialize vote counts
        votes: Dict[str, int] = {p: 0 for p in self.turn_order}
        passes = 0
        # Ask each player
        for p in list(self.turn_order):
            prompt = [
                {"role": "system", "content": f"You are player {p}."},
                {"role": "system", "content": "Vote to kick a player or say 'Pass'."},
                {"role": "system", "content": "Choices: " + ", ".join(self.turn_order) + ", Pass"}
            ]
            raw = chat_completion(
                chat_history=prompt,
                temperature=self.temperature,
                player_name=p,
                player_model_map=self.player_model_map
            )
            choice = sanitize_reply(raw).strip()
            if choice == "Pass":
                passes += 1
            elif choice in votes:
                votes[choice] += 1
            else:
                # Invalid choice treated as pass
                passes += 1
        # Filter out passes
        filtered_votes = {p: c for p, c in votes.items() if c > 0}
        if not filtered_votes:
            return None
        # Determine highest and tie
        max_votes = max(filtered_votes.values())
        top = [p for p, c in filtered_votes.items() if c == max_votes]
        if len(top) > 1:
            return None
        kicked = top[0]
        # Remove from game
        self.update_player_list(kicked)
        return kicked


    def run_game(self) -> None:
        """
        Main game loop combining day and night stages until end state.
        """
        round_counter = 0
        while True:
            # Night: vampires choose a victim
            victim = self.vampires_voting()

            print(f"Night: {victim} has been chosen as the victim.")

            # Moderator announces results and updates about the night actions
            self.mod_announcing_updates("Night", victim)

            finished, winner = self.check_game_end()
            if finished:
                print(f"Game over! {winner} wins!")
                break

            # Announce alive players before day discussion
            self.mod_announcing_alive_players()

            # Day: players discuss
            self.public_chat(rounds=len(self.turn_order)*2)

            # Vote for a player to kick out
            kicked_player = self.vote()

            print(f"Day: {kicked_player} has been voted out.")

            # Moderator announces results and updates about the poll results
            self.mod_announcing_updates("Day", kicked_player)

            finished, winner = self.check_game_end()
            if finished:
                print(f"Game over! {winner} wins!")
                break

            # Announce alive players before next night
            self.mod_announcing_alive_players()

# --- example ---
if __name__ == "__main__":
    load_dotenv()
    players = ["John","Bob","Sarah","Alice", "Charlie", "David"]
    models = [
        "openai/o4-mini-high",
        "google/gemini-2.5-pro-preview",
        "qwen/qwen3-32b",
        "anthropic/claude-3.7-sonnet",
        "x-ai/grok-3-mini-beta",
        "deepseek/deepseek-r1"
    ]

    game = Vampire_or_Peasant(players, models)
    game.introduce_players()
    game.assign_roles(vampire_population=1)

    # run the full game loop
    game.run_game()

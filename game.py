import os
import random
from typing import List, Dict, Optional, Any, Tuple
from dotenv import load_dotenv
import yaml

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
        rules_file_path: str,
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

        # Some helpful variables
        self.has_doctor_protected_himself = False
        self.protected_player = None

        # Roles mapping
        self.roles: Dict[str, str] = {}

        # Game rules - loaded from file
        self.rules = self._load_rules_from_file(rules_file_path)

    def _load_rules_from_file(self, file_path: str) -> Dict[str, Any]:
        """Loads game rules from a YAML file."""
        try:
            with open(file_path, 'r') as f:
                rules_config = yaml.safe_load(f)
            
            # Assuming the rules are under a top-level key, e.g., 'game_rules'
            # and that this key contains a dictionary like the original self.rules
            if not isinstance(rules_config, dict) or 'game_system_prompt' not in rules_config:
                raise ValueError(f"YAML file '{file_path}' must contain a top-level key 'game_system_prompt' "
                                 "with 'role' and 'content'.")
            
            game_system_prompt = rules_config['game_system_prompt']
            if not isinstance(game_system_prompt, dict) or \
               'role' not in game_system_prompt or \
               'content' not in game_system_prompt:
                raise ValueError("The 'game_system_prompt' in the YAML must be a dictionary "
                                 "containing 'role' and 'content' keys.")
            
            return game_system_prompt # This is the direct replacement for the old self.rules
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Rules file not found: {file_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML rules file {file_path}: {e}")
        except Exception as e: # Catch other potential issues during loading/parsing
            raise ValueError(f"An unexpected error occurred while loading rules from {file_path}: {e}")

    def introduce_players(self) -> None:
        """Announce players once at game start."""
        names = ", ".join(self.turn_order)

        # Append system messages to shared history
        self.shared_history.append({
            "role": "system",
            "content": (
                "Game rules: " + self.rules["content"] + ". "
        )})
        
       # Append system messages to shared history (welcome message)
        self.shared_history.append({
            "role": "system",
            "content": (
                "Hello everyone. I am the moderator. Players are: " + names + ". "
                "Roles assigned. Game begins now."
            )
        })


    def assign_roles(self, vampire_population: int = 1) -> None:
        """
        Randomly assign secret roles to each player. Called once per game.
        Roles:
        - N Vampires (as per vampire_population)
        - 1 Observer
        - 1 Clown
        - 1 Doctor
        - 1 Musketeer
        - Remaining: Peasants (without special abilities)
        """
        num_players = len(self.turn_order)

        # Define counts for the fixed special roles
        num_observer = 1
        num_clown = 1
        num_doctor = 1
        num_musketeer = 1

        # Calculate the total number of roles that have a fixed count or are specified by parameter
        total_specific_roles = (
            vampire_population
            + num_observer
            + num_clown
            + num_doctor
            + num_musketeer
        )

        # --- Validations ---
        if not (vampire_population >= 1):
            raise ValueError("vampire_population must be at least 1.")

        if total_specific_roles > num_players:
            raise ValueError(
                f"Not enough players ({num_players}) for the specified roles. "
                f"Required: {vampire_population} Vampires, {num_observer} Observer, "
                f"{num_clown} Clown, {num_doctor} Doctor, {num_musketeer} Musketeer. "
                f"Total specific roles: {total_specific_roles}."
            )

        # --- Role Assignment ---
        # Create a mutable list of players and shuffle it for random assignment.
        # This list contains player names and is used to pick players for roles.
        players_to_assign_from = list(self.turn_order)
        random.shuffle(players_to_assign_from)

        # Assign Vampires directly to self.roles
        for _ in range(vampire_population):
            player = players_to_assign_from.pop(0) # Take from the front of the shuffled list
            self.roles[player] = "Vampire"

        # Assign Observer
        player = players_to_assign_from.pop(0)
        self.roles[player] = "Observer"

        # Assign Clown
        player = players_to_assign_from.pop(0)
        self.roles[player] = "Clown"

        # Assign Doctor
        player = players_to_assign_from.pop(0)
        self.roles[player] = "Doctor"

        # Assign Musketeer
        player = players_to_assign_from.pop(0)
        self.roles[player] = "Musketeer"

        # Assign remaining players as "Peasant" (without special roles)
        for player in players_to_assign_from: # Any players left in the list
            self.roles[player] = "Peasant"

        # --- Update private_histories ---
        # self.roles is now fully populated.
        # Iterate through the original turn_order (or all player_names) to update their private history.
        for player_name in self.turn_order:
            role = self.roles[player_name] # Get the assigned role for this player

            # Append system messages to private history for each player
            self.private_histories[player_name].append(
                {"role": "system", "content": f"You are {player_name}."}
            )
            self.private_histories[player_name].append(
                {"role": "system", "content": f"Your secret role is: {role}."}
            )

            # Optional: Add role-specific introductory messages
            if role == "Vampire":
                self.private_histories[player_name].append(
                    {"role": "system", "content": "You are a Vampire. Your goal is to eliminate all Peasants. You can choose one Peasant to kill each night."}
                )
            elif role == "Observer":
                self.private_histories[player_name].append(
                    {"role": "system", "content": "You are an Observer. Your goal is to identify the Vampires. You can observe one player each night to learn their role."}
                )
            elif role == "Clown":
                self.private_histories[player_name].append(
                    {"role": "system", "content": "You are the Clown. Your goal is to get yourself eliminated by public vote. If you succeed, you might win alone!"}
                )
            elif role == "Doctor":
                self.private_histories[player_name].append(
                    {"role": "system", "content": "You are a Doctor. Each night, you may choose one player to protect from a Vampire attack. Your goal is to help the Peasants survive."}
                )
            elif role == "Musketeer":
                self.private_histories[player_name].append(
                    {"role": "system", "content": "You are a Musketeer. If you've been eliminated by public vote, you can choose one player to eliminate as you go down."}
                )
            elif role == "Peasant":
                self.private_histories[player_name].append(
                    {"role": "system", "content": "You are a Peasant. You have no special abilities. Your goal is to work with others to identify and eliminate all Vampires."}
                )

    def build_conversation(self, player_name: str) -> List[Dict[str, Any]]:
        """
        Build the conversation history for a specific player.
        This includes the shared history and the player's private history.
        """
        # Build conversation for this player
        shared_sep = {"role": "system", "content": "Here is the chat so far:"}
        private_sep = {"role": "system", "content": "Here is your private history:"}
        last_warning = {"role": "system", "content": "Do not put your name before your message. Just write your message."}
        msgs = [shared_sep] + self.shared_history + [private_sep] + self.private_histories[player_name] + [last_warning]
        return msgs

    def public_chat(self, rounds: int = 1) -> List[Dict[str, Any]]:
        for _ in range(rounds):
            speaker = self.turn_order[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.turn_order)

            msgs = self.build_conversation(speaker)
            reply = chat_completion(
                chat_history=msgs,
                temperature=self.temperature,
                player_name=speaker,
                player_model_map=self.player_model_map
            )

            # reply = sanitize_reply(raw_reply)
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
        peasants = [p for p, role in self.roles.items() if role != "Vampire" and p in self.turn_order]
        if not vampires or not peasants:
            return None

        # Collect votes
        votes: Dict[str, int] = {peasant: 0 for peasant in peasants}
        for vamp in vampires:
            prompt = [
                {"role": "system", "content": f"You are the vampire {vamp}."},
                {"role": "system", "content": "Choose one peasant to kill tonight."},
                {"role": "system", "content": "Choices: " + ", ".join(peasants) + "Only reply with the name of the chosen peasant."}
            ]
            choice = chat_completion(
                chat_history=prompt,
                temperature=self.temperature,
                player_name=vamp,
                player_model_map=self.player_model_map
            )
            #choice = sanitize_reply(raw).strip()
            if choice not in peasants:
                choice = random.choice(peasants)
            votes[choice] += 1

        # Determine highest votes and resolve ties
        max_votes = max(votes.values())
        top_choices = [p for p, count in votes.items() if count == max_votes]
        victim = random.choice(top_choices) if len(top_choices) > 1 else top_choices[0]

        if victim == self.protected_player:
            return None

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
        print(announcement)


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

    def check_game_end(self, kicked: str = None) -> Tuple[bool, str]:
        """
        Evaluate win conditions:
        - If the kicked player had the role "Clown", then game ends. Clown wins.
        - If no vampires remain, peasants win.
        - If vampires >= peasants, vampires win.
        Returns (ended: bool, winner: str).
        """
        # Check Clown win condition first
        if kicked: # Ensure kicked is not empty or None
            kicked_role = self.roles.get(kicked)
            if kicked_role == "Clown":
                return True, "Clown"

        # Count roles among alive players
        alive = self.turn_order
        num_vampires = sum(1 for p in alive if self.roles.get(p) == "Vampire")
        num_peasants = sum(1 for p in alive if self.roles.get(p) != "Vampire") # Assuming non-Vampires are Peasants for this count

        # Peasants win if no vampires remain
        if num_vampires == 0:
            return True, "Peasants"

        # Vampires win if they are equal or outnumber peasants
        # This condition should only be checked if there are still vampires.
        # If num_vampires is 0, the above condition already handles it.
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
    
    # There is a single observer. So there is no need to vote.
    def observer_action(self) -> Optional[str]:
        """
        Observer action: choose a player to observe.
        Returns the name of the observed player, or None if no valid choice.
        """
        if not self.turn_order:
            return None
        # Identify the observer
        observer = [p for p, role in self.roles.items() if role == "Observer"]
        observer = observer[0]
        others = [p for p in self.turn_order if p != observer]
        # Check if the observer is alive
        if observer not in self.turn_order:
            return
        
        # Observer asks to observe a player. Exclude himself.
        prompt = [
            {"role": "system", "content": f"You are the observer {observer}."},
            {"role": "system", "content": "Choose one player to know if vampire or peasant."},
            {"role": "system", "content": "Choices: " + ", ".join(others) + "Output only the name of the player and nothing else."}
        ]
        
        msgs = self.build_conversation(observer) + prompt
        observed_player = chat_completion(
            chat_history=msgs,
            temperature=self.temperature,
            player_name=observer,
            player_model_map=self.player_model_map
        )
        # Get the role of the observed player (only vampire or not vampire)
        # observed_player = sanitize_reply(reply).strip()
        if observed_player not in others:
            # Invalid choice treated as random
            observed_player = random.choice(others)
            
        actual_role_of_observed = self.roles[observed_player]
        
        # Determine the message about the role to provide to the observer.
        # The observer learns if the player is "Vampire" or "Peasant (Non-vampire)".
        if actual_role_of_observed == "Vampire":
            role_feedback_segment = f"{observed_player} is a Vampire."
        else:
            # Any non-Vampire role (Peasant, Doctor, Hunter, etc.) is reported as "Peasant (Non-vampire)"
            role_feedback_segment = f"{observed_player} is a Peasant (Non-vampire)."

        # Append the observation result to the observer's private history.
        observation_result_message = f"You chose to observe {observed_player}. {role_feedback_segment}"
        self.private_histories[observer].append(
            {"role": "system", "content": observation_result_message}
        )

    # There is a single doctor. So there is no need to vote.
    def doctor_action(self) -> Optional[str]:
        """
        Doctor action: choose a player to protect.
        Returns the name of the protected player, or None if no valid choice.
        """
        if not self.turn_order:
            return None
        # Identify the observer
        doctor = [p for p, role in self.roles.items() if role == "Doctor"]
        doctor = doctor[0]
        others = [p for p in self.turn_order if p != doctor]

        # Check the variable self.has_doctor_protected_himself to decide whether to add doctor to the list of others
        if not self.has_doctor_protected_himself:
            others.append(doctor)

        # Check if the doctor is alive
        if doctor not in self.turn_order:
            return

        # Observer asks to observe a player. Exclude himself.
        prompt = [
            {"role": "system", "content": f"You are the doctor {doctor}."},
            {"role": "system", "content": "Choose one player to protect from vampire."},
            {"role": "system", "content": "Choices: " + ", ".join(others) + "Output only the name of the player and nothing else."}
        ]
        
        msgs = self.build_conversation(doctor) + prompt
        protected_player = chat_completion(
            chat_history=msgs,
            temperature=self.temperature,
            player_name=doctor,
            player_model_map=self.player_model_map
        )
        if protected_player not in others:
            raise ValueError
        elif protected_player == doctor:
            self.has_doctor_protected_himself = True
        else:
            # If the doctor has protected himself, set the flag to True
            if protected_player == doctor[0]:
                self.has_doctor_protected_himself = True
        self.protected_player = protected_player

        # Append the observation result to the doctor's private history.
        protection_message = f"You chose to protect {protected_player}."
        self.private_histories[doctor].append(
            {"role": "system", "content": protection_message}
        )

        
    def run_game(self) -> None:
        """
        Main game loop combining day and night stages until end state.
        """
        while True:
            self.observer_action()
            self.doctor_action()

            # Night: vampires choose a victim
            victim = self.vampires_voting()

            if victim:
                print(f"Night: {victim} has been chosen as the victim.")
            else:
                print("Night: Noone died tonight.")
            self.protected_player = None

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

            finished, winner = self.check_game_end(kicked=kicked_player)
            if finished:
                print(f"Game over! {winner} wins!")
                break

            # Announce alive players before next night
            self.mod_announcing_alive_players()

# --- example ---
if __name__ == "__main__":
    load_dotenv()
    players = ["John","Bob","Sarah","Alice", "Charlie", "David", "Eva", "Frank", "Grace"]
    models = [
        "openai/o4-mini-high",
        "google/gemini-2.5-pro-preview",
        "qwen/qwen3-32b",
        "qwen/qwq-32b",
        "anthropic/claude-3.7-sonnet",
        "x-ai/grok-3-mini-beta",
        "deepseek/deepseek-r1",
        "mistralai/mistral-medium-3",
        "meta-llama/llama-4-maverick"
    ]

    game = Vampire_or_Peasant(players, models, "game_rules.yaml", temperature=0.6)
    game.introduce_players()
    game.assign_roles(vampire_population=2)

    # run the full game loop
    game.run_game()

    # TODO: Voting choices are not being recorded in the shared history.
    # TODO: When initialing classes, assign observer, clown, doctor, and musketeer to their own variables.
    # TODO: Add round numbers to the both histories

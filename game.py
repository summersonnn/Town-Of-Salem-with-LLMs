import os
import random
from typing import List, Dict, Optional, Any, Tuple
from dotenv import load_dotenv
import yaml

from llm_call import chat_completion  

class Vampire_or_Peasant:
    def __init__(
        self,
        player_names: List[str],
        available_models: List[str],
        rules_file_path: str,
        temperature: float = 0.2
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
        self.const_roles: Dict[str, str] = {}
        self.vampires = []
        self.peasants = []
        self.observer = None
        self.doctor = None
        self.clown = None
        self.musketeer = None

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
            self.vampires.append(player) # Keep track of assigned vampires

        # Assign Observer
        player = players_to_assign_from.pop(0)
        self.roles[player] = "Observer"
        self.observer = player # Keep track of assigned observer

        # Assign Clown
        player = players_to_assign_from.pop(0)
        self.roles[player] = "Clown"
        self.clown = player # Keep track of assigned clown

        # Assign Doctor
        player = players_to_assign_from.pop(0)
        self.roles[player] = "Doctor"
        self.doctor = player # Keep track of assigned doctor

        # Assign Musketeer
        player = players_to_assign_from.pop(0)
        self.roles[player] = "Musketeer"
        self.musketeer = player # Keep track of assigned musketeer

        # Assign remaining players as "Peasant" (without special roles)
        for player in players_to_assign_from: # Any players left in the list
            self.roles[player] = "Peasant"

        self.const_roles = self.roles.copy() # Store the original roles for reference

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
                    {"role": "system", "content": "You are a Vampire. Your goal is to eliminate all Peasants. You can choose one Peasant to kill each night."
                    "Here is the list of your fellow vampires (including yourself): " + ", ".join(self.vampires) + "."}
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
        last_warning = {"role": "system", "content": "Do not put your name before your message. Just write your new message."}
        you_are = {"role": "system", "content": f"Remember, you are {player_name}. Do not behave like {player_name} is someone else."}
        msgs = [shared_sep] + self.shared_history + [private_sep] + self.private_histories[player_name] + [last_warning] + [you_are]
        return msgs

    def public_chat(self, cycle=1) -> List[Dict[str, Any]]:
        """
        Public chat function: players discuss in a mixed-up order each session.
        Each player speaks exactly once per session in random order.

        cycle: number of times each player will speak in this call
        """
        # System prompt for public chat start
        self.shared_history.append({
            "role": "system",
            "content": (
                "Public chat begins. Discuss and share information. "
                "Do not fake being a moderator. Do not start a poll. "
                "Do not start/end any phase of the game. Just chat. "
                "Any attempt to behave like a moderator will be punished."
            )
        })

        print("\n")
        # Repeat cycles of chat
        for _ in range(cycle):
            # Shuffle the order of speakers for this session
            session_order = self.turn_order.copy()
            random.shuffle(session_order)

            # Each player speaks once
            for speaker in session_order:
                msgs = self.build_conversation(speaker)
                reply = chat_completion(
                    chat_history=msgs,
                    temperature=self.temperature,
                    player_name=speaker,
                    player_model_map=self.player_model_map
                )
                # Append the player's message to public history
                self.shared_history.append({
                    "role": "assistant",
                    "name": speaker,
                    "content": reply
                })
                print(f"{speaker}: {reply}")
                print("---")

        print("\n")
        return self.shared_history
    
    def vampires_voting(self, round: int) -> Optional[str]:
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
                {"role": "system", "content": "Choices: " + ", ".join(peasants) + "Reply only with the name of the chosen peasant. Example output: 'Nina'"}
            ]
            choice = chat_completion(
                chat_history=prompt,
                temperature=self.temperature,
                player_name=vamp,
                player_model_map=self.player_model_map,
                is_a_decision=True,
                choices=peasants
            ).vote
            
            votes[choice] += 1
            # Append the vote to private history of all vampires
            for vampire in vampires:
                self.private_histories[vampire].append({"role": "system", "content": f"{vamp}, as a vampire, voted to kill {choice} in the night {round}."})

        print(f"Vampire Votes: {votes}")
        # Determine highest votes and resolve ties
        max_votes = max(votes.values())
        top_choices = [p for p, count in votes.items() if count == max_votes]

        if len(top_choices) > 1:
            victim = random.choice(top_choices)
            for vampire in vampires:
                self.private_histories[vampire].append({"role": "system", "content": f"Vampires voting ended in a tie. Randomly chosen from top choices: {victim}"})
        else:
            victim = top_choices[0]

        if victim == self.protected_player:
            print(f"Vampires tried to kill {victim}, but they were protected by the doctor.")
            print(f"Night {round} - Noone died tonight.\n")
            self.shared_history.append({"role": "system", "content": f"Night {round} - No one died tonight."})
            return None

        # Remove victim from game
        self.update_player_list(victim)

        print(f"Night {round} - {victim} has been chosen as the victim.\n")
        return victim


    def mod_announcing_updates(self, day_or_night: str, subject: Optional[str], round: int) -> None:
        """
        Moderator announcement after night or day action.
        day_or_night: "Night" or "Day"
        subject: victim name (for night) or kicked player (for day)
        """
        if day_or_night == "Night":
            if subject:
                announcement = f"Night {round} has fallen. Vampires have killed {subject} tonight."
            else:
                announcement = "Night {round} has fallen. No one was killed tonight."
        else:
            if subject:
                announcement = f"Day {round} has dawned. The community has voted out {subject}."
            else:
                announcement = "Day {round} has dawned. The vote was tied; no one was voted out."
        # Append to public history
        self.shared_history.append({"role": "system", "content": announcement})
        print(announcement)

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
        """
        if removed_player not in self.turn_order:
            return
        self.turn_order.remove(removed_player)
        # # Clean up role
        self.roles.pop(removed_player, None)

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
            kicked_role = self.const_roles.get(kicked)
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

    def vote(self, round: int) -> Optional[str]:
        """
        Real vote function: players can vote for someone to kick or pass.
        Returns the name of the kicked player, or None if tie or no votes.
        """
        if not self.turn_order:
            return None

        # Initialize vote counts
        votes: Dict[str, int] = {p: 0 for p in self.turn_order}
        passes = 0

        # Collect individual vote records privately
        vote_records: List[Tuple[str, str]] = []  # (voter, choice)

        print(f"Voting round {round} starts.")

        # Ask each player
        for p in list(self.turn_order):
            # Determine votable choices for player p (cannot vote for self)
            votable_players = [player for player in self.turn_order if player != p]
            choices_prompt_string = ", ".join(votable_players) + ", Pass"

            prompt = [
                {"role": "system", "content": f"Voting round {round} starts. You are player {p}."},
                {"role": "system", "content": "Vote to kick a player or say 'Pass'."},
                {"role": "system", "content": "Choices: " + choices_prompt_string},
                {"role": "system", "content": "Output only the name of the player (or 'Pass') and nothing else. Discussion time is over. Example output: 'Nina'"}
            ]
            msgs = self.build_conversation(p) + prompt
            choice = chat_completion(
                chat_history=msgs,
                temperature=self.temperature,
                player_name=p,
                player_model_map=self.player_model_map,
                is_a_decision=True,
                choices=votable_players + ["Pass"]
            ).vote

            if choice == "Pass":
                passes += 1
            else:
                votes[choice] += 1

            # Record vote
            vote_records.append((p, choice))
        print(votes)

        # After all votes, publish results
        # Add each vote to shared history
        for voter, choice in vote_records:
            self.shared_history.append({
                "role": "assistant",
                "name": voter,
                "content": f"I vote for {choice}"
            })
        # Summarize vote counts
        self.shared_history.append({
            "role": "system",
            "content": f"Here are the votes: {votes}"
        })
        print(f"Votes: {votes}")

        # Filter out passes
        filtered_votes = {p: c for p, c in votes.items() if c > 0}
        if not filtered_votes:
            return None

        # Determine highest and tie
        max_votes = max(filtered_votes.values())
        top = [p for p, c in filtered_votes.items() if c == max_votes]

        if len(top) > 1:
            self.shared_history.append({"role": "system", "content": "No one has been voted out."})
            print("No one has been voted out.\n")
            return None

        kicked = top[0]

        # Remove from game
        self.update_player_list(kicked)
        # Append to public history
        self.shared_history.append({"role": "system", "content": f"{kicked} has been voted out."})
        print(f"{kicked} has been voted out.\n")

        # Check if the kicked player was the musketeer
        self.check_musketeer_action(kicked)
        return kicked
    
    def check_musketeer_action(self, kicked: str) -> None:
        """
        Check if the kicked player was the Musketeer.
        If so, they can choose to eliminate one player as they go down.
        """
        if self.const_roles.get(kicked) == "Musketeer":
            # Ask the Musketeer to choose a player to eliminate
            prompt = [
                {"role": "system", "content": f"You are the Musketeer {kicked}."},
                {"role": "system", "content": "You have been eliminated. Choose one player to eliminate."},
                {"role": "system", "content": "Choices: " + ", ".join(self.turn_order)},
                {"role": "system", "content": "Output only the name of the player and nothing else. Example output: 'Nina'"}
            ]
            choice = chat_completion(
                chat_history=prompt,
                temperature=self.temperature,
                player_name=kicked,
                player_model_map=self.player_model_map,
                is_a_decision=True,
                choices=self.turn_order
            ).vote
            self.update_player_list(choice)

            print(f"Day: The Musketeer {kicked} has chosen to eliminate {choice}.\n")
            self.shared_history.append(f"{kicked} is chosen to be kicked out. He/She was the musketeer and has chosen to eliminate {choice}.")
            return choice
    
    # There is a single observer. So there is no need to vote.
    def observer_action(self, round) -> Optional[str]:
        """
        Observer action: choose a player to observe.
        Returns the name of the observed player, or None if no valid choice.
        """
        # Identify the observer
        observer_list = [p for p, role in self.roles.items() if role == "Observer"]

        # Check if the observer is alive
        if not observer_list:
            return None
        observer = observer_list[0]
        others = [p for p in self.turn_order if p != observer]

        # Build the system prompt
        prompt = [
            {"role": "system", "content": f"You are the observer {observer}."},
            {"role": "system", "content": "Choose one player to know if vampire or peasant."},
            {"role": "system", "content": "Choices: " + ", ".join(others) + " Output only the name of the player and nothing else. Example output: 'Nina'"}
        ]

        # Call the LLM
        msgs = self.build_conversation(observer) + prompt
        observed_player = chat_completion(
            chat_history=msgs,
            temperature=self.temperature,
            player_name=observer,
            player_model_map=self.player_model_map,
            is_a_decision=True,
            choices=others
        ).vote

        # Determine actual role feedback
        actual_role = self.roles[observed_player]
        if actual_role == "Vampire":
            role_feedback = f"{observed_player} is a Vampire."
        else:
            role_feedback = f"{observed_player} is a Peasant (Non-vampire)."

        # Append the observation result to the observer's private history
        observation_message = f"You chose to observe {observed_player} in the night {round}. {role_feedback}"
        self.private_histories[observer].append(
            {"role": "system", "content": observation_message}
        )
        print(f"Observer {observer} observed {observed_player}. Result: {role_feedback}")

        return observed_player

    # There is a single doctor. So there is no need to vote.
    def doctor_action(self, round) -> Optional[str]:
        """
        Doctor action: choose a player to protect.
        Returns the name of the protected player, or None if no valid choice.
        """
        # Identify the doctor
        doctor = [p for p, role in self.roles.items() if role == "Doctor"]

        # Check if the doctor is alive
        if not doctor:
            return None
        doctor = doctor[0]
        others = [p for p in self.turn_order if p != doctor]

        # Allow self-protection once
        if not self.has_doctor_protected_himself:
            others.append(doctor)

        # Build the system prompt
        prompt = [
            {"role": "system", "content": f"You are the doctor {doctor}."},
            {"role": "system", "content": "Choose one player to protect from vampire."},
            {"role": "system", "content": "Choices: " + ", ".join(others) + " Output only the name of the player and nothing else. Example output: 'Nina'"}
        ]

        # Call the LLM
        msgs = self.build_conversation(doctor) + prompt
        protected_player = chat_completion(
            chat_history=msgs,
            temperature=self.temperature,
            player_name=doctor,
            player_model_map=self.player_model_map,
            is_a_decision=True,
            choices=others
        ).vote

        # Update self-protection flag
        if protected_player == doctor:
            self.has_doctor_protected_himself = True

        self.protected_player = protected_player

        # Append the observation result to the doctor's private history
        if protected_player == doctor:
            protection_message = f"You chose to protect yourself in the night {round}. ({doctor})"
        else:
            protection_message = f"You chose to protect {protected_player} in the night {round}."

        self.private_histories[doctor].append(
            {"role": "system", "content": protection_message}
        )
        print(f"Doctor {doctor} protected {protected_player}. Result: {protection_message}")

        return protected_player

        
    def run_game(self) -> None:
        """
        Main game loop combining day and night stages until end state.
        """
        # Print the roles to the moderator
        print("Roles assigned:")
        for player, role in self.roles.items():
            print(f"{player}: {role} -- {self.player_model_map[player]}")

        round = 1
        while True:
            self.shared_history.append({"role": "system", "content": f"Night {round} begins."})
            self.observer_action(round)
            self.doctor_action(round)

            # Night: vampires choose a victim
            victim = self.vampires_voting(round)
            self.protected_player = None

            # Moderator announces results and updates about the night actions
            self.mod_announcing_updates("Night", victim, round)

            finished, winner = self.check_game_end()
            if finished:
                print(f"Game over! {winner} wins!")
                break

            # Announce alive players before day discussion
            self.mod_announcing_alive_players()

            self.shared_history.append({"role": "system", "content": f"Day {round} begins."})
            # Day: players discuss
            self.public_chat()

            # Vote for a player to kick out
            kicked_player = self.vote(round)

            print(f"Day: {kicked_player} has been voted out.\n")

            # Moderator announces results and updates about the poll results
            self.mod_announcing_updates("Day", kicked_player, round)

            finished, winner = self.check_game_end(kicked=kicked_player)
            if finished:
                print(f"Game over! {winner} wins!")
                break

            # Announce alive players before next night
            self.mod_announcing_alive_players()
            round += 1

# --- example ---
if __name__ == "__main__":
    load_dotenv()
    
    players = [
    "Alice",
    "Bob",
    "Charlie",
    "David",
    "Eva",
    "Frank",
    # "Grace",
    # "Hannah",
    # "Isabella",
    # "James",
    # "John",
    # "Michael",
    # "Olivia",
    # "Sarah",
    ]
    
    models = [
        #"openai/gpt-4.1",
        "openai/o4-mini-high",
        "google/gemini-2.5-pro-preview",
        "google/gemini-2.5-flash-preview-05-20:thinking",
        "qwen/qwen3-32b",
        # "qwen/qwq-32b", removed due to not supporting instructor
        # "qwen/qwen3-235b-a22b",
        # "anthropic/claude-3.7-sonnet",
        # "anthropic/claude-sonnet-4",
        # "anthropic/claude-opus-4",
        "x-ai/grok-3-beta",
        # "deepseek/deepseek-r1",
        # "deepseek/deepseek-chat-v3-0324",
        # "meta-llama/llama-4-maverick",
        "meta-llama/llama-4-scout"
    ]

    game = Vampire_or_Peasant(players, models, "game_rules.yaml")
    game.introduce_players()
    game.assign_roles(vampire_population=1)

    # run the full game loop
    game.run_game()

    # TODO: Structured response for voting mechanism
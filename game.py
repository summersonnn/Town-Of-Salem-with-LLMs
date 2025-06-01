import os
import random
from typing import List, Dict, Optional, Any, Tuple
from dotenv import load_dotenv
import yaml

from llm_call import chat_completion
from game_logs import GameLogger 
from game_points import GamePoints

class Vampire_or_Peasant:
    def __init__(
        self,
        player_names: List[str],
        available_models: List[str],
        rules_file_path: str,
        game_id: int,
        temperature: float = 0.2
    ):
        """
        player_names: list of human-readable names
        available_models: unique model strings to assign (must >= players)
        """
        if len(available_models) < len(player_names):
            raise ValueError("Not enough distinct models for each player.")
        self.rules_file_path = rules_file_path
        self.game_id = game_id # Store game_id
        self.logger = GameLogger(game_id=self.game_id)
        
        # Store original player names for logging setup
        self.initial_player_names = player_names[:]

        # Assign unique models with :nitro suffix
        # suffixed = [m + ":nitro" for m in random.sample(available_models, len(player_names))]
        # We no longer use nitro suffix.
        suffixed = [m for m in random.sample(available_models, len(player_names))]
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
        self.observer = None
        self.doctor = None
        self.clown = None
        self.musketeer = None

        # Game rules - loaded from file
        self.rules = self._load_rules_from_file(rules_file_path)

        # --- Points System Attributes ---
        # Initialized with 0 for all players who start the game.
        self.player_rounds_survived: Dict[str, int] = {name: 0 for name in self.initial_player_names}
        # Points accumulated by non-vampires for surviving nights.
        self.player_nightly_points: Dict[str, float] = {name: 0.0 for name in self.initial_player_names}
        self.winner_team: str = ""  # Stores "Vampires", "Peasants", or "Clown"
        self.kicked_clown_name: Optional[str] = None # Stores the name of the Clown if they win by being kicked
        self.total_rounds_played_in_game: int = 0 

        # Initialize GamePoints handler
        # This is fine here as GamePoints accesses game attributes lazily (during process_points)
        self.game_points_handler = GamePoints(self)

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

        # Game rules announcement
        rules_message_content = "Game rules: " + self.rules["content"] + ". "
        self.shared_history.append({
            "role": "system",
            "content": rules_message_content
        })
        
        # Welcome message announcement
        welcome_message_content = (
            "Hello everyone. I am the moderator. Players are: " + names + ". "
            "Roles assigned. Game begins now."
        )
        self.shared_history.append({
            "role": "system",
            "content": welcome_message_content
        })
        self.logger.log_moderator_announcement(welcome_message_content)
        self.logger.save_log()


    def assign_roles(self, vampire_population: int = 1) -> None:
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
        
        # Log game setup and roles
        self.logger.log_game_setup_and_roles(
            player_names=self.initial_player_names, # Original list of players
            player_model_map=self.player_model_map,
            roles_map=self.const_roles,
            rules_file=self.rules_file_path,
            initial_vampire_population=vampire_population
        )
        self.logger.save_log()

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

    def public_chat(self, cycle: int = 1, round_num: Optional[int] = None) -> List[Dict[str, Any]]:
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
        self.logger.log_moderator_announcement("Public chat begins.\n", round_num=round_num, phase="Public Chat")

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
                self.logger.log_player_chat(speaker, reply, round_num=round_num, phase="Day Discussion")
                print(f"{speaker}: {reply}")
                print("------------------------------------------------------------------------------------")

        print("\n")
        self.logger.log_moderator_announcement("Public chat ended. Moving to voting phase.\n", round_num=round_num, phase="Public Chat")
        self.logger.save_log()
        return self.shared_history
    
    def vampires_voting(self, round: int) -> Optional[str]:
            current_phase = "Night - Vampire Voting"
            self.logger.log_game_event("Vampire Voting Phase", "Vampires are choosing a victim.", round_num=round, phase=current_phase)

            alive_vampires = [p for p, role in self.roles.items() if role == "Vampire" and p in self.turn_order]
            potential_victims = [p for p in self.turn_order if self.roles.get(p) != "Vampire"]

            votes: Dict[str, int] = {peasant: 0 for peasant in potential_victims}
            # Store individual vote records privately until all votes are cast
            # Each item will be a tuple: (vampire_who_voted, chosen_victim)
            individual_vampire_votes: List[Tuple[str, str]] = []
            
            # Construct the part of the prompt that is common for all vampires making this decision
            # This will be appended to their individual full conversation history
            vampire_decision_prompt_suffix = [
                {"role": "system", "content": f"It is Night {round}. As a Vampire, you and your fellow vampires must choose one non-Vampire player to kill."},
                {"role": "system", "content": "Review the public chat and your private history to make a strategic decision."},
                {"role": "system", "content": "Your fellow vampires are: " + ", ".join(v for v in self.vampires if v in self.turn_order) + "."}, # List alive fellow vampires
                {"role": "system", "content": "Alive non-Vampire players (potential targets): " + ", ".join(potential_victims) + "."},
                {"role": "system", "content": "Reply with the name of the player you vote to kill."}
            ]

            for vamp_attacker in alive_vampires:
                # Build the full conversation history for this vampire
                messages_for_llm = self.build_conversation(vamp_attacker)
                # Append the specific voting instructions
                messages_for_llm.extend(vampire_decision_prompt_suffix)
                
                choice_obj = chat_completion(
                    chat_history=messages_for_llm,
                    temperature=self.temperature,
                    player_name=vamp_attacker,
                    player_model_map=self.player_model_map,
                    is_a_decision=True,
                    choices=potential_victims
                )
                choice = choice_obj.vote
                
                if choice in votes: # Ensure the choice is a valid potential victim
                    votes[choice] += 1
                    individual_vampire_votes.append((vamp_attacker, choice)) # Record the vote
                    self.logger.log_player_action_choice(vamp_attacker, "Vampire Vote", choice, round_num=round, phase=current_phase, valid_choices=potential_victims)
                    print(f"Vampire {vamp_attacker} (privately) voted to kill {choice}.") # Server log
                else:
                    # Handle invalid choice - e.g., log it, and perhaps the vampire's vote is forfeited for this round
                    self.logger.log_game_event("Invalid Vampire Vote", f"Vampire {vamp_attacker} made an invalid choice: {choice}. Vote ignored.", round_num=round, phase=current_phase)

            self.logger.log_vote_tally("Vampire Kill", votes, round_num=round, phase=current_phase)
            print(f"Night {round} - All Vampire Votes Collected. Tally: {votes}")

            max_votes = max(votes.values())
            top_choices = [p for p, count in votes.items() if count == max_votes]

            # After all vampires have voted, update their private histories
            for vamp_recipient in alive_vampires:
                # Add each individual vote to the recipient's private history
                # This mimics the "assistant" role messages in the public vote
                for voter_vamp, victim_choice in individual_vampire_votes:
                    self.private_histories[vamp_recipient].append({
                        "role": "assistant", # Message is from the perspective of the voter_vamp
                        "name": voter_vamp,
                        "content": f"I voted to kill {victim_choice}."
                })

                # Add a system message summarizing the vote tally to the recipient's private history
                self.private_histories[vamp_recipient].append({
                    "role": "system",
                    "content": f"Night {round} vampire vote tally: {votes}"
                })
                
            # Now determine the outcome based on the vote tally
            if len(top_choices) > 1:
                victim = random.choice(top_choices)
                tie_msg = f"Vampire voting resulted in a tie. {victim} was randomly selected from the tied players ({', '.join(top_choices)}) to be killed."
                self.logger.log_game_event("Vampire Vote Tie Broken", tie_msg, round_num=round, phase=current_phase)
                for other_vamp in alive_vampires:
                    self.private_histories[other_vamp].append({"role": "system", "content": tie_msg})
            else:
                victim = top_choices[0]
                chosen_msg = f"Vampires collectively chose to kill {victim}."
                self.logger.log_game_event("Vampire Victim Chosen", chosen_msg, round_num=round, phase=current_phase)
                for other_vamp in alive_vampires:
                    self.private_histories[other_vamp].append({"role": "system", "content": chosen_msg})

            if victim == self.protected_player:
                protection_msg = f"Vampires tried to kill {victim}, but they were protected by the doctor."
                print(protection_msg)
                self.logger.log_game_event("Protection Successful", protection_msg, round_num=round, phase="Night")
                self.logger.save_log()
                return None 

            self.logger.log_elimination(victim, "Killed by Vampires", round_num=round, phase="Night", original_role=self.const_roles.get(victim))
            self.update_player_list(victim)

            print(f"Night {round} - {victim} has been chosen as the victim.\n")
            self.logger.save_log()
            return victim


    def mod_announcing_updates(self, day_or_night: str, subject: Optional[str], round: int) -> None:
        announcement: str
        if day_or_night == "Night":
            if subject:
                announcement = f"Night {round} has fallen. Vampires have killed {subject} tonight."
            else:
                announcement = f"Night {round} has fallen. No one was killed tonight."
        else: # Day
            if subject:
                announcement = f"Day {round} has dawned. The community has voted out {subject}."
            else:
                announcement = f"Day {round} has dawned. The vote was tied; no one was voted out."
        
        self.shared_history.append({"role": "system", "content": announcement})
        self.logger.log_moderator_announcement(announcement, round_num=round, phase=day_or_night)
        print(announcement)
        self.logger.save_log()

    def mod_announcing_alive_players(self, round_num: Optional[int] = None, phase: Optional[str] = None) -> None:
        if not self.turn_order:
            return
        announcement = "Currently alive players: " + ", ".join(self.turn_order) + "."
        self.shared_history.append({"role": "system", "content": announcement})
        self.logger.log_moderator_announcement(announcement, round_num=round_num, phase=phase)
        print(announcement)
        self.logger.save_log()

    def update_player_list(self, removed_player: str) -> None:
        """
        Remove eliminated player from turn order, roles, and private history.
        """
        if removed_player not in self.turn_order:
            return
        self.turn_order.remove(removed_player)
        # # Clean up role
        self.roles.pop(removed_player, None)

    def check_game_end(self, round_num: Optional[int] = None, kicked: str = None) -> Tuple[bool, str]:
        winner = ""
        reason = ""
        ended = False

        if kicked:
            kicked_role = self.const_roles.get(kicked)
            if kicked_role == "Clown":
                ended = True
                winner = "Clown"
                reason = f"Clown ({kicked}) was successfully voted out."

        if not ended:
            alive_players = self.turn_order
            # Use self.roles for current roles of ALIVE players for game logic
            # but self.const_roles for identifying original roles if needed elsewhere
            num_vampires = sum(1 for p in alive_players if self.roles.get(p) == "Vampire")
            # Non-vampires are anyone not a vampire among the living
            num_non_vampires = sum(1 for p in alive_players if self.roles.get(p) != "Vampire")
            
            print(f"[DEBUG] Game End Check (Round {round_num}): Vampires: {num_vampires}, Non-Vampires: {num_non_vampires}, Alive: {', '.join(alive_players)}")
            self.logger.log_game_event("Game End Check Status", 
                                       f"Vampires: {num_vampires}, Non-Vampires: {num_non_vampires}, Alive: {len(alive_players)} - This info is not shared with players.",
                                       round_num=round_num)

            if num_vampires == 0:
                ended = True
                winner = "Peasants" # Includes all non-vampire roles that survived
                reason = "All vampires have been eliminated."
            elif num_non_vampires <= num_vampires : # Vampires win if they are equal or outnumber peasants
                ended = True
                winner = "Vampires"
                reason = "Vampires equal or outnumber other players."

        if ended:
            final_alive_player_roles = {p: self.roles.get(p, "Unknown - Eliminated?") for p in self.turn_order}
            self.logger.log_game_end(winner, reason, final_alive_player_roles, self.const_roles)
            self.logger.save_log()
            return True, winner

        return False, ""

    def vote(self, round: int) -> Optional[str]:
        """
        Real vote function: players can vote for someone to kick or pass.
        Returns the name of the kicked player, or None if tie or no votes.
        """
        current_phase = "Day Voting"
        self.logger.log_game_event("Public Voting Phase", f"Day {round} voting starts.", round_num=round, phase=current_phase)

        # Initialize vote counts
        votes: Dict[str, int] = {p: 0 for p in self.turn_order}
        passes = 0

        # Collect individual vote records privately
        vote_records: List[Tuple[str, str]] = []  # (voter, choice)

        print(f"Voting round {round} starts.")
        self.logger.log_moderator_announcement("Public voting begins.\n", round_num=round, phase=f"Public Voting")

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
            choice_obj = chat_completion(
                chat_history=msgs,
                temperature=self.temperature,
                player_name=p,
                player_model_map=self.player_model_map,
                is_a_decision=True,
                choices=votable_players + ["Pass"]
            )
            choice = choice_obj.vote

            if choice == "Pass":
                passes += 1
            else:
                votes[choice] += 1

            # Record vote
            vote_records.append((p, choice))
            print(f"{p} voted for {choice}.")

        self.logger.log_vote_tally("Public Kick-Out", votes, round_num=round, phase=current_phase)
        print(f"Votes: {votes}")

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
            outcome_msg = "The vote was tied. No one has been voted out."
            self.logger.log_vote_outcome(outcome_msg, round_num=round, phase=current_phase)
            self.shared_history.append({"role": "system", "content": outcome_msg})
            print(outcome_msg + "\n")
            self.logger.save_log()
            return None
        
        kicked = top[0]
        outcome_msg = f"{kicked} has been voted out with {max_votes} vote(s)."
        self.logger.log_vote_outcome(outcome_msg, round_num=round, phase=current_phase)
        self.shared_history.append({"role": "system", "content": f"{kicked} has been voted out."}) # Simpler for chat
        print(f"{kicked} has been voted out.\n")

        # Log elimination before updating list and checking musketeer
        self.logger.log_elimination(kicked, "Voted out by players", round_num=round, phase=current_phase, original_role=self.const_roles.get(kicked))
        self.update_player_list(kicked)
        
        self.check_musketeer_action(kicked, round_num=round) # Pass round_num
        self.logger.log_moderator_announcement("Public voting ended.\n", round_num=round, phase="Public Voting")
        self.logger.save_log()
        return kicked
    
    def check_musketeer_action(self, kicked: str, round_num: int) -> None:
        """
        Check if the kicked player was the Musketeer.
        If so, they can choose to eliminate one player as they go down.
        """
        current_phase = "Day - Musketeer Action"
        if self.const_roles.get(kicked) == "Musketeer":
            self.logger.log_game_event("Musketeer Ability Triggered", f"{kicked} (Musketeer) was eliminated, can use ability.", round_num=round_num, phase=current_phase)
            # Ask the Musketeer to choose a player to eliminate
            prompt = [
                {"role": "system", "content": f"You are the Musketeer {kicked}."},
                {"role": "system", "content": "You have been eliminated. Choose one player to eliminate."},
                {"role": "system", "content": "Choices: " + ", ".join(self.turn_order)}
            ]
            choice_obj = chat_completion(
                chat_history=prompt, # Simplified history
                temperature=self.temperature,
                player_name=kicked, # Use the kicked player's name/model
                player_model_map=self.player_model_map,
                is_a_decision=True,
                choices=self.turn_order # Can choose from remaining alive players
            )
            choice = choice_obj.vote

            self.logger.log_player_action_choice(kicked, "Musketeer Retaliation", choice, round_num=round_num, phase=current_phase, valid_choices=self.turn_order)
            
            musketeer_msg = f"{kicked} was voted out. As the Musketeer, they chose to eliminate {choice}."
            print(musketeer_msg + "\n")
            self.shared_history.append({"role": "system", "content": musketeer_msg})
            # Log this specific moderator announcement as well
            self.logger.log_moderator_announcement(musketeer_msg, round_num=round_num, phase=current_phase)

            # Log elimination before updating list
            self.logger.log_elimination(choice, f"Eliminated by Musketeer {kicked}", 
                                        round_num=round_num, phase=current_phase, 
                                        eliminated_by=kicked, original_role=self.const_roles.get(choice))
            self.update_player_list(choice)
            self.logger.save_log()
    
    # There is a single observer. So there is no need to vote.
    def observer_action(self, round) -> Optional[str]:
        """
        Observer action: choose a player to observe.
        Returns the name of the observed player, or None if no valid choice.
        """
        current_phase = "Night - Observer Action"
        # Identify the observer
        observer_list = [p for p, role in self.roles.items() if role == "Observer"]

        # Check if the observer is alive
        if not observer_list:
            self.logger.log_game_event("Observer Action Skipped", "Observer is not active or available.", round_num=round, phase=current_phase)
            self.logger.save_log()
            return None
        
        observer = observer_list[0]
        others = [p for p in self.turn_order if p != observer]

        # Build the system prompt
        prompt = [
            {"role": "system", "content": f"You are the observer {observer}."},
            {"role": "system", "content": "Choose one player to know if they are a Vampire or not a Vampire."},
            {"role": "system", "content": "Choices: " + ", ".join(others) + " Output the name of the player."}
        ]

        # Call the LLM
        msgs = self.build_conversation(observer) + prompt
        choice_obj = chat_completion(
            chat_history=msgs,
            temperature=self.temperature,
            player_name=self.observer,
            player_model_map=self.player_model_map,
            is_a_decision=True,
            choices=others
        )
        observed_player = choice_obj.vote
        self.logger.log_player_action_choice(self.observer, "Observer Choice", observed_player, round_num=round, phase=current_phase, valid_choices=others)

        # Determine actual role feedback
        actual_role = self.roles[observed_player]
        if actual_role == "Vampire":
            role_feedback = f"{observed_player} is a Vampire."
        else:
            role_feedback = f"{observed_player} is a Peasant (Non-vampire)."

        # Append the observation result to the observer's private history
        observation_message = f"You chose to observe {observed_player} in the night {round}. {role_feedback}"
        self.logger.log_private_info(self.observer, "Observation Result", observation_message, round_num=round, phase=current_phase)
        self.private_histories[observer].append(
            {"role": "system", "content": observation_message}
        )
        print(f"Observer {observer} observed {observed_player}. Result: {role_feedback}")
        self.logger.save_log()
        return observed_player

    # There is a single doctor. So there is no need to vote.
    def doctor_action(self, round) -> Optional[str]:
        """
        Doctor action: choose a player to protect.
        Returns the name of the protected player, or None if no valid choice.
        """
        current_phase = "Night - Doctor Action"
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
        choice_obj = chat_completion(
            chat_history=msgs,
            temperature=self.temperature,
            player_name=self.doctor,
            player_model_map=self.player_model_map,
            is_a_decision=True,
            choices=others 
        )
        protected_player = choice_obj.vote
        self.logger.log_player_action_choice(self.doctor, "Doctor Protection", protected_player, round_num=round, phase=current_phase, valid_choices=others)

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
        self.logger.log_private_info(self.doctor, "Protection Confirmation", protection_message, round_num=round, phase=current_phase)
        self.logger.save_log()
        return protected_player

        
    def run_game(self) -> None:
        print(f"\n--- Starting Game {self.game_id} ---")
        print("Roles assigned (Moderator View for Game {self.game_id}):")
        for player, role in self.const_roles.items():
            print(f"- {player}: {role} (Model: {self.player_model_map[player]})")
        print("-----------------------------------------")

        round_num = 1
        while True:
            self.total_rounds_played_in_game = round_num # Update total rounds played

            print(f"\n--- Round {round_num} ---")
            # Increment rounds survived for players alive at the START of this round
            for alive_player_this_round_start in list(self.turn_order): # Iterate copy
                self.player_rounds_survived[alive_player_this_round_start] = \
                    self.player_rounds_survived.get(alive_player_this_round_start, 0) + 1

            # --- NIGHT PHASE ---
            night_phase_str = f"Night {round_num}"
            self.logger.log_game_event("Phase Start", f"{night_phase_str} begins.", round_num=round_num, phase="Night")
            self.logger.save_log()
            self.shared_history.append({"role": "system", "content": f"{night_phase_str} begins."})
            
            self.observer_action(round_num) # Logging within method
            self.doctor_action(round_num)   # Logging within method

            victim = self.vampires_voting(round_num) # Logging within method
            self.protected_player = None # Reset protection after vampire attack resolution

            self.mod_announcing_updates("Night", victim, round_num) # Logging within method

            # Award nightly points to non-vampires alive AFTER night's events
            for alive_player_after_night in list(self.turn_order): # Iterate copy
                player_original_role = self.const_roles.get(alive_player_after_night)
                if player_original_role and player_original_role != "Vampire":
                    self.player_nightly_points[alive_player_after_night] = \
                        self.player_nightly_points.get(alive_player_after_night, 0.0) + 0.1
            self.logger.save_log() # Save after nightly points update

            finished, winner = self.check_game_end(round_num=round_num) # Logging within method if game ends
            if finished:
                self.winner_team = winner # Store the winning team/role string
                print(f"Game over! {winner} wins!")
                self.logger.log_moderator_announcement(f"Game over! {winner} wins!", round_num=round_num, phase="Game End")
                self.logger.save_log()
                break

            self.mod_announcing_alive_players(round_num=round_num, phase="Night End") # Logging within method

            # --- DAY PHASE ---
            day_phase_str = f"Day {round_num}"
            self.logger.log_game_event("Phase Start", f"{day_phase_str} begins.", round_num=round_num, phase="Day")
            self.logger.save_log()
            self.shared_history.append({"role": "system", "content": f"{day_phase_str} begins."})
            
            self.public_chat(cycle=1, round_num=round_num) # Logging within method

            kicked_player = self.vote(round_num) # Logging within method

            self.mod_announcing_updates("Day", kicked_player, round_num) # Logging within method

            # Pass kicked_player to check_game_end for Clown win condition
            finished, winner = self.check_game_end(round_num=round_num, kicked=kicked_player) # Logging within method if game ends
            if finished:
                self.winner_team = winner
                if self.winner_team == "Clown" and kicked_player is not None and self.const_roles.get(kicked_player) == "Clown":
                    self.kicked_clown_name = kicked_player
                print(f"Game over! {winner} wins!")
                self.logger.log_moderator_announcement(f"Game over! {winner} wins!", round_num=round_num, phase="Game End")
                self.logger.save_log()
                break

            self.mod_announcing_alive_players(round_num=round_num, phase="Day End") # Logging within method
            round_num += 1
        
        # --- Game End Processing ---
        self.total_rounds_played_in_game = round_num # Final round count
        self.game_points_handler.process_points() # Process points after winner_team is set
        print(f"Game over! {self.winner_team} wins!")
        self.logger.log_moderator_announcement(f"Game over! {self.winner_team} wins!", round_num=self.total_rounds_played_in_game, phase="Game End")

        # Final save, though individual methods save frequently
        self.logger.save_log()
        print(f"--- Game {self.game_id} Concluded ---")

# --- Helper function to load config ---
def load_game_config(config_file_path="game_config.yaml"):
    """Loads player and model lists from a YAML configuration file."""
    try:
        with open(config_file_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if not isinstance(config, dict):
            raise ValueError(f"Configuration file {config_file_path} should be a YAML dictionary.")

        all_players = config.get('players')
        all_models = config.get('models')

        if not all_players or not isinstance(all_players, list):
            raise ValueError(f"Missing or invalid 'players' list in {config_file_path}.")
        if not all_models or not isinstance(all_models, list):
            raise ValueError(f"Missing or invalid 'models' list in {config_file_path}.")
            
        return all_players, all_models
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file_path}' not found.")
        raise
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{config_file_path}': {e}")
        raise
    except ValueError as e:
        print(f"Error in configuration file structure: {e}")
        raise

# --- example ---
if __name__ == "__main__":
    load_dotenv()

    # --- Configuration ---
    CONFIG_FILE = "game_config.yaml" # Name of your new config file
    RULES_FILE = "game_rules.yaml"
    NUM_GAMES_TO_RUN = 1
    NUM_PLAYERS_PER_GAME = 10

    # Load players and models from the external file
    try:
        ALL_PLAYERS, ALL_MODELS = load_game_config(CONFIG_FILE)
        print(f"Successfully loaded {len(ALL_PLAYERS)} players and {len(ALL_MODELS)} models from {CONFIG_FILE}.")
    except Exception as e:
        print(f"Failed to load game configuration: {e}")
        print("Exiting.")
        exit(1) # Exit if we can't load essential config

    # Ensure we have enough unique players and models for selection
    if len(ALL_PLAYERS) < NUM_PLAYERS_PER_GAME:
        raise ValueError(f"Not enough players in ALL_PLAYERS ({len(ALL_PLAYERS)}) to select {NUM_PLAYERS_PER_GAME}.")
    if len(ALL_MODELS) < NUM_PLAYERS_PER_GAME:
        raise ValueError(f"Not enough models in ALL_MODELS ({len(ALL_MODELS)}) to select {NUM_PLAYERS_PER_GAME}.")
    
    rules_file = "game_rules.yaml"

    for game_num in range(1, NUM_GAMES_TO_RUN + 1):
        print(f"\n\n===== INITIALIZING GAME {game_num} / {NUM_GAMES_TO_RUN} =====")
        
        # Select a random subset of players and models for this game
        # Ensure player names are unique for the game. random.sample handles this.
        selected_players = random.sample(ALL_PLAYERS, NUM_PLAYERS_PER_GAME)
        # Ensure model names are unique for the game. random.sample handles this.
        selected_models = random.sample(ALL_MODELS, NUM_PLAYERS_PER_GAME)

        print(f"Selected for Game {game_num}:")
        print(f"Players: {selected_players}")
        print(f"Models: {selected_models}")

        try:
            game_instance = Vampire_or_Peasant(
                player_names=selected_players,
                available_models=selected_models,
                rules_file_path=rules_file,
                game_id=game_num, # Pass the current game number
            )
            game_instance.introduce_players()
            game_instance.assign_roles(vampire_population=2) 
            game_instance.run_game()

        except Exception as e:
            print(f"!!!!!! CRITICAL ERROR IN GAME {game_num} !!!!!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {e}")
            import traceback
            traceback.print_exc()
            # Optionally, log this critical error to a master error log
            # For now, just prints and continues to the next game if possible

        print(f"===== GAME {game_num} COMPLETE =====")
        if game_num < NUM_GAMES_TO_RUN:
            print(f"Proceeding to Game {game_num + 1}...")
            # Add a small delay if desired, e.g., time.sleep(5)
        else:
            print("All games finished.")

    
    # DONE: Finish game logging for every step.
    # DONE: Implement a mechanism to randomly select 10 models and 10 names to start game.
    # DONE: Implement a run with 100 games, all running in a loop. Log files will be named Game 1, Game 2 etc.
    # DONE: Implement error handling to never stop a game.
    # DONE: Implement points system
    # DONE: Implement distinct point logs for every model and name. It includes how many times peasant, vampire, won, points etc.

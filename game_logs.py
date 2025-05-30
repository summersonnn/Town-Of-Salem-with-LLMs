import datetime
import os
from typing import List, Dict, Optional, Any, Tuple

class GameLogger:
    def __init__(self, game_id: Optional[str] = None, log_directory: str = "game_logs"):
        self.log_lines: List[str] = []
        self.game_id = game_id if game_id else datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_directory = log_directory
        os.makedirs(self.log_directory, exist_ok=True)
        
        self._add_log_entry(f"--- Game Log: {self.game_id} ---", include_timestamp=False)
        self._add_log_entry(f"--- Log started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---", include_timestamp=False)
        self._add_log_entry("="*50, include_timestamp=False)

    def _add_log_entry(self, message: str, include_timestamp: bool = True):
        if include_timestamp:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_lines.append(f"[{timestamp}] {message}")
        else:
            self.log_lines.append(message)

    def log_game_setup_and_roles(
        self,
        player_names: List[str], # Initial list of players before any potential reordering for roles
        player_model_map: Dict[str, str],
        roles_map: Dict[str, str], # This should be const_roles
        rules_file: str,
        initial_vampire_population: int # The requested number for setup
    ):
        self._add_log_entry("GAME SETUP & INITIAL ROLES:")
        self.log_lines.append(f"  Rules File: {rules_file}")
        self.log_lines.append(f"  Requested Vampire Population: {initial_vampire_population}") # Log what was requested
        
        # Determine actual number of vampires assigned for verification
        actual_vampires_assigned = sum(1 for role in roles_map.values() if role == "Vampire")
        self.log_lines.append(f"  Actual Vampires Assigned: {actual_vampires_assigned}")

        self.log_lines.append(f"  Players, Roles, and Models:")
        # Iterate using player_names to maintain original order if desired,
        # or iterate by roles_map.keys() if order from roles_map is fine.
        # Using player_names (original turn order) for consistency:
        for player_name in player_names:
            role = roles_map.get(player_name, "N/A - Role not found")
            model = player_model_map.get(player_name, "N/A - Model not found")
            self.log_lines.append(f"    - {player_name}: {role} (Model: {model})")
        self._add_log_entry("-" * 20, include_timestamp=False)

    def log_moderator_announcement(self, message: str, round_num: Optional[int] = None, phase: Optional[str] = None):
        context = []
        if round_num is not None:
            context.append(f"Round {round_num}")
        if phase:
            context.append(phase)
        context_str = f" ({', '.join(context)})" if context else ""
        self._add_log_entry(f"MODERATOR{context_str}: {message}")

    def log_player_chat(self, speaker: str, message: str, round_num: Optional[int] = None, phase: Optional[str] = None):
        context_parts = []
        if round_num is not None:
            context_parts.append(f"R{round_num}")
        if phase:
            phase_short = phase.replace(" Discussion", "").replace(" Voting", "Vote")
            context_parts.append(phase_short)
        context_str = f" ({', '.join(context_parts)})" if context_parts else ""
        self._add_log_entry(f"{speaker}{context_str}: {message.strip()}")

    def log_private_info(self, recipient: str, info_type: str, details_str: str, round_num: Optional[int] = None, phase: Optional[str] = None):
        context = []
        if round_num is not None:
            context.append(f"Round {round_num}")
        if phase:
            context.append(phase)
        context_str = f" ({', '.join(context)})" if context else ""
        self._add_log_entry(f"PRIVATE INFO for {recipient}{context_str} ({info_type}): {details_str}")

    def log_player_action_choice(self, actor: str, action_type: str, choice: Any, round_num: Optional[int] = None, phase: Optional[str] = None, valid_choices: Optional[List[str]] = None):
        context = []
        if round_num is not None:
            context.append(f"R{round_num}")
        if phase:
            context.append(phase)
        context_str = f" ({', '.join(context)})" if context else ""
        self._add_log_entry(f"ACTION{context_str}: {actor} [{action_type}] chose: {str(choice)}")

    def log_vote_tally(self, vote_type: str, votes_tally: Dict[str, int], round_num: Optional[int] = None, phase: Optional[str] = None):
        context = []
        if round_num is not None:
            context.append(f"Round {round_num}")
        if phase:
            context.append(phase)
        context_str = f" ({', '.join(context)})" if context else ""
        self._add_log_entry(f"VOTE TALLY{context_str} - Type: {vote_type}")
        if not votes_tally or all(v == 0 for v in votes_tally.values()):
            self.log_lines.append("  No votes cast or only passes.")
        else:
            for player, count in votes_tally.items():
                if count > 0 :
                    self.log_lines.append(f"  {player}: {count} vote(s)")
        self._add_log_entry("-" * 20, include_timestamp=False)

    def log_vote_outcome(self, outcome_message: str, round_num: Optional[int] = None, phase: Optional[str] = None):
        context = []
        if round_num is not None:
            context.append(f"Round {round_num}")
        if phase:
            context.append(phase)
        context_str = f" ({', '.join(context)})" if context else ""
        self._add_log_entry(f"VOTE OUTCOME{context_str}: {outcome_message}")

    def log_elimination(self, player_name: str, reason: str, round_num: Optional[int] = None, phase: Optional[str] = None, eliminated_by: Optional[str] = None, original_role: Optional[str] = None):
        context = []
        if round_num is not None:
            context.append(f"Round {round_num}")
        if phase:
            context.append(phase)
        context_str = f" ({', '.join(context)})" if context else ""
        role_info = f" (Role: {original_role})" if original_role else ""
        by_info = f" by {eliminated_by}" if eliminated_by else ""
        self._add_log_entry(f"ELIMINATION{context_str}: {player_name}{role_info} was eliminated. Reason: {reason}{by_info}.")

    def log_game_event(self, event_name: str, details_str: str, round_num: Optional[int] = None, phase: Optional[str] = None):
        context = []
        if round_num is not None:
            context.append(f"Round {round_num}")
        if phase:
            context.append(phase)
        context_str = f" ({', '.join(context)})" if context else ""
        self._add_log_entry(f"EVENT{context_str}: {event_name} - {details_str}")

    def log_game_end(self, winner: str, reason: str, final_alive_player_roles: Dict[str, str], all_initial_roles: Dict[str,str]):
        self._add_log_entry("="*50, include_timestamp=False)
        self._add_log_entry("GAME END:")
        self.log_lines.append(f"  Winner(s): {winner}")
        self.log_lines.append(f"  Reason: {reason}")
        self.log_lines.append(f"  Final Alive Players & Roles:")
        if final_alive_player_roles:
            for player, role in final_alive_player_roles.items():
                self.log_lines.append(f"    - {player}: {role}")
        else:
            self.log_lines.append("    - None")
        self._add_log_entry("="*50, include_timestamp=False)
        self._add_log_entry(f"--- Log ended at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---", include_timestamp=False)

    def save_log(self, filename: Optional[str] = None):
        if filename is None:
            filename = f"game_log_{self.game_id}.txt"
        filepath = os.path.join(self.log_directory, filename)
        try:
            with open(filepath, 'w') as f:
                for line in self.log_lines:
                    f.write(line + "\n")
            print(f"Game log saved to {filepath}")
        except IOError as e:
            print(f"Error saving game log to {filepath}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while saving log: {e}")
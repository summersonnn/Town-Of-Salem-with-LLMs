import os
import random
from typing import List, Dict, Optional, Any, Tuple
from dotenv import load_dotenv
import yaml
import re # For sanitizing filenames

# Assuming llm_call and game_logs are available
# from llm_call import chat_completion
# from game_logs import GameLogger

# --- GamePoints Class ---
class GamePoints:
    STATS_FOOTER_MARKER = "--- Summary Statistics ---"
    GLOBAL_STATS_FILE = os.path.join("point_stats", "global_game_stats.txt")

    def __init__(self, game_instance: 'Vampire_or_Peasant', base_dir: str = "point_stats"):
        self.game = game_instance
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        # Ensure the global stats file directory exists (it's within base_dir)
        os.makedirs(os.path.dirname(self.GLOBAL_STATS_FILE), exist_ok=True)


    def _sanitize_filename(self, name: str) -> str:
        name = str(name)
        name = re.sub(r'[^\w\-. ]', '', name)
        name = name.replace(' ', '_')
        return name

    def _get_player_file_path(self, player_name: str) -> str:
        safe_name = self._sanitize_filename(player_name)
        return os.path.join(self.base_dir, f"player_{safe_name}.txt")

    def _get_model_file_path(self, model_name: str) -> str:
        safe_name = self._sanitize_filename(model_name)
        return os.path.join(self.base_dir, f"model_{safe_name}.txt")

    def _parse_summary_stats_from_lines(self, lines: List[str]) -> Dict[str, float]:
        stats = {
            "Total Rounds Survived (Non-Vampire Games)": 0.0,
            "Total Rounds in all Non-Vampire Games": 0.0, # ADDED
            "Total Vampire Games": 0.0,
            "Won Vampire Games": 0.0,
            "Won and Survived Vampire Games": 0.0,
            "Total Peasant Role Games": 0.0, # Player's role was literally "Peasant"
            "Won Peasant Role Games": 0.0,
            "Total Clown Games": 0.0,
            "Won Clown Games": 0.0,
        }
        in_summary_section = False
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped: # Skip empty lines
                continue
            if self.STATS_FOOTER_MARKER in line_stripped:
                in_summary_section = True
                continue
            if not in_summary_section:
                continue

            try:
                key, value_str = line_stripped.split(":", 1)
                key = key.strip()
                
                if "Percentage" in key or "Ratio" in key: # Percentages are recalculated
                    continue
                
                if key in stats:
                    # Try to parse the numeric part (e.g., "10.0" from "10.0 %")
                    numeric_part = value_str.strip().split(" ")[0]
                    stats[key] = float(numeric_part)
            except ValueError:
                # print(f"Debug: Could not parse summary line: '{line_stripped}'")
                pass # Ignore lines that don't fit the expected key: value format or are percentages
        return stats

    def _format_summary_stats_for_file(self, stats_data: Dict[str, float]) -> str:
        # Calculate percentages
        vamp_win_perc = (stats_data["Won Vampire Games"] / stats_data["Total Vampire Games"] * 100) \
            if stats_data["Total Vampire Games"] > 0 else 0.0
        peasant_role_win_perc = (stats_data["Won Peasant Role Games"] / stats_data["Total Peasant Role Games"] * 100) \
            if stats_data["Total Peasant Role Games"] > 0 else 0.0
        clown_win_perc = (stats_data["Won Clown Games"] / stats_data["Total Clown Games"] * 100) \
            if stats_data["Total Clown Games"] > 0 else 0.0

        summary_lines = [f"{self.STATS_FOOTER_MARKER}\n"]
        summary_lines.append(f"Total Rounds Survived (Non-Vampire Games): {int(stats_data['Total Rounds Survived (Non-Vampire Games)'])}\n")
        summary_lines.append(f"Total Rounds in all Non-Vampire Games: {int(stats_data['Total Rounds in all Non-Vampire Games'])}\n") # ADDED
        
        summary_lines.append(f"Total Vampire Games: {int(stats_data['Total Vampire Games'])}\n")
        summary_lines.append(f"Won Vampire Games: {int(stats_data['Won Vampire Games'])}\n")
        summary_lines.append(f"Won and Survived Vampire Games: {int(stats_data['Won and Survived Vampire Games'])}\n")
        summary_lines.append(f"Vampire Win Percentage: {vamp_win_perc:.1f}%\n")

        summary_lines.append(f"Total Peasant Role Games: {int(stats_data['Total Peasant Role Games'])}\n")
        summary_lines.append(f"Won Peasant Role Games: {int(stats_data['Won Peasant Role Games'])}\n")
        summary_lines.append(f"Peasant Role Win Percentage: {peasant_role_win_perc:.1f}%\n")
        
        summary_lines.append(f"Total Clown Games: {int(stats_data['Total Clown Games'])}\n")
        summary_lines.append(f"Won Clown Games: {int(stats_data['Won Clown Games'])}\n")
        summary_lines.append(f"Clown Win Percentage: {clown_win_perc:.1f}%\n")
        
        return "".join(summary_lines)

    def _update_individual_stats_file(self, file_path: str, game_entry_text_block: str, current_game_numeric_stats: Dict[str, Any]):
        existing_game_entries_text = ""
        # Initialize with default values, will be overwritten if file exists and has stats
        summary_data = self._parse_summary_stats_from_lines([]) 

        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            summary_start_index = -1
            for i, line in enumerate(lines):
                if self.STATS_FOOTER_MARKER in line:
                    summary_start_index = i
                    break
            
            if summary_start_index != -1:
                existing_game_entries_text = "".join(lines[:summary_start_index])
                summary_data = self._parse_summary_stats_from_lines(lines[summary_start_index:])
            else:
                existing_game_entries_text = "".join(lines)

        if current_game_numeric_stats.get("was_non_vampire_this_game", False):
            summary_data["Total Rounds Survived (Non-Vampire Games)"] += current_game_numeric_stats.get("rounds_survived_for_calc", 0)
            summary_data["Total Rounds in all Non-Vampire Games"] += current_game_numeric_stats.get("total_rounds_in_this_game_for_calc", 0) # MODIFIED

        role = current_game_numeric_stats.get("original_role")
        if role == "Vampire":
            summary_data["Total Vampire Games"] += 1
            if current_game_numeric_stats.get("won_as_vampire", False):
                summary_data["Won Vampire Games"] += 1
                if current_game_numeric_stats.get("is_alive_at_end", False): # Only relevant if won as vampire
                    summary_data["Won and Survived Vampire Games"] += 1

        elif role == "Clown":
            summary_data["Total Clown Games"] += 1
            if current_game_numeric_stats.get("won_as_clown", False):
                summary_data["Won Clown Games"] += 1
        
        else: # Peasant or other roles (e.g. Observer, Doctor, Musketeer if counted as Peasant role)
            summary_data["Total Peasant Role Games"] += 1
            if current_game_numeric_stats.get("won_as_peasant_role", False):
                summary_data["Won Peasant Role Games"] += 1


        all_entries_text = existing_game_entries_text.strip() + "\n" + game_entry_text_block if existing_game_entries_text.strip() else game_entry_text_block
        formatted_summary_text = self._format_summary_stats_for_file(summary_data)
        
        final_text_to_write = all_entries_text + formatted_summary_text
        
        with open(file_path, 'w') as f:
            f.write(final_text_to_write)

    def process_stats(self):
        winner_team = self.game.winner_team
        
        for player_name in self.game.initial_player_names:
            original_role = self.game.const_roles.get(player_name, "Unknown Role")
            model_name = self.game.player_model_map.get(player_name, "Unknown Model")
            is_alive_at_end = player_name in self.game.turn_order
            rounds_survived_by_player = self.game.player_rounds_survived.get(player_name, 0)

            # --- Role-specific win condition points ---
            # Initialize stats for current game, to be passed for summary updates
            current_game_numeric_stats = {
                "original_role": original_role,
                "is_alive_at_end": is_alive_at_end,
                "was_non_vampire_this_game": (original_role != "Vampire"),
                "rounds_survived_for_calc": 0, # Conditional
                "total_rounds_in_this_game_for_calc": 0, # Conditional, ADDED
                "won_as_vampire": False,
                "won_as_peasant_role": False,
                "won_as_clown": False,
            }

            if original_role != "Vampire":
                current_game_numeric_stats["rounds_survived_for_calc"] = rounds_survived_by_player
                current_game_numeric_stats["total_rounds_in_this_game_for_calc"] = self.game.max_survivable_rounds # ADDED
            # Else, for Vampires, these remain 0, so they don't affect non-vampire specific stats.


            if original_role == "Vampire":
                if winner_team == "Vampires":
                    current_game_numeric_stats["won_as_vampire"] = True
            elif original_role == "Clown":
                if winner_team == "Clown" and self.game.kicked_clown_name == player_name:
                    current_game_numeric_stats["won_as_clown"] = True
            else: # Peasant, Observer, Doctor, Musketeer
                 if winner_team == "Peasants":
                      current_game_numeric_stats["won_as_peasant_role"] = True

            # Determine overall win/loss status for this player for the game entry
            player_won_this_game = False
            if original_role == "Vampire":
                player_won_this_game = (winner_team == "Vampires")
            elif original_role == "Clown":
                player_won_this_game = (winner_team == "Clown" and self.game.kicked_clown_name == player_name)
            else: # Peasant, Observer, Doctor, Musketeer
                player_won_this_game = (winner_team == "Peasants")
            
            # --- Player's File Entry Text Block ---
            player_game_entry_list = [
                f"Game ID: {self.game.game_id}\n",
                f"Players in Game (Name: Model): { {p: self.game.player_model_map.get(p) for p in self.game.initial_player_names} }\n",
                f"Your Role: {original_role}\n",
                f"Game Outcome for You: {'Won' if player_won_this_game else 'Lost'}\n",
            ]
            if original_role != "Vampire":
                player_game_entry_list.append(f"Rounds Survived by Player: {rounds_survived_by_player}\n")
                player_game_entry_list.append(f"Max Survivable rounds in this Game: {self.game.max_survivable_rounds}\n")
            else: # For Vampires
                player_game_entry_list.append(f"Rounds Survived by Player: {rounds_survived_by_player} (Vampire Game - survival stats not tracked for summary)\n")
                player_game_entry_list.append(f"Max Survivable rounds in this Game: {self.game.max_survivable_rounds} (Vampire Game - total rounds not tracked for non-vampire summary)\n")

            player_game_entry_list.extend([
                f"------------------------------------\n"
            ])
            player_game_entry_text_block = "".join(player_game_entry_list)
            player_file_path = self._get_player_file_path(player_name)
            self._update_individual_stats_file(player_file_path, player_game_entry_text_block, current_game_numeric_stats)

            # --- Model's File Entry Text Block ---
            model_game_entry_list = [
                f"Game ID: {self.game.game_id}\n",
                f"Played by (Player Name): {player_name}\n",
                f"Player's Role in this Game: {original_role}\n",
                f"Game Outcome for Player: {'Won' if player_won_this_game else 'Lost'}\n",
            ]
            if original_role != "Vampire":
                model_game_entry_list.append(f"Rounds Survived by Player: {rounds_survived_by_player}\n")
                model_game_entry_list.append(f"Max Survivable rounds in this Game: {self.game.max_survivable_rounds}\n")
            else:
                model_game_entry_list.append(f"Rounds Survived by Player: {rounds_survived_by_player} (Vampire Game - survival stats not tracked for summary)\n")
                model_game_entry_list.append(f"Max Survivable rounds in this Game: {self.game.max_survivable_rounds} (Vampire Game - total rounds not tracked for non-vampire summary)\n")

            model_game_entry_list.extend([
                f"------------------------------------\n"
            ])
            model_game_entry_text_block = "".join(model_game_entry_list)
            model_file_path = self._get_model_file_path(model_name)
            self._update_individual_stats_file(model_file_path, model_game_entry_text_block, current_game_numeric_stats)

        self.update_global_game_stats() # Call after processing all players
        print(f"Global stats processed and updated for Game {self.game.game_id}.")

    def update_global_game_stats(self):
        game_id = self.game.game_id
        winner_team = self.game.winner_team # "Vampires", "Peasants", "Clown"

        new_game_log_entry = f"Game {game_id}\nWon by {winner_team}\n\n"
        
        existing_log_entries = ""
        if os.path.exists(self.GLOBAL_STATS_FILE):
            with open(self.GLOBAL_STATS_FILE, 'r') as f:
                lines = f.readlines()
            
            # Extract only game log entries, discard old summary
            for i, line in enumerate(lines):
                if "Vampires win ratio:" in line or \
                   "Peasants win ratio:" in line or \
                   "Clown win ratio:" in line:
                    break 
                existing_log_entries += line
        
        all_log_entries = existing_log_entries.strip() + "\n" + new_game_log_entry if existing_log_entries.strip() else new_game_log_entry

        # Recalculate overall stats from all_log_entries
        total_games_played = 0
        vampire_team_wins = 0
        peasant_team_wins = 0
        clown_role_wins = 0 # Clown winning their specific way

        temp_lines = all_log_entries.splitlines()
        i = 0
        while i < len(temp_lines):
            if temp_lines[i].startswith("Game "):
                total_games_played += 1
                if i + 1 < len(temp_lines):
                    if temp_lines[i+1].startswith("Won by Vampires"):
                        vampire_team_wins += 1
                    elif temp_lines[i+1].startswith("Won by Peasants"):
                        peasant_team_wins += 1
                    elif temp_lines[i+1].startswith("Won by Clown"):
                        clown_role_wins += 1
                i += 1 # Move past "Won by" line
            i += 1


        vamp_ratio_str = f"Vampires win ratio: {vampire_team_wins}/{total_games_played} : {(vampire_team_wins/total_games_played*100) if total_games_played > 0 else 0:.1f}%\n"
        peasant_ratio_str = f"Peasants win ratio: {peasant_team_wins}/{total_games_played} : {(peasant_team_wins/total_games_played*100) if total_games_played > 0 else 0:.1f}%\n"
        clown_ratio_str = f"Clown win ratio: {clown_role_wins}/{total_games_played} : {(clown_role_wins/total_games_played*100) if total_games_played > 0 else 0:.1f}%\n"

        with open(self.GLOBAL_STATS_FILE, 'w') as f:
            f.write(all_log_entries.strip() + "\n\n") # Write all game logs
            f.write(vamp_ratio_str)
            f.write(peasant_ratio_str)
            f.write(clown_ratio_str)
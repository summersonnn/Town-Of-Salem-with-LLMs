import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import textwrap # For wrapping long labels

# New entity names (persons)
entities = [
    "Carter",
    "Casey",
    "Chuck",
    "Devon",
    "Elias",
    "Ellie",
    "Finch",
    "Fusco",
    "Greer",
    "Jeff",
    "Lester",
    "Morgan",
    "Reese",
    "Root",
    "Sarah",
    "Shaw"
]

# New scores for "Clown Win Ratio" for the persons
survival_rate_strings = [ # Variable name kept for consistency, holds win ratios
    "30.0%", "0.0%", "22.2%", "30.0%", "25.0%", "0.0%", "0.0%", "0.0%",
    "20.0%", "50.0%", "50.0%", "11.1%", "25.0%", "12.5%", "0.0%", "40.0%"
]
# Convert percentage strings to numerical values
scores = [float(s.replace('%', '')) for s in survival_rate_strings]

# Define number of bars
n = len(entities)
x = np.arange(n)
colors = plt.cm.tab20.colors[:n] # Same colors, will cycle if n > 20

# --- Configuration for dynamic labeling (ADAPTED FOR 0-100 SCALE - same as previous chart) ---
EXTERNAL_ENTITY_NAME_THRESHOLD = 8.0
WRAP_WIDTH_HORIZONTAL_EXTERNAL = 15 # Keep this, might be useful for long names if any
WRAP_WIDTH_VERTICAL_INTERNAL = 25   # Keep this
SHOW_VALUES_ABOVE_BAR = True
MIN_HEIGHT_TO_SHOW_VALUE = 0.0
VALUE_PADDING_ABOVE_BAR = 1.0
VALUE_FONT_SIZE = 7
VALUE_DECIMAL_PLACES = 1
ESTIMATED_VALUE_TEXT_HEIGHT_DATA_UNITS = 2.5
ENTITY_NAME_PADDING_ABOVE_VALUE = 0.5
ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR = 1.0
ESTIMATED_ENTITY_NAME_LINE_HEIGHT_DATA_UNITS = 2.5
# --- End Configuration ---

fig, ax = plt.subplots(figsize=(18, 9))
bars = ax.bar(x, scores, color=colors)

max_y_coord_overall = max(scores) if scores else 100.0 # Initialize with max score or 100

for i, bar in enumerate(bars):
    height = bar.get_height()
    original_entity_name = entities[i]
    entity_name_to_display = original_entity_name # Default to original
    bar_center_x = bar.get_x() + bar.get_width() / 2

    y_position_for_next_external_text_bottom = height
    value_text_was_plotted = False

    if SHOW_VALUES_ABOVE_BAR and height >= MIN_HEIGHT_TO_SHOW_VALUE:
        value_str = f"{height:.{VALUE_DECIMAL_PLACES}f}%"
        value_y_pos_bottom = y_position_for_next_external_text_bottom + VALUE_PADDING_ABOVE_BAR
        ax.text(bar_center_x, value_y_pos_bottom, value_str,
                ha='center', va='bottom', color='black',
                fontsize=VALUE_FONT_SIZE, rotation=0)
        y_position_for_next_external_text_bottom = value_y_pos_bottom + ESTIMATED_VALUE_TEXT_HEIGHT_DATA_UNITS
        value_text_was_plotted = True
    max_y_coord_overall = max(max_y_coord_overall, y_position_for_next_external_text_bottom)

    # The specific "Gemini-2.5 Pro Preview" check is no longer relevant with new entities,
    # but the general structure for potential future modifications is fine.
    # if original_entity_name == "SomeFutureLongName":
    #     entity_name_to_display = "SomeFuture\nLongName"

    if height < 20: # Font size logic remains based on bar height
        entity_fontsize = 8
    elif height <= 50:
        entity_fontsize = 10
    else:
        entity_fontsize = 12

    if height < EXTERNAL_ENTITY_NAME_THRESHOLD: # External label for short bars
        wrapped_entity_name = textwrap.fill(entity_name_to_display, width=WRAP_WIDTH_HORIZONTAL_EXTERNAL)
        num_lines_entity = wrapped_entity_name.count('\n') + 1
        estimated_total_entity_height = num_lines_entity * (ESTIMATED_ENTITY_NAME_LINE_HEIGHT_DATA_UNITS * (entity_fontsize / 8.0))

        if value_text_was_plotted:
            entity_y_pos_bottom = y_position_for_next_external_text_bottom + ENTITY_NAME_PADDING_ABOVE_VALUE
        else:
            entity_y_pos_bottom = height + ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR
            if height == 0: # Special handling for zero-height bars
                 entity_y_pos_bottom = max(ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR, 0.5) # Ensure text is visible

        ax.text(bar_center_x, entity_y_pos_bottom, wrapped_entity_name,
                ha='center', va='bottom', color='black',
                fontsize=entity_fontsize, rotation=0)
        max_y_coord_overall = max(max_y_coord_overall, entity_y_pos_bottom + estimated_total_entity_height)
    else: # Internal label for tall bars
        wrapped_entity_name = textwrap.fill(entity_name_to_display, width=WRAP_WIDTH_VERTICAL_INTERNAL)
        entity_y_pos_center = height / 2
        ax.text(bar_center_x, entity_y_pos_center, wrapped_entity_name,
                ha='center', va='center', color='white',
                fontsize=entity_fontsize, rotation=90,
                bbox=dict(facecolor='none', edgecolor='none', pad=0))

# Styling
ax.set_ylim(0, max(100.0, max_y_coord_overall + 5.0)) # Ensure y-limit accommodates 100% and any text above
ax.set_xticks([]) # Keep x-ticks hidden as names are on/above bars
ax.set_title("Clown Win Ratio", fontsize=18, pad=20) # Title remains the same
ax.set_ylabel("Win Ratio (%)", fontsize=14) # Y-axis label remains the same

plt.tight_layout()
plt.show()
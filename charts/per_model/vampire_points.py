import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import textwrap # For wrapping long labels

# Entity names and their corresponding scores
entities = [
    "Claude 3.7 Sonnet",
    "Claude Opus 4",
    "Claude Sonnet 4",
    "Deepseek-r1-0528",
    "Deepseek-r1-0528-qwen3-8b",
    "Gemini-2.5 Pro Preview",
    "Gemini-2.5 Flash Preview-0520:thinking",
    "Llama-4-Scout",
    "Llama-4-Maverick",
    "Nvidia-Llama-3.1-nemotron-ultra-253B-v1",
    "GPT4.1",
    "o1",
    "Qwen3-32B",
    "Qwen3-235B-A22B",
    "QwQ-32B",
    "Grok 3 Beta"
]

scores = [0.2, 0, 0.2, 0.625, 0.307, 0.227, 0.416, 0.285, 0.178, 0.115, 0.47, 0.227, 0.409, 0.392, 0.375, 0.153]

# Define number of bars
n = len(entities)
x = np.arange(n)
colors = plt.cm.tab20.colors[:n]

# --- Configuration for dynamic labeling ---
# Threshold for placing entity name externally (above bar/value) vs. internally
EXTERNAL_ENTITY_NAME_THRESHOLD = 0.08 # If bar height < this, entity name is external

# Text wrapping widths
WRAP_WIDTH_HORIZONTAL_EXTERNAL = 15 # For entity names placed externally
WRAP_WIDTH_VERTICAL_INTERNAL = 25   # For entity names placed internally

# Configuration for Score Value text (placed above bar)
SHOW_VALUES_ABOVE_BAR = True
MIN_HEIGHT_TO_SHOW_VALUE = 0.0 # Show value even for 0-height bars (as "0.00")
VALUE_PADDING_ABOVE_BAR = 0.01 # Gap between bar top and bottom of value text
VALUE_FONT_SIZE = 7
VALUE_DECIMAL_PLACES = 3
# Approximate height of value text in data units (for stacking entity name above it)
# This may need tuning based on figure size and y-axis scale
ESTIMATED_VALUE_TEXT_HEIGHT_DATA_UNITS = 0.025

# Configuration for External Entity Name text (if placed above value)
ENTITY_NAME_PADDING_ABOVE_VALUE = 0.005 # Gap between value top and entity name bottom
ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR = 0.01 # Gap if no value text is shown, or for 0-height bar
# Approximate height of one line of external entity name text in data units
ESTIMATED_ENTITY_NAME_LINE_HEIGHT_DATA_UNITS = 0.025
# --- End Configuration ---

fig, ax = plt.subplots(figsize=(18, 9))
bars = ax.bar(x, scores, color=colors)

max_y_coord_overall = max(scores) if scores else 1.0 # Initialize with max score

# Add text labels (entity names and score values)
for i, bar in enumerate(bars):
    height = bar.get_height()
    original_entity_name = entities[i]
    entity_name_to_display = original_entity_name
    bar_center_x = bar.get_x() + bar.get_width() / 2

    # This variable will track the y-coordinate for the bottom of the next piece of external text
    y_position_for_next_external_text_bottom = height
    value_text_was_plotted = False

    # --- 1. Handle Score Value (conditionally above bar) ---
    if SHOW_VALUES_ABOVE_BAR and height >= MIN_HEIGHT_TO_SHOW_VALUE:
        value_str = f"{height:.{VALUE_DECIMAL_PLACES}f}"
        # Position value text with its bottom edge starting above the bar
        value_y_pos_bottom = y_position_for_next_external_text_bottom + VALUE_PADDING_ABOVE_BAR

        ax.text(bar_center_x, value_y_pos_bottom, value_str,
                ha='center', va='bottom', color='black',
                fontsize=VALUE_FONT_SIZE, rotation=0)
        
        # Update the y-level for the next potential text item (entity name)
        y_position_for_next_external_text_bottom = value_y_pos_bottom + ESTIMATED_VALUE_TEXT_HEIGHT_DATA_UNITS
        value_text_was_plotted = True
    
    max_y_coord_overall = max(max_y_coord_overall, y_position_for_next_external_text_bottom)


    # --- 2. Handle Entity Name ---
    # Specific modification for "Gemini-2.5 Pro Preview"
    if original_entity_name == "Gemini-2.5 Pro Preview":
        entity_name_to_display = "Gemini-2.5 Pro\nPreview"

    # Determine font size for entity name based on height
    if height < 0.2:
        entity_fontsize = 8
    elif height <= 0.5:
        entity_fontsize = 10
    else: # height > 0.5
        entity_fontsize = 12

    if height < EXTERNAL_ENTITY_NAME_THRESHOLD: # Entity name is external (horizontal, above value/bar)
        wrapped_entity_name = textwrap.fill(entity_name_to_display, width=WRAP_WIDTH_HORIZONTAL_EXTERNAL)
        num_lines_entity = wrapped_entity_name.count('\n') + 1
        estimated_total_entity_height = num_lines_entity * (ESTIMATED_ENTITY_NAME_LINE_HEIGHT_DATA_UNITS * (entity_fontsize / 8.0)) # Scale estimate by font size

        if value_text_was_plotted:
            entity_y_pos_bottom = y_position_for_next_external_text_bottom + ENTITY_NAME_PADDING_ABOVE_VALUE
        else: # No value text, or value text not shown for this bar
            entity_y_pos_bottom = height + ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR
            if height == 0: # Ensure it's slightly above axis for zero bars
                 entity_y_pos_bottom = max(ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR, 0.005)


        ax.text(bar_center_x, entity_y_pos_bottom, wrapped_entity_name,
                ha='center', va='bottom', color='black',
                fontsize=entity_fontsize, rotation=0)
        max_y_coord_overall = max(max_y_coord_overall, entity_y_pos_bottom + estimated_total_entity_height)

    else: # Entity name is internal (vertical)
        wrapped_entity_name = textwrap.fill(entity_name_to_display, width=WRAP_WIDTH_VERTICAL_INTERNAL)
        entity_y_pos_center = height / 2
        ax.text(bar_center_x, entity_y_pos_center, wrapped_entity_name,
                ha='center', va='center', color='white',
                fontsize=entity_fontsize, rotation=90,
                bbox=dict(facecolor='none', edgecolor='none', pad=0))
        # Internal text does not affect max_y_coord_overall beyond the bar height + value text

# Styling
ax.set_ylim(0, max(1.0, max_y_coord_overall + 0.05)) # Add a little padding above the highest text
ax.set_xticks([])
ax.set_title("Vampire Points per game", fontsize=18, pad=20)
ax.set_ylabel("Points (Max = 1)", fontsize=14)

plt.tight_layout()
plt.show()
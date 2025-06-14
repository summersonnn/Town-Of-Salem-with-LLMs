import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import textwrap # For wrapping long labels

# Entity names (player names - preserved)
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

# New scores for "Vampires Win Ratio" (updated values)
survival_rate_strings = [
    "41.70%", "37.50%", "50%", "25%", "45.50%", "11.10%", "28.60%", "35.30%",
    "35.70%", "55.60%", "27.30%", "36.40%", "27.80%", "22.20%", "38.10%", "30%"
]
# Convert percentage strings to numerical values
scores = [float(s.replace('%', '')) for s in survival_rate_strings]

# Define number of bars
n = len(entities)
x = np.arange(n)
colors = plt.cm.tab20.colors[:n] # Same colors

# --- Configuration for dynamic labeling (ADAPTED FOR 0-100 SCALE - same as previous chart) ---
EXTERNAL_ENTITY_NAME_THRESHOLD = 8.0 # If bar height is less than this, name goes outside
WRAP_WIDTH_HORIZONTAL_EXTERNAL = 15 # For names outside the bar (horizontal)
WRAP_WIDTH_VERTICAL_INTERNAL = 25   # For names inside the bar (vertical)
SHOW_VALUES_ABOVE_BAR = True
MIN_HEIGHT_TO_SHOW_VALUE = 0.0 # Show value even for 0 height bars (will be above bar)
VALUE_PADDING_ABOVE_BAR = 1.0
VALUE_FONT_SIZE = 7
VALUE_DECIMAL_PLACES = 1 # Display one decimal place for the percentage value
ESTIMATED_VALUE_TEXT_HEIGHT_DATA_UNITS = 2.5 # Estimated height of the value text in data units
ENTITY_NAME_PADDING_ABOVE_VALUE = 0.5 # Padding between value text and entity name (if both external)
ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR = 1.0 # Padding between bar and entity name (if value not shown or internal)
ESTIMATED_ENTITY_NAME_LINE_HEIGHT_DATA_UNITS = 2.5 # Estimated height of one line of entity name text
# --- End Configuration ---

# === MODIFIED LINE FOR FULL HD (1920x1080) ===
# We set figsize to (19.2, 10.8) which at a standard 100 DPI gives 1920x1080 pixels.
fig, ax = plt.subplots(figsize=(19.2, 10.8))
# ===============================================

bars = ax.bar(x, scores, color=colors)

max_y_coord_overall = max(scores) if scores else 100.0 # Initialize with max score or 100

for i, bar in enumerate(bars):
    height = bar.get_height()
    original_entity_name = entities[i]
    entity_name_to_display = original_entity_name
    bar_center_x = bar.get_x() + bar.get_width() / 2

    y_position_for_next_external_text_bottom = height # Start from top of the bar
    value_text_was_plotted = False

    # Plot value above the bar
    if SHOW_VALUES_ABOVE_BAR and height >= MIN_HEIGHT_TO_SHOW_VALUE:
        value_str = f"{height:.{VALUE_DECIMAL_PLACES}f}%"
        value_y_pos_bottom = y_position_for_next_external_text_bottom + VALUE_PADDING_ABOVE_BAR
        ax.text(bar_center_x, value_y_pos_bottom, value_str,
                ha='center', va='bottom', color='black',
                fontsize=VALUE_FONT_SIZE, rotation=0)
        y_position_for_next_external_text_bottom = value_y_pos_bottom + ESTIMATED_VALUE_TEXT_HEIGHT_DATA_UNITS # Update for next text
        value_text_was_plotted = True
    max_y_coord_overall = max(max_y_coord_overall, y_position_for_next_external_text_bottom)


    # Determine entity name font size based on bar height
    if height < 20: # Small bars
        entity_fontsize = 8
    elif height <= 50: # Medium bars
        entity_fontsize = 10
    else: # Tall bars
        entity_fontsize = 12

    # Plot entity name (either outside or inside the bar)
    if height < EXTERNAL_ENTITY_NAME_THRESHOLD: # Place name outside (above)
        wrapped_entity_name = textwrap.fill(entity_name_to_display, width=WRAP_WIDTH_HORIZONTAL_EXTERNAL)
        num_lines_entity = wrapped_entity_name.count('\n') + 1
        # Estimate total height of the wrapped entity name text
        estimated_total_entity_height = num_lines_entity * (ESTIMATED_ENTITY_NAME_LINE_HEIGHT_DATA_UNITS * (entity_fontsize / 8.0)) # Scale by fontsize ratio

        if value_text_was_plotted:
            entity_y_pos_bottom = y_position_for_next_external_text_bottom + ENTITY_NAME_PADDING_ABOVE_VALUE
        else: # Value was not plotted, place name directly above bar
            entity_y_pos_bottom = height + ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR
            if height == 0: # Special case for zero height bars to ensure visibility
                 entity_y_pos_bottom = max(ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR, 0.5) # Ensure it's at least a bit above x-axis

        ax.text(bar_center_x, entity_y_pos_bottom, wrapped_entity_name,
                ha='center', va='bottom', color='black',
                fontsize=entity_fontsize, rotation=0)
        max_y_coord_overall = max(max_y_coord_overall, entity_y_pos_bottom + estimated_total_entity_height)
    else: # Place name inside the bar (vertically)
        wrapped_entity_name = textwrap.fill(entity_name_to_display, width=WRAP_WIDTH_VERTICAL_INTERNAL)
        entity_y_pos_center = height / 2 # Center vertically within the bar
        ax.text(bar_center_x, entity_y_pos_center, wrapped_entity_name,
                ha='center', va='center', color='white', # White text for contrast
                fontsize=entity_fontsize, rotation=90, # Rotate for vertical display
                bbox=dict(facecolor='none', edgecolor='none', pad=0)) # No visible bounding box

# Styling
ax.set_ylim(0, max(100.0, max_y_coord_overall + 5.0)) # Ensure y-limit accommodates all text, at least 0-100
ax.set_xticks([]) # Remove x-axis ticks (player names are on/above bars)
ax.set_title("Vampires Win Ratio", fontsize=18, pad=20) # New title
ax.set_ylabel("Win Ratio (%)", fontsize=14) # Updated Y-axis label

plt.tight_layout() # Adjust plot to ensure everything fits without overlapping

# To save the figure as a 1920x1080 PNG file, uncomment the line below
# plt.savefig('vampires_win_ratio_persons_full_hd.png', dpi=100)

plt.show()
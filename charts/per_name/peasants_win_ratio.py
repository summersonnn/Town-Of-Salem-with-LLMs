import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import textwrap # For wrapping long labels

# Entity names (updated to player names)
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

# New scores for "Peasant Win Ratio"
survival_rate_strings = [
    "38.2%", "51.1%", "46.7%", "41.4%", "41.4%", "42.4%", "45.8%", "44.0%",
    "51.6%", "37.5%", "52.6%", "28.0%", "39.3%", "51.4%", "57.1%", "48.5%"
]
# Convert percentage strings to numerical values
scores = [float(s.replace('%', '')) for s in survival_rate_strings]

# Define number of bars
n = len(entities)
x = np.arange(n)
colors = plt.cm.tab20.colors[:n] # Same colors

# --- Configuration for dynamic labeling (ADAPTED FOR 0-100 SCALE - same as previous chart) ---
EXTERNAL_ENTITY_NAME_THRESHOLD = 8.0
WRAP_WIDTH_HORIZONTAL_EXTERNAL = 15
WRAP_WIDTH_VERTICAL_INTERNAL = 25
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

max_y_coord_overall = max(scores) if scores else 100.0

for i, bar in enumerate(bars):
    height = bar.get_height()
    original_entity_name = entities[i]
    entity_name_to_display = original_entity_name
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

    # Removed specific handling for "Gemini-2.5 Pro Preview" as it's no longer in entities
    # if original_entity_name == "Gemini-2.5 Pro Preview":
    #     entity_name_to_display = "Gemini-2.5 Pro\nPreview"

    if height < 20:
        entity_fontsize = 8
    elif height <= 50:
        entity_fontsize = 10
    else:
        entity_fontsize = 12

    if height < EXTERNAL_ENTITY_NAME_THRESHOLD:
        wrapped_entity_name = textwrap.fill(entity_name_to_display, width=WRAP_WIDTH_HORIZONTAL_EXTERNAL)
        num_lines_entity = wrapped_entity_name.count('\n') + 1
        estimated_total_entity_height = num_lines_entity * (ESTIMATED_ENTITY_NAME_LINE_HEIGHT_DATA_UNITS * (entity_fontsize / 8.0))

        if value_text_was_plotted:
            entity_y_pos_bottom = y_position_for_next_external_text_bottom + ENTITY_NAME_PADDING_ABOVE_VALUE
        else:
            entity_y_pos_bottom = height + ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR
            if height == 0:
                 entity_y_pos_bottom = max(ENTITY_NAME_PADDING_DIRECTLY_ABOVE_BAR, 0.5)

        ax.text(bar_center_x, entity_y_pos_bottom, wrapped_entity_name,
                ha='center', va='bottom', color='black',
                fontsize=entity_fontsize, rotation=0)
        max_y_coord_overall = max(max_y_coord_overall, entity_y_pos_bottom + estimated_total_entity_height)
    else:
        wrapped_entity_name = textwrap.fill(entity_name_to_display, width=WRAP_WIDTH_VERTICAL_INTERNAL)
        entity_y_pos_center = height / 2
        ax.text(bar_center_x, entity_y_pos_center, wrapped_entity_name,
                ha='center', va='center', color='white',
                fontsize=entity_fontsize, rotation=90,
                bbox=dict(facecolor='none', edgecolor='none', pad=0))

# Styling
ax.set_ylim(0, max(100.0, max_y_coord_overall + 5.0))
ax.set_xticks([])
ax.set_title("Peasant Win Ratio", fontsize=18, pad=20) # New title
ax.set_ylabel("Win Ratio (%)", fontsize=14) # Updated Y-axis label

plt.tight_layout()
plt.show()
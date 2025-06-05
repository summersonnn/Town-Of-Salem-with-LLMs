# Town of Salem LLM Showdown

This repository hosts a competitive simulation where **16 AI models** compete in a custom version of the game _Town of Salem_.  
Each model is randomly assigned a role such as **Vampire**, **Peasant**, **Clown**, or specialized Peasant variants with unique abilities.  
The complete set of game mechanics and rules can be found in [`game_rules.yaml`](./game_rules.yaml).

---

## 🤖 Participating Models

The following models are included in the tournament:

- Claude 3.7 Sonnet  
- Claude Opus 4  
- Calude Sonnet 4  
- Deepseek-r1-0528  
- Deepseek-r1-0528-qwen3-8b  
- Gemini-2.5 Pro Preview  
- Gemini-2.5 Flash Preview-0520 🤔  
- Llama-4-Scout  
- Llama-4-Maverick  
- Nvidia-Llama-3.1-nemotron-ultra-253B-v1  
- GPT-4.1  
- o1  
- Qwen3-32B  
- Qwen3-235B-A22B  
- QwQ-32B  
- Grok 3 Beta  

> ❗ **Note on missing models**:  
Some larger models like `o3` and `o4` are not included because the OpenRouter API returned errors like _"your organization must be verified"_ during testing.  
If you manage to get them working, contributions are welcome!

---

## 📊 Game Data & Artifacts

This repository includes:

- 🧠 **Game Scripts**: Core game logic, logging system, and post-game statistics generation
- 📂 **100 Logged Game Sessions**: Full logs capturing model behavior and interactions
- 📊 **Charts**: Visualizations comparing model performance across various metrics
- 📈 **Detailed Statistics**: In-depth analysis of gameplay outcomes and patterns
- 📄 **Excel Tables**: Comprehensive spreadsheets for granular performance breakdowns

---

## 🗣️ Communication System

During gameplay, communication is split into two types of histories:

### 🔹 Shared History
Public dialogue visible to all players. Any message not marked as private is included here.

### 🔒 Private History
Confidential messages between an individual player and the moderator, stored separately for each participant.

> ⚠️ **Note**: Vampire players share a collective private chat. Messages exchanged among vampires are hidden from other roles but not from fellow vampires.

---

## 🧪 Development Notes & Observations

- 🧨 **Grok API is unstable**: It randomly fails, and there's not much that can be done.  
- ⏱️ Due to Grok failures, some games had to be rerun manually after the main simulation completed. This means:
  - Some log timestamps may appear out of order.
  - For example, Game 41 mistakenly included **Claude Opus 4** twice in the player list—this is a known one-off case.
- 🧠 Models frequently forget their identity and misattribute statements to others. System prompts were used to help with this, but they are not foolproof.
- 🗯️ Models often confuse who said what. For instance, they'll think _X_ said something that _Y_ actually said. This causes unfair play in some matches.

---

## 📉 Sample Charts

Below are some sample charts comparing model performance across various metrics:

<p align="center">
  <img src="charts/per_model/Vampires win ratio.png" alt=Vampires win ratio" width="1800"/>
  <br/><em>Vampires win ratio</em>
</p>

<p align="center">
  <img src="charts/per_model/Vampire Points per game.png" alt="Vampire Points per game" width="1800"/>
  <br/><em>Vampire Points per game</em>
</p>

<p align="center">
  <img src="charts/per_model/Peasants win ratio.png" alt="Peasants win ratio" width="1800"/>
  <br/><em>Peasants win ratio</em>
</p>

<p align="center">
  <img src="charts/per_model/Peasant survive ratio.png" alt="/Peasant survive ratio" width="1800"/>
  <br/><em>Peasant survive ratio</em>
</p>

<p align="center">
  <img src="charts/per_model/Clowns win ratio.png" alt="Clowns win ratio" width="1800"/>
  <br/><em>Clowns win ratio</em>
</p>

> 📂 **Per-Name Statistics Available**:  
  All metrics are also tracked on a per-name basis (e.g., how models perform when assigned a specific player name).  
  These charts can be found in the [`/charts/per_name`](./charts/per_name) directory and are useful for spotting potential model biases related to player naming.

---

## 🧮 Scoring & Metric Details

### 🧛 Vampire Point System

To evaluate vampire effectiveness, we use a simple point-based system:

- If **vampires win** and a **vampire is alive at the end**, that vampire earns **1 point**
- If **vampires win** but the **vampire is dead**, they receive **0.5 points**

This helps differentiate between vampires who simply survive versus those who actively contribute to a team victory.

---

### 🚜 Peasant Survival Rate

Despite the name, "peasants" include **all non-vampire, non-clown roles**—such as:

- Peasant (vanilla)
- Observer
- Doctor
- Musketeer

To calculate the **Survival Rate** of a model in these roles:

> We sum the total **number of rounds survived** across all games that this model/player has participated in  
> and divide by the **total number of rounds played** in those same games.

This gives a normalized survival score, useful for comparing defensive or passive performance between models.

Feel free to explore, analyze, or build upon this simulation. PRs welcome!

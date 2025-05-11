import os
from typing import List, Dict, Optional # Added Optional
from openai import OpenAI
from dotenv import load_dotenv

def chat_completion(
    chat_history: List[Dict[str, str]],
    temperature: float = 0.9,
    player_name: str = "Player",
    player_model_map: Optional[Dict[str, str]] = None, # New parameter
) -> str:
    """
    Unified chat completion function using OpenAI-compatible API.

    Args:
        chat_history: A list of message dictionaries representing the conversation history.
        temperature: The sampling temperature for the completion. Defaults to 0.9.
        player_name: The name of the player for whom the completion is generated.
                     Used to look up a specific model in `player_model_map`. Defaults to "Player".
        player_model_map: An optional dictionary mapping player names to specific
                          model names (e.g., {"John": "meta-llama/llama-3.3-70b-instruct:nitro"}).
                          If a mapping exists for the given `player_name`, that model
                          will be used. Otherwise, the model specified by the
                          `MODEL_NAME` environment variable is used. Defaults to None.

    Returns:
        The content of the generated message.
        
    Raises:
        Any exception from the OpenAI client during API call.
        AttributeError: If LLM_BASE_URL or LLM_API_KEY env vars are not set (from .rstrip('/')).
    """
    base_url = os.getenv("LLM_BASE_URL").rstrip('/')
    api_key = os.getenv("LLM_API_KEY").rstrip('/')
    
    # Determine the model to use
    model_to_use: Optional[str]
    if player_model_map and player_name in player_model_map:
        # If a map is provided and the player has a specific model, use it.
        # This takes precedence over the environment variable.
        model_to_use = player_model_map[player_name]
    else:
        raise ValueError

    # Create OpenAI client
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # Prepare request parameters
    request_params = {
        "model": model_to_use,
        "messages": chat_history.copy(),
        "temperature": temperature,
    }

    try:
        response = client.chat.completions.create(**request_params)
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error during chat completion:")
        print(f"Full base URL: {base_url}")
        print(f"Model used: {model_to_use}")
        # print(f"Request params: {request_params}") # Be cautious printing full request if it contains sensitive data
        # For debugging, printing only model and messages structure can be safer:
        print(f"Request params (model and message count): model={request_params.get('model')}, num_messages={len(request_params.get('messages', []))}")
        raise

# --- Example Usage (concise) ---
def run_example():
    load_dotenv()  # Load variables from .env file

    player_specific_models = {
        "John": "meta-llama/llama-3.3-70b-instruct:nitro",
        "Sarah": "mistralai/mistral-medium-3"
    }
    sample_history = [{"role": "user", "content": "Hi there, who are you?"}]
    
    chosen_player = "Max" # Or "Sarah"

    try:
        print(f"Requesting completion for player: {chosen_player}...")
        response_content = chat_completion(
            chat_history=sample_history,
            player_name=chosen_player,
            player_model_map=player_specific_models
        )
        print(f"\nResponse for {chosen_player}:\n{response_content}")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    run_example()
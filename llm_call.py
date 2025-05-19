import os
import time # For retry delay
from typing import List, Dict, Optional
from openai import OpenAI # type: ignore
from dotenv import load_dotenv

# Define retry constants
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2 # Simple fixed delay

def chat_completion(
    chat_history: List[Dict[str, str]],
    temperature: float = 0.2,
    player_name: str = "Player",
    player_model_map: Optional[Dict[str, str]] = None,
) -> str:
    """
    Unified chat completion function using OpenAI-compatible API.
    Retries the API call in case of transient errors.

    Args:
        chat_history: A list of message dictionaries representing the conversation history.
        temperature: The sampling temperature for the completion. Defaults to 0.2.
        player_name: The name of the player for whom the completion is generated.
                     Used to look up a specific model in `player_model_map`. Defaults to "Player".
        player_model_map: An optional dictionary mapping player names to specific
                          model names (e.g., {"John": "meta-llama/llama-3.3-70b-instruct:nitro"}).
                          If a mapping exists for the given `player_name`, that model
                          will be used.

    Returns:
        The content of the generated message.
        
    Raises:
        AttributeError: If LLM_BASE_URL or LLM_API_KEY env vars are not set.
        ValueError: If a model cannot be determined for the player based on `player_model_map`
                    (e.g., map is None, or player not in map, and no other fallback is configured).
        Any exception from the OpenAI client during API call, after all retries have failed.
    """
    base_url_env = os.getenv("LLM_BASE_URL")
    api_key_env = os.getenv("LLM_API_KEY")

    if base_url_env is None:
        raise AttributeError("LLM_BASE_URL environment variable not set.")
    if api_key_env is None:
        raise AttributeError("LLM_API_KEY environment variable not set.")

    base_url = base_url_env.rstrip('/')
    api_key = api_key_env.rstrip('/')
    
    # Determine the model to use
    model_to_use: Optional[str] = None 
    if player_model_map and player_name in player_model_map:
        model_to_use = player_model_map[player_name]
    else:
        error_message: str
        if player_model_map is None:
            error_message = f"player_model_map is None, and no model specified for player '{player_name}'."
        elif player_name not in player_model_map: # player_model_map is not None here
             error_message = f"Player '{player_name}' not found as a key in the provided player_model_map."
        else: # Should not happen given the outer if condition, but as a safeguard
            error_message = f"Could not determine model for player '{player_name}' with the provided player_model_map."
        
        raise ValueError(error_message + " No fallback model resolution implemented for this case.")

    # Create OpenAI client
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    request_params = {
        "model": model_to_use,
        "messages": chat_history.copy(), # Use a copy
        "temperature": temperature,
    }

    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(**request_params)
            return response.choices[0].message.content
        except Exception as e:
            last_exception = e
            print(f"Error during chat completion on attempt {attempt + 1}/{MAX_RETRIES}: {type(e).__name__}: {str(e)}")
            
            if attempt < MAX_RETRIES - 1:
                print(f"Waiting {RETRY_DELAY_SECONDS} seconds before next retry...")
                # Remove the :nitro suffix if present in the model name. Also change the request params
                # to use the modified model name.
                if model_to_use.endswith(":nitro"):
                    model_to_use = model_to_use[:-len(":nitro")]
                    request_params["model"] = model_to_use
                print(f"Will be tried with the model name without the :nitro suffix. So: '{model_to_use}'")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                # This is the last attempt
                print(f"All {MAX_RETRIES} retry attempts failed for model {model_to_use}.")
                print(f"Final error details:")
                print(f"  Full base URL: {base_url}")
                print(f"  Model used: {model_to_use}")
                print(f"  Request params (model and message count): model={request_params.get('model')}, num_messages={len(request_params.get('messages', []))}")
                print(f"  Last exception: {type(last_exception).__name__}: {str(last_exception)}")
                raise # Re-raise the last caught exception

    # This part of the code should not be reached if MAX_RETRIES > 0,
    # as the loop will either return on success or raise on the final failed attempt.
    if last_exception:
        raise last_exception # Should be already raised from the loop
    else:
        # This case is logically very unlikely if MAX_RETRIES > 0.
        raise RuntimeError("Chat completion failed unexpectedly without a caught exception after retry loop.")


if __name__ == "__main__":
    load_dotenv()
        # 1. Define the player name
    player_to_use = "Alice"

    # 2. Define the player_model_map
    model_map = {
        "Max": "google/gemini-2.5-pro-preview:nitro",
        "Sam": "anthropic/claude-3.7-sonnet", # Another player, different model
        "Player": "openai/gpt-4.1", # Default player if name is "Player"
        "Alice": "openai/o4-mini-high"
    }

    # 3. Create a sample chat history
    sample_history = [
        {"role": "system", "content": "You are an assistant."},
        {"role": "user", "content": "What is the meaning of life?"},
    ]

    # 4. Call the function
    print(f"Attempting chat completion for player: {player_to_use}")
    response_content = chat_completion(
        chat_history=sample_history,
        player_name=player_to_use,
        player_model_map=model_map,
        temperature=0.7
    )
    print(f"\nModel ({model_map[player_to_use]}) response for {player_to_use}:")
    print(response_content)
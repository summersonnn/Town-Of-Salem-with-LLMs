import os
import time
from typing import List, Dict, Optional
from openai import OpenAI
import instructor
from pydantic import BaseModel, create_model
from typing import Literal
from dotenv import load_dotenv
import random

# Define retry constants
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2 # Simple fixed delay

# Constrain vote to predefined options
class Vote(BaseModel):
    reasoning: str
    vote: Literal["Alice", "Bob", "Charlie", "Cem"]

def chat_completion(
    chat_history: List[Dict[str, str]],
    temperature: float = 0.2,
    player_name: str = "Player",
    player_model_map: Optional[Dict[str, str]] = None,
    is_a_decision: bool = False,
    choices: List[str] = None,
    round: Optional[int] = 1,
) -> str | Vote:

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
    
    # For qwen models, choose the fastest provider!
    if "qwen" in model_to_use:
        model_to_use = model_to_use + ":nitro"
    
    # Initialize request_params with common parameters
    request_params = {
        "model": model_to_use,
        "messages": chat_history.copy(), # Use a copy
        "temperature": temperature,
        #"extra_body": {"max_tokens": 2048},  # Default max tokens
        "max_tokens": 2048*round,  # Default max tokens
    }
    
    # Enable extended thinking for Anthropic models
    if "anthropic" in model_to_use:
        request_params["extra_body"] = {}
        request_params["extra_body"]["thinking"] = {"type": "enabled", "budget_tokens": 2048}


    if is_a_decision:
        # Enable instructor patches for OpenAI client
        client = instructor.from_openai(client, mode=instructor.Mode.JSON)
        
        if not choices:
            raise ValueError("choices must be provided when is_a_decision is True")

        DynamicVote = create_model(
            "DynamicVote",
            reasoning=(str, ...),
            vote=(Literal[tuple(choices)], ...)  # Dynamically constrain vote
        )
        request_params["response_model"] = DynamicVote
        
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(**request_params)
            return response.choices[0].message.content if not is_a_decision else response
        except Exception as e:
            last_exception = e
            print(f"Error during chat completion on attempt {attempt + 1}/{MAX_RETRIES}: {type(e).__name__}: {str(e)}")

            # If grok model fails, switch to a smaller model
            # Check if the failed model is x-ai/grok-3-beta and switch to x-ai/grok-3-mini-beta for retries
            current_model_in_params = request_params.get("model")
            if current_model_in_params == "x-ai/grok-3-beta":
                new_model_for_retry = "x-ai/grok-3-mini-beta"
                print(f"Switching model from {current_model_in_params} to {new_model_for_retry} for subsequent retries.")
                request_params["model"] = new_model_for_retry
                # Update model_to_use as well, so if all retries fail, the final log message reflects the last model tried.
                model_to_use = new_model_for_retry 
 
            
            if attempt < MAX_RETRIES - 1:
                print(f"Waiting {RETRY_DELAY_SECONDS} seconds before next retry...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                # This is the last attempt
                print(f"\n\nAll {MAX_RETRIES} retry attempts failed for model {model_to_use}.")
                print(f"Final error details:")
                print(f"  Full base URL: {base_url}")
                print(f"  Model used: {model_to_use}")
                print(f"  Request params (model and message count): model={request_params.get('model')}, num_messages={len(request_params.get('messages', []))}")
                print(f"  Last exception: {type(last_exception).__name__}: {str(last_exception)}\n\n")
                
                '''
                # Return a DyanmicVote with a random choice if is_a_decision
                if is_a_decision:
                    random_choice = random.choice(choices)
                    return DynamicVote(
                        reasoning=f"Randomly selected {random_choice} after {MAX_RETRIES} failed attempts.",
                        vote=random_choice
                    )
                # If not a decision, return an empty string
                else:
                    return ""
                '''
                raise Exception
                    

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
    player_to_use = "Max"

    # 2. Define the player_model_map
    model_map = {
        "Max": "openai/gpt-4.1",
    }

    # 3. Create a sample chat history
    sample_history = [
        {"role": "system", "content": "You are an assistant."},
        {"role": "user", "content": "Alice is a liar. Bob is a pervert. Charlie is foul mouthed. Cem is an alcoholic. Who are you choosing to vote out and why?"},
    ]

    # 4. Call the function
    print(f"Attempting chat completion for player: {player_to_use}")
    response_content = chat_completion(
        chat_history=sample_history,
        player_name=player_to_use,
        player_model_map=model_map,
        temperature=0.2,
        is_a_decision=True,
        choices=["Alice","Bob", "Charlie", "Cem"]
    )
    print(f"\nModel ({model_map[player_to_use]}) response for {player_to_use}:")
    print(response_content)
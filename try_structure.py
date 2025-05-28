import os
from openai import OpenAI
import instructor
from pydantic import BaseModel
from typing import Literal

# Initialize with API key
# client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Create OpenAI client
client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1",
)


models = [
        "openai/gpt-4.1",
        "openai/o4-mini-high",
        "google/gemini-2.5-pro-preview",
        "google/gemini-2.5-flash-preview-05-20:thinking",
        "qwen/qwen3-32b",
        # "qwen/qwq-32b",    removed due to not supporting instructor
        "qwen/qwen3-235b-a22b",
        "anthropic/claude-3.7-sonnet",
        "anthropic/claude-sonnet-4",
        "anthropic/claude-opus-4",
        "x-ai/grok-3-beta",
        "deepseek/deepseek-r1",
        "deepseek/deepseek-chat-v3-0324",
        "meta-llama/llama-4-maverick",
        "meta-llama/llama-4-scout"
]
    
# Enable instructor patches for OpenAI client
client = instructor.from_openai(client)

# Constrain vote to predefined options
class User(BaseModel):
    reasoning: str
    vote: Literal["Alice", "Bob", "Charlie", "Cem"]

# Create structured output
user = client.chat.completions.create(
    model=models[5],
    messages=[
        {"role": "user", "content": "Alice is thief. Bob is a pervert. Charlie is foul mouthed. Cem is an alcoholic. Who are you choosing to vote out and why?"},
    ],
    response_model=User,
)

print(user)
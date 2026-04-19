import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])


def chat(messages: list, tools: list = None, model: str = "llama-3.3-70b-versatile"):
    """
    Send messages to Groq and return the assistant message object.
    Pass tools to enable tool use. Returns a ChatCompletionMessage.
    """
    client = _client
    kwargs = {
        "model": model,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message

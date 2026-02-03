import openai
import os

from app.find_trails import find_trails

# 1. Configuration
OPENAI_API_KEY = os.getenv("OPEN_AI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)


def generate_description(generated_trails:str ):
    # To replicate ConversationalChain, we keep a history of the chat
    messages = [
        {"role": "system", "content": "You provide trails description based on GEOjson files."}
    ]
    # Append user message to history
    messages.append({"role": "user", "content": generated_trails})

    try:
        # 2. Model Interaction (Equivalent to your model builder)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8
        )

        # Extract the text
        answer = response.choices[0].message.content
        print(f"\n{answer}\n")

        # Append assistant response to history to maintain the "Chain"
        messages.append({"role": "assistant", "content": answer})

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    trails = find_trails(46.586035980892554, 11.296098698279467, 1, 10, 5)
    generate_description(trails)
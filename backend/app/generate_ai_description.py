import openai
import os
import json
from app.find_trails import *
from loguru import logger

# 1. Configuration
OPENAI_API_KEY = os.getenv("OPEN_AI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)


def generate_description(simplified_trails_str: str):
    messages = [
        {"role": "system", "content": """
You will be provided with a JSON object containing a list of trails. Each trail object has a path_id, a start point [lon, lat], and an end point [lon, lat].
Your task is to provide a name and a meaningful description for each trail based on its start and end points.
Look for nearby points of interest, villages, or natural landmarks.

For each trail, provide a JSON object with the following keys:
- "path_id": the ID of the trail.
- "name": a name for the trail.
- "description": a meaningful description of the trail.

The output should be a single JSON object containing a list of these trail objects under the key "trails".
        """}
    ]
    messages.append({"role": "user", "content": simplified_trails_str})

    try:
        logger.info("Contacting AI API")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
            response_format={"type": "json_object"}
        )
        answer = response.choices[0].message.content
        return answer

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def generate_and_add_description(trails_geojson_str: str):
    try:
        trails_geojson = json.loads(trails_geojson_str)
    except json.JSONDecodeError:
        logger.error("Invalid GeoJSON string provided.")
        return None

    simplified_trails = []
    for feature in trails_geojson.get("features", []):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if "path_id" in properties and "coordinates" in geometry:
            simplified_trails.append({
                "path_id": properties["path_id"],
                "start": geometry["coordinates"][0],
                "end": geometry["coordinates"][-1]
            })

    if not simplified_trails:
        logger.warning("No trails found to generate descriptions for.")
        return trails_geojson_str

    simplified_trails_str = json.dumps({"trails": simplified_trails}, indent=2)

    descriptions_json_str = generate_description(simplified_trails_str)
    if not descriptions_json_str:
        return None

    try:
        descriptions_data = json.loads(descriptions_json_str)
    except json.JSONDecodeError:
        logger.error("Invalid JSON response from AI.")
        return None

    desc_map = {
        trail['path_id']: {
            'description': trail['description'],
            'name': trail['name']
        }
        for trail in descriptions_data.get('trails', [])
    }

    for feature in trails_geojson.get("features", []):
        path_id = feature.get("properties", {}).get("path_id")
        if path_id in desc_map:
            feature["properties"]["description"] = desc_map[path_id]['description']
            feature["properties"]["name"] = desc_map[path_id]['name']

    return json.dumps(trails_geojson, indent=2)


if __name__ == "__main__":
    trails = find_trails(46.586035980892554, 11.296098698279467, 1, 13, 5)
    if trails:
        trails_with_descriptions = generate_and_add_description(trails)
        print(trails_with_descriptions)
        logger.info("Successfully generated trails with descriptions")

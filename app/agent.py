# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
from google import genai
from google.cloud import firestore, storage

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from .a2ui_utils import a2ui_callback

# Hardcoded Project ID string (required so Agent Platform does not use project number)
PROJECT_ID = "qwiklabs-gcp-01-141f75f249db"


def _get_db():
    if os.path.exists("/tmp/sa-key.json"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/sa-key.json"
    return firestore.Client(project=PROJECT_ID, database="(default)")


def search_monsters(query: str = "") -> str:
    """Searches the Firestore monsters database for matching monsters or returns all if query is empty.

    Args:
        query: Optional name or partial name of the monster to search for.

    Returns:
        JSON string containing the matching monsters and their stats (CR, Type, HP, AC, Alignment, Description).
    """
    try:
        db = _get_db()
        docs = db.collection("monsters").stream()
        results = []
        q_lower = query.lower().strip()

        for doc in docs:
            data = doc.to_dict()
            name = data.get("name", "")
            doc_type = data.get("type", "")
            if not q_lower or q_lower in name.lower() or q_lower in doc_type.lower():
                results.append(data)

        if not results:
            return f"No monsters found matching '{query}'."

        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching monsters in Firestore: {str(e)}"


def search_spells(query: str = "") -> str:
    """Searches the Firestore spells database for matching spells or returns all if query is empty.

    Args:
        query: Optional name or school of the spell to search for.

    Returns:
        JSON string containing the matching spells and their stats (Level, School, Casting Time, Range, Description).
    """
    try:
        db = _get_db()
        docs = db.collection("spells").stream()
        results = []
        q_lower = query.lower().strip()

        for doc in docs:
            data = doc.to_dict()
            name = data.get("name", "")
            school = data.get("school", "")
            if not q_lower or q_lower in name.lower() or q_lower in school.lower():
                results.append(data)

        if not results:
            return f"No spells found matching '{query}'."

        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching spells in Firestore: {str(e)}"


def save_monster(
    name: str,
    cr: str,
    monster_type: str,
    hp: int,
    ac: int,
    alignment: str,
    description: str,
) -> str:
    """Saves or updates a monster entry in the Firestore database.

    Args:
        name: Name of the monster (e.g. 'Red Dragon').
        cr: Challenge Rating (e.g. '1/4', '10').
        monster_type: Creature type (e.g. 'Dragon', 'Humanoid').
        hp: Hit points.
        ac: Armor Class.
        alignment: Creature alignment (e.g. 'Chaotic Evil').
        description: Description of the monster's features and traits.

    Returns:
        Confirmation message.
    """
    try:
        db = _get_db()
        doc_id = name.lower().replace(" ", "_")
        monster_data = {
            "id": doc_id,
            "name": name,
            "cr": cr,
            "type": monster_type,
            "hp": hp,
            "ac": ac,
            "alignment": alignment,
            "description": description,
        }
        db.collection("monsters").document(doc_id).set(monster_data)
        return f"Successfully saved monster '{name}' ({doc_id}) to Firestore."
    except Exception as e:
        return f"Error saving monster to Firestore: {str(e)}"


def save_spell(
    name: str,
    level: int,
    school: str,
    casting_time: str,
    spell_range: str,
    description: str,
) -> str:
    """Saves or updates a spell entry in the Firestore database.

    Args:
        name: Name of the spell (e.g. 'Lightning Bolt').
        level: Spell level (0 for cantrip, 1-9).
        school: School of magic (e.g. 'Evocation', 'Abjuration').
        casting_time: Casting time (e.g. '1 action').
        spell_range: Range (e.g. '150 feet', 'Touch').
        description: Description of the spell effect.

    Returns:
        Confirmation message.
    """
    try:
        db = _get_db()
        doc_id = name.lower().replace(" ", "_")
        spell_data = {
            "id": doc_id,
            "name": name,
            "level": level,
            "school": school,
            "casting_time": casting_time,
            "range": spell_range,
            "description": description,
        }
        db.collection("spells").document(doc_id).set(spell_data)
        return f"Successfully saved spell '{name}' ({doc_id}) to Firestore."
    except Exception as e:
        return f"Error saving spell to Firestore: {str(e)}"


def roll_dice(expression: str) -> str:
    """Rolls tabletop RPG dice based on standard dice notation (e.g. '2d6+3', '1d20+5', '3d8').

    Args:
        expression: Dice expression string such as '2d6+3', '1d20+5', or '3d8'.

    Returns:
        Summary string showing individual die rolls and the calculated total score.
    """
    expr = expression.lower().replace(" ", "")
    match = re.match(r"^(\d*)d(\d+)(?:([+-])(\d+))?$", expr)
    if not match:
        return f"Invalid dice expression '{expression}'. Please use format like '2d6+3', '1d20', or '3d8-1'."

    num_dice = int(match.group(1)) if match.group(1) else 1
    num_sides = int(match.group(2))
    sign = match.group(3)
    modifier = int(match.group(4)) if match.group(4) else 0

    if num_dice > 100 or num_sides > 1000:
        return "Dice roll limit exceeded (max 100 dice, max 1000 sides)."

    rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
    subtotal = sum(rolls)

    if sign == "+":
        total = subtotal + modifier
        mod_str = f" + {modifier}"
    elif sign == "-":
        total = subtotal - modifier
        mod_str = f" - {modifier}"
    else:
        total = subtotal
        mod_str = ""

    return f"Rolled {expression}: {rolls}{mod_str} = {total} total"


def fetch_dnd_srd_spell(spell_name: str) -> str:
    """Fetches official D&D 5e SRD spell details from the free public D&D 5e API (dnd5eapi.co).

    Args:
        spell_name: Name of the spell to look up (e.g. 'fireball', 'fly', 'magic-missile', 'cure-wounds').

    Returns:
        JSON string containing official spell details (level, school, range, components, description).
    """
    api_key = os.environ.get("DND_API_KEY", "")  # Optional API key support if required
    slug = spell_name.lower().strip().replace(" ", "-")
    url = f"https://www.dnd5eapi.co/api/2014/spells/{urllib.parse.quote(slug)}"

    headers = {"User-Agent": "CampaignMasterAgent/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            return json.dumps(
                {
                    "name": data.get("name"),
                    "level": data.get("level"),
                    "school": data.get("school", {}).get("name"),
                    "casting_time": data.get("casting_time"),
                    "range": data.get("range"),
                    "components": data.get("components"),
                    "description": data.get("desc"),
                },
                indent=2,
            )
    except Exception as e:
        return f"Could not find spell '{spell_name}' on public D&D 5e API: {str(e)}"


def geocode_address(address: str) -> str:
    """Converts a street address or location name into geographic coordinates (latitude/longitude) using Google Geocoding API.

    Args:
        address: The address or place name to geocode (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        JSON string containing the name/formatted address, location coordinates (lat, lng), and place_id.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    params = urllib.parse.urlencode({"address": address, "key": api_key})
    url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") != "OK" or not data.get("results"):
                return f"Geocoding failed for '{address}': {data.get('status', 'ZERO_RESULTS')}"

            result = data["results"][0]
            loc = result.get("geometry", {}).get("location", {})
            return json.dumps(
                {
                    "address": result.get("formatted_address"),
                    "location": {"latitude": loc.get("lat"), "longitude": loc.get("lng")},
                    "place_id": result.get("place_id"),
                },
                indent=2,
            )
    except Exception as e:
        return f"Geocoding error for '{address}': {str(e)}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
) -> str:
    """Finds nearby places of a given type around a location using Google Places API (New).

    Args:
        latitude: Latitude coordinate of the search center.
        longitude: Longitude coordinate of the search center.
        place_type: Type of place to search for (e.g. 'restaurant', 'store', 'cafe', 'park', 'lodging').
        radius_meters: Search radius in meters (default: 1000.0).

    Returns:
        JSON string listing matching nearby places with key fields (name, formatted address, location).
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    body = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_meters),
            }
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            places = data.get("places", [])
            results = []
            for p in places:
                results.append(
                    {
                        "name": p.get("displayName", {}).get("text"),
                        "address": p.get("formattedAddress"),
                        "location": p.get("location"),
                    }
                )
            return json.dumps(results, indent=2)
    except Exception as e:
        return f"Places API error: {str(e)}"


async def generate_item_image(
    item_name: str, description: str, tool_context: ToolContext
) -> str:
    """Generates visual artwork for an RPG campaign item, monster, spell, or scene using gemini-3.1-flash-lite-image in the global region.

    Saves the image as an ADK artifact and uploads it to the public Cloud Storage bucket.

    Args:
        item_name: Name of the item, monster, or spell (e.g. 'Vorpal Sword', 'Healing Potion').
        description: Visual description for the image generation prompt.
        tool_context: ADK ToolContext for saving artifacts.

    Returns:
        Confirmation message containing the public HTTPS URL of the uploaded image.
    """
    project_id = "qwiklabs-gcp-01-141f75f249db"
    bucket_name = "campaign-master-assets-141f75f249db"

    client = genai.Client(
        vertexai=True,
        project=project_id,
        location="global",
    )

    prompt = f"Detailed fantasy concept illustration of {item_name}: {description}. D&D RPG artwork style."

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        image_bytes = None
        mime_type = "image/png"
        for part in response.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

        if not image_bytes:
            return f"Failed to generate image for '{item_name}': No image data in model response."

        slug = re.sub(r"[^a-z0-9_]", "", item_name.lower().replace(" ", "_"))
        timestamp = int(time.time())
        filename = f"{slug}_{timestamp}.png"

        # (1) Save artifact for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # (2) Upload image bytes to public Cloud Storage bucket
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        object_path = f"items/{filename}"
        blob = bucket.blob(object_path)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{bucket_name}/{object_path}"
        return f"Successfully generated artwork for '{item_name}'. Public URL: {public_url}"

    except Exception as e:
        return f"Error generating image: {str(e)}"


async def generate_item_video(
    item_name: str, description: str, tool_context: ToolContext
) -> str:
    """Generates a short video for an RPG item, spell, monster, or scene using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Do two things: (1) Save video as an ADK artifact with tool_context.save_artifact, and (2) Upload video bytes to the public Cloud Storage bucket and return its public HTTPS URL.

    Args:
        item_name: Name of the RPG item, monster, spell, or scene (e.g. 'Flame Tongue Sword', 'Fireball Spell').
        description: Visual and cinematic motion description for the video prompt.
        tool_context: ADK ToolContext for saving artifacts.

    Returns:
        Confirmation message containing the public HTTPS URL (https://storage.googleapis.com/<bucket>/<object>) of the uploaded video.
    """
    project_id = "qwiklabs-gcp-01-141f75f249db"
    bucket_name = "campaign-master-assets-141f75f249db"

    client = genai.Client(
        vertexai=True,
        project=project_id,
        location="global",
    )

    prompt = f"Cinematic fantasy RPG short video of {item_name}: {description}. Atmospheric lighting, smooth motion, high detail."

    try:
        res = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_bytes = None
        mime_type = "video/mp4"

        if hasattr(res, "output_video") and res.output_video and getattr(res.output_video, "data", None):
            data = res.output_video.data
            video_bytes = base64.b64decode(data) if isinstance(data, str) else data
        elif hasattr(res, "steps") and res.steps:
            for step in res.steps:
                if getattr(step, "type", "") == "model_output":
                    for item in getattr(step, "content", []) or []:
                        if getattr(item, "type", "") == "video":
                            if getattr(item, "mime_type", None):
                                mime_type = item.mime_type
                            data = getattr(item, "data", None)
                            if data:
                                video_bytes = base64.b64decode(data) if isinstance(data, str) else data
                                break

        if not video_bytes:
            return f"Failed to generate video for '{item_name}': No video data in model interaction response."

        slug = re.sub(r"[^a-z0-9_]", "", item_name.lower().replace(" ", "_"))
        timestamp = int(time.time())
        filename = f"{slug}_{timestamp}.mp4"

        # (1) Save artifact for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # (2) Upload video bytes to public Cloud Storage bucket
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        object_path = f"items/{filename}"
        blob = bucket.blob(object_path)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{bucket_name}/{object_path}"
        return f"Successfully generated video for '{item_name}'. Public URL: {public_url}"

    except Exception as e:
        return f"Error generating video with gemini-omni-flash-preview: {str(e)}"


# Load Agent Engine resource name from deployment_metadata.json if available
agent_engine_resource_name = None
metadata_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deployment_metadata.json"
)
if os.path.exists(metadata_path):
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Campaign Master Agent, an expert RPG and Dungeon Master assistant. "
        "You help players and Dungeon Masters manage campaigns by rolling dice, looking up official D&D 5e SRD rules, "
        "generating fantasy item/monster artwork with generate_item_image, generating short fantasy videos with generate_item_video, geocoding locations, running python code calculations in a sandbox, and managing Firestore. "
        "You remember all user details across sessions using your Memory Bank, with special priority given to remembering all user allergies, dietary restrictions, sensitivities, and personal preferences. "
        "Always check and strictly respect any remembered user allergies in all recommendations, campaign planning, and responses. "
        "When asked to calculate or execute python code, write your Python code inside a ```python ``` code block to execute it in the sandbox."
    ),
    workflow_description="Analyze the request, call tools when appropriate, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        search_monsters,
        search_spells,
        save_monster,
        save_spell,
        roll_dice,
        fetch_dnd_srd_spell,
        geocode_address,
        find_nearby_places,
        generate_item_image,
        generate_item_video,
        PreloadMemoryTool(),
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)

import os
import sys
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-01-141f75f249db"

if os.path.exists("/tmp/sa-key.json"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/sa-key.json"

def seed_database():
    print(f"Connecting to Firestore for project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID, database="(default)")

    # Seed Monsters collection
    monsters_ref = db.collection("monsters")
    monsters_data = [
        {
            "id": "goblin",
            "name": "Goblin",
            "cr": "1/4",
            "type": "Humanoid",
            "hp": 7,
            "ac": 15,
            "alignment": "Neutral Evil",
            "description": "A small, malicious humanoid that lurks in dungeons and caverns."
        },
        {
            "id": "owlbear",
            "name": "Owlbear",
            "cr": "3",
            "type": "Monstrosity",
            "hp": 59,
            "ac": 13,
            "alignment": "Unaligned",
            "description": "A ferocious creature combining the strength of a bear with the head of an owl."
        },
        {
            "id": "young_red_dragon",
            "name": "Young Red Dragon",
            "cr": "10",
            "type": "Dragon",
            "hp": 178,
            "ac": 18,
            "alignment": "Chaotic Evil",
            "description": "A fierce, fire-breathing apex predator with crimson scales and terrifying power."
        },
        {
            "id": "beholder",
            "name": "Beholder",
            "cr": "13",
            "type": "Aberration",
            "hp": 180,
            "ac": 18,
            "alignment": "Lawful Evil",
            "description": "A floating sphere dominated by a central eye and ten writhing eyestalks."
        }
    ]

    for monster in monsters_data:
        doc_id = monster["id"]
        monsters_ref.document(doc_id).set(monster)
        print(f"  [Monsters] Seeded: {monster['name']} ({doc_id})")

    # Seed Spells collection
    spells_ref = db.collection("spells")
    spells_data = [
        {
            "id": "fireball",
            "name": "Fireball",
            "level": 3,
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "150 feet",
            "description": "A bright streak flashes from your pointing finger to a point you choose within range then blossoms into an explosion of flame."
        },
        {
            "id": "cure_wounds",
            "name": "Cure Wounds",
            "level": 1,
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "Touch",
            "description": "A creature you touch regains a number of hit points equal to 1d8 + your spellcasting ability modifier."
        },
        {
            "id": "counterspell",
            "name": "Counterspell",
            "level": 3,
            "school": "Abjuration",
            "casting_time": "1 reaction",
            "range": "60 feet",
            "description": "You attempt to interrupt a creature in the process of casting a spell."
        }
    ]

    for spell in spells_data:
        doc_id = spell["id"]
        spells_ref.document(doc_id).set(spell)
        print(f"  [Spells] Seeded: {spell['name']} ({doc_id})")

    print("✅ Firestore seeding completed successfully!")

if __name__ == "__main__":
    seed_database()

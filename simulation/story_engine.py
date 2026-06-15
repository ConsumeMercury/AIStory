from datetime import datetime

class StoryEngine:
    def __init__(self):
        pass

    def build_story_context(self, player, world, active_npcs,
                            recent_memories, important_memories, last_action):
        npc_summary = [
            {
                "name": npc["name"],
                "location": npc.get("location"),
                "goals": npc.get("goals", []),
                "traits": npc.get("traits", {}),
            }
            for npc in active_npcs
        ]
        return {
            "world": world,
            "player": player,
            "active_npcs": npc_summary,
            "recent_memories": recent_memories,
            "important_memories": important_memories,
            "last_action": last_action,
            "timestamp": str(datetime.now()),
        }

    def create_prompt(self, context):
        return f"""You are a professional fantasy novelist.

WORLD: {context['world']}
PLAYER: {context['player']}
ACTIVE NPCS: {context['active_npcs']}
RECENT MEMORIES: {context['recent_memories']}
IMPORTANT MEMORIES: {context['important_memories']}
PLAYER ACTION: {context['last_action']}

Write the next scene. Rules: player is the protagonist, NPCs act on their goals and remember past events, show dialogue and emotion, write like a published fantasy novel. Do not summarize."""
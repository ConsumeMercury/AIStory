def get_relevant_memories(memories, query, limit=20):
    """
    Rank logged events by relevance to a free-text query.

    Events come from event_logger.log_event(), whose schema uses
    "action"/"type"/"actor"/"location" (there is no "event" key), so we
    build the searchable text from those fields. Importance, if present,
    is used as a base score.
    """
    scored = []
    query_words = set(query.lower().split())

    for memory in memories:
        if not isinstance(memory, dict):
            continue

        text = " ".join(
            str(memory.get(field, ""))
            for field in ("action", "type", "actor", "location")
        ).lower()

        score = memory.get("importance", 0)
        score += sum(1 for word in query_words if word in text) * 20
        scored.append((score, memory))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in scored[:limit]]

def attach_timeline(document_memory, timeline):

    if "layer6" not in document_memory or document_memory["layer6"] is None:
        document_memory["layer6"] = {}

    document_memory["layer6"]["timeline_events"] = timeline

    return document_memory
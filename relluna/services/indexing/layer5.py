def index_layer5(dm: DocumentMemory) -> None:
    index_primary(dm)
    index_time(dm)
    index_space(dm)
    index_semantic(dm)
    index_similarity_candidates(dm)

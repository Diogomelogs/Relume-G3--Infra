def bump_version(dm: DocumentMemory, reason: str) -> DocumentMemory:
    previous = dm.version

    new_version = increment_patch(previous)

    dm.layer0.versiongraph.append(
        VersionGraphEntry(
            version=new_version,
            parent_version=previous,
            created_at=utcnow(),
            reason=reason,
        )
    )

    dm.layer0.processingevents.append(
        ProcessingEvent(
            event="version_bump",
            from_version=previous,
            to_version=new_version,
            timestamp=utcnow(),
            agent="basic_pipeline",
        )
    )

    dm.version = new_version
    return dm

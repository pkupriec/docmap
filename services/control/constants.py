PIPELINE_TYPES = (
    "full_pipeline",
    "crawl_only",
    "extract_only",
    "geocode_only",
    "analytics_only",
    "export_only",
)

TARGET_SCOPES = (
    "all",
    "single_document",
    "document_range",
    "incremental",
)

STAGE_ORDER = {
    "crawl": 1,
    "extract": 2,
    "geocode": 3,
    "analytics": 4,
    "export": 5,
}

STAGES_BY_PIPELINE_TYPE = {
    "full_pipeline": ["crawl", "extract", "geocode", "analytics", "export"],
    "crawl_only": ["crawl"],
    "extract_only": ["extract"],
    "geocode_only": ["geocode"],
    "analytics_only": ["analytics"],
    "export_only": ["export"],
}

ACTIVE_RUN_STATUSES = ("pending", "running", "cancelling")
TERMINAL_RUN_STATUSES = ("cancelled", "failed", "success")

RUN_STATUSES = ACTIVE_RUN_STATUSES + TERMINAL_RUN_STATUSES
STAGE_STATUSES = ("pending", "running", "success", "failed", "skipped")
COMMAND_STATUSES = ("pending", "accepted", "applied", "rejected", "failed")

COMMAND_TYPES = ("start_run", "cancel_run", "retry_run", "retry_stage")


def downstream_stages(stage_name: str) -> list[str]:
    ordered = [name for name, _ in sorted(STAGE_ORDER.items(), key=lambda item: item[1])]
    if stage_name not in STAGE_ORDER:
        raise ValueError(f"Unknown stage: {stage_name}")
    idx = ordered.index(stage_name)
    return ordered[idx:]


def downstream_stages_after(stage_name: str) -> list[str]:
    ordered = [name for name, _ in sorted(STAGE_ORDER.items(), key=lambda item: item[1])]
    if stage_name not in STAGE_ORDER:
        raise ValueError(f"Unknown stage: {stage_name}")
    idx = ordered.index(stage_name)
    return ordered[idx + 1 :]

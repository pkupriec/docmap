from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from playwright.sync_api import BrowserContext, Page, sync_playwright


@dataclass(frozen=True)
class Scenario:
    name: str
    wait_expression: str
    wait_ms: int


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="low_zoom_pan",
        wait_expression="() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug().boundariesStatus === 'ready'",
        wait_ms=700,
    ),
    Scenario(
        name="regional_pan",
        wait_expression="() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug().boundariesStatus === 'ready'",
        wait_ms=700,
    ),
    Scenario(
        name="hover_click_select",
        wait_expression="() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug().explicitBoundaryLocationIds.length >= 1",
        wait_ms=700,
    ),
    Scenario(
        name="search_highlight",
        wait_expression="() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug().explicitBoundaryLocationIds.length >= 1",
        wait_ms=1000,
    ),
)


def _safe_json_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _ratio(before: Any, after: Any) -> float | None:
    left = _safe_json_number(before)
    right = _safe_json_number(after)
    if left is None or right is None or right <= 0:
        return None
    return round(left / right, 3)


def _collect_current_metrics(page: Page, context: BrowserContext, base_url: str) -> dict[str, Any]:
    manifest_response = requests.get(f"{base_url.rstrip('/')}/api/map/baked/manifest", timeout=30)
    if manifest_response.status_code != 200:
        raise RuntimeError(
            f"baked manifest unavailable at {base_url.rstrip('/')}/api/map/baked/manifest "
            f"(status={manifest_response.status_code}); generate analytics baked artifacts before running Phase F"
        )

    cdp = context.new_cdp_session(page)
    cdp.send("Performance.enable")
    state: dict[str, Any] = {
        "scenario": "initial_load",
        "console": {},
        "requests": [],
        "responses_encoded": {},
        "responses_decoded": {},
    }

    locations = requests.get(f"{base_url.rstrip('/')}/api/map/locations", timeout=30).json()
    location_ids = [str(row["location_id"]) for row in locations[:4]]

    def parse_console(msg_text: str) -> None:
        token = "presentation.performance."
        if token not in msg_text or "_ms" not in msg_text:
            return
        parts = msg_text.split()
        if len(parts) != 2:
            return
        name = parts[0].replace(token, "", 1)
        if not name.endswith("_ms"):
            return
        metric_value = _safe_json_number(parts[1])
        if metric_value is not None:
            state["console"][name] = metric_value

    def on_request(req) -> None:
        parsed = urlparse(req.url)
        state["requests"].append(
            {
                "scenario": state["scenario"],
                "url": req.url,
                "path": parsed.path,
                "method": req.method,
            }
        )

    def on_response(resp) -> None:
        key = (state["scenario"], resp.url)
        content_length = resp.headers.get("content-length")
        encoded_size = int(content_length) if content_length and content_length.isdigit() else 0
        state["responses_encoded"][key] = int(state["responses_encoded"].get(key, 0)) + encoded_size
        decoded_size = 0
        try:
            decoded_size = len(resp.body())
        except Exception:
            decoded_size = 0
        state["responses_decoded"][key] = int(state["responses_decoded"].get(key, 0)) + decoded_size

    page.on("console", lambda msg: parse_console(msg.text))
    page.on("request", on_request)
    page.on("response", on_response)

    def get_perf() -> dict[str, float]:
        metrics = cdp.send("Performance.getMetrics")["metrics"]
        values = {metric["name"]: metric["value"] for metric in metrics}
        return {
            "TaskDuration": float(values.get("TaskDuration", 0.0)),
            "ScriptDuration": float(values.get("ScriptDuration", 0.0)),
            "JSHeapUsedSize": float(values.get("JSHeapUsedSize", 0.0)),
            "Nodes": float(values.get("Nodes", 0.0)),
        }

    page.goto(base_url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_function("() => Boolean(window.__DOCMAP_TEST_HOOKS__?.setViewport)", timeout=120000)
    page.wait_for_function(
        "() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug().boundariesStatus === 'ready'",
        timeout=120000,
    )
    page.wait_for_timeout(800)

    initial_requests = [item for item in state["requests"] if item["scenario"] == "initial_load"]
    initial_api_requests = [item for item in initial_requests if item["path"].startswith("/api/")]
    initial_api_paths = [item["path"] for item in initial_api_requests]
    uses_legacy_boundaries = "/api/map/boundaries" in initial_api_paths
    uses_baked_manifest = "/api/map/baked/manifest" in initial_api_paths
    uses_baked_tiles = any(path.startswith("/api/map/baked/tiles/") for path in initial_api_paths)
    if uses_legacy_boundaries or not uses_baked_manifest or not uses_baked_tiles:
        raise RuntimeError(
            "invalid Phase F runtime state: normal view must load baked manifest/tiles and must not call "
            "/api/map/boundaries during initial load"
        )

    initial_bytes_encoded = sum(
        size for (scenario_name, _), size in state["responses_encoded"].items() if scenario_name == "initial_load"
    )
    initial_bytes_decoded = sum(
        size for (scenario_name, _), size in state["responses_decoded"].items() if scenario_name == "initial_load"
    )
    output: dict[str, Any] = {
        "measured_at_utc": datetime.now(tz=UTC).isoformat(),
        "base_url": base_url.rstrip("/"),
        "baseline": {
            "first_meaningful_render_ms": state["console"].get("first_meaningful_render_ms"),
            "boundaries_ready_ms": state["console"].get("boundaries_ready_ms"),
            "request_count": len(initial_requests),
            "api_request_count": len(initial_api_requests),
            "normal_view_uses_baked_only": True,
            "response_content_length_bytes": int(initial_bytes_encoded),
            "response_decoded_body_bytes": int(initial_bytes_decoded),
        },
        "scenarios": {},
    }

    def clear_explicit_state() -> None:
        page.evaluate(
            """
            () => {
              const hooks = window.__DOCMAP_TEST_HOOKS__;
              hooks?.setPinnedLocationId?.(null);
              hooks?.clearHighlightedLocationIds?.();
            }
            """
        )

    def run_scenario(scenario: Scenario) -> None:
        state["scenario"] = scenario.name
        clear_explicit_state()
        before = get_perf()
        started = time.perf_counter()

        if scenario.name == "low_zoom_pan":
            page.evaluate(
                "(v) => window.__DOCMAP_TEST_HOOKS__.setViewport(v)",
                {"zoom": 2.2, "west": -180, "east": 180, "south": -30, "north": 60},
            )
        elif scenario.name == "regional_pan":
            page.evaluate(
                "(v) => window.__DOCMAP_TEST_HOOKS__.setViewport(v)",
                {"zoom": 4.5, "west": 0, "east": 40, "south": 24, "north": 48},
            )
            page.wait_for_timeout(250)
            page.evaluate(
                "(v) => window.__DOCMAP_TEST_HOOKS__.setViewport(v)",
                {"zoom": 4.5, "west": 20, "east": 60, "south": 24, "north": 48},
            )
        elif scenario.name == "hover_click_select" and location_ids:
            page.evaluate(
                "(locationId) => window.__DOCMAP_TEST_HOOKS__.setPinnedLocationId(locationId)",
                location_ids[0],
            )
        elif scenario.name == "search_highlight" and location_ids:
            highlighted = location_ids[:2] if len(location_ids) >= 2 else location_ids[:1]
            page.evaluate(
                "(locationIds) => window.__DOCMAP_TEST_HOOKS__.setHighlightedLocationIds(locationIds)",
                highlighted,
            )

        page.wait_for_function(scenario.wait_expression, timeout=120000)
        page.wait_for_timeout(scenario.wait_ms)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        after = get_perf()

        scenario_requests = [item for item in state["requests"] if item["scenario"] == scenario.name]
        scenario_api_requests = [item for item in scenario_requests if item["path"].startswith("/api/")]
        scenario_bytes_encoded = sum(
            size for (scenario_name, _), size in state["responses_encoded"].items() if scenario_name == scenario.name
        )
        scenario_bytes_decoded = sum(
            size for (scenario_name, _), size in state["responses_decoded"].items() if scenario_name == scenario.name
        )
        output["scenarios"][scenario.name] = {
            "elapsed_ms": round(elapsed_ms, 2),
            "request_count": len(scenario_requests),
            "api_request_count": len(scenario_api_requests),
            "response_content_length_bytes": int(scenario_bytes_encoded),
            "response_decoded_body_bytes": int(scenario_bytes_decoded),
            "task_duration_delta_ms": round((after["TaskDuration"] - before["TaskDuration"]) * 1000.0, 2),
            "script_duration_delta_ms": round((after["ScriptDuration"] - before["ScriptDuration"]) * 1000.0, 2),
            "heap_used_delta_mb": round((after["JSHeapUsedSize"] - before["JSHeapUsedSize"]) / 1024.0 / 1024.0, 3),
            "heap_used_mb_after": round(after["JSHeapUsedSize"] / 1024.0 / 1024.0, 3),
            "nodes_after": int(after["Nodes"]),
        }

    for scenario in SCENARIOS:
        if scenario.name in {"hover_click_select", "search_highlight"} and not location_ids:
            continue
        run_scenario(scenario)

    return output


def _build_comparison_summary(baseline_payload: dict[str, Any], current_payload: dict[str, Any]) -> dict[str, Any]:
    baseline = baseline_payload.get("baseline", {})
    current = current_payload.get("baseline", {})
    baseline_scenarios = baseline_payload.get("scenarios", {})
    current_scenarios = current_payload.get("scenarios", {})

    low_zoom_elapsed_x = _ratio(
        baseline_scenarios.get("low_zoom_pan", {}).get("elapsed_ms"),
        current_scenarios.get("low_zoom_pan", {}).get("elapsed_ms"),
    )
    regional_elapsed_x = _ratio(
        baseline_scenarios.get("regional_pan", {}).get("elapsed_ms"),
        current_scenarios.get("regional_pan", {}).get("elapsed_ms"),
    )
    hover_click_elapsed_x = _ratio(
        baseline_scenarios.get("hover_click_select", {}).get("elapsed_ms"),
        current_scenarios.get("hover_click_select", {}).get("elapsed_ms"),
    )
    search_highlight_elapsed_x = _ratio(
        baseline_scenarios.get("search_highlight", {}).get("elapsed_ms"),
        current_scenarios.get("search_highlight", {}).get("elapsed_ms"),
    )
    first_useful_interaction_x = _ratio(
        baseline.get("boundaries_ready_ms"),
        current.get("boundaries_ready_ms"),
    )

    pan_candidates = [value for value in [low_zoom_elapsed_x, regional_elapsed_x] if value is not None]
    worst_pan_zoom_elapsed_x = min(pan_candidates) if pan_candidates else None

    def meets_threshold(value: float | None, threshold: float) -> bool:
        return bool(value is not None and value >= threshold)

    minimum_5x_met = (
        meets_threshold(first_useful_interaction_x, 5.0)
        and meets_threshold(worst_pan_zoom_elapsed_x, 5.0)
        and meets_threshold(hover_click_elapsed_x, 5.0)
    )
    stretch_20x_met = (
        meets_threshold(first_useful_interaction_x, 20.0)
        and meets_threshold(worst_pan_zoom_elapsed_x, 20.0)
        and meets_threshold(hover_click_elapsed_x, 20.0)
    )

    limiting_factors: list[dict[str, Any]] = []
    if not meets_threshold(first_useful_interaction_x, 20.0):
        limiting_factors.append(
            {
                "area": "first_useful_interaction",
                "metric": "boundaries_ready_ms",
                "improvement_x": first_useful_interaction_x,
                "note": "Includes first baked manifest/tile availability plus initial style/tile decode time.",
            }
        )
    if not meets_threshold(low_zoom_elapsed_x, 20.0):
        limiting_factors.append(
            {
                "area": "pan_zoom",
                "metric": "low_zoom_pan.elapsed_ms",
                "improvement_x": low_zoom_elapsed_x,
                "note": "Low-zoom interaction still includes map redraw, tile decode, and event/frame scheduling costs.",
            }
        )
    if not meets_threshold(regional_elapsed_x, 20.0):
        limiting_factors.append(
            {
                "area": "pan_zoom",
                "metric": "regional_pan.elapsed_ms",
                "improvement_x": regional_elapsed_x,
                "note": "Regional pan cost now bounded by vector-tile decode and render update instead of large GeoJSON fetch/parse.",
            }
        )
    if not meets_threshold(hover_click_elapsed_x, 20.0):
        limiting_factors.append(
            {
                "area": "hover_click",
                "metric": "hover_click_select.elapsed_ms",
                "improvement_x": hover_click_elapsed_x,
                "note": "Explicit live overlay fetch remains by design for selected/highlighted geometry.",
            }
        )

    return {
        "summary": {
            "first_useful_interaction_improvement_x": first_useful_interaction_x,
            "pan_zoom_improvement_x": {
                "low_zoom_elapsed_x": low_zoom_elapsed_x,
                "regional_elapsed_x": regional_elapsed_x,
                "worst_of_pan_zoom_elapsed_x": worst_pan_zoom_elapsed_x,
            },
            "hover_click_improvement_x": hover_click_elapsed_x,
            "search_highlight_improvement_x": search_highlight_elapsed_x,
            "minimum_5x_met": minimum_5x_met,
            "stretch_20x_met": stretch_20x_met,
        },
        "detailed_comparison": {
            "baseline": baseline_payload,
            "current": current_payload,
            "initial_load": {
                "request_count_x": _ratio(
                    baseline.get("request_count"),
                    current.get("request_count"),
                ),
                "api_request_count_x": _ratio(
                    baseline.get("api_request_count"),
                    current.get("api_request_count"),
                ),
                "content_length_bytes_x": _ratio(
                    baseline.get("response_content_length_bytes"),
                    current.get("response_content_length_bytes"),
                ),
                "decoded_body_bytes_x": _ratio(
                    baseline.get("response_decoded_body_bytes"),
                    current.get("response_decoded_body_bytes"),
                ),
            },
            "scenarios": {},
        },
        "limiting_factors_for_20x": limiting_factors,
    }


def _add_scenario_comparison(
    comparison_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    current_payload: dict[str, Any],
) -> None:
    baseline_scenarios = baseline_payload.get("scenarios", {})
    current_scenarios = current_payload.get("scenarios", {})
    metrics = [
        "elapsed_ms",
        "request_count",
        "api_request_count",
        "response_content_length_bytes",
        "response_decoded_body_bytes",
        "task_duration_delta_ms",
        "script_duration_delta_ms",
        "heap_used_mb_after",
    ]
    for name in sorted(set(baseline_scenarios.keys()) | set(current_scenarios.keys())):
        before = baseline_scenarios.get(name, {})
        after = current_scenarios.get(name, {})
        ratio_by_metric = {metric: _ratio(before.get(metric), after.get(metric)) for metric in metrics}
        comparison_payload["detailed_comparison"]["scenarios"][name] = {
            "before": before,
            "after": after,
            "improvement_x": ratio_by_metric,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure current baked-geometry performance and compare against Phase A baseline."
    )
    parser.add_argument("--base-url", default="http://localhost:8080", help="Presentation base URL.")
    parser.add_argument(
        "--baseline-json",
        default="docs/qa/baked_interactive_geometry_phase_a_ui_baseline_2026-04-17.json",
        help="Path to Phase A baseline JSON.",
    )
    parser.add_argument(
        "--current-output",
        default="docs/qa/baked_interactive_geometry_phase_f_current_2026-04-20.json",
        help="Output path for current run metrics JSON.",
    )
    parser.add_argument(
        "--comparison-output",
        default="docs/qa/baked_interactive_geometry_phase_f_comparison_2026-04-20.json",
        help="Output path for baseline-vs-current comparison JSON.",
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline_json)
    if not baseline_path.exists():
        raise FileNotFoundError(f"baseline JSON not found: {baseline_path}")
    baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        try:
            current_payload = _collect_current_metrics(page, context, args.base_url)
        finally:
            browser.close()

    current_encoded = json.dumps(current_payload, indent=2) + "\n"
    Path(args.current_output).write_text(current_encoded, encoding="utf-8")

    comparison_payload = _build_comparison_summary(baseline_payload, current_payload)
    _add_scenario_comparison(comparison_payload, baseline_payload, current_payload)
    comparison_payload["measured_at_utc"] = datetime.now(tz=UTC).isoformat()
    comparison_payload["baseline_path"] = str(baseline_path.as_posix())
    comparison_payload["current_path"] = str(Path(args.current_output).as_posix())

    comparison_encoded = json.dumps(comparison_payload, indent=2) + "\n"
    Path(args.comparison_output).write_text(comparison_encoded, encoding="utf-8")
    print(comparison_encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from typing import Any

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


def _collect_metrics(page: Page, context: BrowserContext, base_url: str) -> dict[str, Any]:
    cdp = context.new_cdp_session(page)
    cdp.send("Performance.enable")
    state: dict[str, Any] = {
        "scenario": "initial_load",
        "console": {},
        "requests": [],
        "responses": {},
    }

    locations = requests.get(f"{base_url.rstrip('/')}/api/map/locations", timeout=30).json()
    location_ids = [str(row["location_id"]) for row in locations[:3]]

    def parse_console(msg_text: str) -> None:
        match = re.search(r"presentation\.performance\.([a-z_]+)_ms\s+([0-9.]+)", msg_text)
        if not match:
            return
        state["console"][f"{match.group(1)}_ms"] = float(match.group(2))

    page.on("console", lambda msg: parse_console(msg.text))
    page.on(
        "request",
        lambda req: state["requests"].append(
            {"scenario": state["scenario"], "url": req.url, "method": req.method}
        ),
    )

    def on_response(resp) -> None:
        content_length = resp.headers.get("content-length")
        size = int(content_length) if content_length and content_length.isdigit() else 0
        key = (state["scenario"], resp.url)
        state["responses"][key] = int(state["responses"].get(key, 0)) + size

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
    page.wait_for_timeout(600)

    initial_requests = [item for item in state["requests"] if item["scenario"] == "initial_load"]
    initial_bytes = sum(size for (scenario, _), size in state["responses"].items() if scenario == "initial_load")
    output: dict[str, Any] = {
        "baseline": {
            "first_meaningful_render_ms": state["console"].get("first_meaningful_render_ms"),
            "boundaries_ready_ms": state["console"].get("boundaries_ready_ms"),
            "request_count": len(initial_requests),
            "response_content_length_bytes": int(initial_bytes),
        },
        "scenarios": {},
    }

    def run_scenario(scenario: Scenario) -> None:
        state["scenario"] = scenario.name
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
        elif scenario.name == "search_highlight":
            page.fill("input[type='search']", "paris")

        page.wait_for_function(scenario.wait_expression, timeout=120000)
        page.wait_for_timeout(scenario.wait_ms)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        after = get_perf()

        scenario_requests = [item for item in state["requests"] if item["scenario"] == scenario.name]
        scenario_bytes = sum(
            size for (scenario_name, _), size in state["responses"].items() if scenario_name == scenario.name
        )
        output["scenarios"][scenario.name] = {
            "elapsed_ms": round(elapsed_ms, 2),
            "request_count": len(scenario_requests),
            "response_content_length_bytes": int(scenario_bytes),
            "task_duration_delta_ms": round((after["TaskDuration"] - before["TaskDuration"]) * 1000.0, 2),
            "script_duration_delta_ms": round((after["ScriptDuration"] - before["ScriptDuration"]) * 1000.0, 2),
            "heap_used_delta_mb": round((after["JSHeapUsedSize"] - before["JSHeapUsedSize"]) / 1024.0 / 1024.0, 3),
            "heap_used_mb_after": round(after["JSHeapUsedSize"] / 1024.0 / 1024.0, 3),
            "nodes_after": int(after["Nodes"]),
        }

    for scenario in SCENARIOS:
        if scenario.name == "hover_click_select" and not location_ids:
            continue
        run_scenario(scenario)

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure current presentation runtime UI baseline for Phase A.")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Presentation base URL.")
    parser.add_argument("--output", default="", help="Optional output path for JSON metrics.")
    args = parser.parse_args()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        try:
            payload = _collect_metrics(page, context, args.base_url)
        finally:
            browser.close()

    encoded = json.dumps(payload, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

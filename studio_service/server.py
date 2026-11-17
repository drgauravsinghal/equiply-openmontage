"""AGPL-3.0. Stateless API around OpenMontage's production contracts.

No provider credentials, user uploads, project database or remote URL fetching.
Artifacts are returned to the caller for storage alongside its approved plan.
"""
from __future__ import annotations

import hmac
import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jsonschema import ValidationError
from lib.delivery_promise import DeliveryPromise
from lib.pipeline_loader import load_pipeline_readonly
from schemas.artifacts import ARTIFACT_NAMES, load_schema, validate_artifact
from studio_service import workflow

ROOT = Path(__file__).resolve().parent.parent
REVISION = "2e003e65fa99a0f329478a2c1cdcf26bc481933a"
MAX_BODY = 1024 * 1024
PIPELINES = {"cinematic", "screen-demo", "animated-explainer", "hybrid"}


def stage_contract(data):
    pipeline = data.get("pipeline", "cinematic")
    if pipeline not in PIPELINES:
        raise ValueError("Unsupported production pipeline")
    manifest = load_pipeline_readonly(pipeline)
    stage = next((s for s in manifest["stages"] if s["name"] == data.get("stage")), None)
    if not stage:
        raise ValueError("Unknown production stage")
    skill = ROOT / "skills" / (stage["skill"] + ".md")
    return {
        "engine": "OpenMontage", "upstreamRevision": REVISION,
        "pipeline": pipeline, "stage": stage,
        "direction": skill.read_text(encoding="utf-8"),
        "schemas": {name: load_schema(name) for name in stage.get("produces", []) if name in ARTIFACT_NAMES},
    }


def validate(data):
    name = data.get("name")
    if name not in ARTIFACT_NAMES:
        raise ValueError("Unknown production artifact")
    validate_artifact(name, data.get("artifact"))
    return {"valid": True, "name": name, "upstreamRevision": REVISION}


def story_artifacts(data):
    """Map an approved generic beat sheet to canonical upstream artifacts.

    Validation does not claim creative approval or inspection of generated media.
    Asset identifiers are opaque; the host must verify ownership and provenance.
    """
    story = data["story"]
    beats = story["beats"]
    if not isinstance(beats, list) or not 4 <= len(beats) <= 12:
        raise ValueError("A story needs four to twelve beats")
    sections, scenes = [], []
    cursor = 0
    for beat in beats:
        duration = beat["seconds"]
        if isinstance(duration, bool) or not isinstance(duration, (float, int)) or not 0 < duration <= 60:
            raise ValueError("Invalid beat duration")
        end = round(cursor + duration, 3)
        sections.append({"id": beat["id"], "label": beat["role"], "text": beat["copy"],
                         "start_seconds": cursor, "end_seconds": end})
        scenes.append({"id": beat["id"], "type": "generated" if beat.get("mediaRequest") else "broll",
                       "description": beat["visual"], "start_seconds": cursor, "end_seconds": end,
                       "script_section_id": beat["id"], "shot_intent": beat["purpose"],
                       "movement": beat["motion"], "overlay_notes": beat["copy"],
                       "hero_moment": beat["role"] == "payoff"})
        cursor = end
    if abs(cursor - data["duration"]) > .1:
        raise ValueError("Story timing does not match the brief")
    script = {"version": "1.0", "title": story["concept"], "total_duration_seconds": cursor, "sections": sections}
    scene_plan = {"version": "1.0", "scenes": scenes}
    validate_artifact("script", script)
    validate_artifact("scene_plan", scene_plan)
    promise_data = data.get("promise")
    promise_check = None
    if promise_data:
        promise_check = DeliveryPromise.from_dict(promise_data).validate_cuts(data.get("cuts", []))
        if not promise_check["valid"]:
            return {"engine": "OpenMontage", "upstreamRevision": REVISION,
                    "valid": False, "issues": promise_check["violations"]}
    return {"engine": "OpenMontage", "upstreamRevision": REVISION, "valid": True,
            "artifacts": {"script": script, "scene_plan": scene_plan},
            "status": "planned", "deliveryPromise": promise_data,
            "promiseCheck": promise_check, "reviewedExport": False}


def delivery(data):
    promise = DeliveryPromise.from_dict(data["promise"])
    cuts = data["cuts"]
    if not isinstance(cuts, list) or len(cuts) > 100:
        raise ValueError("Invalid edit cuts")
    return {**promise.validate_cuts(cuts), "upstreamRevision": REVISION}


ROUTES = {"/v1/stage": stage_contract, "/v1/artifacts/validate": validate,
          "/v1/story/artifacts": story_artifacts, "/v1/delivery/validate": delivery,
          "/v2/planning": workflow.planning, "/v2/capabilities": workflow.capabilities, "/v2/runs/create": workflow.create,
          "/v2/runs/start": workflow.start, "/v2/runs/status": workflow.status,
          "/v2/runs/delete": workflow.remove}


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenMontageStudio/1"

    def log_message(self, fmt, *args):
        # Never log request bodies, credentials or business reference material.
        pass

    def log_failure(self, error):
        # Log code locations and exception type, never request data or secrets.
        frames = traceback.extract_tb(error.__traceback__)
        print(json.dumps({"event": "production_error", "route": self.path,
                          "type": type(error).__name__,
                          "locations": [f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in frames]}), flush=True)

    def reply(self, status, result):
        body = json.dumps(result, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/v2/runs/"):
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + os.environ["STUDIO_SERVICE_TOKEN"]):
                return self.reply(401, {"error": "Unauthorized"})
            try:
                parts = self.path.split("/")
                if len(parts) != 5 or parts[4] != "video":
                    raise ValueError("Unknown export")
                if workflow.status({"runId": parts[3]})["state"] != "complete":
                    return self.reply(409, {"error": "Export not ready"})
                path = workflow.run_dir(parts[3]) / "renders/final.mp4"
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(path.stat().st_size))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with path.open("rb") as source:
                    while chunk := source.read(65536):
                        self.wfile.write(chunk)
                return
            except (ValueError, OSError):
                return self.reply(404, {"error": "Export unavailable"})
        if self.path == "/healthz":
            return self.reply(200, {"status": "ok", "engine": "OpenMontage", "upstreamRevision": REVISION,
                                    "executionVersion": 2})
        if self.path in ("/", "/source"):
            return self.reply(200, {"license": "AGPL-3.0", "source": os.environ["SOURCE_URL"],
                                    "upstream": "https://github.com/OpenMontageInc/OpenMontage",
                                    "upstreamRevision": REVISION})
        self.reply(404, {"error": "Not found"})

    def do_PUT(self):
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + os.environ["STUDIO_SERVICE_TOKEN"]):
            return self.reply(401, {"error": "Unauthorized"})
        try:
            parts = self.path.split("/")
            if len(parts) != 6 or parts[1:3] != ["v2", "runs"] or parts[4] != "assets":
                raise ValueError("Unknown upload")
            self.connection.settimeout(120)
            result = workflow.upload(parts[3], parts[5], self.rfile, int(self.headers.get("Content-Length", "0")))
            return self.reply(200, result)
        except (ValueError, KeyError, OSError):
            return self.reply(422, {"error": "Asset upload failed"})

    def do_POST(self):
        token = os.environ["STUDIO_SERVICE_TOKEN"]
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
            print(json.dumps({"event": "production_auth_rejected", "route": self.path}), flush=True)
            return self.reply(401, {"error": "Unauthorized"})
        fn = ROUTES.get(self.path)
        if not fn:
            return self.reply(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.reply(413, {"error": "Invalid request size"})
            self.connection.settimeout(15)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Incomplete request")
            data = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite number")))
            if not isinstance(data, dict):
                raise ValueError("Expected an object")
            return self.reply(200, fn(data))
        except ValidationError as error:
            return self.reply(422, {"error": "Artifact validation failed", "path": list(error.absolute_path),
                                    "rule": error.validator})
        except (ValueError, KeyError, TypeError) as error:
            return self.reply(422, {"error": str(error)[:1000]})
        except Exception as error:
            self.log_failure(error)
            return self.reply(500, {"error": "Production contract unavailable"})


def main():
    if len(os.environ.get("STUDIO_SERVICE_TOKEN", "")) < 32:
        raise RuntimeError("Configure a service token of at least 32 characters")
    if not os.environ.get("SOURCE_URL", "").startswith("https://github.com/"):
        raise RuntimeError("Configure this service's corresponding source URL")
    # Fail readiness before accepting traffic if the pinned source is incomplete.
    for pipeline in PIPELINES:
        load_pipeline_readonly(pipeline)
    try:
        workflow.capabilities({})
        print('Production capability discovery ready', flush=True)
    except Exception as error:
        frames = traceback.extract_tb(error.__traceback__)
        print(json.dumps({"event": "production_preflight_error", "type": type(error).__name__,
                          "locations": [f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in frames]}), flush=True)
    threading.Thread(target=workflow.cleanup_loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "10000"))), Handler).serve_forever()


if __name__ == "__main__":
    main()

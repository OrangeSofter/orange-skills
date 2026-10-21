#!/usr/bin/env python3
"""Repeatable Codex sessions, metrics, validation, and cleanup (stdlib only)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import statistics
import subprocess
import tempfile
import time
import tomllib
import uuid


TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens")
METRICS = ("duration_seconds", "input_tokens", "cached_input_tokens", "output_tokens",
           "total_tokens", "model_responses")


def write_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class SessionError(ValueError):
    """The required session log is unavailable or has invalid metadata."""


def parse_jsonl(text: str, source: str, warnings: list[str]) -> list[tuple[int, dict]]:
    records = []
    for line_number, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("expected object")
        except ValueError:
            warnings.append(f"{source}:{line_number}: invalid JSON record")
            continue
        records.append((line_number, record))
    return records


def read_jsonl(path: Path, warnings: list[str]) -> list[tuple[int, dict]]:
    try:
        return parse_jsonl(path.read_text(encoding="utf-8", errors="replace"), path.name, warnings)
    except OSError as error:
        warnings.append(f"Failed to read {path.name}: {error}")
        return []


def stop_process_group(process: subprocess.Popen) -> None:
    """Kill the process group before cleanup on timeout or interruption.

    A single signal also stops children that ignore SIGTERM. Do not wait for
    the parent first: it may exit before other processes in the group.
    """
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_process(command: list[str], directory: Path, timeout: float, *,
                stdin_text: str = "", env: dict | None = None,
                capture_events: bool = False) -> dict:
    """Save stdout immediately and measure process duration."""
    stdout_path = directory / ("events.jsonl" if capture_events else "stdout.log")
    result = {"status": "error", "exit_code": None, "duration_seconds": None}
    start = time.monotonic()
    process = None
    with tempfile.TemporaryFile() as prompt, stdout_path.open("wb") as output, \
            (directory / "stderr.log").open("wb") as errors:
        prompt.write(stdin_text.encode("utf-8"))
        prompt.seek(0)

        def consume(chunk: bytes) -> None:
            output.write(chunk)
            output.flush()

        try:
            start = time.monotonic()
            process = subprocess.Popen(command, stdin=prompt, stdout=subprocess.PIPE,
                stderr=errors, env=env, start_new_session=True)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map() or process.poll() is None:
                    remaining = timeout - (time.monotonic() - start)
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, timeout)
                    for key, _ in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if chunk:
                            consume(chunk)
                        else:
                            selector.unregister(key.fileobj)
                process.wait()
            result["status"] = "completed" if process.returncode == 0 else "error"
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            if process is not None:
                stop_process_group(process)
        except KeyboardInterrupt:
            result["status"] = "interrupted"
            if process is not None:
                stop_process_group(process)
        except OSError as error:
            result["error"] = str(error)
            if process is not None:
                stop_process_group(process)
        finally:
            result["duration_seconds"] = round(time.monotonic() - start, 6)
            if process is not None:
                result["exit_code"] = process.returncode
                if process.stdout is not None:
                    # After stopping the group, drain remaining output without waiting for EOF.
                    os.set_blocking(process.stdout.fileno(), False)
                    while True:
                        try:
                            chunk = os.read(process.stdout.fileno(), 65536)
                        except BlockingIOError:
                            break
                        if not chunk:
                            break
                        consume(chunk)
                    process.stdout.close()
    return result


def load_session(thread_id: str | None, codex_home: Path, destination: Path,
                 warnings: list[str]) -> list[tuple[int, dict]]:
    if not isinstance(thread_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", thread_id):
        raise SessionError("No valid thread_id to locate the session log")
    try:
        candidates = list((codex_home / "sessions").rglob(f"*{thread_id}*.jsonl"))
        if not candidates:
            raise SessionError(f"No session log found for thread_id={thread_id}")
        if len(candidates) != 1:
            raise SessionError(f"Multiple session logs found for thread_id={thread_id}")
        content = candidates[0].read_bytes()
        destination.write_bytes(content)
        session = parse_jsonl(content.decode("utf-8", errors="replace"), destination.name, warnings)
        if not session or session[0][0] != 1:
            raise SessionError("Session log is empty or does not start with valid metadata")
        metadata = session[0][1]
        payload = metadata.get("payload")
        if (not isinstance(payload, dict) or metadata.get("type") != "session_meta"
                or payload.get("id") != thread_id):
            raise SessionError("Session log metadata does not match thread_id")
    except OSError as error:
        raise SessionError(f"Failed to read or copy the session log: {error}") from error
    return session


def token_number(usage: dict, name: str) -> int | None:
    value = usage.get(name)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def parse_experiment(session: list[tuple[int, dict]], thread_id: str,
                     turn_completed: bool, warnings: list[str]) -> dict:
    model_responses = 0
    total_usage = None
    for line, row in session:
        event_type = row.get("type")
        if event_type == "token_usage_record":
            model_responses += 1
            continue

        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if event_type != "event_msg" or payload.get("type") != "token_count":
            continue

        info = payload.get("info")
        if not info:
            continue
        total_usage = None
        if isinstance(info, dict):
            total_usage = info.get("total_token_usage")
        if not isinstance(total_usage, dict):
            total_usage = None
            warnings.append(f"session.jsonl:{line}: invalid total_token_usage")

    tokens = {key: token_number(total_usage or {}, key)
              for key in (*TOKEN_KEYS, "total_tokens")}
    if tokens["total_tokens"] is None:
        warnings.append("Total token usage is unavailable")

    return {**tokens, "thread_id": thread_id,
        "model_responses": model_responses,
        "turn_completed": turn_completed,
        "data_complete": not warnings, "warnings": list(dict.fromkeys(warnings))}


def summary_for(runs: list[dict]) -> dict:
    aggregates = {}
    for metric in METRICS:
        values = [run[metric] for run in runs if run.get("status") == "completed"
                  and isinstance(run.get(metric), (int, float))]
        aggregates[metric] = {"samples": len(values),
            "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None}
    known_tokens = [run["total_tokens"] for run in runs if run.get("total_tokens") is not None]
    return {"attempts": len(runs), "completed": sum(run.get("status") == "completed" for run in runs),
        "failed": sum(run.get("status") != "completed" for run in runs),
        "registered_total_tokens": sum(known_tokens) if known_tokens else None,
        "attempts_with_token_data": len(known_tokens), "completed_statistics": aggregates}


def save_summary(directory: Path, manifest: dict, runs: list[dict]) -> None:
    write_json(directory / "summary.json", {**manifest, "summary": summary_for(runs), "runs": runs})
    fields = ["iteration", "status", "exit_code", *METRICS, "data_complete",
              "validation_status", "validation_seconds", "cleanup_status", "cleanup_seconds", "thread_id"]
    with (directory / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for run in runs:
            validation = run.get("validation", {})
            cleanup = run.get("cleanup", {})
            writer.writerow({**run, "validation_status": validation.get("status", "not_requested"),
                             "validation_seconds": validation.get("duration_seconds"),
                             "cleanup_status": cleanup.get("status", "not_requested"),
                             "cleanup_seconds": cleanup.get("duration_seconds")})


def positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("Expected a positive integer") from None
    if value <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer")
    return value


def positive_seconds(text: str) -> float:
    import math
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("Expected a positive number of seconds") from None
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("Expected a positive number of seconds")
    return value


def load_config(path: Path) -> dict:
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    defaults = {"model": None, "profile": None,
        "output_dir": str(Path(__file__).resolve().parent / "results"),
        "timeout_seconds": 900, "cleanup_script": None,
        "cleanup_args": [], "cleanup_timeout_seconds": 120,
        "validation_script": None, "validation_args": [], "validation_timeout_seconds": 120}
    unknown = config.keys() - (defaults.keys() | {"prompt"})
    if unknown:
        raise ValueError("Unknown fields: " + ", ".join(sorted(unknown)))
    for key in ("prompt", "model", "profile", "output_dir", "cleanup_script", "validation_script"):
        if key in config and (not isinstance(config[key], str) or not config[key].strip()
                              or "\0" in config[key]):
            raise ValueError(f"{key}: expected a nonempty string without NUL")
    if "prompt" not in config:
        raise ValueError("Required field prompt is missing")
    for key in ("timeout_seconds", "cleanup_timeout_seconds", "validation_timeout_seconds"):
        if key in config:
            if type(config[key]) not in (int, float):
                raise ValueError(f"{key}: expected a positive number of seconds")
            try:
                config[key] = positive_seconds(str(config[key]))
            except argparse.ArgumentTypeError as error:
                raise ValueError(f"{key}: {error}") from None
    for kind in ("cleanup", "validation"):
        arguments = config.get(f"{kind}_args", [])
        if not isinstance(arguments, list) or any(not isinstance(arg, str) or "\0" in arg for arg in arguments):
            raise ValueError(f"{kind}_args: expected an array of strings without NUL")
        if arguments and f"{kind}_script" not in config:
            raise ValueError(f"{kind}_args requires {kind}_script")
    config = defaults | config
    for key in ("output_dir", "cleanup_script", "validation_script"):
        if config[key] is not None:
            config[key] = (path.parent / config[key]).resolve()
    for kind in ("cleanup", "validation"):
        script = config[f"{kind}_script"]
        if script and (not script.is_file() or not os.access(script, os.X_OK)):
            raise ValueError(f"{kind.capitalize()} script must exist and be executable")
    return config


def main(argv: list[str] | None = None) -> int:
    working_directory = Path.cwd()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iterations", type=positive_int)
    args = parser.parse_args(argv)
    config_path = working_directory / "benchmark_config.toml"
    try:
        config = load_config(config_path)
    except (OSError, ValueError) as error:
        parser.error(f"{config_path}: {error}")
    # Keep the legacy cleanup_arg name in manifest parameters.
    config["cleanup_arg"] = config.pop("cleanup_args")
    vars(args).update(config)
    codex = shutil.which("codex")
    if codex is None:
        parser.error("codex not found in PATH")
    try:
        version = subprocess.run([codex, "--version"], capture_output=True, text=True,
                                 timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        parser.error(f"Failed to check Codex CLI: {error}")
    series = args.output_dir.resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                                         + "-" + uuid.uuid4().hex[:8] + "-" + working_directory.name)
    series.mkdir(parents=True)
    codex_env = dict(os.environ)
    codex_env.setdefault("RUST_LOG", "warn,codex_api=trace")
    manifest = {"schema_version": 1, "prompt": args.prompt, "iterations_requested": args.iterations,
        "codex_version": version, "cwd": str(working_directory),
        "codex_rust_log": codex_env["RUST_LOG"],
        "parameters": {key: str(value) if isinstance(value, Path) else value
                       for key, value in vars(args).items() if key != "prompt"},
        "state_reset": bool(args.cleanup_script), "series_status": "running"}
    write_json(series / "manifest.json", manifest)
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    runs = []

    def run_hook(kind: str, phase: str, iteration: int, directory: Path) -> dict:
        script = getattr(args, f"{kind}_script")
        if not script:
            return {"status": "not_requested"}
        target = directory / kind
        target.mkdir()
        env = {**os.environ, "BENCHMARK_PHASE": phase, "BENCHMARK_ITERATION": str(iteration),
               "BENCHMARK_RUN_DIR": str(directory)}
        print(f"{kind.capitalize()} {phase}, iteration {iteration}…", flush=True)
        arguments = args.cleanup_arg if kind == "cleanup" else args.validation_args
        result = run_process([str(script), *arguments], target,
                             getattr(args, f"{kind}_timeout_seconds"), env=env)
        write_json(target / "result.json", result)
        return result

    print(f"Results: {series}", flush=True)
    try:
        if args.cleanup_script:
            manifest["setup"] = run_hook("cleanup", "setup", 0, series)
            if manifest["setup"]["status"] != "completed":
                manifest["series_status"] = "setup_failed"
                return 1
        for iteration in range(1, args.iterations + 1):
            directory = series / f"run-{iteration:03d}"
            directory.mkdir()
            codex_output = directory / "codex_output"
            codex_output.mkdir()
            run_codex_env = {**codex_env, "CODEX_ROLLOUT_TRACE_ROOT": str(codex_output)}
            command = [codex, "exec", "--json", "--color", "never", "-C", str(working_directory),
                       "--output-last-message", str(codex_output / "final_answer.txt")]
            for option in ("model", "profile"):
                if getattr(args, option):
                    command.extend([f"--{option}", getattr(args, option)])
            command.append("-")
            print(f"Experiment {iteration}/{args.iterations}…", flush=True)
            result = {"iteration": iteration}
            runs.append(result)
            try:
                result.update(run_process(command, codex_output, args.timeout_seconds,
                    stdin_text=args.prompt, env=run_codex_env, capture_events=True))
                warnings = []
                events = read_jsonl(codex_output / "events.jsonl", warnings)
                thread_id = next((row.get("thread_id") for _, row in events
                                  if row.get("type") == "thread.started"), None)
                result["thread_id"] = thread_id
                terminals = [row["type"] for _, row in events
                             if row.get("type") in ("turn.completed", "turn.failed")]
                turn_completed = bool(terminals and terminals[-1] == "turn.completed")
                session = load_session(thread_id, codex_home, codex_output / "session.jsonl", warnings)
                result.update(parse_experiment(session, thread_id, turn_completed, warnings))
                if result["status"] == "completed" and not result["turn_completed"]:
                    result["status"] = "error"
                    result["warnings"].append("CLI did not confirm successful turn completion")
            except KeyboardInterrupt:
                result.update(status="interrupted", data_complete=False)
            except SessionError as error:
                result.update(data_complete=False, session_error=str(error))
                if result.get("status") not in ("timeout", "interrupted"):
                    result["status"] = "error"
                print(f"Session error: {error}", flush=True)
            except Exception as error:
                result.update(data_complete=False, parse_error=str(error))
                if result.get("status") not in ("timeout", "interrupted"):
                    result["status"] = "error"
            finally:
                result["validation"] = {"status": "skipped" if args.validation_script else "not_requested"}
                try:
                    if result.get("status") == "completed":
                        result["validation"] = run_hook("validation", "validation", iteration, directory)
                        validation_status = result["validation"]["status"]
                        if validation_status == "interrupted":
                            result["status"] = "interrupted"
                        elif validation_status not in ("completed", "not_requested"):
                            result["status"] = "validation_failed"
                finally:
                    result["cleanup"] = run_hook("cleanup", "cleanup", iteration, directory)
                write_json(directory / "benchmark_result.json", result)
                save_summary(series, manifest, runs)
            value = lambda key: result.get(key) if result.get(key) is not None else "N/A"
            print(f"{iteration:>3} | {result['status']} | {value('duration_seconds')}s | "
                  f"input={value('input_tokens')} cached={value('cached_input_tokens')} "
                  f"output={value('output_tokens')} total={value('total_tokens')} | "
                  f"MODEL={value('model_responses')} | "
                  f"validation={result['validation']['status']} | "
                  f"cleanup={result['cleanup']['status']} | "
                  f"data={'complete' if result.get('data_complete') else 'partial'}", flush=True)
            if result["status"] == "interrupted":
                manifest["series_status"] = "interrupted"
                return 130
            if "session_error" in result:
                manifest["series_status"] = "session_failed"
                return 1
            if result["cleanup"]["status"] not in ("completed", "not_requested"):
                manifest["series_status"] = "cleanup_failed"
                return 1
        manifest["series_status"] = "completed" if all(r["status"] == "completed" for r in runs) else "completed_with_errors"
        return 0 if manifest["series_status"] == "completed" else 1
    except KeyboardInterrupt:
        manifest["series_status"] = "interrupted"
        return 130
    finally:
        save_summary(series, manifest, runs)
        write_json(series / "manifest.json", manifest)
        totals = summary_for(runs)
        print(f"Completed: {totals['completed']}; failed: {totals['failed']}; "
              f"recorded tokens: {totals['registered_total_tokens']}", flush=True)
        for metric in ("duration_seconds", "total_tokens"):
            stats = totals["completed_statistics"][metric]
            print(f"{metric}: mean={stats['mean']}, median={stats['median']}, n={stats['samples']}", flush=True)
        print(f"Summary: {series / 'summary.json'}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())

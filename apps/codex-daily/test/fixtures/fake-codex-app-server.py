#!/usr/bin/env python3
import json
import hashlib
import signal
import threading
import sys
import os

initialized = False
reporting_thread_created = False
analysis_thread_count = 0
analysis_threads = set()


def thread(thread_id, **overrides):
    names = {
        "thread-one": "Observed chat",
        "thread-two": "Second observed chat",
        "older-active-thread": "Older active chat",
    }
    value = {
        "id": thread_id,
        "sessionId": f"session-{thread_id}",
        "forkedFromId": None,
        "parentThreadId": None,
        "preview": "SECRET PREVIEW MUST NEVER BE STORED",
        "ephemeral": False,
        "model": "gpt-5.6-sol",
        "modelProvider": "openai",
        "createdAt": 1785312000,
        "updatedAt": 1785320000 if thread_id == "thread-two" else 1785319200,
        "recencyAt": 1785320000,
        "status": {"type": "active", "activeFlags": []},
        "path": "/secret/internal/session.jsonl",
        "cwd": f"/workspace/{thread_id}",
        "cliVersion": "0.146.0-fake",
        "source": "cli",
        "threadSource": None,
        "agentNickname": None,
        "agentRole": None,
        "gitInfo": None,
        "name": names.get(
            thread_id,
            f"Recent session {thread_id.removeprefix('thread-')}",
        ),
        "turns": [],
    }
    value.update(overrides)
    return value


def send(value):
    sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
    sys.stdout.flush()

def safe_request_record(message):
    method = message.get("method")
    params = message.get("params", {})
    if method == "initialize":
        capabilities = params.get("capabilities", {})
        return {
            "method": method,
            "experimentalApi": capabilities.get("experimentalApi") is True,
        }
    if method == "thread/read":
        return {
            "method": method,
            "includeTurns": params.get("includeTurns") is True,
            "sourceThread": "ordinary",
        }
    if method == "thread/start":
        return {
            "method": method,
            "params": params,
        }
    if method == "turn/start":
        input_value = params.get("input", [])
        input_text = "".join(
            item.get("text", "")
            for item in input_value
            if isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
        )
        thread_id = params.get("threadId")
        return {
            "method": method,
            "analysisThread": thread_id in analysis_threads,
            "parameterKeys": sorted(params.keys()),
            "model": params.get("model"),
            "effort": params.get("effort"),
            "environments": params.get("environments"),
            "outputSchema": params.get("outputSchema"),
            "inputCharacterCount": len(input_text),
            "inputSha256": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
        }
    return {"method": method}


shared_live = "proxy" in sys.argv
method_log = os.environ.get("CODEX_DAILY_FAKE_METHOD_LOG")
request_log = os.environ.get("CODEX_DAILY_FAKE_REQUEST_LOG")
analysis_mode = os.environ.get("CODEX_DAILY_FAKE_ANALYSIS_MODE", "success")
session_count = int(os.environ.get("CODEX_DAILY_FAKE_SESSION_COUNT", "2"))


def ordinary_threads():
    if session_count <= 2:
        return [thread("thread-one"), thread("thread-two")]
    recent = []
    ids = ["thread-one", "thread-two"] + [
        f"thread-{index}" for index in range(3, 11)
    ]
    for index, thread_id in enumerate(ids):
        timestamp = 1785321000 - index * 60
        recent.append(
            thread(
                thread_id,
                updatedAt=timestamp,
                recencyAt=timestamp,
                status={"type": "idle", "activeFlags": []},
            )
        )
    recent.append(
        thread(
            "older-active-thread",
            updatedAt=1785310000,
            recencyAt=1785310000,
            status={"type": "active", "activeFlags": []},
        )
    )
    return recent[:session_count]


def live_fact():
    send(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-one",
                "turn": {
                    "id": "turn-one",
                    "items": [],
                    "itemsView": "full",
                    "status": "completed",
                    "error": None,
                    "startedAt": 1785319100,
                    "completedAt": 1785319200,
                    "durationMs": 100000,
                },
            },
        }
    )
    if shared_live:
        send(
            {
                "id": 700,
                "method": "item/commandExecution/requestApproval",
                "params": {
                    "threadId": "thread-one",
                    "turnId": "turn-approval",
                    "itemId": "item-approval",
                    "command": "SECRET COMMAND",
                    "startedAtMs": 1785320100000,
                },
            }
        )
        send(
            {
                "id": 701,
                "method": "item/tool/requestUserInput",
                "params": {
                    "threadId": "thread-one",
                    "turnId": "turn-question",
                    "itemId": "item-question",
                    "questions": [{"question": "SECRET QUESTION"}],
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-two",
                    "turn": {
                        "id": "turn-failed",
                        "items": [],
                        "itemsView": "full",
                        "status": "failed",
                        "error": {"message": "SECRET FAILURE"},
                        "startedAt": 1785320110,
                        "completedAt": 1785320120,
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-two",
                    "turn": {
                        "id": "turn-interrupted",
                        "items": [],
                        "itemsView": "full",
                        "status": "interrupted",
                        "error": None,
                        "startedAt": 1785320130,
                        "completedAt": 1785320140,
                    },
                },
            }
        )
        send(
            {
                "method": "thread/goal/updated",
                "params": {
                    "threadId": "thread-two",
                    "turnId": "turn-blocked",
                    "goal": {
                        "status": "blocked",
                        "updatedAt": 1785320150,
                        "objective": "SECRET BLOCKER",
                    },
                },
            }
        )


signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(0))

for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method_log and method:
        with open(method_log, "a", encoding="utf-8") as handle:
            handle.write(method + "\n")
    if request_log and method in {
        "initialize",
        "thread/read",
        "thread/start",
        "turn/start",
    }:
        with open(request_log, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(safe_request_record(message), separators=(",", ":")) + "\n"
            )
    if method == "initialize":
        send(
            {
                "id": message["id"],
                "result": {
                    "userAgent": "fake-codex",
                    "codexHome": "/tmp/fake-codex-home",
                    "platformFamily": "unix",
                    "platformOs": "linux",
                },
            }
        )
    elif method == "initialized":
        initialized = True
    elif not initialized:
        send({"id": message.get("id"), "error": {"code": -1, "message": "not initialized"}})
    elif method == "thread/list":
        params = message.get("params", {})
        if params.get("archived"):
            send(
                {
                    "id": message["id"],
                    "result": {"data": [], "nextCursor": None, "backwardsCursor": None},
                }
            )
        elif not params.get("cursor"):
            data = [ordinary_threads()[0]]
            if reporting_thread_created:
                data.append(thread("codex-daily-reporting-thread"))
            send(
                {
                    "id": message["id"],
                    "result": {
                        "data": data,
                        "nextCursor": "page-two",
                        "backwardsCursor": None,
                    },
                }
            )
        else:
            send(
                {
                    "id": message["id"],
                    "result": {
                        "data": [
                            *ordinary_threads()[1:],
                            thread(
                                "child-thread",
                                parentThreadId="thread-one",
                                source={"subAgent": "review"},
                            ),
                        ],
                        "nextCursor": None,
                        "backwardsCursor": None,
                    },
                }
            )
            threading.Timer(0.01, live_fact).start()
    elif method == "thread/read":
        source_thread_id = message["params"]["threadId"]
        if analysis_mode == "source_missing":
            send(
                {
                    "id": message["id"],
                    "error": {"code": -32001, "message": "thread not found"},
                }
            )
            continue
        source_inventory = next(
            (
                candidate
                for candidate in ordinary_threads()
                if candidate["id"] == source_thread_id
            ),
            thread(source_thread_id),
        )
        source_updated_at = source_inventory["updatedAt"]
        if analysis_mode == "source_changed" and source_thread_id == "thread-one":
            source_updated_at += 300
        send(
            {
                "id": message["id"],
                "result": {
                    "thread": thread(
                        source_thread_id,
                        updatedAt=source_updated_at,
                        turns=[
                            {
                                "id": "turn-intent",
                                "status": "completed",
                                "items": [
                                    {
                                        "id": "user-secret",
                                        "type": "userMessage",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "SYNTHETIC_SOURCE_SECRET plan the release",
                                            },
                                            {
                                                "type": "localImage",
                                                "path": "/secret/unsupported.png",
                                            },
                                        ],
                                        "token": "STRUCTURED_TOKEN_MUST_DROP",
                                    },
                                    {
                                        "id": "reasoning-secret",
                                        "type": "reasoning",
                                        "summary": "SYNTHETIC_REASONING_SECRET",
                                    },
                                    {
                                        "id": "message-secret",
                                        "type": "agentMessage",
                                        "text": "SECRET RESPONSE",
                                    }
                                ],
                            }
                        ],
                    )
                },
            }
        )
    elif method == "thread/start":
        params = message.get("params", {})
        is_analysis = params.get("ephemeral") is True
        if is_analysis:
            analysis_thread_count += 1
            created_thread_id = f"codex-daily-analysis-{analysis_thread_count}"
            analysis_threads.add(created_thread_id)
        else:
            reporting_thread_created = True
            created_thread_id = "codex-daily-reporting-thread"
        # Deliberately notify before resolving thread/start. Codex Daily must
        # never project this thread before it can be durably excluded.
        send(
            {
                "method": "thread/started",
                "params": {
                    "thread": thread(
                        created_thread_id,
                        ephemeral=(
                            False
                            if is_analysis
                            and analysis_mode == "contradictory_durable"
                            else is_analysis
                        ),
                        source="appServer",
                    )
                },
            }
        )
        if is_analysis and analysis_mode == "unavailable":
            threading.Timer(
                0.05,
                lambda request_id=message["id"]: send(
                    {
                        "id": request_id,
                        "error": {"code": -32000, "message": "model unavailable"},
                    }
                ),
            ).start()
        else:
            response_ephemeral = (
                False
                if is_analysis
                and analysis_mode in ("durable", "contradictory_durable")
                else is_analysis
            )
            response_model = (
                "gpt-5.6-terra"
                if is_analysis and analysis_mode == "wrong_model"
                else "gpt-5.6-sol"
            )
            response_thread = (
                {"id": created_thread_id}
                if is_analysis and analysis_mode == "malformed"
                else thread(
                    created_thread_id,
                    ephemeral=response_ephemeral,
                    model=response_model,
                )
            )
            threading.Timer(
                0.05,
                lambda request_id=message["id"], response=response_thread: send(
                    {
                        "id": request_id,
                        "result": {
                            "model": response_model,
                            "thread": response,
                        },
                    }
                ),
            ).start()
    elif method == "turn/start":
        reporting_thread_id = message["params"]["threadId"]
        is_analysis = reporting_thread_id in analysis_threads
        turn_id = (
            f"analysis-turn-{reporting_thread_id}"
            if is_analysis
            else "reporting-turn"
        )
        send(
            {
                "id": message["id"],
                "result": {
                    "turn": {
                        "id": turn_id,
                        "status": "inProgress",
                        "items": [],
                    }
                },
            }
        )
        prompt = json.dumps(message["params"].get("input", []))
        if is_analysis:
            # A crossed completion must never satisfy exact turn correlation.
            send(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": reporting_thread_id,
                        "turn": {
                            "id": "wrong-analysis-turn",
                            "status": "completed",
                            "items": [
                                {
                                    "type": "agentMessage",
                                    "text": '{"currentState":"WRONG TURN"}',
                                }
                            ],
                        },
                    },
                }
            )
        if "NO_COMPLETION" not in prompt and analysis_mode != "slow":
            if is_analysis and analysis_mode == "invalid":
                response_text = "```json\n{\"raw\":\"SYNTHETIC_RAW_OUTPUT_SECRET\"}\n```"
            elif is_analysis and analysis_mode == "refusal":
                response_text = None
            elif is_analysis:
                response_text = json.dumps(
                    {
                        "currentState": "The chat is organizing the release.",
                        "done": ["The chat reports the monitor foundation is ready."],
                        "operatorActions": ["Review the pending release checklist."],
                        "blockers": [],
                        "confidence": "high",
                        "evidence": ["user:first-intent", "assistant:recent-1"],
                    },
                    separators=(",", ":"),
                )
            else:
                response_text = json.dumps(
                    {
                        "text": "Generated summary from the dedicated reporting thread.",
                        "suggestions": [],
                    },
                    separators=(",", ":"),
                )
            threading.Timer(
                0.01,
                lambda completed_thread_id=reporting_thread_id, completed_turn_id=turn_id, final_text=response_text: send(
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": completed_thread_id,
                            "turn": {
                                "id": completed_turn_id,
                                "status": "completed",
                                "items": [] if final_text is None else [
                                    {
                                        "id": "reporting-message",
                                        "type": "agentMessage",
                                        "text": final_text,
                                    }
                                ],
                            },
                        },
                    }
                ),
            ).start()
    else:
        send({"id": message.get("id"), "error": {"code": -32601, "message": "unsupported"}})

#!/usr/bin/env python3
import json
import signal
import sys
import threading

initialized = False


def thread(thread_id, **overrides):
    value = {
        "id": thread_id,
        "sessionId": f"session-{thread_id}",
        "forkedFromId": None,
        "parentThreadId": None,
        "preview": "SECRET PREVIEW MUST NEVER BE STORED",
        "ephemeral": False,
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
        "name": "Second observed chat" if thread_id == "thread-two" else "Observed chat",
        "turns": [],
    }
    value.update(overrides)
    return value


def send(value):
    sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
    sys.stdout.flush()


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


signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(0))

for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
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
            send(
                {
                    "id": message["id"],
                    "result": {
                        "data": [thread("thread-one")],
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
                            thread("thread-two"),
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
        send(
            {
                "id": message["id"],
                "result": {
                    "thread": thread(
                        message["params"]["threadId"],
                        turns=[
                            {
                                "id": "turn-secret",
                                "status": "completed",
                                "items": [
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
    else:
        send({"id": message.get("id"), "error": {"code": -32601, "message": "unsupported"}})

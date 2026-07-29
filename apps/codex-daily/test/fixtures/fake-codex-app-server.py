#!/usr/bin/env python3
import json
import signal
import threading
import sys

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


shared_live = "proxy" in sys.argv


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

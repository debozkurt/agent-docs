# tools.py
"""Four tools. Each emits tracing calls so verbose mode shows DB writes
and full row state. Sensitive tools do NOT contain gate logic — the graph
decides when to pause via policy.py."""
from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

import tracing
from db import connect, dump_rows, init_db, new_id, now


@tool
def list_contacts(query: Optional[str] = None) -> list[dict]:
    """Search the user's contact list. Returns matching contacts.

    Use this when the user references people by name or segment.

    Args:
        query: Substring to match against name, email, or segments.
    """
    init_db()
    tracing.trace_tool_call("list_contacts", {"query": query})
    conn = connect()
    try:
        if query:
            rows = conn.execute(
                "SELECT email, name, segments FROM contacts "
                "WHERE email LIKE ? OR name LIKE ? OR segments LIKE ? "
                "LIMIT 20",
                (f"%{query}%", f"%{query}%", f"%{query}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT email, name, segments FROM contacts LIMIT 20"
            ).fetchall()
        result = [{"email": e, "name": n, "segments": s.split(",")}
                  for (e, n, s) in rows]
        tracing.trace_tool_result("list_contacts", result)
        return result
    finally:
        conn.close()


@tool
def draft_message(recipient: str, subject: str, body: str) -> dict:
    """Create a local draft of a message. Nothing is sent.

    Always draft before sending — composition (cheap) before transmission
    (irreversible). Returns the draft_id for send_message.

    Args:
        recipient: Email address.
        subject: Subject line.
        body: Message body.
    """
    init_db()
    tracing.trace_tool_call("draft_message",
                            {"recipient": recipient, "subject": subject})
    draft_id = new_id("d")
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO drafts (draft_id, recipient, subject, body, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (draft_id, recipient, subject, body, now()),
        )
        conn.commit()
    finally:
        conn.close()

    # Verbose: show the full row just written.
    row = {"draft_id": draft_id, "recipient": recipient,
           "subject": subject, "body": body, "status": "drafted"}
    tracing.trace_db_write("drafts", row)

    result = {"draft_id": draft_id, "recipient": recipient, "subject": subject}
    tracing.trace_tool_result("draft_message", result)
    return result


@tool
def send_message(draft_id: str) -> dict:
    """Send a previously drafted message. IRREVERSIBLE.

    The pre-approval gate fires BEFORE this runs — by the time we get here,
    the human has already approved.

    Args:
        draft_id: From an earlier draft_message call.
    """
    init_db()
    tracing.trace_tool_call("send_message", {"draft_id": draft_id})
    conn = connect()
    try:
        row = conn.execute(
            "SELECT recipient, subject, body FROM drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
        if not row:
            result = {"status": "error", "reason": f"no draft {draft_id}"}
            tracing.trace_tool_result("send_message", result)
            return result
        message_id = new_id("m")
        conn.execute(
            "INSERT INTO sent_log (message_id, draft_id, sent_at) "
            "VALUES (?, ?, ?)",
            (message_id, draft_id, now()),
        )
        conn.execute(
            "UPDATE drafts SET status = 'sent' WHERE draft_id = ?",
            (draft_id,),
        )
        conn.commit()
    finally:
        conn.close()

    # Verbose: show sent_log row and updated draft.
    tracing.trace_db_write("sent_log",
                           {"message_id": message_id, "draft_id": draft_id})
    tracing.trace_db_state("sent_log", dump_rows("sent_log",
                           "draft_id = ?", (draft_id,)))

    result = {"status": "sent", "message_id": message_id,
              "recipient": row[0], "subject": row[1]}
    tracing.trace_tool_result("send_message", result)
    return result


@tool
def generate_campaign_list(segment_query: str) -> dict:
    """Generate a recipient list for a bulk campaign.

    The post-review gate fires AFTER this runs — the human sees the list
    before anything downstream uses it.

    Args:
        segment_query: e.g. "inactive users from Q3".
    """
    init_db()
    tracing.trace_tool_call("generate_campaign_list",
                            {"segment_query": segment_query})
    tokens = [t.strip().lower() for t in segment_query.split() if t.strip()]
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT email, name, segments FROM contacts"
        ).fetchall()
    finally:
        conn.close()
    matches = []
    for email, name, segments in rows:
        combined = (name + " " + segments + " " + email).lower()
        if all(tok in combined for tok in tokens):
            matches.append({"email": email, "name": name})
    result = {
        "list_id": new_id("L"),
        "segment": segment_query,
        "count": len(matches),
        "sample": matches[:5],
        "full_list": matches,
    }
    tracing.trace_tool_result("generate_campaign_list", result)
    return result

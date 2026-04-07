# Chapter 4 — MCP: Tools as a Protocol

[← Previous](./03-tools.md) · [Index](./README.md) · [Next →](./05-execution-loop.md)

## The concept

Chapter 3 treated tools as Python functions you bind to a model. That's the right mental model for *one* application. But the moment you want a tool to be reusable across applications — your agent, your IDE, your teammate's chatbot — defining it inline stops working. Every framework had its own tool format; nothing was portable.

The **Model Context Protocol (MCP)**[^mcp], introduced by Anthropic in late 2024 and now broadly adopted (Claude, ChatGPT, Cursor, VS Code, Claude Code, Goose, Warp), is the open standard that fixes this. It's worth its own chapter because it changes how you architect tool surfaces, not just how you wire them.

## The anatomy

MCP is a client-server protocol. Three roles:

- **MCP server** — a process that exposes a set of *tools*, *resources* (read-only data the model can pull in), and *prompts* (parameterized templates).
- **MCP client** — your agent or harness. It connects to one or more servers, discovers what they offer, and routes the model's tool calls to the right server.
- **Transport** — stdio (the server is a subprocess) or HTTP/SSE (the server is a network service). Same protocol either way.

The model still uses its normal tool-calling API. The client is what makes the bridge: when the model emits a tool call, the client looks up which server owns that tool and forwards the call. The server returns a result; the client appends it to the message list. From the model's perspective, nothing has changed.

```
┌────────┐    tool_call    ┌────────┐    JSON-RPC    ┌──────────────┐
│ Model  │ ──────────────► │ Client │ ─────────────► │ MCP Server   │
└────────┘                 │ (your  │                │ (postgres,   │
     ▲                     │ agent) │                │  github, fs) │
     │      result         └────────┘                └──────────────┘
     └─────────────────────────┘
```

## What you actually get

- **Portability.** A tool written once as an MCP server works in any MCP client. Build your "internal company knowledge" server once; your agent, your IDE, and your support bot all use it.
- **Ecosystem.** Public servers exist for filesystems, GitHub, Postgres, Slack, Notion, Google Drive, Sentry, and many more. You don't have to build them.
- **Process isolation.** A misbehaving tool can't crash your agent process. Servers can run as different users, with different secrets, on different machines.
- **A trust boundary.** This is the underrated one. The server is a *security boundary* — you decide what credentials it has, what it can reach, and what it returns. Your agent doesn't need the database password; the MCP server does.

## When to use MCP — and when not to

**Use MCP when:**

- The tool is reusable across more than one application or client.
- You want process isolation or a different credential scope from the agent.
- You're building on an ecosystem (your client is Claude Code, Cursor, ChatGPT, etc., which already speaks MCP).
- The tool surface is large and you'd rather discover it dynamically than hard-code it.

**Skip MCP (define tools inline) when:**

- The tool is single-use, internal to one agent.
- Performance is critical — an in-process Python call beats a JSON-RPC round trip every time.
- You need to share rich Python state (live DB connections, large in-memory objects) between the tool and the rest of your application.

## How this changes your architecture

Before MCP, "what tools does my agent have?" was answered by reading code. With MCP, the answer is "whatever servers it's connected to right now" — and that set can change between sessions, between users, even mid-session. This is powerful but introduces three new design questions:

1. **Discovery.** When a client connects, it asks the server what's available. You should expect tools to vary across users and *test for that*. Don't hard-code tool names in prompts; reference them from the discovery result.
2. **Trust.** A user-installed MCP server is *untrusted code with tool-calling power*. Treat its outputs the same way you'd treat user input: as a potential injection vector (more on this in Chapter 20).
3. **Versioning.** Servers evolve. Tool schemas change. Your agent code can't assume a server it connected to last month exposes the same surface today. Validate the discovered schema against expectations and fail loudly when it drifts.

## Heuristic

> **If a tool might ever be useful outside this one application, build it as an MCP server. If it's permanently glued to your app's internals, define it inline.**

## Key takeaway

MCP turns tools from app-internal functions into portable, isolated services with their own trust scope. The protocol itself is simple — a model still just calls a function — but the architectural shift (tools as a discoverable, swappable layer) is what makes it worth knowing even if you never write a server yourself.

[^mcp]: [Model Context Protocol](https://modelcontextprotocol.io) — open standard, multiple SDKs, broad client support across Claude, ChatGPT, Cursor, VS Code, and more.

[← Previous](./03-tools.md) · [Index](./README.md) · [Next: The execution loop →](./05-execution-loop.md)

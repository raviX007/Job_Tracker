# LLM Stack Rationale: Why Not LangChain / LangGraph

This project uses the **OpenAI SDK directly** + **Langfuse** for prompt management and tracing. This document explains why LangChain and LangGraph were evaluated and intentionally not adopted.

---

## What This Project's LLM Calls Actually Do

Every LLM interaction in this pipeline is a **single-turn, stateless call**:

| Call Site | Input | Output | Complexity |
|-----------|-------|--------|------------|
| Job analysis (`llm_analyzer.py`) | System prompt + JD text | Structured JSON (14 fields) | Single call, JSON mode |
| Cold email (`cold_email.py`) | Job + analysis + profile | Subject + body text | Single call |
| Cover letter (`cover_letter.py`) | Job + analysis + profile | Plain text | Single call |
| Startup analysis (`_startup_analyzer.py`) | Startup data + profile | JSON (relevance + profile) | Single call |

No multi-step reasoning. No tool use. No agent loops. No RAG retrieval chains. No conversation memory. No branching decision trees.

---

## What We Use Instead

| Concern | LangChain Would Provide | What We Use | Lines of Code |
|---------|------------------------|-------------|---------------|
| LLM calls | `ChatOpenAI` wrapper | `openai.AsyncOpenAI` directly | ~40 lines in `core/llm.py` |
| Structured output | `PydanticOutputParser` | OpenAI native `json_object` mode | Built-in, 1 line |
| Prompt templates | `PromptTemplate` / `ChatPromptTemplate` | Langfuse versioned prompts | Better — A/B testable, no deploy needed |
| Retry logic | `RetryChain` / callbacks | `tenacity` decorator | 5 lines |
| Tracing / observability | LangSmith | Langfuse `@observe` + auto-tracing | Already integrated |
| Pipeline orchestration | `SequentialChain` / LangGraph | Plain async Python (`pipeline.py`) | Explicit, debuggable |

**Total LLM client code: ~175 lines** across `core/llm.py` (client) and `core/langfuse_client.py` (prompt fetching + tracing).

---

## Why LangChain Doesn't Fit

### 1. Abstraction Without Benefit

LangChain wraps the OpenAI SDK to provide provider-agnostic LLM calls. We use **one provider** (GPT-4o-mini). The abstraction adds indirection without benefit:

```python
# What LangChain gives you
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
result = await llm.ainvoke(messages)

# What we do (same thing, no wrapper)
response = await self.openai_client.chat.completions.create(
    model=self.model, messages=messages, temperature=0.2
)
```

Same result. One fewer dependency. Direct stack traces on failure.

### 2. Dependency Bloat

LangChain pulls in a large dependency tree:

| Package | What It Adds |
|---------|-------------|
| `langchain-core` | Base abstractions, LCEL, runnables |
| `langchain-openai` | OpenAI wrapper |
| `langchain` | Chains, agents, memory |
| Transitive deps | pydantic, tenacity, jsonpatch, packaging, requests, etc. |

Our LLM stack: `openai` + `langfuse` + `tenacity`. Three packages, all directly useful.

### 3. Prompt Management Is Already Better

LangChain's prompt templates are code-level strings. Changing a prompt means changing code, committing, and deploying. Langfuse gives us:

- **Versioned prompts** editable in a web UI
- **A/B testing** between prompt versions
- **No-deploy prompt updates** — change prompts without touching code
- **Per-call tracing** — see exact prompts, tokens, latency, cost

This is strictly superior to LangChain's `PromptTemplate` for production use.

### 4. Debugging Overhead

When an LLM call fails with the direct SDK, the stack trace points to your code. With LangChain, you navigate through `RunnableSequence → RunnableParallel → ChatOpenAI → BaseChatModel → _generate → _agenerate` before reaching the actual error. [Multiple](https://www.octomind.dev/blog/why-we-no-longer-use-langchain-for-building-our-ai-agents) [production](https://community.latenode.com/t/why-im-avoiding-langchain-in-2025/39046) teams have cited this as a primary reason for removing LangChain.

### 5. Latency

LangChain's abstractions — message parsing, chain management, callback system, memory features (even if unused) — add measurable overhead per call. One [engineering team reported](https://community.openai.com/t/thoughts-on-replacing-langchain-with-native-orchestration-and-doubling-down-openai-apis-directly/1360207) cutting >1 second of latency per API call by removing LangChain's memory wrapper alone.

---

## Why LangGraph Doesn't Fit

LangGraph is for **stateful, multi-agent workflows with cycles** — think autonomous agents that use tools, backtrack, and maintain long-running state.

Our pipeline is:

```
scrape → dedup → filter → embed → analyze → save → email
```

That's a **linear pipeline**, not a graph. There are no:
- Agent loops (retry-with-different-strategy patterns)
- Tool use chains (LLM decides which tool to call)
- Multi-agent coordination (agents talking to each other)
- Stateful memory across turns
- Conditional cycles (go back to step 2 if step 5 fails)

LangGraph's abstractions (nodes, edges, state channels, checkpointers) would add complexity to express what is currently a straightforward `async def run()` method.

---

## Industry Context (2025-2026)

The trend is moving **away** from LangChain for simple use cases:

- A [2025 developer survey](https://sider.ai/blog/ai-tools/is-langchain-still-worth-it-a-2025-review-of-features-limits-and-real-world-fit) found that 45% of developers who experiment with LangChain never use it in production, and 23% who adopted it eventually removed it.
- [Octomind](https://www.octomind.dev/blog/why-we-no-longer-use-langchain-for-building-our-ai-agents) used LangChain in production for 12+ months before removing it, citing abstraction overhead and debugging difficulty.
- The [OpenAI developer community](https://community.openai.com/t/thoughts-on-replacing-langchain-with-native-orchestration-and-doubling-down-openai-apis-directly/1360207) increasingly recommends direct SDK usage for single-provider projects.
- LangChain itself now [recommends LangGraph](https://kanerika.com/blogs/langchain-vs-langgraph/) for anything beyond simple chains — acknowledging that plain LangChain chains are limited.

**LangChain makes sense when you need:** multi-provider abstraction, RAG with complex retrieval, agent-based tool use, or LangSmith integration. We need none of these.

---

## When We Would Reconsider

LangChain or LangGraph would become worth evaluating if:

1. **Multi-step agent reasoning** — e.g., LLM autonomously decides to scrape more data, re-analyze, or try a different email strategy
2. **Tool use chains** — e.g., LLM calls external APIs (search, web browse) as part of analysis
3. **Multi-provider needs** — e.g., using Claude for analysis and GPT for generation with a unified interface
4. **RAG pipeline** — e.g., retrieving from a vector store as part of job analysis
5. **Conversational interface** — e.g., chat-based job search with memory

None of these are on the roadmap. The pipeline's LLM needs are well-served by direct SDK calls.

---

## Summary

| Question | Answer |
|----------|--------|
| Do we need LangChain? | No — single provider, single-turn calls, no chains |
| Do we need LangGraph? | No — linear pipeline, no agent loops or cycles |
| What do we use? | OpenAI SDK + Langfuse + tenacity (~175 lines) |
| Is this a common choice? | Yes — direct SDK is the [recommended approach](https://community.openai.com/t/thoughts-on-replacing-langchain-with-native-orchestration-and-doubling-down-openai-apis-directly/1360207) for simple LLM integrations |

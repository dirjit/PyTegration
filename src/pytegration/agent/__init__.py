"""agent — the agentic / LLM-integration layer.

LESSON: Module 10 (Agentic / LLM Integration). See docs/10-agentic-llm.md
LAYER:  agent. Sits beside `services`: the agent ORCHESTRATES an LLM and a set of
        tools, where each tool is a thin wrapper around the SAME TaskService the
        REST API uses. The LLM never touches the database or business rules
        directly — it can only request tool calls, which we validate and execute.

THE BIG IDEA (tool calling / "function calling"):
    A modern LLM can be told "here are some tools you may use". Instead of
    answering directly, it can reply "please run tool X with these arguments".
    Your code runs the tool and feeds the result back. The model then continues,
    possibly calling more tools, until it produces a final answer. That
    request/run/feedback cycle is the AGENT LOOP (see loop.py).
    JAVA NOTE: there is no direct Java analog. The provider abstraction below,
    however, is a textbook Strategy pattern behind an interface.
"""

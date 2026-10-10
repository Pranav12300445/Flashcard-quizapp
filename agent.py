"""
agent.py — FlashMind, the Flashcard Quiz Agent (T26)

Autonomous plan-act-observe loop with real tool execution and session memory.
Primary engine: Groq   | Fallback engine: Google Gemini  (both via the OpenAI client)
"""
import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

from memory import FlashcardMemory
from tools import TOOLS_SCHEMA, add_card, get_stats, grade_answer, quiz_me

SYSTEM_PROMPT = """You are FlashMind, an autonomous flashcard quiz agent. Your only name is FlashMind.

YOUR TOOLS:
- add_card(question, answer): store a flashcard. Call once per card the user gives you.
- quiz_me(): choose the next card. It favours cards the user got wrong. Returns the question only.
- grade_answer(user_answer): grade the user's reply to the pending question and update their record.
- get_stats(): accuracy + weak cards. Call it before answering any question about progress.

CRITICAL RULES:
1. Never invent questions, answers or scores. Everything comes from tool results.
2. To start or continue a quiz, call quiz_me() and ask the question EXACTLY as returned. Never reveal the answer before the user replies.
3. ALWAYS call grade_answer(user_answer) with the user's EXACT reply text when they answer a quiz question. NEVER try to grade an answer yourself — only the tool knows which question is pending. Pass the user's raw answer as-is to grade_answer.
4. After grade_answer returns, tell the user if they were right. If wrong, show the correct answer from the tool result. Then IMMEDIATELY call quiz_me() to ask the next question, unless the user said stop or the message says it is the last card.
5. When quiz_me() reports a WEAK card, briefly tell the user you are re-asking it because they missed it earlier.
6. If the user adds cards, add all of them, then confirm the deck size.
7. If the user asks how they are doing, call get_stats() and name their weakest cards.
8. You are an AGENT: take multiple steps, use tools, make decisions. Do not just chat. Be concise and encouraging."""


class FlashcardAgent:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.groq_key = (api_key or os.environ.get("GROQ_API_KEY", "")).strip().strip('"').strip("'")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
        if self.groq_key:
            self._setup_groq(model)
        elif self.gemini_key:
            self._setup_gemini(model)
        else:
            raise ValueError("No API keys found. Set GROQ_API_KEY or GEMINI_API_KEY in your .env file.")
        self.memory = FlashcardMemory()
        self.step_log: list[str] = []

    def _setup_groq(self, model: str | None = None):
        self.provider = "Groq"
        self.model = model or os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
        self.client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=self.groq_key)
        print(f"Connected to [Groq] -> Model: {self.model}")

    def _setup_gemini(self, model: str | None = None):
        self.provider = "Google Gemini"
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=self.gemini_key)
        print(f"Connected to [Google Gemini] -> Model: {self.model}")

    def _call_llm(self, messages):
        return self.client.chat.completions.create(
            model=self.model, messages=messages, tools=TOOLS_SCHEMA, tool_choice="auto")

    def chat(self, user_message: str, verbose: bool = True) -> str:
        """Plan-act-observe loop: the LLM picks a tool, we run it, the result feeds the next step."""
        self.step_log = []
        self.memory.add_message("user", user_message)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.memory.get_messages())

        for step in range(1, 11):  # max 10 steps
            if verbose:
                self._log(f"\n{'=' * 50}\nSTEP {step} [{self.provider}: {self.model}]\n{'=' * 50}")
            try:
                response = self._call_llm(messages)
            except Exception as e:
                self._log(f"[{self.provider}] error: {e}")
                if self.provider == "Groq" and self.gemini_key:
                    self._log("Failing over to [Google Gemini]...")
                    self._setup_gemini()
                    response = self._call_llm(messages)
                else:
                    raise

            msg = response.choices[0].message

            # Exit condition: no tool requested -> this is the final answer
            if not msg.tool_calls:
                final = msg.content or ""
                self.memory.add_message("assistant", final)
                if verbose:
                    self._log(f"FINAL RESPONSE:\n{final}")
                return final

            # Act + observe
            messages.append(msg)
            for call in msg.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                if verbose:
                    self._log(f"TOOL CALL: {name}({json.dumps(args)})")
                result = self._execute_tool(name, args)
                if verbose:
                    self._log(f"TOOL RESULT: {result}")
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        fallback = "Reached step limit. Please clarify your request."
        self.memory.add_message("assistant", fallback)
        return fallback

    def _execute_tool(self, name: str, args: dict) -> str:
        try:
            if name == "add_card":
                return add_card(args["question"], args["answer"], self.memory)
            if name == "quiz_me":
                return quiz_me(self.memory)
            if name == "grade_answer":
                return grade_answer(args["user_answer"], self.memory)
            if name == "get_stats":
                return get_stats(self.memory)
            return json.dumps({"error": f"Unknown tool: {name}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _log(self, message: str) -> None:
        try:
            print(message)
        except UnicodeEncodeError:
            print(message.encode('utf-8', errors='replace').decode('utf-8'))
        self.step_log.append(message)

    def reset(self) -> None:
        self.memory.clear()
        self.step_log = []

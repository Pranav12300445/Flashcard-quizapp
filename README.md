# FlashMind — Flashcard Quiz Agent

**CSE476 · CA1 Project 1 · Topic T26 · Solo**

## What It Does

FlashMind is an AI-powered flashcard quiz app with a sleek dark-mode UI. Add flashcards, get quizzed by an intelligent agent that prioritizes your weakest cards, and track your progress — all in the browser.

## Features

- **Split-panel UI** — "Add Flashcards" panel on the left, "Question Me" quiz panel on the right
- **AI card creation** — Natural language card adding via LLM agent (e.g., "add card: What is H2O? = Water")
- **Bulk add** — Paste multiple cards at once in `Q? = A` format
- **Smart quizzing** — Weakness-weighted card selection (`3×wrong − right + staleness + new-card bonus`), never random
- **Deterministic grading** — Quiz grading bypasses the LLM entirely using direct API endpoints for 100% reliable results
- **Fuzzy matching** — Answers are graded with `difflib` similarity + keyword overlap, so typos and minor variations are accepted
- **Quiz summary** — After answering all cards, a summary card shows correct/wrong counts, accuracy %, and weak cards to review
- **Deck persistence** — Cards are saved to `deck_data.json` and survive page refreshes and server restarts
- **Card deletion** — Hover any card in the deck to reveal a delete button; deletions persist across refreshes
- **Reset** — Clears all cards, quiz progress, and the persistence file

## Tools

FlashMind calls real Python functions through OpenAI-compatible tool calling:

| Tool | Purpose |
|------|---------|
| `add_card(question, answer)` | Store a card in the deck |
| `quiz_me()` | Pick the next card by weakness score, return the question only |
| `grade_answer(user_answer)` | Grade the reply against the pending card, update right/wrong counters |
| `get_stats()` | Report accuracy and weak cards |

Every number the agent states comes from a tool result.

## Memory

Two layers persist across turns:

- **Layer 1 (Deck state)** — `dict` of cards with `right`, `wrong`, `last_asked`, plus the pending card ID. Tools read/write this, and it drives the re-quiz priority. Persisted to `deck_data.json` on every mutation.
- **Layer 2 (Conversation buffer)** — Rolling buffer of user/assistant messages injected into each LLM call. Ephemeral (not saved to disk).

A card missed in turn 3 is asked again more often in later turns, and "how am I doing?" is answered from stored counters.

## Architecture

```
index.html  ──►  /api/chat        → LLM agent (add cards, stats, conversation)
                 /api/start_quiz   → Direct quiz_me() call (no LLM)
                 /api/grade        → Direct grade_answer() + quiz_me() (no LLM)
                 /api/deck         → Return persisted deck
                 /api/delete_card  → Remove a card
                 /api/reset        → Clear everything
```

Quiz grading uses **direct API endpoints** that call the Python tool functions without going through the LLM, eliminating any possibility of the agent confusing which question is pending.

## One Honest Failure

Grading free-text answers with exact matching marked correct paraphrases as wrong, which wrongly raised a card's weakness score and made it return too often. I added fuzzy matching (`difflib` similarity plus key-word overlap in `tools.py`), which fixed typos and extra words, but heavy paraphrases can still be marked wrong; the correct answer is always shown so the user can see why.

## Run Locally

```bash
pip install -r requirements.txt
cp .env.example .env   # add your API key
python server.py       # → http://127.0.0.1:5000
```

Or open `demo.ipynb` for a notebook walkthrough.

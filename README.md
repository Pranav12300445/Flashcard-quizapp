# FlashMind — Flashcard Quiz Agent

**CSE476 · CA1 Project 1 · Topic T26 · Solo**

## Tools

FlashMind calls real Python functions through OpenAI-compatible tool calling. **`add_card(question, answer)`** stores a card in the session deck. **`quiz_me()`** picks the next card by a weakness score (`3×wrong − right + staleness + new-card bonus`), never at random, and returns the question without the answer. Two supporting tools complete the loop: **`grade_answer(user_answer)`** checks the reply against the pending card and updates its right/wrong counters, and **`get_stats()`** reports accuracy and weak cards. Every number the agent states comes from a tool result.

## Memory

Two layers persist across turns. **Layer 1** is the deck (`dict` of cards with `right`, `wrong`, `last_asked`, plus the pending card), which the tools read and write and which drives the re-quiz decision. **Layer 2** is the conversation buffer injected into each LLM call. A card missed in turn 3 is therefore asked again, more often, in turns 5-9, and "how am I doing?" is answered from the stored counters without the user repeating anything.

## One Honest Failure

*(Replace this with the failure you actually hit when you run it. Draft based on a limitation seen while testing:)* Grading free-text answers with exact matching marked correct paraphrases as wrong, which wrongly raised a card's weakness score and made it return too often. I added fuzzy matching (`difflib` similarity plus key-word overlap in `tools.py`), which fixed typos and extra words, but heavy paraphrases can still be marked wrong; the correct answer is always shown so the user can see why.

*Run locally:* `pip install -r requirements.txt`, copy `.env.example` to `.env`, add a key, then `python server.py` or open `demo.ipynb`.

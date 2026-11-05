# AI Professor (PoC)

```
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...        # Windows: set OPENAI_API_KEY=...

python parse.py chapter_5_clean.md         # 1. markdown -> topics.json   (instant, no AI)
python generate.py                         # 2. key points, MCQs, video queries -> content.json (one-off, ~17 LLM calls)
uvicorn server:app --reload                # 3a. FastAPI version: http://127.0.0.1:8000
python app_gradio.py                       # 3b. or the Gradio version: http://127.0.0.1:7860
```

Optional: `export YOUTUBE_API_KEY=...` to embed real YouTube results in the Videos tab
(otherwise it shows ready-made YouTube search links).

Models are configurable (defaults `gpt-4.1` for generation and chat, `gpt-4.1-mini` for the scope check): `GEN_MODEL`, `CHAT_MODEL`, `GUARD_MODEL`.

## How it works
- `parse.py` – headings become the tree (chapter / subchapter / example).
- `generate.py` – one LLM call per topic with strict JSON-schema output and validation. Resumable; edit
  `content.json` by hand to fix anything. `--only <id>` / `--force` to regenerate.
- `server.py` – `/api/topics`, `/api/videos/{id}`, `/api/chat`. Chat = cheap scope classifier first,
  then an answer grounded only in the chapter text (OpenAI caches the repeated chapter prefix automatically).
- `static/index.html` – tree, key points (core vs. supporting), source text, videos, quiz, chat.

## Known PoC limits
- Videos are searched, not guaranteed to match the text exactly.
- The source has no figures (Figure 5.1 etc. are referenced but missing).
- Whole chapter is sent with each chat turn; for a whole book, switch to retrieval per subchapter.

## Gradio version
`app_gradio.py` has the same features (tree, key points, source text, videos, quiz, scoped chat) and reuses the logic in `server.py`.
In Colab it prints a public `gradio.live` link automatically, so no tunnel is needed.

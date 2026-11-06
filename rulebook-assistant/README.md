# Rulebook Assistant

Answers questions from the Rulebook Agent document pack, with the exact source. There is no
search step: the whole pack is loaded once, cached, and reused for every question.

There are two routes:

- **No code:** Claude Projects. Follow [claude-project/SETUP.md](claude-project/SETUP.md).
- **Builder:** this app, which uses the Claude API with prompt caching and a simple web front end.

## Run the app

You need an API key from the Claude Console. From this folder, in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

The app asks for your key when it starts, unless `ANTHROPIC_API_KEY` is already set. The key
stays hidden and isn't saved. Then open http://127.0.0.1:5000. Each answer shows whether it
hit the cache.

## How it works

| Part | What it does |
| --- | --- |
| `pack.py` | Reads the Document Register, loads each Current file from `Data Sources`, and splits it into one block per paragraph or table row |
| `assistant.py` | Sends the pack with a cache marker after the last document, streams the answer, and maps citations back to document, version and text |
| `app.py` | Serves the page and the `/api/ask` stream |
| `static/index.html` | The chat page |

- **Citations** use the API's citations feature, so each source is text from the pack, down
  to the table row, rather than a reference the model wrote.
- **Refusals** start with exactly `Not in the rulebook`, and an `Escalate to:` line says who to
  ask. Conflicts between two rules start with `Conflict:` and show both sides without choosing.
  Both come from the instructions in `assistant.py`, so the model applies them; code doesn't
  enforce them.
- **Cache** lasts 1 hour and renews each time it is read. The first question after a gap pays
  to write the pack; the others read it.
- **Model** is `claude-opus-5-5`. Set `RULEBOOK_MODEL` to change it.
- **Fallback** is on: if the model declines a question, the API retries it on another model.
- **Conversations** are held in memory and are lost when the app restarts.

## Publish a new version

The Document Register decides what loads.

1. Add the new file to `Data Sources`.
2. In `Rulebook Agent Document Register.xlsx`, add its row as Current and mark the old row Superseded.
3. Restart the app. The sidebar shows the new versions and pack ID.
4. Run the tests.

The app won't start if a Current file is missing or a document has two Current versions.
It warns about files in `Data Sources` that aren't in the register, and doesn't load them.

## Test

```powershell
.venv\Scripts\python -m pytest tests
```

The tests use the real SDK against a fake API, so they need no key and cost nothing. They
check the pack and the request shape, not the quality of Claude's answers.

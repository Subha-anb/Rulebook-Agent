# Rulebook Agent

An AI assistant that answers questions from a company's standard document set, with the
exact source. It uses Cache-Augmented Generation (CAG): the whole rulebook is loaded once,
cached, and reused for every question, with no search engine in the middle. If the answer
isn't in the documents, it says `Not in the rulebook` and escalates. If two rules conflict,
it flags both.

| Folder or file | What it is |
| --- | --- |
| [rulebook-assistant](rulebook-assistant) | The app, using the Claude API with prompt caching and a simple web front end |
| [rulebook-assistant/claude-project](rulebook-assistant/claude-project) | The no-code route, using Claude Projects |
| [Data Sources](Data%20Sources) | The document pack |
| `Rulebook Agent Document Register.xlsx` | Which version of each document is current; the app reads this |
| `Rulebook Agent CAG vs RAG Decision Note.pdf` | Why CAG was chosen over RAG |

To run the app, see the [app README](rulebook-assistant/README.md).

The documents are fictional samples or simplified for testing. They are not legal advice.

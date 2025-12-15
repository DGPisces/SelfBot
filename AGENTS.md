# Repository Guidelines

## Project Structure & Module Organization
- `prompt.txt` holds the product brief; keep it concise and non-technical for stakeholders.
- `bot/` (planned) will contain runtime code: `discord/` adapters, `core/` pipeline, `llm/`, `asr/`, `storage/`, and `policy/`.
- `configs/` stores runtime settings (e.g., `config.yaml`); `.env.example` lists required secrets.
- `tests/` mirrors `bot/` layout; add fixtures under `tests/fixtures/`.
- `docker/` (optional) for Dockerfile/compose overrides; root `Dockerfile` preferred.

## Build, Test, and Development Commands
- Install: `python -m pip install -r requirements.txt` (use a virtualenv).
- Run locally: `python -m bot.main` with environment variables set from `.env`.
- Format/lint: `ruff check .` and `black .` (run both before commits).
- Tests: `pytest` (use `pytest -k name -vv` for focused runs).
- Docker: `docker compose up --build` to start the bot stack.

## Coding Style & Naming Conventions
- Python 3.11+; prefer async/await across Discord handlers and I/O.
- Use Black defaults (88 cols) and Ruff for linting; fix warnings or add minimal `# noqa` with reason.
- Naming: modules_snake_case, ClassNames in PascalCase, functions/vars in snake_case. Config keys in lower-kebab or snake, stay consistent per file.
- Docstrings: concise one-liners for public functions; add brief comments for non-obvious logic only.

## Testing Guidelines
- Framework: pytest with `asyncio` markers for async flows.
- Cover routing, safety/policy, context store, and LLM/ASR stubs; target ≥80% line coverage on new code.
- Name tests `test_<unit>.py`; prefer Arrange-Act-Assert structure; use fixtures for Discord event samples and stub providers.

## Commit & Pull Request Guidelines
- Commits: small, focused messages in imperative mood (e.g., `add router fallback`, `fix context ttl`).
- PRs: describe intent, main changes, and testing done; link issues/tasks; include screenshots or logs if UX/bot behavior changes.
- Keep config diffs called out explicitly (env vars, rate limits, channel scopes). Note any migrations or breaking changes.

## Security & Configuration Tips
- Never commit real tokens/keys; use `.env.example` placeholders and Git ignore rules.
- Minimize data exposure: scrub PII in logs/exports; ensure admin-only commands for data export/reset.
- Default to least privilege on Discord scopes and channel whitelists; document any required permissions updates in PRs.
- Use vitural environemnt during development

## Communication Preference
Always use chinese to communicate with me
# Contributing to Creamsicle: OS Buddy

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository and clone your fork.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install pytest
   ```
3. Run the test suite to verify your environment:
   ```bash
   python -m pytest tests/ -v
   ```

## Making Changes

- Keep changes focused — one fix or feature per pull request.
- Add or update tests for any logic you change in `flasher.py` or `app.py`.
- The test suite must pass before submitting (`python -m pytest tests/`).

## Adding a New Board

Open `flasher.py` and add an entry to the `BOARDS` dict:

```python
BOARDS = {
    ...
    "your-board-id": "Your Board Display Name",
}
```

The `board_id` must match the subdirectory name used in the Armbian archive URL:
`https://dl.armbian.com/<board_id>/archive/`

## Reporting Bugs

Open an issue and include:
- Your Windows version
- Python version (`python --version`)
- The SD card or USB drive model
- The full error message or screenshot

## Security Issues

Please do **not** open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) instead.

# FontMaker

FontMaker is a lightweight Python web application for designing Persian-first fonts with English support.

## Features

- Create new font projects from the browser
- Review existing font projects in a table view
- Open a studio with editable cell-based canvases for Persian forms (`isolated`, `initial`, `medial`, `final`)
- Edit English uppercase, lowercase, and digit glyphs alongside Persian glyphs
- Export a completed font package as JSON

## Run locally

```bash
python app.py
```

Then open `http://127.0.0.1:8000`.

## Run tests

```bash
python -m unittest discover -s tests
```
# LFY US Discount Researcher

Internal Streamlit app for US discount policy research.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.yml config.local.yml  # optional overrides
streamlit run app.py
```

Windows:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## API keys (optional)

Set keys in `.env` or environment variables. If no keys are provided, the app skips URL discovery and outputs INFERRED results.

```
SERPAPI_API_KEY=your_key_here
GOOGLE_CSE_API_KEY=your_key_here
GOOGLE_CSE_CX=your_cx_here
```

## Notes

- Upload a CSV or XLSX with a `brand` column (max 300).
- Outputs are stored under `runs/<run_id>/`.
- Download files from the UI after the run completes.

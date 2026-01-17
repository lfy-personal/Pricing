# LFY US Discount Researcher

Internal Streamlit app for US discount policy research.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt && streamlit run app.py
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt; streamlit run app.py
```

## API keys (optional)

Set keys in `.env` or environment variables. If no keys are provided, the app skips URL discovery and outputs INFERRED results.

```
SERPAPI_API_KEY=your_key_here
GOOGLE_CSE_API_KEY=your_key_here
GOOGLE_CSE_CX=your_cx_here
```

## Windows helpers

- `run.bat` starts the Streamlit app after your environment is activated.
- `run.ps1` starts the Streamlit app after your environment is activated.

## Notes

- Upload a CSV or XLSX with a `brand` column (max 300).
- Outputs are stored under `runs/<run_id>/`.
- Download files from the UI after the run completes.

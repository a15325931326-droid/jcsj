# jcsj

Scrape JCZQ football match data from NetEase sports.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/jczq_scraper.py --out jczq_matches.json --raw-html raw.html --verbose
```

## Notes

- If the page layout changes, save `--raw-html` and inspect it to adjust parsing.
- Some networks may require additional cookies or allowlist rules to access the page.

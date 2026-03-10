# E‑Commerce Scraper (Take‑Home Task)

Command line application that scrapes the Web Scraper static e‑commerce test site and outputs a single JSON object with all products and a total field.

## What it does

- Starts from `https://webscraper.io/test-sites/e-commerce/static`.
- Crawls all pages under that path.
- Extracts, for every product:
  - `name` (string)
  - `description` (string)
  - `price` (number)
  - `colors` (string array, only when multiple distinct colour options are detected)
- If a detail page exposes multiple HDD / storage options (e.g. `128GB`, `256GB`), each option is treated as a separate product entry with the configuration appended to the name.
- Outputs a single JSON object:
  - `results`: array of product objects
  - `total`: sum of all **unique** product prices in the `results` array.

The scraper uses straightforward HTML parsing with `requests` and `BeautifulSoup`. Listing pages are handled via the product thumbnail structure; detail pages are handled separately, with a best‑effort pass over storage and colour option widgets.

## Running the scraper

From the project directory:

```bash
pip install -r requirements.txt
python scraper.py --pretty > output.json
```

Options:

- `--pretty`: pretty‑prints the JSON with indentation.
- `--url`: override the starting URL (must stay under `https://webscraper.io/test-sites/e-commerce/static`).

By default the JSON is written to standard output so you can redirect it to a file as needed.


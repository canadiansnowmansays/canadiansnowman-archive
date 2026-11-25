# Canadian Snowman Says: The Archive

An independent backup of every essay Stephen Gordon has published at
[CanadianSnowmanSays on Substack](https://canadiansnowmansays.substack.com),
live at **https://canadiansnowmansays.github.io/canadiansnowman-archive/**.

## How it stays up to date

Nothing needs doing by hand. Every six hours, GitHub runs
`.github/workflows/publish.yml`, which:

1. reads the public Substack archive and saves any new essays into `src/data/`
   (once a week it also re-checks titles, subtitles and series);
2. picks up any new series on Substack, with its description and thumbnail;
3. rebuilds the whole site and its full-text search, and publishes it.

To force an update now: **Actions** tab → *Update and publish the archive* → **Run workflow**.

## What's where

| Path | What it is |
| --- | --- |
| `src/data/posts.json` | One record per essay: title, subtitle, date, Substack section, cover image |
| `src/data/posts/<number>.html` | The cleaned text of each essay (the actual backup) |
| `src/series.json` | Every series: name, short name, description, image, grouping, sort order |
| `src/series_overrides.json` | Optional hand corrections: `{"<essay number>": "Series Name"}` |
| `src/build.py` | Builds the site into `_site/` |
| `src/update.py` | Fetches new essays from Substack |
| `src/import_export.py` | One-time import from a Substack export zip |

Series come from the section each essay is filed under on Substack. Essays filed
under no section fall back to the May 2026 assignments, then the title prefix, then
*Essays & Dispatches*. Grouped sections (The Middle Kingdom, The Opera Cycle,
The AI Trials and Tribulations) are set with `"parent"` in `series.json`.

Photos are still served from Substack's image servers; the text, titles, dates and
series structure live here.

## Building locally

```
pip install beautifulsoup4
python src/build.py _site
npx -y pagefind@1.6.0 --site _site
python -m http.server -d _site
```

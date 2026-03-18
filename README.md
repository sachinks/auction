# ⚡ Sachin Kolige Premier League Auction Engine

A full-featured cricket auction and tournament management system built with Django.  
Handles team auctions, pool-based league fixtures, jersey management, and live public dashboards.

**Live:** https://auction-hyfq.onrender.com  
**Stack:** Django 4.2 · SQLite · Vanilla JS · ReportLab · openpyxl  
**Default login:** `sk` / `kpl2025`

---

## Features

### Auction
- Configurable bidding slots, base prices per role (AR / BAT / BOWL / PLY), and total team points
- **Automatic category ordering** — AR → BAT → BOWL → PLY (configurable)
- **Pass 1 → Rebid → Pass 2** flow with transition banners and admin confirmation
- **Icon category blocking** — teams that already own an AR/BAT/BOWL are blocked in Pass 1
- **Unsafe bid warning** — flags bids that would leave a team unable to fill remaining slots
- **Force Sell** — override validation when needed (admin decision)
- **Undo** last action with full point refund
- **Refresh Points** — recalculate all team wallets from DB (fixes any corruption)
- Live AJAX updates — sell/unsold/not-playing without page reload
- Complete **Auction Summary** page post-auction

### Players & Teams
- **CSV import** with validate-only (dry-run) mode before committing
- Import players (name, role, phone, place) or teams (name, short\_name, owners)
- **Demo data loader** — 4 bundled CSVs committed to the repo, loadable from the UI with one click (works on Render too)
  - `short_players.csv` — 30 players for quick testing
  - `short_teams.csv` — 4 Sachin Kolige Premier League local teams
  - `long_players.csv` — 249 real IPL player names
  - `long_teams.csv` — 16 teams (10 IPL franchises + 6 local)

### Pools & Fixtures
- **Configure pools** — set number of pools, teams per pool, teams advancing, and assignment order
- **Spin wheel team assignment** — auto-assigns to correct pool based on chosen order:
  - *Sequential*: fill Pool A completely, then Pool B, etc.
  - *Round Robin*: one team per pool per spin, repeat
- **Admin adjustment** — move teams between pools before fixtures are drawn
- **Generate fixtures** — circle-method round-robin within each pool (maximum rest guaranteed)
- **Day-pair interleaved schedule** — Pool A + B on Day 1, Pool C + D on Day 2; matches alternate A/B within each day
- **No consecutive matches** for any team — verified by test suite
- Match results — admin records winner or draw via modal; points table updates live
- **Points table** per pool (Played / Won / Lost / Points)

### Jersey Management
- Per-player jersey name, jersey number, size (number ↔ text, bidirectional sync), sponsor
- **Size mapping** — configure number-to-text mapping (e.g. 40→M, 42→L), editable in the admin UI
- Extra team members (coach, manager) and organisers — same jersey fields
- **Team-wise PDF export** with sponsor column

### Reports
- All Players — full player list with role filter, PDF + Excel
- Auction Results — with status filter (SOLD / UNSOLD / NOT PLAYING), PDF + Excel
- Team-wise — squad breakdown per team, PDF + Excel

### Public Dashboard (`/`)
- **Pre-auction**: team list with owners, full player register by role
- **Live auction**: current player on block, all team grids with wallet and squad
- **Post-auction**:
  - Pool standings (team names before matches, points table once results start)
  - League fixture schedule — interleaved, day-pair two-column layout with Pool badge
  - Squad cards grouped by pool — serial #, player name, jersey name, jersey number
- Auto-refreshes every 5 seconds

### Logging
Three rotating log files in `logs/` (max 1 MB each, 5 backups):
- `auction.log` — every sell, unsold, undo, match result
- `system.log` — admin actions, CSV imports, pool/fixture operations
- `error.log` — all exceptions with full traceback

Configure in `config/log_settings.py`. On Render, console output is disabled automatically.

---

## Quick Start (Local)

```bash
git clone <repo>
cd kpl

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

python dev_reset.py               # creates DB, runs migrations, creates superuser sk/kpl2025

python manage.py runserver
```

Open http://127.0.0.1:8000 — public board  
Open http://127.0.0.1:8000/auction/ — admin panel

### Load demo data

Go to **CSV Upload** → **Load Demo Data** → select a file → click **Load Selected Demo File**.

Or from the shell:
```bash
python manage.py shell -c "
from auction.services.csv_service import CSVService
CSVService().import_teams('sample_data/short_teams.csv')
CSVService().import_players('sample_data/short_players.csv')
"
```

---

## Deployment (Render)

1. Push to GitHub
2. New Web Service → connect repo
3. **Build command:** `./build.sh`
4. **Start command:** `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
5. Set environment variable: `RENDER=true`

`build.sh` runs: `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate && python manage.py shell -c "..."` (creates superuser sk/kpl2025 if not exists)

---

## Makefile Shortcuts

A `Makefile` is included for common dev tasks. Instead of typing long commands, just use `make <command>`.

| Command | What it does |
|---------|-------------|
| `make reset` | Wipe DB, re-migrate, recreate superuser (dev only) |
| `make migrate` | Run migrations |
| `make test` | Run all pytest tests — **auto-skipped on Render/production** |
| `make check` | Django config/syntax check (fast, no DB needed) |
| `make shell` | Open Django shell |
| `make logs` | Tail all 3 log files live (`auction`, `system`, `error`) |
| `make clean` | Delete `.pyc` files and `__pycache__` folders |
| `make fresh` | **Full restart** — clean → reset → test |
| `make help` | Show all available commands |

**How `make test` works:**
```bash
make test
# Runs pytest locally (RENDER not set)
# Automatically skips on Render where RENDER=true
```

> No internet or data usage — all commands run locally on your machine.

---

## Running Tests

```bash
pip install pytest pytest-django
pytest auction/tests/ -v
```

151 tests across 8 modules:

| Module | Tests | Covers |
|--------|-------|--------|
| `test_models.py` | 15 | Point deduction/refund/switch, get\_short, singleton, pool fields |
| `test_auction_engine.py` | 16 | Round labels, blocked teams, recalculate points, activate |
| `test_bidding_service.py` | 23 | Bid validation, sell, force-sell, unsold, auto-drop, undo |
| `test_csv_service.py` | 21 | Import/validate players & teams, error handling, sample files |
| `test_fixture_service.py` | 27 | Pool creation, schedule generation, no-consecutive-match proof |
| `test_jersey_service.py` | 11 | Jersey fields, extra members, PDF export, AJAX save |
| `test_report_service.py` | 11 | PDF and Excel for all report types |
| `test_views.py` | 27 | HTTP status codes, AJAX endpoints, pool/fixture/result flows |

---

## URL Reference

| URL | Description |
|-----|-------------|
| `/` | Public board (TV display) |
| `/auction/` | Auction control panel |
| `/auction/start/` | Create tournament config |
| `/auction/next/` | Advance to next player (AJAX) |
| `/auction/sell/` | Sell player (AJAX) |
| `/auction/unsold/` | Mark unsold (AJAX) |
| `/auction/not-playing/` | Mark not playing (AJAX) |
| `/auction/undo/` | Undo last action |
| `/auction/refresh/` | Recalculate team points |
| `/auction/complete/` | Mark auction complete |
| `/auction/summary/` | Post-auction summary |
| `/auction/upload-csv/` | Import players / teams CSV |
| `/auction/audit-log/` | Action history |
| `/auction/banner/` | Upload banner / tournament settings |
| `/fixtures/pools/` | Pool config + spin assignment + fixture schedule |
| `/fixtures/draw/generate/` | Generate all pool fixtures |
| `/fixtures/draw/reset/` | Clear all fixtures (keep pools) |
| `/fixtures/draw/result/` | Record match result (AJAX) |
| `/jersey/` | Jersey management |
| `/jersey/pdf/` | Export jersey PDF |
| `/reports/` | Report download centre |
| `/admin/` | Django admin |

---

## Project Structure

```
kpl/
├── auction/
│   ├── models.py               # Player, Team, TournamentConfig, AuctionState,
│   │                           #   Match, TournamentPool, PoolTeam, Jersey,
│   │                           #   ExtraJerseyMember, AuctionAction
│   ├── views.py                # All HTTP views and AJAX endpoints
│   ├── urls.py                 # 41 URL routes
│   ├── services/
│   │   ├── auction_engine.py   # Phase transitions, player picking, blocked teams
│   │   ├── bidding_service.py  # Sell, unsold, not-playing, undo, validation
│   │   ├── csv_service.py      # CSV import/validate for players and teams
│   │   ├── fixture_service.py  # Pool creation, round-robin, interleaved schedule
│   │   ├── jersey_service.py   # PDF export
│   │   ├── report_service.py   # PDF + Excel reports
│   │   └── rebid_service.py    # Rebid pool helpers
│   └── tests/
│       ├── conftest.py         # Shared pytest fixtures
│       ├── test_models.py
│       ├── test_auction_engine.py
│       ├── test_bidding_service.py
│       ├── test_csv_service.py
│       ├── test_fixture_service.py
│       ├── test_jersey_service.py
│       ├── test_report_service.py
│       └── test_views.py
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── log_settings.py         # Tune log levels, rotation, console output
│   ├── error_settings.py       # Error display policy (local vs Render)
│   └── logging_config.py       # Builds the 3 loggers from log_settings
├── templates/                  # All HTML templates (dark theme)
├── static/                     # CSS, JS, images
├── sample_data/                # Bundled CSV files (committed to git)
│   ├── short_teams.csv
│   ├── short_players.csv
│   ├── long_teams.csv
│   └── long_players.csv
├── logs/                       # Runtime log files (gitignored)
├── media/                      # Uploaded banners (gitignored)
├── dev_reset.py                # Local dev reset — wipes DB and re-migrates
├── build.sh                    # Render build script
├── pytest.ini
└── requirements.txt
```

---

## Configuration

### Tournament Settings (`/auction/banner/`)
- Tournament name, match date, banner image

### Auction Config (`/auction/start/`)
- Total team points
- Bidding slots (max squad size)
- Base prices per role
- Max rebid attempts for PLY
- Category order

### Log Settings (`config/log_settings.py`)
- `DEFAULT_LOG_LEVEL` — INFO by default, override with `LOG_LEVEL` env var
- `LOG_MAX_BYTES` — 1 MB default, override with `LOG_MAX_BYTES` env var
- `CONSOLE_ENABLED` — True locally, False on Render (auto-detected)

### Error Settings (`config/error_settings.py`)
- `EXPOSE_API_ERRORS` — full exception in JSON responses locally, generic message on Render
- `SHOW_TRACEBACKS` — traceback in error pages locally only

---

## Superuser

Default: **`sk`** / **`kpl2025`**  
Created automatically by `dev_reset.py` and `build.sh`.

To create manually:
```bash
python manage.py createsuperuser
```

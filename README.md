# ⚡ Sachin Kolige Premier League Auction Engine

A full-featured cricket auction and tournament management system built with Django.
Handles team auctions, pool-based league fixtures, jersey management, and live public dashboards.

**Live:** https://auction-hyfq.onrender.com
**Stack:** Django 6.0.3 · SQLite · Vanilla JS · ReportLab · openpyxl
**Default login:** `sk` / *****

---

## Features

### Auction Flow

Each auction category follows a strict phase sequence managed by `AuctionEngine`.

#### ICON Categories (AR · BAT · BOWL) — 3-phase flow

```
Main Round  →  Rebid Round  →  Spin Round
```

1. **Main Round** — All available players go on the block one by one (random pick). Teams that already own an icon of that role are blocked from bidding. Once the pool is exhausted, a transition modal fires.
2. **Rebid Round** — All unsold players from the Main Round get another chance, one by one. Players that reach `max_rebid_attempts` without being sold remain `UNSOLD` and move to the Spin Round.
3. **Spin Round** — No player goes on the block individually. Instead a dual spin board appears:
   - **Left panel** — all remaining unsold ICON players for the current category
   - **Right panel** — all teams that do not yet have a sold player in this ICON role
   - The auction engine returns `None` for `current_player` during this phase — no player card appears on the block
   - Press **SPIN PLAYER** — the left panel animates (bounce highlight) and lands on a random player
   - Press **SPIN TEAM** — the right panel animates and lands on a random team
   - Both spins must complete before **Confirm** is enabled
   - Press **Confirm** — the selected player is sold to the selected team at base price; both cells are removed from their panels
   - The page does **not** reload after each assignment — spins continue without interruption until either panel empties
   - When either panel is empty (all teams assigned or all players distributed), the page reloads and the auction advances to the next category
   - **Public board** shows `🎰 SPIN ROUND / GOING ON` instead of "Waiting for next player…" throughout this phase

After all three ICON rounds complete → transition message: `"All ICON Rounds complete · Starting Player Round"`

#### PLY Category (Players) — 2-phase flow

```
Main Round  →  Rebid Round  (→ Spin Board if unsold remain)
```

- Main Round: players go on the block until pool exhausted
- Rebid Round: unsold players get extra attempts up to `max_rebid_attempts`
- **PLY Spin Board** (if unsold remain after rebid): same dual spin-board mechanic as ICON Spin Round
  - Left panel: all remaining AVAILABLE + UNSOLD PLY players
  - Right panel: all teams that still have slots available
  - Spin player → spin team → confirm → both removed from panels; no reload until a panel empties
  - PLY Spin Board is separate from ICON Spin (triggered by `show_ply_spin_btn` flag, not `PHASE_SPIN`)

#### PLY Round Team Blocking

During the PLY round, once a team fills all its `bidding_slots`, its bid button is **disabled** until every other team has also filled their slots. Once all teams are at capacity, all buttons re-enable for overflow bidding. This prevents one team from hoarding extra players while others still need their quota.

#### Spin Round — Technical Detail

| Aspect | ICON Spin Round | PLY Spin Board |
|--------|----------------|----------------|
| **Trigger** | After REBID exhausted, unsold ICON players remain AND teams without the role exist | After REBID exhausted, AVAILABLE/UNSOLD PLY players remain |
| **Phase** | `AuctionState.PHASE_SPIN` | Still `PHASE_MAIN` / `PHASE_REBID` (separate flag) |
| **Left panel** | Unsold ICON players for current category | Available + Unsold PLY players |
| **Right panel** | Teams without a sold player of this ICON role | Teams with slots remaining |
| **Auto-reload** | Suppressed during spin (no 4-second auto-reload) | Suppressed during spin |
| **On confirm** | Player sold at base price; both cells removed from DOM | Player sold at base price; both cells removed from DOM |
| **Page reload** | Only when either panel is empty | Only when either panel is empty |
| **Public board** | 🎰 SPIN ROUND / GOING ON | 🎰 SPIN ROUND / GOING ON |
| **After complete** | Transition to next ICON category (or Player Round) | Auction advances normally |

**Spin animation** (`_srBounce`):
- Shared animation function used by both ICON and PLY spin
- Bounces a highlight across all cells for `duration` ms, then lands on `winnerIdx`
- Applies `sr-winner` CSS class with `@keyframes srWin` glow animation
- Duration: ~3.2 seconds — auto-reload is explicitly suppressed during this window to prevent the animation from being interrupted

**Why auto-reload is suppressed:**
The control panel normally reloads every 4 seconds when `current_player` is `None` and no transition is pending. During spin rounds, `current_player` is always `None`, which would trigger the reload and cancel the spin animation mid-bounce. The condition `{% if not show_spin_round %}` (and equivalent for PLY) wraps the `setTimeout(reload, 4000)` call to prevent this.

#### Phase Transition Modals

Between every phase, an admin-confirmation modal pauses the auction:

| Transition | Icon | Colour | Button label |
|------------|------|--------|--------------|
| → Rebid Round | 🔄 | Orange | Start Rebid Round → |
| → Spin Round | 🎰 | Purple | Start SPIN Round → |
| → Next category | ⚡ | Default | Continue → |
| → Auction Done | ✅ | Default | Continue → |

---

### Auction Control Panel

- **Configurable** bidding slots, base prices per role, total team points, category order
- **Icon category blocking** — teams that already own an AR / BAT / BOWL are blocked from bidding for the same role
- **Unsafe bid warning** — flags bids that would leave a team unable to fill remaining slots
- **Force Sell** — override the safety validation when needed (admin decision)
- **Undo** last action with full point refund
- **Refresh Points** — recalculates all team wallets from the database (AJAX, no page redirect)
- **Live AJAX** updates — sell / unsold / not-playing without page reload
- Complete **Auction Summary** page post-auction

---

### Players & Teams

- **CSV import** with validate-only (dry-run) mode before committing
- Import players (name, role, phone, place) or teams (name, short\_name, owners)
- **Demo data loader** — 6 bundled CSVs committed to the repo, loadable from the UI with one click

| Dataset | Teams | Players | Composition |
|---------|-------|---------|-------------|
| `small` | 4 | 20 | 4 AR + 4 BAT + 4 BOWL + 8 PLY (IPL players) |
| `medium` | 8 | 40 | 8 AR + 8 BAT + 8 BOWL + 16 PLY |
| `large` | 16 | 96 | 16 AR + 16 BAT + 16 BOWL + 48 PLY |

---

### Pools & Fixtures

- **Configure pools** — number of pools, teams per pool, teams advancing, and assignment order
- **Spin wheel team assignment** — auto-assigns to the correct pool:
  - *Sequential*: fill Pool A completely, then Pool B, etc.
  - *Round Robin*: one team per pool per spin, repeat
- **Admin adjustment** — move teams between pools before fixtures are drawn
- **Generate fixtures** — circle-method round-robin within each pool (maximum rest guaranteed)
- **Day-pair interleaved schedule** — Pool A + B on Day 1, Pool C + D on Day 2; matches alternate A/B within each day
- **No consecutive matches** for any team — verified by test suite
- Match results — admin records winner or draw via modal; points table updates live
- **Points table** per pool (Played / Won / Lost / Points)
- Knockout stages: QF, SF, Final

---

### Jersey Management

#### Player Jerseys
- Per-player: jersey name (name printed on jersey), jersey number, size (number ↔ text, bidirectional sync), sponsor
- **Size mapping** — configure number-to-text mapping (e.g. 40 → M, 42 → L), editable in the admin UI

#### Extra Members
- **Team staff** — manager, coach, supporter etc. (linked to a team)
- **Organisers** — volunteers, officials, etc. (grouped as "Organisers")
- Same jersey fields as players

#### Export Board (single unified panel)

Three export options in one card panel at the top of the Jersey Management page:

| Option | Description | Formats |
|--------|-------------|---------|
| **Players** | Team & category-wise list for all sold players (AR / BAT / BOWL / PLY). Jersey name, number, size, sponsor. | PDF · Excel |
| **Staff & Organisers** | Team staff (managers, coaches) grouped by team, plus all tournament organisers and volunteers. | PDF · Excel |
| **Complete Jersey List** | Everything above combined — players + staff + organisers, teamwise, in one document. | PDF |

---

### Public Dashboard (`/`)

- **Pre-auction** — team list with owners, full player register by role
- **Live auction** — current player on block, all team grids with wallet and squad
- **Spin Round** — shows `🎰 SPIN ROUND / GOING ON` instead of "Waiting for next player..." (applies to both ICON and PLY spin rounds)
- **Post-auction** — pool standings, league fixture schedule, squad cards grouped by pool

#### Player display on squad cards

Each sold player is shown as:
```
#serial_number   Player Name           (bold, role colour)
                 Jersey name   jersey_number
```
- Serial number is always shown and never replaced by the jersey number
- Jersey name and jersey number appear below the player name once jerseys are assigned
- Size details are not shown on the public board

- **Auto-refreshes** every 5 seconds

---

### Reports

- **All Players** — full player list with role filter, PDF + Excel
- **Auction Results** — with status filter (SOLD / UNSOLD / NOT PLAYING), PDF + Excel
- **Team-wise** — squad breakdown per team, PDF + Excel

---

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
cd auction

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
CSVService().import_teams('sample_data/small_teams.csv')
CSVService().import_players('sample_data/small_players.csv')
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

| Command | What it does |
|---------|-------------|
| `make reset` | Wipe DB, re-migrate, recreate superuser (dev only) |
| `make migrate` | Run migrations |
| `make test` | Run all pytest tests — auto-skipped on Render/production |
| `make check` | Django config/syntax check (fast, no DB needed) |
| `make shell` | Open Django shell |
| `make logs` | Tail all 3 log files live (`auction`, `system`, `error`) |
| `make clean` | Delete `.pyc` files and `__pycache__` folders |
| `make fresh` | **Full restart** — clean → reset (run `make test` separately) |
| `make help` | Show all available commands |

**Migration strategy (dev):**
- `0001_initial.py` is the only migration file — always committed to git
- `make fresh` wipes the DB and re-applies it; never accumulates `0002_` etc.
- `make test` detects model changes and auto-regenerates `0001_initial.py` before running tests
- When moving to production (PostgreSQL), switch to accumulating migrations

---

## Running Tests

```bash
pip install pytest pytest-django
pytest auction/tests/ -v
```

| Module | Tests | Covers |
|--------|-------|--------|
| `test_models.py` | 15 | Point deduction/refund/switch, get\_short, singleton, pool fields |
| `test_auction_engine.py` | 16 | Round labels, blocked teams, recalculate points, activate, phase transitions |
| `test_bidding_service.py` | 23 | Bid validation, sell, force-sell, unsold, auto-drop, undo |
| `test_csv_service.py` | 23 | Import/validate players & teams, error handling, all 6 sample files |
| `test_fixture_service.py` | 27 | Pool creation, schedule generation, no-consecutive-match proof |
| `test_jersey_service.py` | 11 | Jersey fields, extra members, PDF export, AJAX save |
| `test_report_service.py` | 11 | PDF and Excel for all report types |
| `test_views.py` | 19 | HTTP status codes, AJAX endpoints, pool/fixture/result flows |

---

## URL Reference

| URL | Description |
|-----|-------------|
| `/` | Public board (TV display) |
| `/auction/` | Auction control panel |
| `/auction/start/` | Create tournament config |
| `/auction/continue/` | Confirm phase transition |
| `/auction/next/` | Advance to next player (AJAX) |
| `/auction/sell/` | Sell player (AJAX) |
| `/auction/unsold/` | Mark unsold (AJAX) |
| `/auction/not-playing/` | Mark not playing (AJAX) |
| `/auction/spin-round/` | Assign spin round player to team (AJAX) |
| `/auction/undo/` | Undo last action |
| `/auction/refresh/` | Recalculate team points (AJAX) |
| `/auction/complete/` | Mark auction complete |
| `/auction/summary/` | Post-auction summary |
| `/auction/upload-csv/` | Import players / teams CSV |
| `/auction/load-sample/` | Load bundled demo data |
| `/auction/audit-log/` | Action history |
| `/auction/banner/` | Upload banner / tournament settings |
| `/auction/reset/` | Reset auction to initial state |
| `/auction/debug/` | Debug auction state |
| `/fixtures/pools/` | Pool config + spin assignment + fixture schedule |
| `/fixtures/pools/create/` | Create new pool |
| `/fixtures/pools/reset/` | Reset pools (keep teams) |
| `/fixtures/pools/generate/` | Generate matches for a pool |
| `/fixtures/pools/generate-all/` | Generate all pool matches |
| `/fixtures/pools/advance/` | Advance teams from pool results |
| `/fixtures/pools/team-add/` | Add team to pool |
| `/fixtures/pools/team-remove/` | Remove team from pool |
| `/fixtures/pools/spin-assign/` | Spin-wheel team assignment to pool |
| `/fixtures/pools/result/` | Record pool match result |
| `/fixtures/knockout/` | Create knockout stage |
| `/fixtures/draw/` | Fixture draw viewer |
| `/fixtures/draw/generate/` | Generate all fixtures |
| `/fixtures/draw/spin-next/` | Spin next match |
| `/fixtures/draw/reset/` | Clear all fixtures |
| `/fixtures/draw/result/` | Record fixture result |
| `/jersey/` | Jersey management portal |
| `/jersey/save/` | Save player jersey (AJAX) |
| `/jersey/save-extra/` | Save extra member jersey (AJAX) |
| `/jersey/size-mapping/` | Configure size number ↔ text mapping |
| `/jersey/players/pdf/` | Players jersey PDF |
| `/jersey/players/excel/` | Players jersey Excel |
| `/jersey/organisers/pdf/` | Staff & organisers jersey PDF |
| `/jersey/organisers/excel/` | Staff & organisers jersey Excel |
| `/jersey/combined/pdf/` | Complete jersey list PDF |
| `/reports/` | Report download centre |
| `/reports/download/` | Download report (PDF / Excel) |
| `/admin/` | Django admin |

---

## Data Models

| Model | Purpose |
|-------|---------|
| `Team` | Team name, short name, owners, remaining points (wallet) |
| `Player` | Name, role, base price, sold price, status, rebid count |
| `TournamentSettings` | Singleton — tournament name, dates, banner image |
| `TournamentConfig` | Created on auction start — points, slots, base prices, category order, max rebid attempts, size mapping |
| `AuctionState` | Singleton — current phase, category, pass, player on block, transition flags |
| `AuctionAction` | Audit trail — every sell, unsold, undo with timestamp |
| `Jersey` | Per-player jersey name, number, size, sponsor |
| `ExtraJerseyMember` | Team staff and organisers jersey details |
| `Match` | Fixture — team1, team2, result, pool FK |
| `TournamentPool` | Pool/group stage — teams, advancement rules |
| `PoolTeam` | Pool membership with seeding and advancement tracking |

### TournamentConfig fields

| Field | Default | Purpose |
|-------|---------|---------|
| `total_points` | 10 000 | Budget per team |
| `bidding_slots` | 11 | Standard squad size (disables team button once full until all teams fill) |
| `max_squad_size` | 13 | Hard cap per team |
| `base_price_AR` | 1 000 | Base price for All Rounders |
| `base_price_BAT` | 400 | Base price for Batsmen |
| `base_price_BOWL` | 400 | Base price for Bowlers |
| `base_price_PLY` | 100 | Base price for Players |
| `category_order` | `AR,BAT,BOWL,PLY` | Auction sequence (configurable) |
| `max_rebid_attempts` | 2 | Max rebid rounds before ICON goes to Spin / PLY stays unsold |
| `size_mapping` | `{"36":"XS",...}` | Jersey size number → text mapping |

---

## Project Structure

```
auction/
├── auction/
│   ├── models.py               # All 11 data models
│   ├── views.py                # All HTTP views and AJAX endpoints
│   ├── urls.py                 # 41+ URL routes
│   ├── services/
│   │   ├── auction_engine.py   # Phase transitions, player picking, blocked teams, spin logic
│   │   ├── bidding_service.py  # Sell, unsold, not-playing, undo, bid validation
│   │   ├── csv_service.py      # CSV import/validate for players and teams
│   │   ├── fixture_service.py  # Pool creation, round-robin, interleaved schedule
│   │   ├── jersey_service.py   # PDF + Excel exports for jerseys
│   │   ├── report_service.py   # PDF + Excel for auction and player reports
│   │   └── rebid_service.py    # Rebid pool helpers
│   └── tests/
│       ├── conftest.py
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
│   ├── small_teams.csv         # 4 teams
│   ├── small_players.csv       # 20 players
│   ├── medium_teams.csv        # 8 teams
│   ├── medium_players.csv      # 40 players
│   ├── large_teams.csv         # 16 teams
│   └── large_players.csv       # 96 players
├── logs/                       # Runtime log files (gitignored)
├── media/                      # Uploaded banners (gitignored)
├── dev_reset.py                # Local dev reset — wipes DB and re-migrates
├── build.sh                    # Render build script
├── Makefile
├── pytest.ini
└── requirements.txt
```

---

## Configuration

### Tournament Settings (`/auction/banner/`)
- Tournament name, match date, banner image

### Auction Config (`/auction/start/`)
- Total team points, bidding slots, max squad size
- Base prices per role (AR / BAT / BOWL / PLY)
- Max rebid attempts
- Category order

### Log Settings (`config/log_settings.py`)
- `DEFAULT_LOG_LEVEL` — INFO by default, override with `LOG_LEVEL` env var
- `LOG_MAX_BYTES` — 1 MB default
- `CONSOLE_ENABLED` — True locally, False on Render (auto-detected)

### Error Settings (`config/error_settings.py`)
- `EXPOSE_API_ERRORS` — full exception in JSON responses locally, generic message on Render
- `SHOW_TRACEBACKS` — traceback in error pages locally only

---

## Superuser

Default: **`sk`** / **`kpl2025`**
Created automatically by `dev_reset.py` and `build.sh`.

```bash
python manage.py createsuperuser
```

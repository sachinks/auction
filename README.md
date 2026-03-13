# KPL — Kolige Premier League Auction Engine

Self-hosted Django auction engine for the Kolige Premier League cricket tournament.
Runs entirely on a local machine. No internet required during the event.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Reset DB and create superuser (run once, or after any model change)
python dev_reset.py

# 3. Start server
python manage.py runserver
```

- **Auctioneer screen:** http://127.0.0.1:8000/auction/
- **Public TV board:**   http://127.0.0.1:8000/
- **Django admin:**      http://127.0.0.1:8000/admin/  (sk / sk)

---

## Requirements

```
Django>=4.2
pytest
pytest-django
reportlab
Pillow
```

> On Ubuntu/WSL with "externally managed environment" error:
> ```bash
> pip install -r requirements.txt --break-system-packages
> ```

---

## Project Layout

```
kpl/
├── auction/
│   ├── models.py                 # All data models
│   ├── admin.py                  # Admin panel customisation
│   ├── views.py                  # All view/endpoint functions
│   ├── urls.py                   # URL patterns
│   ├── migrations/               # Auto-generated — do not edit manually
│   ├── services/
│   │   ├── auction_engine.py     # Core flow: phases, passes, transitions
│   │   ├── bidding_service.py    # Sell, unsold, not-playing, undo, validation
│   │   ├── csv_service.py        # CSV import + validation (players & teams)
│   │   ├── jersey_service.py     # ReportLab PDF generation
│   │   └── audit_service.py      # Action log queries
│   ├── tests/
│   │   ├── test_models.py        # Player.save() point logic
│   │   ├── test_bidding_service.py
│   │   ├── test_auction_engine.py
│   │   └── test_csv_service.py
│   └── utils/
│       ├── bid_utils.py          # bid_increment()
│       └── team_utils.py         # short_name() helper (legacy)
├── config/
│   ├── settings.py
│   └── urls.py                   # Root URL conf + media serving
├── templates/
│   ├── base.html                 # Layout, nav, dark theme
│   ├── public_board.html         # Live TV display (auto-refresh 5s)
│   ├── auction_control.html      # Auctioneer panel
│   ├── auction_setup.html        # Config form
│   ├── auction_summary.html      # Final squad summary
│   ├── jersey_management.html    # Jersey add/delete/sort/export
│   ├── banner_upload.html        # Tournament banner upload
│   ├── upload_csv.html           # CSV upload + validate UI
│   └── audit_log.html            # Full action log
├── static/
│   └── backgrounds/              # ← Place auction_bg.jpg here
├── media/
│   └── banners/                  # Uploaded banners saved here (auto-created)
├── dev_reset.py                  # Wipe DB + rebuild + create superuser
├── pytest.ini                    # pytest configuration
└── requirements.txt
```

---

## All URLs

| URL | Method | Purpose |
|-----|--------|---------|
| `/` | GET | Public board — live sold players + current player on TV |
| `/auction/` | GET | Auctioneer control panel (shows setup form if not started) |
| `/auction/start/` | POST | Save tournament config and activate auction |
| `/auction/continue/` | GET | Dismiss transition banner and pick first player of new round |
| `/auction/next/` | GET | Pick next random player from current pool |
| `/auction/sell/` | POST | Sell current player to selected team |
| `/auction/unsold/` | POST | Mark current player unsold (returns to rebid pool) |
| `/auction/not-playing/` | POST | Permanently remove player from auction |
| `/auction/undo/` | GET | Reverse the last recorded action |
| `/auction/refresh/` | POST | Recalculate all team points from DB (fixes corruption) |
| `/auction/complete/` | GET | Mark auction DONE, redirect to summary |
| `/auction/summary/` | GET | Full squad + spend summary for all teams (always accessible) |
| `/auction/upload-csv/` | GET/POST | Upload or validate player/team CSV files |
| `/auction/audit-log/` | GET | Full log of every SELL/UNSOLD/NOT_PLAYING/UNDO action |
| `/auction/banner/` | GET/POST | Upload a tournament background banner image |
| `/auction/reset/` | GET | ⚠ Hard reset — wipes all bids. URL only, not linked in UI |
| `/jersey/` | GET/POST | Add/delete jerseys, sort by team or number |
| `/jersey/pdf/` | GET | Download jersey list as PDF |
| `/admin/` | GET | Django admin panel |

---

## Data Models

### Team
| Field | Type | Notes |
|-------|------|-------|
| `team_serial_number` | AutoField PK | |
| `name` | CharField | Full team name |
| `short_name` | CharField | Abbreviation shown on buttons e.g. `MW`. Auto-generated from initials if blank |
| `owners` | CharField | |
| `remaining_points` | IntegerField | Auto-updated by Player.save() |

### Player
| Field | Type | Notes |
|-------|------|-------|
| `serial_number` | AutoField PK | |
| `name`, `place`, `phone` | CharField | |
| `role` | CharField | `AR` / `BAT` / `BOWL` / `PLY` |
| `base_price` | IntegerField | Set from config on auction start |
| `sold_price` | IntegerField nullable | |
| `team` | FK → Team | |
| `status` | CharField | `AVAILABLE` / `SOLD` / `UNSOLD` / `NOT_PLAYING` |
| `rebid_count` | IntegerField | Increments each UNSOLD. PLY auto-drops at max |

**Important:** `Player.save()` automatically deducts/refunds `team.remaining_points` whenever sold status, price, or team changes. Never update points manually.

### TournamentConfig
| Field | Notes |
|-------|-------|
| `total_points` | Starting wallet per team |
| `bidding_slots` | Target squad size (triggers over-slots warning) |
| `max_squad_size` | Hard maximum |
| `base_price_AR/BAT/BOWL/PLY` | Minimum bid per role |
| `category_order` | Comma-separated auction order e.g. `AR,BAT,BOWL,PLY` |
| `max_rebid_attempts` | PLY only — auto-drop after this many UNSOLDs |
| `auction_date` | Shown on public board pre-auction and on summary page |
| `banner_path` | Filename of uploaded banner in `media/banners/` |

### AuctionState (singleton — always pk=1)
| Field | Notes |
|-------|-------|
| `phase` | `MAIN` / `REBID` / `DONE` |
| `current_category` | Active role `AR/BAT/BOWL/PLY` |
| `category_pass` | `1` = first pass, `2` = second pass |
| `auction_round` | Increments on every phase transition |
| `awaiting_transition` | `True` = transition banner showing, auction paused |
| `transition_message` | Text shown in the banner |
| `current_player` | FK to Player currently on block |

---

## Auction Flow Reference

```
[Setup] Config form at /auction/ (first visit)
    ↓ POST /auction/start/
[Transition banner] "All Rounder Round – Press Start"
    ↓ Click ▶ Start Round  →  GET /auction/continue/
[AR Pass 1] Teams with 1 AR already are GREYED OUT
    Actions: SELL → /auction/sell/
             UNSOLD → /auction/unsold/
             NOT PLAYING → /auction/not-playing/
             Next player → /auction/next/
    ↓ (pass 1 pool exhausted)
[Transition banner] "AR Pass 1 complete · Starting AR Rebid"
    ↓ if: unsold ARs exist AND not all teams have 1 AR
[AR Rebid] Same blocking rules as Pass 1
    ↓
[Transition banner] "AR Rebid complete · Starting AR Pass 2"
    ↓ if: all teams have 1 AR AND more AR players remain
[AR Pass 2] ALL teams enabled — no blocking
    ↓
[Transition banner] "All Rounder Round complete · Starting Batting Round"
    ↓
[BAT Pass 1 → Rebid → Pass 2] (same pattern)
[BOWL Pass 1 → Rebid → Pass 2] (same pattern)
[PLY Round → Rebid] (no passes, no blocking, PLY auto-drops at max rebid)
    ↓
Admin clicks ■ Complete Auction  (bottom-right, subtle link)
    →  GET /auction/complete/
    →  Redirect to /auction/summary/
```

---

## Bid Validation Rules

All three rules run in order. First failure shows an error.

1. **Base price minimum** — bid must be ≥ role's base price from config
2. **Available points** — bid must be ≤ team's remaining points
3. **Safe bid** — after bidding, team must retain at least `(remaining_slots - 1) × (total_points ÷ 100)` to fill future slots

**Force Sell** bypasses all three rules (admin override for edge cases).

**Over-slots warning** — if team already has ≥ `bidding_slots` players, a dialog shows:
- **Skip** — cancel the sale, player stays on block
- **Force Add** — proceed, team gets extra player beyond normal slots

---

## CSV Formats

### Players CSV
Required columns: `name`, `role`, `phone`, `place`

```csv
name,role,phone,place
Rajesh Kumar,AR,9876543210,Mangalore
Suresh Shetty,BAT,9876543211,Udupi
Ganesh Rao,BOWL,9876543212,Manipal
Mahesh Nair,PLY,9876543213,Kundapur
```

Valid roles: `AR` `BAT` `BOWL` `PLY`
Phone format: 10–12 digits, optional leading `+`

### Teams CSV
Required: `name` — Optional: `short_name`, `owners`, `payment_info`

```csv
name,short_name,owners,payment_info
Mangalore Warriors,MW,Ravi Kumar,0
Udupi Lions,UL,Suresh Nair,0
```

**Always validate before uploading.** The validate action checks all rows and reports errors
without writing anything to the database.

---

## Running Tests

```bash
# Django test runner — all tests
python manage.py test auction.tests

# Django test runner — single file
python manage.py test auction.tests.test_models
python manage.py test auction.tests.test_bidding_service
python manage.py test auction.tests.test_auction_engine
python manage.py test auction.tests.test_csv_service

# pytest — all tests
pytest

# pytest — verbose with test names
pytest -v

# pytest — single file
pytest auction/tests/test_models.py -v

# pytest — single test class
pytest auction/tests/test_bidding_service.py::BiddingValidationTest -v

# pytest — single test function
pytest auction/tests/test_auction_engine.py::BlockedTeamsTest::test_pass2_no_blocking -v

# pytest — stop at first failure
pytest -x -v

# pytest — show print output
pytest -s -v

# pytest — run tests matching a keyword
pytest -k "force_sell" -v
pytest -k "blocked" -v
```

---

## Admin Panel Quick Reference

URL: http://127.0.0.1:8000/admin/ — login: `sk` / `sk`

| Model | What you can do |
|-------|----------------|
| **Player** | Edit name/role/status/team/sold_price. Status is a dropdown. Points auto-adjust on save |
| **Team** | Edit name, short_name, owners. remaining_points auto-managed |
| **TournamentConfig** | Edit config mid-auction (base prices, slots, etc.) |
| **AuctionState** | Inspect/debug current phase, pass, category, transition flags |
| **AuctionAction** | Full audit trail — read only in practice |
| **Jersey** | Add/edit/delete jerseys |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'reportlab'` | `pip install reportlab --break-system-packages` |
| `No module named 'PIL'` | `pip install Pillow --break-system-packages` |
| Points wrong after admin edit | Click **↺ Refresh** (bottom-left of /auction/) |
| Player added in admin not appearing | Set status to `AVAILABLE`, then refresh /auction/ page |
| Background image missing | Place `auction_bg.jpg` in `static/backgrounds/` |
| CSRF error on sell/unsold | These views are csrf_exempt — check your browser isn't blocking JS |
| `--reuse-db` pytest error | Remove `--reuse-db` from `pytest.ini` or run `pytest --create-db` once |
| Transition banner stuck | Visit `/auction/continue/` directly in browser |

---

## Superuser

Auto-created by `dev_reset.py`:
- Username: **sk**
- Password: **sk**
- Admin: http://127.0.0.1:8000/admin/

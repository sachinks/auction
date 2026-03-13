# KPL — Complete Testing Guide

This file covers every feature of the KPL auction engine:
automated pytest tests, manual browser tests, and URL verification.

Run everything from the project root `/path/to/kpl/`.

---

## 0. Before You Test

```bash
# Clean slate — always start fresh
python dev_reset.py

# Confirm server is running in a separate terminal
python manage.py runserver
```

Login for admin tests: http://127.0.0.1:8000/admin/ → **sk / sk**

---

## 1. Automated Tests (pytest)

### 1.1 Install pytest dependencies

```bash
pip install pytest pytest-django --break-system-packages
```

Confirm `pytest.ini` contains:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
```

If `--reuse-db` is in `pytest.ini` and causes issues, remove it or add `--create-db` the first run:
```bash
pytest --create-db -v
```

---

### 1.2 Run All Tests

```bash
# Full suite
pytest -v

# Expected: all green
# auction/tests/test_models.py::TeamShortNameTest::test_multi_word PASSED
# auction/tests/test_models.py::TeamShortNameTest::test_single_word PASSED
# ... 18+ tests total
```

---

### 1.3 Test File: test_models.py

Tests `Player.save()` point deduction and `Team.get_short()`.

```bash
pytest auction/tests/test_models.py -v
```

**What each test checks:**

| Test | Feature | Expected |
|------|---------|----------|
| `test_multi_word` | Team short name auto-generate | `"Mumbai Indians"` → `"MI"` |
| `test_single_word` | Team short name single word | `"Bangalore"` → `"BAN"` |
| `test_explicit_short_name` | Custom short_name field | `"MI"` returned as-is |
| `test_explicit_short_name_lowercased` | Short name uppercased | `"mi"` → `"MI"` |
| `test_sell_deducts_from_team` | Point deduction on sell | Team starts 10000, sell for 1500 → 8500 |
| `test_unsell_refunds_team` | Point refund on unsell | Sold for 800 → unsell → back to 10000 |
| `test_edit_price_no_double_deduct` | Price edit — no double deduction | Sold 600 → edit to 700 → net spend 700 not 1300 |
| `test_switch_team_correct_points` | Team switch refunds old, charges new | Team A refunded, Team B charged correctly |

Run individual tests:
```bash
pytest auction/tests/test_models.py::PlayerSaveTest::test_edit_price_no_double_deduct -v
pytest auction/tests/test_models.py::TeamShortNameTest -v
```

---

### 1.4 Test File: test_bidding_service.py

Tests bid validation rules, force sell, icon vs PLY rebid behaviour.

```bash
pytest auction/tests/test_bidding_service.py -v
```

| Test | Feature | Expected |
|------|---------|----------|
| `test_below_base_price_rejected` | Rule 1: base price minimum | Error string contains "base price" |
| `test_exceeds_available_points` | Rule 2: cannot exceed wallet | Error string contains "exceeds" |
| `test_valid_bid_passes` | Valid bid returns None error | `error is None` |
| `test_force_sell_bypasses_validation` | Force sell at 0 | `success=True`, no error |
| `test_icon_no_auto_drop` | AR unsold 5× — never drops | Status remains UNSOLD |
| `test_ply_auto_drop_after_max` | PLY unsold 3× — auto-drops | Status becomes NOT_PLAYING |

Run individually:
```bash
pytest auction/tests/test_bidding_service.py::BiddingValidationTest::test_force_sell_bypasses_validation -v
pytest auction/tests/test_bidding_service.py::UnsoldRebidTest -v
```

---

### 1.5 Test File: test_auction_engine.py

Tests round labels, team blocking logic, and point recalculation.

```bash
pytest auction/tests/test_auction_engine.py -v
```

| Test | Feature | Expected |
|------|---------|----------|
| `test_main_pass1` | Round label — main | Contains "All Rounder" and "Round" |
| `test_rebid` | Round label — rebid | Contains "Batting" and "Rebid" |
| `test_pass2` | Round label — pass 2 | Contains "Bowling" and "Pass 2" |
| `test_ply` | Round label — PLY | Contains "Player" |
| `test_pass1_blocks_team_with_ar` | Pass 1 blocking | Team with AR in blocked set |
| `test_pass2_no_blocking` | Pass 2 open | Blocked set is empty |
| `test_rebid_pass1_blocks` | Rebid pass 1 blocking | Team with AR still blocked in rebid |
| `test_ply_never_blocked` | PLY no blocking | Blocked set always empty for PLY |
| `test_recalculate_correct` | Refresh/recalculate points | Corrupted 7000 → correct 8500 |

Run individually:
```bash
pytest auction/tests/test_auction_engine.py::BlockedTeamsTest -v
pytest auction/tests/test_auction_engine.py::RecalcPointsTest::test_recalculate_correct -v
```

---

### 1.6 Test File: test_csv_service.py

Tests CSV import and validate-only mode for both players and teams.

```bash
pytest auction/tests/test_csv_service.py -v
```

| Test | Feature | Expected |
|------|---------|----------|
| `test_validate_does_not_create` | Player CSV — validate mode | 1 valid row counted, 0 DB records created |
| `test_import_creates_players` | Player CSV — import mode | 1 player in DB |
| `test_invalid_role_gives_error` | Invalid role detection | 0 valid, errors list non-empty |
| `test_import_teams` | Team CSV import | Team created with correct short_name |
| `test_validate_teams_no_write` | Team CSV validate mode | 1 valid counted, 0 DB records |

Run individually:
```bash
pytest auction/tests/test_csv_service.py::PlayerCSVTest::test_validate_does_not_create -v
pytest auction/tests/test_csv_service.py::TeamCSVTest -v
```

---

### 1.7 Run by keyword

```bash
# All tests related to force sell
pytest -k "force" -v

# All tests related to blocking
pytest -k "blocked" -v

# All tests related to points
pytest -k "points or deduct or refund or recalc" -v

# All CSV tests
pytest -k "csv or CSV" -v
```

---

### 1.8 Django test runner (alternative)

```bash
python manage.py test auction.tests -v 2
python manage.py test auction.tests.test_models -v 2
python manage.py test auction.tests.test_bidding_service -v 2
python manage.py test auction.tests.test_auction_engine -v 2
python manage.py test auction.tests.test_csv_service -v 2
```

---

## 2. Manual Browser Tests — Setup

### 2.1 Upload teams via CSV

1. Create `teams.csv`:
```csv
name,short_name,owners,payment_info
Mangalore Warriors,MW,Owner 1,0
Udupi Lions,UL,Owner 2,0
Manipal Strikers,MS,Owner 3,0
Kundapur Kings,KK,Owner 4,0
```

2. Go to http://127.0.0.1:8000/auction/upload-csv/
3. Under **Teams CSV**, choose file → click **Validate Only**
   - ✅ Should show: "4 valid rows, no errors"
   - No teams created yet in DB
4. Choose file again → click **Upload Teams**
   - ✅ Should show: "4 imported"
5. Go to http://127.0.0.1:8000/admin/auction/team/ → confirm 4 teams exist

---

### 2.2 Upload players via CSV

1. Create `players.csv`:
```csv
name,role,phone,place
Ravi Kumar,AR,9876543210,Mangalore
Suresh Shetty,AR,9876543211,Udupi
Ganesh Rao,BAT,9876543212,Manipal
Mahesh Nair,BAT,9876543213,Kundapur
Pradeep Kini,BOWL,9876543214,Mangalore
Ashwin Bhat,BOWL,9876543215,Udupi
Naveen Kamath,PLY,9876543216,Manipal
Kiran Shenoy,PLY,9876543217,Kundapur
Deepak Rao,PLY,9876543218,Mangalore
```

2. Go to http://127.0.0.1:8000/auction/upload-csv/
3. Under **Players CSV**, choose file → **Validate Only**
   - ✅ Should show 9 valid rows, 0 errors
4. Choose file → **Upload Players**
   - ✅ Should show "9 imported"

**Test validation errors:**

Create `bad_players.csv`:
```csv
name,role,phone,place
Good Player,AR,9876543210,Mangalore
Bad Role,PITCHER,9876543211,Udupi
Bad Phone,BAT,123,Manipal
,BOWL,9876543212,Kundapur
```

Upload to Validate Only → ✅ Should show 1 valid, 3 errors (bad role, bad phone, empty name)

---

### 2.3 Upload banner image

1. Go to http://127.0.0.1:8000/auction/banner/
2. Choose any JPG/PNG image → click **Upload Banner**
   - ✅ Success message shown
   - ✅ Image preview appears
   - ✅ All pages now show it as background
   - ✅ `media/banners/tournament_banner.*` file exists

---

## 3. Manual Browser Tests — Public Board (Pre-Auction)

**URL:** http://127.0.0.1:8000/

Before auction starts:
- ✅ Shows "Auction Coming Soon" (or auction date if set)
- ✅ All players listed grouped by role: All Rounders, Batsmen, Bowlers, Players
- ✅ Each player shows serial number, name, place
- ✅ Page refreshes every 5 seconds

---

## 4. Manual Browser Tests — Auction Setup

### 4.1 Start auction with date

1. Go to http://127.0.0.1:8000/auction/
2. Fill in the config form:
   - Auction Date: pick any future date/time
   - Total Points: 10000
   - Bidding Slots: 11
   - Max Squad Size: 13
   - AR Base Price: 1000
   - BAT Base Price: 400
   - BOWL Base Price: 400
   - PLY Base Price: 100
   - Category Order: AR,BAT,BOWL,PLY
   - Max Rebid Attempts: 2
3. Click **START AUCTION**
   - ✅ Redirects to /auction/
   - ✅ **Transition banner** appears: "All Rounder Round – Press Start to begin"
   - ✅ No player shown yet (awaiting Continue)

---

## 5. Manual Browser Tests — Transition Banners

**Item 4 + 10**

After auction start:
- ✅ Blue banner shows "All Rounder Round – Press Start to begin"
- ✅ Auction control buttons are hidden while banner is shown
- ✅ Clicking **▶ Start Round** picks first AR player and shows the auction panel
- ✅ After all AR players sold/unsold, a new transition banner fires:
  - "AR Pass 1 complete · Starting AR Rebid" (if unsold ARs)
  - OR "All Rounder Round complete · Starting Batting Round" (if no unsold)
- ✅ Banner fires on EVERY transition: rebid start, pass 2 start, next category

---

## 6. Manual Browser Tests — Core Auction Actions

### 6.1 SELL a player

1. Transition banner → click **▶ Start Round**
2. An AR player appears on the card
3. Enter bid amount (must be ≥ 1000)
4. Click a team button
   - ✅ Button highlights gold border, "Bidding: [Team Name]" updates
5. Click **✔ SELL**
   - ✅ Page reloads, player disappears
   - ✅ Team's remaining points decrease by bid amount
   - ✅ Public board shows player under that team
   - ✅ Admin → Player shows status=SOLD, team set, sold_price set

### 6.2 UNSOLD

1. Player on block → click **UNSOLD** (no team selected needed)
   - ✅ Player disappears from block
   - ✅ Player.rebid_count increments by 1
   - ✅ Player status = UNSOLD
   - ✅ Player will reappear in rebid round

### 6.3 NOT PLAYING

1. Player on block → click **NOT PLAYING**
   - ✅ Confirmation dialog appears
   - ✅ After confirm: player status = NOT_PLAYING
   - ✅ Player never appears again in any round
   - ✅ Player excluded from all pool counts

### 6.4 UNDO

1. After any action (SELL/UNSOLD/NOT PLAYING)
2. Click **↩ Undo** (top-right of status bar)
   - ✅ That player is restored to the block
   - ✅ Points refunded if SELL was undone
   - ✅ rebid_count decremented if UNSOLD was undone
   - ✅ Status reverted to AVAILABLE

---

## 7. Manual Browser Tests — Bid Validation (Item 8)

### 7.1 Below base price

1. Player on block (AR, base 1000)
2. Set bid to 500
3. Select any team
4. Click **✔ SELL**
   - ✅ Error banner appears: "Bid ₹500 is below the base price for AR (minimum: ₹1000)"
   - ✅ Two buttons: **Continue** and **Force Sell**

### 7.2 Exceeds team points

1. Set bid to 999999
2. Click SELL
   - ✅ Error: "Bid ₹999999 exceeds [Team]'s available points"
   - ✅ Force Sell button shown

### 7.3 Unsafe bid

1. Set bid so team's remaining after bid is less than `(slots-1) × (total/100)`
   - e.g. with 10000 total, team spending 9950 when they still have 10 slots left
   - ✅ Error: "⚠ Unsafe bid — [Team] would have ... left but needs ..."
   - ✅ Force Sell button shown

### 7.4 Force Sell

After any validation error:
1. Click **Force Sell**
   - ✅ Player sold at entered amount, ALL rules bypassed
   - ✅ Even bid of 0 succeeds with Force Sell

### 7.5 Continue (dismiss error)

After any validation error:
1. Click **Continue**
   - ✅ Error banner hides, player still on block, no sale made

---

## 8. Manual Browser Tests — Pass 1 Blocking (Items 15, 16)

### 8.1 Verify blocking in Pass 1

1. During AR Pass 1 with 4 teams
2. Sell an AR player to Team A
3. Next AR player appears
   - ✅ Team A button is GREYED OUT and unclickable
   - ✅ Teams B, C, D are active

### 8.2 Verify Pass 2 enables all teams

When all 4 teams have 1 AR and more ARs remain:
- ✅ Transition banner: "AR Pass 1 complete · Starting AR Pass 2" (or via Rebid)
- ✅ In Pass 2: ALL team buttons active including Team A

### 8.3 Verify rebid blocking

During AR Rebid (Pass 1):
- ✅ Teams that already have 1 AR are still greyed out
- ✅ Only teams without an AR can bid

---

## 9. Manual Browser Tests — Extra Player Dialog (Item 20)

1. Sell players to one team until they hit the bidding_slots limit (default 11)
2. Try to sell another player to that same team
   - ✅ Dialog appears: "⚠ Team Slots Full — [Team] already has X players (max Y slots). Add as extra?"
   - ✅ **Skip (Cancel)** — closes dialog, player stays on block, NO sale
   - ✅ **Force Add** — player sold to team as extra (beyond slots)

---

## 10. Manual Browser Tests — PLY Auto-Drop (Item 8 / rebid limit)

1. During Player Round, mark a PLY player UNSOLD twice (with max_rebid_attempts=2)
2. On the 3rd UNSOLD:
   - ✅ Player status changes to NOT_PLAYING automatically
   - ✅ Player never appears again
3. For AR/BAT/BOWL: mark UNSOLD any number of times
   - ✅ Status stays UNSOLD — NEVER auto-drops

---

## 11. Manual Browser Tests — Refresh / Point Recalculation (Item 9)

### 11.1 Normal refresh

1. Click **↺ Refresh** (bottom-left of /auction/)
   - ✅ Page reloads
   - ✅ All team remaining_points recalculated from actual sold player records
   - ✅ No auction state changes

### 11.2 Simulate point corruption and fix

1. In Django admin, manually edit a sold player's `sold_price` to a different value
2. Team's `remaining_points` is now wrong (was auto-adjusted at original price)
3. Click **↺ Refresh**
   - ✅ All teams' remaining_points recalculated correctly

---

## 12. Manual Browser Tests — Public Board Live View (Item 7, 21)

**URL:** http://127.0.0.1:8000/ (keep this open in a separate tab)

During auction:
- ✅ Current player shown on left card with role badge, serial number, name (coloured by role), place, base price
- ✅ Player name colour: AR=orange, BAT=blue, BOWL=green, PLY=grey
- ✅ No bullet points before player names in team grids
- ✅ Serial number shown in each team's player list
- ✅ Top-right of player card shows "Avail: X" (MAIN phase) or "Rebid: X" (REBID phase)
- ✅ Sold players listed under their team — name coloured by role
- ✅ Each team shows remaining points
- ✅ Page auto-refreshes every 5 seconds (watch the URL bar)

---

## 13. Manual Browser Tests — Round Labels (Item 3)

On the auction control page status bar, verify the round label shows:

| Category | Phase | Pass | Expected Label |
|----------|-------|------|---------------|
| AR | MAIN | 1 | All Rounder Round |
| AR | MAIN | 2 | All Rounder Round · Pass 2 |
| AR | REBID | 1 | All Rounder Rebid |
| BAT | MAIN | 1 | Batting Round |
| BAT | REBID | 1 | Batting Rebid |
| BOWL | MAIN | 1 | Bowling Round |
| BOWL | MAIN | 2 | Bowling Round · Pass 2 |
| PLY | MAIN | 1 | Player Round |

---

## 14. Manual Browser Tests — Team Short Name (Item 13)

1. Go to http://127.0.0.1:8000/admin/auction/team/
2. Edit a team → set `short_name` to `MW`
3. Go to /auction/
4. ✅ Team button shows `MW` (not full name)
5. ✅ Tooltip on hover shows full team name
6. ✅ "Bidding: [Full Name]" shows full name after clicking

Test auto-generation (no short_name set):
1. Edit team → clear the `short_name` field
2. ✅ Button auto-generates: "Mangalore Warriors" → "MW"

---

## 15. Manual Browser Tests — Summary Page (Item 5, 22)

**URL:** http://127.0.0.1:8000/auction/summary/

- ✅ Accessible at any time — before, during, and after auction
- ✅ Shows all teams with their sold players, amounts, total spent, remaining points
- ✅ Player names coloured by role
- ✅ If auction_date was set in config: shows "Match Date: DD Mon YYYY, HH:MM"
- ✅ **Jersey Management →** link in top-right
- ✅ **← Auction** link to return to control panel

---

## 16. Manual Browser Tests — Jersey Management (Item 6)

**URL:** http://127.0.0.1:8000/jersey/

1. Jersey Management page loads
2. Add a jersey:
   - Select a sold player from dropdown
   - Jersey Name: "RAVI K"
   - Jersey #: 7
   - Size #: 40
   - Size Label: L
   - Sponsor: "KPL 2025"
   - Click **+ Add Jersey**
   - ✅ Jersey appears in table
3. Sort by **#Number** → ✅ Jerseys ordered by jersey number
4. Sort by **Team** → ✅ Jerseys ordered by team name then number
5. Delete a jersey → ✅ Confirmation prompt, then row removed
6. Click **Export PDF** → ✅ PDF downloads with jersey table

---

## 17. Manual Browser Tests — Audit Log

**URL:** http://127.0.0.1:8000/auction/audit-log/

After a few actions:
- ✅ Every SELL, UNSOLD, NOT_PLAYING, UNDO action listed
- ✅ Columns: timestamp, player, action, team, amount, category, round

---

## 18. Manual Browser Tests — Complete Auction

1. Click **■ Complete Auction** (bottom-right, small/subtle)
   - ✅ Confirmation dialog: "Mark auction as COMPLETE?"
   - ✅ After confirm: redirects to /auction/summary/
   - ✅ AuctionState.phase = DONE
   - ✅ is_active = False
   - ✅ Public board shows trophy icon "Auction Complete"

---

## 19. Manual Browser Tests — Admin Mid-Auction Edit

### 19.1 Add player mid-auction

1. While auction is running with current player shown
2. In admin: Add Player → name="New Player", role="AR", status=AVAILABLE
3. Save
4. On auction page: after current player is resolved, click Next Player
   - ✅ Newly added player can appear in pool

### 19.2 Admin manual assignment

1. In admin: Edit Player → set team=Team A, status=SOLD, sold_price=1500
2. Save
   - ✅ Team A's remaining_points automatically deducted by 1500
   - ✅ Player appears in Team A's column on public board

### 19.3 Admin un-assign

1. In admin: Edit the same player → set status=AVAILABLE, team=None, sold_price=None
2. Save
   - ✅ Team A's remaining_points refunded

---

## 20. URL Smoke Tests

Paste each into browser and confirm expected HTTP response:

| URL | Expected |
|-----|----------|
| http://127.0.0.1:8000/ | 200 — Public board |
| http://127.0.0.1:8000/auction/ | 200 — Auction control or setup form |
| http://127.0.0.1:8000/auction/summary/ | 200 — Summary page |
| http://127.0.0.1:8000/auction/upload-csv/ | 200 — CSV upload page |
| http://127.0.0.1:8000/auction/audit-log/ | 200 — Audit log |
| http://127.0.0.1:8000/auction/banner/ | 200 — Banner upload page |
| http://127.0.0.1:8000/jersey/ | 200 — Jersey management |
| http://127.0.0.1:8000/admin/ | 200 — Admin login |
| http://127.0.0.1:8000/auction/next/ | 302 — Redirects to /auction/ |
| http://127.0.0.1:8000/auction/undo/ | 302 — Redirects to /auction/ |
| http://127.0.0.1:8000/auction/complete/ | 302 — Redirects to /auction/summary/ |
| http://127.0.0.1:8000/jersey/pdf/ | 200 — PDF download |
| http://127.0.0.1:8000/auction/reset/ | 302 — Resets and redirects (⚠ destructive) |

POST-only endpoints (will redirect or error if visited via browser GET — that's correct):
- `/auction/sell/`
- `/auction/unsold/`
- `/auction/not-playing/`
- `/auction/refresh/`

---

## 21. Full End-to-End Test Run

Follow this sequence to test the entire system from scratch:

```
python dev_reset.py
python manage.py runserver
```

1. Upload teams CSV → validate → upload
2. Upload players CSV → validate → upload
3. Open two browser windows: /auction/ and /  (public board)
4. Upload banner at /auction/banner/
5. Fill auction setup form with auction_date set → Start Auction
6. Verify transition banner appears on /auction/ and public board shows "Coming Soon"
7. Click ▶ Start Round → AR player appears
8. Sell first AR player to Team A for 1500
   - Check: Team A points dropped by 1500
   - Check: Public board shows player under Team A
   - Check: Team A button greyed for next AR player
9. Mark second AR player as UNSOLD
10. Click Undo → player restored, back on block
11. Re-mark as UNSOLD
12. When all AR Pass 1 players exhausted: transition banner appears
13. Click ▶ Start Round → AR Rebid or Pass 2 begins
14. Complete a few more bids to test BAT round
15. Test force sell: enter 0 bid → SELL → error → Force Sell
16. Test not-playing: player on block → NOT PLAYING → confirm
17. When PLY round: mark same PLY player UNSOLD max_rebid_attempts times
    → Player auto-drops to NOT_PLAYING
18. Click ■ Complete Auction → confirm → lands on /auction/summary/
19. Verify summary shows all teams, spent amounts, match date
20. Go to /jersey/ → add jersey for a sold player → export PDF
21. Run pytest -v → all tests pass
```

---

## 22. Quick Pytest Cheat Sheet

```bash
# Everything
pytest -v

# Just one feature area
pytest auction/tests/test_models.py -v
pytest auction/tests/test_bidding_service.py -v
pytest auction/tests/test_auction_engine.py -v
pytest auction/tests/test_csv_service.py -v

# By keyword
pytest -k "short_name" -v
pytest -k "force_sell" -v
pytest -k "blocked" -v
pytest -k "recalc" -v
pytest -k "ply" -v
pytest -k "csv" -v

# Stop at first failure
pytest -x -v

# Show print output (useful for debugging)
pytest -s -v

# Count only, no details
pytest --co -q

# Run as Django test runner (alternative)
python manage.py test auction.tests -v 2
```

"""
Heads-Up No-Limit Texas Hold'em Agent
Built for DevFun Arena Researcher Track — June 21, 2026
Style: Aggressive, reads opponent, adapts mid-session
"""
import os, sys
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import itertools, random, time, csv
import httpx
from dotenv import load_dotenv
load_dotenv()

API_KEY    = os.environ["ARENA_API_KEY"]
AGENT_ID   = os.environ["ARENA_AGENT_ID"]
BASE       = "https://arena.dev.fun/api/arena"
HEADERS    = {"x-arena-api-key": API_KEY, "Content-Type": "application/json"}
FALLBACK_R = '{vr:"hu",style:"aggressive"}'

# ── Card utilities ─────────────────────────────────────────────────────────────
RANKS    = "23456789TJQKA"
SUITS    = "shdc"
RANK_VAL = {r: i for i, r in enumerate(RANKS)}
DECK     = [r+s for r in RANKS for s in SUITS]

def parse_card(c):
    return (RANK_VAL[c[0].upper()], SUITS.index(c[1].lower()))

def hand_rank(cards):
    best = (0,)
    for combo in itertools.combinations(cards, 5):
        r = _rank5(combo)
        if r > best: best = r
    return best

def _rank5(cards):
    ranks = sorted([c[0] for c in cards], reverse=True)
    suits = [c[1] for c in cards]
    flush    = len(set(suits)) == 1
    straight = (ranks[0]-ranks[4]==4 and len(set(ranks))==5) or ranks==[12,3,2,1,0]
    if straight and ranks[0]==3: ranks=[3,2,1,0,-1]
    counts = {}
    for r in ranks: counts[r]=counts.get(r,0)+1
    freq    = sorted(counts.items(), key=lambda x:(x[1],x[0]), reverse=True)
    groups  = [f[1] for f in freq]
    ordered = [f[0] for f in freq]
    if flush and straight:    return (8,)+tuple(ranks)
    if groups[0]==4:          return (7,)+tuple(ordered)
    if groups[:2]==[3,2]:     return (6,)+tuple(ordered)
    if flush:                 return (5,)+tuple(ranks)
    if straight:              return (4,)+tuple(ranks)
    if groups[0]==3:          return (3,)+tuple(ordered)
    if groups[:2]==[2,2]:     return (2,)+tuple(ordered)
    if groups[0]==2:          return (1,)+tuple(ordered)
    return (0,)+tuple(ranks)

def equity(hole, board, opponents=1, n=800):
    if len(hole) != 2: return 0.5
    try:
        my  = [parse_card(c) for c in hole]
        brd = [parse_card(c) for c in board]
    except: return 0.5
    known  = set(hole)|set(board)
    deck   = [c for c in DECK if c not in known]
    needed = 5-len(board)
    wins=ties=0
    for _ in range(n):
        s    = random.sample(deck, needed+2)
        opp  = s[:2]
        extra= [parse_card(c) for c in s[2:]]
        fb   = brd+extra
        mine = hand_rank(my+fb)
        best = hand_rank([parse_card(c) for c in opp]+fb)
        if mine>best:    wins+=1
        elif mine==best: ties+=0.5
    return (wins+ties)/n

def _hand_class(hole):
    if len(hole)!=2: return ""
    r1,s1=hole[0][0].upper(),hole[0][-1].lower()
    r2,s2=hole[1][0].upper(),hole[1][-1].lower()
    if r1 not in RANKS or r2 not in RANKS: return ""
    if RANKS.index(r1)<RANKS.index(r2): r1,r2,s1,s2=r2,r1,s2,s1
    if r1==r2: return r1+r2
    return f"{r1}{r2}{'s' if s1==s2 else 'o'}"

def _street(board):
    if not board: return "preflop"
    return ("flop","turn","river")[max(0,min(len(board)-3,2))]

# ── Heads-up preflop hand strength ────────────────────────────────────────────
# In heads-up, hand ranges are much wider — top 70% of hands are playable
PREFLOP_STRENGTH = {}
for i,r in enumerate(RANKS):
    PREFLOP_STRENGTH[r+r] = 0.40 + i*0.045
for i,r1 in enumerate(RANKS):
    for j,r2 in enumerate(RANKS):
        if j >= i: continue
        gap  = i-j
        base = (i+j)/2/12
        PREFLOP_STRENGTH[f"{r1}{r2}s"] = min(max(0.0, base-gap*0.03+0.07), 0.95)
        PREFLOP_STRENGTH[f"{r1}{r2}o"] = min(max(0.0, base-gap*0.03+0.02), 0.90)

SUITED_ROYALS = {"AKs","AQs","AJs","ATs","KQs","KJs","QJs","JTs"}

# ── Opponent profiling ────────────────────────────────────────────────────────
OPP_PROFILE = {
    "raises": 0, "calls": 0, "folds": 0, "bets": 0,
    "total_bet_size": 0, "bet_count": 0,
    "vpip": 0,   # voluntarily put chips in pot
    "hands": 0
}

def update_profile(table, self_n):
    for seat in (table.get("seats") or []):
        if seat.get("seatNumber") == self_n: continue
        action = (seat.get("lastAction") or "").lower()
        amt    = seat.get("lastActionAmount") or 0
        if not action: continue
        OPP_PROFILE["hands"] += 1
        if action in ("raise","bet","allin"):
            OPP_PROFILE["raises"] += 1
            OPP_PROFILE["vpip"]   += 1
            if amt: OPP_PROFILE["total_bet_size"] += amt; OPP_PROFILE["bet_count"] += 1
        elif action == "call":
            OPP_PROFILE["calls"] += 1
            OPP_PROFILE["vpip"]  += 1
        elif action == "fold":
            OPP_PROFILE["folds"] += 1

def opp_style():
    """Returns opponent style: aggressive / passive / calling_station / unknown"""
    total = OPP_PROFILE["raises"] + OPP_PROFILE["calls"] + OPP_PROFILE["folds"]
    if total < 8: return "unknown"
    raise_rate = OPP_PROFILE["raises"] / total
    fold_rate  = OPP_PROFILE["folds"]  / total
    call_rate  = OPP_PROFILE["calls"]  / total
    if raise_rate > 0.45:   return "aggressive"
    if fold_rate  > 0.50:   return "passive"
    if call_rate  > 0.55:   return "calling_station"
    return "balanced"

def avg_bet_size():
    if OPP_PROFILE["bet_count"] == 0: return 0
    return OPP_PROFILE["total_bet_size"] / OPP_PROFILE["bet_count"]

# ── Decision engine ────────────────────────────────────────────────────────────
def decide(table, deadline_s=20.0):
    allowed   = table.get("allowedActions") or {}
    available = allowed.get("availableActions") or []

    if deadline_s < 3.0:
        return {"action":"check" if "check" in available else "fold",
                "message":"deadline","reasoning":FALLBACK_R}

    self_n = table.get("selfSeatNumber") or 0
    update_profile(table, self_n)

    seats  = table.get("seats") or []
    me     = next((s for s in seats if s.get("seatNumber")==self_n), {})
    hole   = list(me.get("holeCards") or [])
    board  = list(table.get("boardCards") or [])
    street = _street(board)
    pot    = max(int(table.get("potChips") or 0), 1)
    call_c = int(allowed.get("callChips") or 0)
    my_stk = int(me.get("stackChips") or 1000)
    cls    = _hand_class(hole)
    style  = opp_style()

    rr = allowed.get("raiseRange") or {}
    br = allowed.get("betRange")   or {}
    r_lo = int(rr.get("min") or call_c*2 or 1)
    r_hi = int(rr.get("max") or my_stk)
    b_lo = int(br.get("min") or 1)
    b_hi = int(br.get("max") or my_stk)

    call_frac    = call_c / max(my_stk, 1)
    call_is_big  = call_frac > 0.20
    call_is_huge = call_frac > 0.40
    opp_allin    = call_frac >= 0.85

    def do_bet(frac, msg):
        raw = int(pot * frac)
        raw = max(raw, b_lo)
        raw = min(raw, b_hi)
        if "bet" in available:
            return {"action":"bet","amount":raw,"message":msg,"reasoning":FALLBACK_R}
        if "raise" in available:
            raw = max(raw, r_lo); raw = min(raw, r_hi)
            return {"action":"raise","amount":raw,"message":msg,"reasoning":FALLBACK_R}
        return None

    def do_open(mult, msg):
        amt = max(r_lo, min(r_lo*mult, r_hi))
        act = "raise" if "raise" in available else ("bet" if "bet" in available else None)
        if act: return {"action":act,"amount":amt,"message":msg,"reasoning":FALLBACK_R}
        return None

    def do_allin(msg):
        if "raise" in available:
            return {"action":"raise","amount":r_hi,"message":msg,"reasoning":'{vr:"allin"}'}
        if "bet" in available:
            return {"action":"bet","amount":b_hi,"message":msg,"reasoning":'{vr:"allin"}'}
        if "call" in available:
            return {"action":"call","message":msg,"reasoning":FALLBACK_R}
        return None

    def do_call(msg):
        if "call" in available:
            return {"action":"call","message":msg,"reasoning":FALLBACK_R}
        return None

    def do_check_fold(msg):
        if "check" in available:
            return {"action":"check","message":msg,"reasoning":FALLBACK_R}
        return {"action":"fold","message":msg,"reasoning":FALLBACK_R}

    strength = PREFLOP_STRENGTH.get(cls, 0.30)

    # ── PREFLOP ───────────────────────────────────────────────────────────────
    if street == "preflop":

        # Suited royals — slow play, trap
        if cls in SUITED_ROYALS:
            if opp_allin: return do_call(f"call allin {cls}") or do_check_fold("check")
            if call_c == 0: return do_check_fold(f"check {cls}")
            return do_call(f"call {cls} — royal trap") or do_check_fold("check")

        # Premium — raise hard
        if cls in ("AA","KK","QQ","JJ","TT","AKs","AKo","AQs","AQo"):
            if opp_allin: return do_call(f"call allin {cls}") or do_check_fold("check")
            r = do_open(4, f"raise hard {cls}")
            if r: return r
            return do_call(f"call {cls}") or do_check_fold("check")

        # vs all-in — only call with very strong hands
        if opp_allin:
            if strength >= 0.80:
                return do_call(f"call allin {cls}") or do_check_fold("check")
            return {"action":"fold","message":f"fold vs allin {cls}","reasoning":FALLBACK_R}

        # Heads-up: wide range — play top 70% of hands
        # Adjust based on opponent style
        if style == "passive":
            # Passive opponent folds a lot — steal more, raise wider
            threshold = 0.30
        elif style == "aggressive":
            # Aggressive opponent — tighten up, let them bluff
            threshold = 0.55
        elif style == "calling_station":
            # Calling station — only bet for value, no bluffs
            threshold = 0.50
        else:
            threshold = 0.40  # default heads-up range

        if strength < threshold:
            return do_check_fold(f"fold {cls}")

        if call_c == 0:
            # Steal blinds aggressively
            mult = 3 if strength > 0.70 else 2.5
            r = do_open(mult, f"steal {cls} vs {style}")
            if r: return r
            return do_call(f"limp {cls}") or do_check_fold("check")

        # Facing a raise — call or 3-bet
        if strength >= 0.65:
            if style == "passive" or style == "calling_station":
                r = do_open(3, f"3bet {cls} — exploit {style}")
                if r: return r
            return do_call(f"call {cls}") or do_check_fold("check")

        return {"action":"fold","message":f"fold {cls} vs raise","reasoning":FALLBACK_R}

    # ── POSTFLOP ──────────────────────────────────────────────────────────────
    n_sims  = 800 if deadline_s > 8 else 400
    eq      = equity(hole, board, opponents=1, n=n_sims)
    eq_pct  = int(eq * 100)

    try:
        made_rank = hand_rank([parse_card(c) for c in hole+board])[0]
    except:
        made_rank = 0

    # Check for royal flush
    royal = False
    if cls in SUITED_ROYALS:
        try:
            suit = hole[0][-1] if hole[0][-1] == hole[1][-1] else None
            if suit:
                suited = [c for c in hole+board if c[-1].lower()==suit.lower()]
                royal  = {c[0].upper() for c in suited} >= {"A","K","Q","J","T"}
        except: pass

    # Royal flush — slow play, let opponent bet into us
    if royal:
        if call_c == 0: return do_check_fold("check — royal flush trap")
        return do_allin("ROYAL FLUSH — all in!")

    # ── Opponent-aware postflop strategy ─────────────────────────────────────

    # vs PASSIVE — bluff freely, they fold a lot
    if style == "passive":
        if eq >= 0.40 and call_c == 0:
            bluff_frac = 0.70 if street == "flop" else 0.80
            r = do_bet(bluff_frac, f"bluff vs passive eq={eq_pct}%")
            if r: return r
        if eq >= 0.50:
            return do_call(f"call passive eq={eq_pct}%") or do_check_fold("check")
        if call_c > 0: return {"action":"fold","message":f"fold eq={eq_pct}%","reasoning":FALLBACK_R}
        return do_check_fold(f"check eq={eq_pct}%")

    # vs CALLING STATION — only bet for value, no bluffs
    if style == "calling_station":
        if eq >= 0.65:
            r = do_bet(0.75, f"value vs station eq={eq_pct}%")
            if r: return r
            return do_call(f"call station eq={eq_pct}%") or do_check_fold("check")
        if call_c > 0 and eq < 0.50:
            return {"action":"fold","message":f"fold vs station eq={eq_pct}%","reasoning":FALLBACK_R}
        return do_check_fold(f"check vs station eq={eq_pct}%")

    # vs AGGRESSIVE — trap them, let them bet into us
    if style == "aggressive":
        if made_rank >= 3:  # monster — check/call to let them bluff
            if call_c == 0: return do_check_fold(f"check trap rank{made_rank}")
            if eq >= 0.60: return do_call(f"call trap rank{made_rank}") or do_check_fold("check")
        if eq >= 0.70:  # very strong — raise back
            r = do_bet(0.85, f"raise vs aggressive eq={eq_pct}%")
            if r: return r
            return do_call(f"call aggressive eq={eq_pct}%") or do_check_fold("check")
        if call_c > 0 and eq < 0.45:
            return {"action":"fold","message":f"fold vs aggressive eq={eq_pct}%","reasoning":FALLBACK_R}
        return do_check_fold(f"check vs aggressive eq={eq_pct}%")

    # ── Default balanced play ─────────────────────────────────────────────────

    # River blast — 90%+ equity
    if street == "river" and eq >= 0.90:
        return do_allin(f"river blast eq={eq_pct}%")

    # Strong made hands — fire every street
    if made_rank >= 3:
        r = do_bet(0.85, f"fire monster rank{made_rank}")
        if r: return r
        return do_call("call monster") or do_check_fold("check")

    if made_rank == 2:
        r = do_bet(0.75, "fire two pair")
        if r: return r
        return do_call("call two pair") or do_check_fold("check")

    if made_rank == 1 and eq >= 0.55:
        r = do_bet(0.60, f"fire top pair eq={eq_pct}%")
        if r: return r
        return do_call("call top pair") or do_check_fold("check")

    # Equity based
    need = 0.65 if call_is_huge else (0.55 if call_is_big else 0.45)
    if eq >= need:
        if call_c == 0:
            r = do_bet(0.55, f"value eq={eq_pct}%")
            if r: return r
        else:
            return do_call(f"call EV eq={eq_pct}%") or do_check_fold("check")

    # Bluff 1 in 4 times on flop/turn with dry board
    if call_c == 0 and street in ("flop","turn") and eq < 0.45:
        if random.random() < 0.25:
            r = do_bet(0.60, f"bluff eq={eq_pct}%")
            if r: return r

    if call_c > 0:
        return {"action":"fold","message":f"fold eq={eq_pct}%","reasoning":FALLBACK_R}

    return do_check_fold(f"check eq={eq_pct}%")


# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    # Find heads-up competition
    client = httpx.Client(timeout=60, headers=HEADERS, verify=False)

    def safe_get(url, **kw):
        try:
            r = client.get(url, **kw)
            return r.json() if r.content else {}
        except: return {}

    def safe_post(url, **kw):
        try:
            r = client.post(url, **kw)
            return r.json() if r.content else {}
        except: return {}

    # List active competitions and find heads-up one
    comps = safe_get(f"{BASE}/competition/list-active")
    hu_comp = None
    for c in (comps if isinstance(comps, list) else []):
        name = c.get("name","").lower()
        if "heads" in name or "researcher" in name or "1v1" in name or "headsup" in name:
            hu_comp = c["id"]
            print(f"Found heads-up competition: {c['name']} ({hu_comp})", flush=True)
            break

    if not hu_comp:
        print("No heads-up competition found yet. Available:", flush=True)
        for c in (comps if isinstance(comps, list) else []):
            print(f"  - {c.get('name')} ({c.get('id')})", flush=True)
        print("Waiting for researcher track to open on June 21...", flush=True)
        return

    # Join
    d = safe_post(f"{BASE}/texas/join", json={"competitionId": hu_comp})
    print(f"Join: {d}", flush=True)

    last_stat = time.time()
    print("Heads-up agent running — adaptive style based on opponent profiling.", flush=True)

    while True:
        now = time.time()

        if now - last_stat > 30:
            sd    = safe_get(f"{BASE}/agent/{AGENT_ID}/stats", params={"competitionId": hu_comp})
            chips = sd.get("totalScore", 0)
            rank  = sd.get("rank","?")
            hands = sd.get("totalSubmissions", 0)
            print(f"  Chips={chips} | Rank={rank} | Hands={hands} | OppStyle={opp_style()}", flush=True)
            last_stat = now

        pd     = safe_get(f"{BASE}/texas/pending-actions", params={"competitionId": hu_comp})
        tables = pd.get("tables") or []

        if not tables:
            # Try to join a new table
            safe_post(f"{BASE}/texas/join", json={"competitionId": hu_comp})
            time.sleep(0.5)
            continue

        tables.sort(key=lambda t: t.get("actionDeadlineAt") or 0)

        for table in tables:
            tid        = table.get("tableId","")
            deadline_s = max(0.0,((table.get("actionDeadlineAt") or 0)-time.time()*1000)/1000)
            dec        = decide(table, deadline_s)
            action     = dec["action"]

            payload = {"tableId":tid,"action":action,
                       "message":dec.get("message","")[:500],
                       "reasoning":dec.get("reasoning",FALLBACK_R)[:150]}
            if "amount" in dec and action not in ("fold","check","call"):
                payload["amount"] = dec["amount"]

            self_n = table.get("selfSeatNumber") or 0
            hole   = next((s.get("holeCards",[]) for s in (table.get("seats") or [])
                           if s.get("seatNumber")==self_n),[])
            board  = table.get("boardCards") or []
            cls    = _hand_class(hole)
            amt_str= f" {payload['amount']}" if "amount" in payload else ""
            print(f"  [{tid[:6]}] {cls} {board} -> {action}{amt_str} [{opp_style()}]", flush=True)

            try:
                client.post(f"{BASE}/texas/action", json=payload)
            except Exception as e:
                print(f"  Exc: {e}")

    client.close()

if __name__ == "__main__":
    main()

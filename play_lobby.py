"""
Statistical equity agent — slow build, no rushing.
Key concepts: pot odds, implied odds, SPR, board texture, EV-based decisions.
"""
import os, sys
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import itertools, random, time, csv, os
import httpx
from dotenv import load_dotenv
load_dotenv()

# ── Game log setup ────────────────────────────────────────────────────────────
LOG_FILE = "gamelog.csv"
def _init_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow([
                "timestamp","competition","table_id","street","hand_class",
                "hole_cards","board_cards","action","amount","equity_pct",
                "pot","call_amount","stack","message"
            ])

def _log_hand(comp_id, tid, street, cls, hole, board, action, amount, eq_pct, pot, call_c, stack, msg):
    try:
        with open(LOG_FILE, "a", newline="") as f:
            csv.writer(f).writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"), comp_id, tid, street, cls,
                " ".join(hole), " ".join(board), action, amount,
                eq_pct, pot, call_c, stack, msg
            ])
    except: pass

API_KEY      = os.environ["ARENA_API_KEY"]
AGENT_ID     = os.environ["ARENA_AGENT_ID"]
BASE         = "https://arena.dev.fun/api/arena"
HEADERS      = {"x-arena-api-key": API_KEY, "Content-Type": "application/json"}
FALLBACK_R   = '{vr:"stat",ke:"ev",pp:"slow"}'

COMPETITIONS = [
    {"id": "cmqggiv9k37am11ydmppz466e", "name": "Tournament S2", "max_tables": 5},
    {"id": "cmqf827h30u7dfca3x2aqvzjv", "name": "Playground S3", "max_tables": 5},
]

# ── Card utilities ────────────────────────────────────────────────────────────

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

def equity(hole, board, opponents=1, n=600):
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
        s    = random.sample(deck, needed+2*opponents)
        opps = [s[i*2:(i+1)*2] for i in range(opponents)]
        extra= [parse_card(c) for c in s[2*opponents:]]
        fb   = brd+extra
        mine = hand_rank(my+fb)
        best = max(hand_rank([parse_card(c) for c in o]+fb) for o in opps)
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

def _count_players(table):
    return sum(1 for s in (table.get("seats") or []) if s.get("stackChips",0)>0)

def pot_odds(call_amount, pot_size):
    total = pot_size + call_amount
    return call_amount / total if total else 0.0

def implied_odds_factor(street, n_opponents):
    if street == "river": return 1.0
    if street == "turn":  return 1.25
    return 1.0 + 0.15 * n_opponents

def spr(stack, pot):
    return stack / max(pot, 1)

def board_texture(board):
    if not board: return 0, False, False
    suits = [c[-1].lower() for c in board]
    vals  = sorted([RANK_VAL[c[0].upper()] for c in board])
    flush_possible    = max(suits.count(s) for s in "shdc") >= 3
    gaps = [vals[i+1]-vals[i] for i in range(len(vals)-1)]
    straight_possible = any(g <= 2 for g in gaps) if gaps else False
    wet = (1 if flush_possible else 0) + (1 if straight_possible else 0)
    return wet, flush_possible, straight_possible

def draw_equity_boost(hole, board):
    try:
        suits  = [c[-1].lower() for c in hole+board]
        hole_s = [c[-1].lower() for c in hole]
        vals   = sorted([RANK_VAL[c[0].upper()] for c in hole+board])
        flush_outs = 0
        for s in "shdc":
            if suits.count(s) == 4 and hole_s.count(s) >= 1:
                flush_outs = 9
        oesd_outs = 0
        for i in range(len(vals)-3):
            if vals[i+3]-vals[i] == 3 and len(set(vals[i:i+4]))==4:
                oesd_outs = 8
        outs = max(flush_outs, oesd_outs)
        streets_left = 2 if len(board)==3 else (1 if len(board)==4 else 0)
        return outs * (4 if streets_left==2 else 2) / 100
    except: return 0.0

# ── Preflop hand strength ─────────────────────────────────────────────────────
PREFLOP_STRENGTH = {}
for i,r in enumerate(RANKS):
    PREFLOP_STRENGTH[r+r] = 0.35 + i*0.05
for i,r1 in enumerate(RANKS):
    for j,r2 in enumerate(RANKS):
        if j >= i: continue
        gap  = i-j
        base = (i+j)/2/12
        PREFLOP_STRENGTH[f"{r1}{r2}s"] = min(max(0.0, base-gap*0.04+0.06), 0.90)
        PREFLOP_STRENGTH[f"{r1}{r2}o"] = min(max(0.0, base-gap*0.04),      0.85)

LATE_POS      = {1, 2, 6}
SUITED_ROYALS = {"AKs","AJs","ATs","KQs","KJs","QJs","JTs"}  # AQs handled separately

def _is_suited_royal(hole):
    return _hand_class(hole) in SUITED_ROYALS

def _made_flush(hole, board):
    try:
        all_s  = [c[-1].lower() for c in hole+board]
        hole_s = [c[-1].lower() for c in hole]
        return any(all_s.count(s)>=5 and hole_s.count(s)>=1 for s in "shdc")
    except: return False

def _is_royal_flush(hole, board):
    try:
        all_cards = hole + board
        for suit in "shdc":
            suited = [c for c in all_cards if c[-1].lower() == suit]
            if len(suited) >= 5:
                ranks_in_suit = {c[0].upper() for c in suited}
                if {"A","K","Q","J","T"}.issubset(ranks_in_suit):
                    return True
        return False
    except: return False

# ── Opponent aggression tracker ───────────────────────────────────────────────
# Maps agentId -> {"raises": int, "calls": int, "folds": int}
OPP_STATS = {}

def _track_opponents(table):
    for seat in (table.get("seats") or []):
        aid = seat.get("agentId") or seat.get("handle") or ""
        if not aid or seat.get("seatNumber") == table.get("selfSeatNumber"):
            continue
        action = (seat.get("lastAction") or "").lower()
        if not action: continue
        s = OPP_STATS.setdefault(aid, {"raises":0,"calls":0,"folds":0})
        if action in ("raise","bet","allin"): s["raises"] += 1
        elif action == "call":               s["calls"]  += 1
        elif action == "fold":               s["folds"]  += 1

def _opp_is_aggressive(table):
    for seat in (table.get("seats") or []):
        aid = seat.get("agentId") or seat.get("handle") or ""
        s = OPP_STATS.get(aid)
        if not s: continue
        total = s["raises"] + s["calls"] + s["folds"]
        if total >= 5 and s["raises"] / total > 0.45:
            return True
    return False

def _opp_is_passive(table):
    """Opponent folds a lot — good bluff target."""
    for seat in (table.get("seats") or []):
        aid = seat.get("agentId") or seat.get("handle") or ""
        s = OPP_STATS.get(aid)
        if not s: continue
        total = s["raises"] + s["calls"] + s["folds"]
        if total >= 6 and s["folds"] / total > 0.55:
            return True
    return False

def _has_flush_draw(hole, board):
    try:
        all_s  = [c[-1].lower() for c in hole+board]
        hole_s = [c[-1].lower() for c in hole]
        return any(all_s.count(s)==4 and hole_s.count(s)>=1 for s in "shdc")
    except: return False


def decide(table, deadline_s=20.0):
    allowed   = table.get("allowedActions") or {}
    available = allowed.get("availableActions") or []

    if deadline_s < 3.0:
        return {"action":"check" if "check" in available else "fold",
                "message":"deadline","reasoning":FALLBACK_R}

    _track_opponents(table)
    opp_aggressive = _opp_is_aggressive(table)
    opp_passive    = _opp_is_passive(table)

    self_n  = table.get("selfSeatNumber") or 0
    seats   = table.get("seats") or []
    me      = next((s for s in seats if s.get("seatNumber")==self_n), {})
    hole    = list(me.get("holeCards") or [])
    board   = list(table.get("boardCards") or [])
    street  = _street(board)
    pot     = max(int(table.get("potChips") or 0), 1)
    call_c  = int(allowed.get("callChips") or 0)
    my_stk  = int(me.get("stackChips") or 1000)
    n_play  = _count_players(table)
    n_opp   = max(1, n_play-1)
    cls     = _hand_class(hole)
    in_pos  = self_n in LATE_POS

    rr   = allowed.get("raiseRange") or {}
    br   = allowed.get("betRange")   or {}
    r_lo = int(rr.get("min") or 4);  r_hi = int(rr.get("max") or r_lo)
    b_lo = int(br.get("min") or 4);  b_hi = int(br.get("max") or b_lo)

    call_frac    = call_c / max(my_stk, 1)
    call_is_big  = call_frac > 0.15
    call_is_huge = call_frac > 0.35
    opp_allin    = call_frac >= 0.80
    p_odds       = pot_odds(call_c, pot)
    impl_factor  = implied_odds_factor(street, n_opp)
    spr_val      = spr(my_stk, pot)
    wet, fp, sp  = board_texture(board)
    suited_royal = _is_suited_royal(hole)

    def do_bet(frac, msg):
        raw = int(pot * frac)
        if street != "preflop":
            raw = max(raw, 100)   # postflop minimum 100
            raw = min(raw, max(int(my_stk * 0.60), 100))  # never more than 60% of stack
        if "bet" in available:
            return {"action":"bet","amount":max(b_lo,min(raw,b_hi)),"message":msg,"reasoning":FALLBACK_R}
        if "raise" in available:
            return {"action":"raise","amount":max(r_lo,min(raw,r_hi)),"message":msg,"reasoning":FALLBACK_R}
        return None

    def do_open(mult, msg):
        amt = max(r_lo, min(r_lo*mult, r_hi))
        if street == "preflop":
            amt = min(amt, 30)  # never raise more than 30 preflop — keep players in
        act = "raise" if "raise" in available else ("bet" if "bet" in available else None)
        if act:
            return {"action":act,"amount":amt,"message":msg,"reasoning":FALLBACK_R}
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

    # ── PREFLOP ──────────────────────────────────────────────────────────────
    if street == "preflop":
        strength = PREFLOP_STRENGTH.get(cls, 0.30)

        # Suited royals — just call, never raise, keep players in
        if suited_royal:
            if opp_allin:
                return do_call(f"call allin {cls}") or do_check_fold("check")
            if call_c == 0:
                return do_check_fold(f"check {cls} — suited royal")
            if not call_is_huge:
                return do_call(f"call {cls} — suited royal") or do_check_fold("check")
            return {"action":"fold","message":f"fold {cls} — too expensive","reasoning":FALLBACK_R}

        # Premium hands — open raise if no one raised yet, otherwise just call
        if cls in ("AA","KK","QQ","JJ","AKs","AKo","AQs","AQo","TT","99","AJs","AJo","ATs"):
            if opp_allin:
                return do_call(f"call allin {cls}") or do_check_fold("check")
            if call_c == 0:
                r = do_open(2, f"raise {cls}")
                if r: return r
            # Facing a raise — just call, see the flop first
            return do_call(f"call {cls} — see flop") or do_check_fold("check")

        # vs all-in — fold everything else
        if opp_allin:
            return {"action":"fold","message":f"fold vs allin {cls}","reasoning":FALLBACK_R}

        threshold = 0.54 if not in_pos else 0.46
        if strength < threshold:
            return do_check_fold(f"fold {cls}")

        if call_c == 0:
            mult = 2 if strength > 0.75 else 1.5
            r = do_open(mult, f"open {cls}")
            if r: return r
            return do_call(f"limp {cls}") or do_check_fold("check")

        is_suited = cls.endswith("s")
        raise_threshold = 0.55
        if strength >= raise_threshold:
            # Just call — see the flop before deciding, don't out-raise
            return do_call(f"call {cls} — see flop") or do_check_fold("check")

        # Facing a raise with mediocre hand — fold
        return {"action":"fold","message":f"fold {cls} vs raise","reasoning":FALLBACK_R}

    # ── POSTFLOP ─────────────────────────────────────────────────────────────

    try:
        made_rank = hand_rank([parse_card(c) for c in hole+board])[0]
    except Exception:
        made_rank = 0

    n_sims  = 600 if deadline_s > 8 else 350
    eq      = equity(hole, board, opponents=min(n_opp,3), n=n_sims)
    draw_eq = draw_equity_boost(hole, board)
    eff_eq  = min(eq + draw_eq * (impl_factor - 1.0), 0.99)
    eq_pct  = int(eff_eq*100)

    flush_draw  = _has_flush_draw(hole, board)
    made_flush_ = _made_flush(hole, board)

    # ── Suited royal postflop ─────────────────────────────────────────────────
    royal_flush = _is_royal_flush(hole, board)
    if suited_royal:
        if royal_flush:
            # Slow play — trap opponents, don't scare them away
            if call_c == 0:
                return do_check_fold(f"check — royal flush, slow play")
            # Opponent raised — re-raise to extract value
            return do_bet(0.85, f"re-raise royal flush {cls}") or do_call(f"call royal flush {cls}")
        if made_flush_ or made_rank >= 5:
            r = do_bet(0.85, f"FLUSH HIT — royal {cls}")
            if r: return r
        elif flush_draw:
            if call_c == 0:
                return do_check_fold("check — drawing")
            break_even = p_odds / impl_factor
            if eff_eq >= break_even:
                return do_call("call flush draw") or do_check_fold("check")
            return {"action":"fold","message":"fold flush draw — bad odds","reasoning":FALLBACK_R}

    # ── Flush draw (non-suited-royal): call if not hugely expensive ──────────
    if flush_draw and not suited_royal and street in ("flop", "turn"):
        if call_c == 0:
            r = do_bet(0.40, "flush draw — semi-bluff")
            if r: return r
            return do_check_fold("check — flush draw")
        if not call_is_huge:
            return do_call(f"call flush draw {eq_pct}%") or do_check_fold("check")
        # huge call on a draw: only if EV clearly positive
        ev = eff_eq * pot - (1-eff_eq) * call_c
        if ev > 0:
            return do_call(f"call big flush draw EV={int(ev)}") or do_check_fold("check")
        return {"action":"fold","message":"fold flush draw — too expensive","reasoning":FALLBACK_R}

    # ── Opponent all-in ───────────────────────────────────────────────────────
    if opp_allin:
        ev = eff_eq * pot - (1-eff_eq) * call_c
        if ev > 0 or made_rank >= 3:
            return do_call(f"call allin EV={int(ev)} eq={eq_pct}%") or do_check_fold("check")
        return {"action":"fold","message":f"fold allin EV={int(ev)}","reasoning":FALLBACK_R}

    # ── Monsters (trips+): big value bet, no all-in ───────────────────────────
    if made_rank >= 3:
        if call_c == 0:
            r = do_bet(0.80, f"monster rank{made_rank}")
            if r: return r
        else:
            r = do_bet(0.85, f"raise monster rank{made_rank}")
            if r: return r
            return do_call(f"call monster") or do_check_fold("check")
        return do_check_fold("check monster")

    # ── Two pair: raise, never fold ───────────────────────────────────────────
    if made_rank == 2:
        if call_c == 0:
            r = do_bet(0.65, "two-pair value")
            if r: return r
        else:
            if not call_is_huge:
                r = do_bet(0.75, "two-pair raise")
                if r: return r
            return do_call("two-pair call") or do_check_fold("check")

    # ── River blast — very strong hand, big raise not all-in ─────────────────
    if street == "river" and eff_eq >= 0.90:
        r = do_bet(0.75, f"river blast eq={eq_pct}%")
        if r: return r

    # ── Main equity + EV engine ───────────────────────────────────────────────
    if call_is_huge:
        need = 0.68
    elif call_is_big:
        need = 0.58
    else:
        need = 0.50

    if wet == 2: need += 0.04
    elif wet == 1: need += 0.02

    # vs aggressive opponent — demand more equity before calling
    if opp_aggressive and call_c > 0:
        need += 0.05

    ev_call = eff_eq * pot - (1-eff_eq) * call_c

    if eff_eq >= need:
        if call_c == 0:
            bet_frac = 0.40 if wet >= 1 else 0.50
            if spr_val < 4: bet_frac = 0.65
            r = do_bet(bet_frac, f"value eq={eq_pct}%")
            if r: return r
        elif ev_call > 0:
            if not call_is_huge:
                r = do_bet(0.55, f"raise eq={eq_pct}%")
                if r: return r
            return do_call(f"call EV={int(ev_call)}") or do_check_fold("check")
    else:
        # Bluff opportunity — opponent is passive/foldy, board is dry, heads up
        if (call_c == 0 and opp_passive and not opp_aggressive
                and wet == 0 and n_opp == 1
                and street in ("flop", "turn")
                and random.random() < 0.20):  # bluff 1 in 5 times when conditions met
            r = do_bet(0.60, f"bluff — passive opp, dry board eq={eq_pct}%")
            if r: return r
        if call_c > 0:
            return {"action":"fold","message":f"fold eq={eq_pct}%","reasoning":FALLBACK_R}

    return do_check_fold(f"check eq={eq_pct}%")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
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

    def try_join(comp_id):
        d = safe_post(f"{BASE}/texas/join", json={"competitionId": comp_id})
        kind = d.get("kind","")
        if kind=="queued":
            print(f"  [{comp_id[:8]}] Queued {(d.get('lobby') or {}).get('position','?')}", flush=True)
        elif kind=="seated":
            print(f"  [{comp_id[:8]}] Seated!", flush=True)
        elif "error" in d:
            if "enough chips" not in str(d.get("error","")):
                print(f"  [{comp_id[:8]}] Join: {d['error']}", flush=True)

    last_join = {c["id"]: 0 for c in COMPETITIONS}
    last_stat = time.time()

    _init_log()
    print("Statistical equity agent — Tournament S2 + Playground S3.", flush=True)

    for comp in COMPETITIONS:
        try_join(comp["id"])

    while True:
        now = time.time()

        if now - last_stat > 30:
            for comp in COMPETITIONS:
                sd    = safe_get(f"{BASE}/agent/{AGENT_ID}/stats",
                                 params={"competitionId": comp["id"]})
                chips = sd.get("totalScore", 0)
                rank  = sd.get("rank","?")
                hands = sd.get("totalSubmissions", 0)
                print(f"  [{comp['name']}] Chips={chips} | Rank={rank} | Hands={hands}", flush=True)
            last_stat = now

        all_tables = []
        for comp in COMPETITIONS:
            cid = comp["id"]
            if now - last_join[cid] > 3:
                sd     = safe_get(f"{BASE}/agent/{AGENT_ID}/stats", params={"competitionId": cid})
                chips  = sd.get("totalScore", 1000)
                pd     = safe_get(f"{BASE}/texas/pending-actions", params={"competitionId": cid})
                active = len(pd.get("tables") or [])
                while active < comp["max_tables"] and chips >= 200:
                    try_join(cid)
                    active += 1
                last_join[cid] = now

            pd = safe_get(f"{BASE}/texas/pending-actions", params={"competitionId": cid})
            for t in (pd.get("tables") or []):
                t["_comp_id"] = cid
                all_tables.append(t)

        if not all_tables:
            time.sleep(0.3)
            continue

        all_tables.sort(key=lambda t: t.get("actionDeadlineAt") or 0)

        for table in all_tables:
            tid        = table.get("tableId","")
            comp_id    = table.get("_comp_id","")
            deadline_s = max(0.0,((table.get("actionDeadlineAt") or 0)-time.time()*1000)/1000)
            dec        = decide(table, deadline_s)
            action     = dec["action"]

            payload = {"tableId":tid,"action":action,
                       "message":dec.get("message","")[:500],
                       "reasoning":dec.get("reasoning",FALLBACK_R)[:150]}
            if "amount" in dec and action not in ("fold","check","call"):
                payload["amount"] = dec["amount"]

            self_n = table.get("selfSeatNumber") or 0
            me_s   = next((s for s in (table.get("seats") or []) if s.get("seatNumber")==self_n), {})
            hole   = list(me_s.get("holeCards") or [])
            board  = table.get("boardCards") or []
            cls    = _hand_class(hole)
            street = _street(board)
            pot    = int(table.get("potChips") or 0)
            call_c = int((table.get("allowedActions") or {}).get("callChips") or 0)
            stack  = int(me_s.get("stackChips") or 0)
            amt    = payload.get("amount", 0)
            eq_pct = int(dec.get("message","0%").split("eq=")[-1].replace("%","").split()[0]) if "eq=" in dec.get("message","") else 0
            amt_str= f" {amt}" if amt else ""
            print(f"  [{comp_id[:8]}][{tid[:6]}] {cls} {board} -> {action}{amt_str}", flush=True)
            _log_hand(comp_id, tid, street, cls, hole, board, action, amt, eq_pct, pot, call_c, stack, dec.get("message",""))

            try:
                client.post(f"{BASE}/texas/action", json=payload)
            except Exception as e:
                print(f"  Exc: {e}")

    client.close()

if __name__=="__main__":
    main()

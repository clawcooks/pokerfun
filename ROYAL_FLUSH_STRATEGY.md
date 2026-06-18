# Royal Flush Strategy

This is the slow-play trap strategy we use when holding suited royal cards. It is designed to maximize pot size when we complete a royal flush or strong flush by keeping opponents in the hand as long as possible.

---

## Qualifying Hands (Suited Royals)

These are the hands that trigger the royal flush strategy:

| Hand | Description |
|------|-------------|
| AKs | Ace-King suited |
| AJs | Ace-Jack suited |
| ATs | Ace-Ten suited |
| KQs | King-Queen suited |
| KJs | King-Jack suited |
| QJs | Queen-Jack suited |
| JTs | Jack-Ten suited |

All five cards needed for a royal flush (A, K, Q, J, T) are represented across these combinations. Any two of these hole cards plus the right board completes the royal.

---

## The Strategy — Street by Street

### Preflop
- **Never raise** — just call the big blind or any raise
- If no one has raised, check if possible
- The goal is to keep as many players in the pot as possible
- A raise here telegraphs strength and reduces the pot we will eventually win

### Flop (3 board cards)
- **Flush draw (4 cards to flush):** Check or call small bets — never fold a flush draw with suited royals. Free cards are ideal.
- **No draw yet:** Check/fold if facing a large bet — don't chase with only 2 suited cards
- **Made flush already:** Bet 85% pot — extract value but leave room for opponents to call or re-raise

### Turn (4th board card)
- **Still drawing:** Continue calling cheap bets, check when possible. Implied odds are strong with one card left.
- **Made flush:** Bet 85% pot, call any raise — we are almost certainly ahead
- **Royal flush complete:** **CHECK** — do not bet. Let opponent bet into us.

### River (5th board card)
- **Royal flush complete:** Check or call. If opponent bets, **raise** to extract maximum value.
- **Made flush (not royal):** Bet 75–85% pot. If equity ≥ 90%, blast the river with a large bet.
- **Missed draw:** Check/fold — cut losses, do not bluff with a missed royal draw

---

## Why This Works

1. **Deception** — Passive preflop and early street play disguises the hand strength. Opponents assume we are weak or on a draw, not sitting on a monster.

2. **Pot building** — By not raising early, we encourage more players to stay in and build the pot naturally. A royal flush win against 3 players is worth far more than winning preflop with a 3-bet.

3. **Opponent commitment** — By the river, opponents are often pot-committed. A check on the river invites a bluff or value bet from opponents who think they are ahead, then we raise and collect.

4. **Unpredictability** — Aggressive agents expect aggression back. A passive line from us on strong hands creates confusion — they cannot tell if we are weak or trapping.

---

## Real Example

> We held **Q♠ J♠** in the Small Blind. Preflop: just called the big blind. Flop came **K♠ 9♠ 3♣** — flush draw. We checked. Turn: **T♠** — we now have Q♠ J♠ K♠ T♠, one card from a royal flush. We called a small bet. River: **A♠** — royal flush complete (A♠ K♠ Q♠ J♠ T♠). We checked. Opponent bet. We raised. Maximum value extracted.

---

## Key Rules Summary

| Situation | Action |
|-----------|--------|
| Preflop with suited royal | Call only, never raise |
| Flop — flush draw | Check or call cheap |
| Flop — made flush | Bet 85% pot |
| Turn — still drawing | Call cheap, check free |
| Turn — made flush | Bet 85% pot |
| River — royal flush complete | Check, then raise if opponent bets |
| River — strong flush, 90%+ equity | Bet 75% pot |
| River — missed draw | Check/fold |

---

## Research Note

The royal flush slow play demonstrates a broader principle: **hand strength alone does not determine optimal strategy — pot geometry and opponent psychology do.** A royal flush played aggressively from the start often wins less than one played passively, because opponents fold before committing chips. This is a case where maximizing EV requires counter-intuitive passivity early in the hand.

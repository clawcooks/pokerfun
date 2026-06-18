# Poker Arena Agent — Claude Sonnet

An AI poker agent competing in [DevFun Arena](https://arena.dev.fun) No-Limit Texas Hold'em tournaments and playgrounds.

**Handle:** claude-sonnet-46  
**Current competitions:** Tournament S2, Playground S3

---

## Strategy Overview

### Preflop
- Folds weak hands, plays top hands by strength score
- **Premium hands** (AA, KK, QQ, JJ, AKs, AKo, AQs, AQo, TT, 99, AJs, ATs) — always open raise or call, never fold
- **Suited royals** (AKs, AJs, ATs, KQs, KJs, QJs, JTs) — just call preflop, never raise (slow play to keep players in)
- **Facing a raise** — call if hand strength ≥ 0.55, otherwise fold. Never re-raise preflop.
- Preflop raises capped at 30 chips to avoid scaring opponents away

### Postflop
- **600 Monte Carlo simulations** to calculate exact equity vs opponents
- **Pot odds** — only call if mathematically justified
- **Implied odds** — flop/turn draws worth more (future streets factor)
- **SPR** (Stack-to-Pot Ratio) — adjusts bet sizing based on commitment level
- **Board texture** — wet boards (flush/straight draws) demand higher equity threshold
- **EV calculation** — only calls where expected value is positive

### Equity thresholds
| Situation | Equity needed |
|-----------|--------------|
| Normal call | 50% |
| Big call (15–35% of stack) | 58% |
| Huge call (35%+ of stack) | 68% |
| Wet board adjustment | +2–4% |
| vs Aggressive opponent | +5% |

### Special rules
- **Royal flush** — check/call all the way, only raise if opponent raises. Never scare them away.
- **Flush draws** — always call on flop/turn unless bet is huge (>35% of stack)
- **River blast** — 75% pot bet when equity ≥ 90% (near unbeatable hand)
- **Bluffing** — 1 in 5 chance on dry boards, heads up, against passive opponents only
- **Opponent tracking** — tracks raise/call/fold rate per opponent across hands and adjusts accordingly

### Bet sizing
- Postflop raises: minimum 100 chips, max 60% of stack
- Monsters (trips+): 80–85% pot
- Two pair: 65–75% pot
- Value bets: 40–55% pot

---

## Setup

### Requirements
```
pip install httpx python-dotenv
```

### Environment variables
Create a `.env` file (never commit this):
```
ARENA_API_KEY=your_api_key_here
ARENA_AGENT_ID=your_agent_id_here
```

### Run
```powershell
python run_forever.py
```

The agent joins tables automatically, handles reconnects, and plays both competitions simultaneously.

---

## Results
- **Playground S1** — peaked at rank #9 out of ~800 agents (44,242 chips from 1,000 start)
- **Tournament S1** — best rank #11
- **Tournament S2** — best rank #4 (active)
- **Playground S3** — active

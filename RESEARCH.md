# Research Write-Up: Statistical Equity Agent for No-Limit Texas Hold'em

**Agent:** Claude Sonnet (claude-sonnet-46)  
**Platform:** DevFun Arena  
**Author:** clawcooks  
**GitHub:** https://github.com/clawcooks/pokerfun

---

## Abstract

This project explores the application of real-time statistical decision-making in an AI poker agent competing in No-Limit Texas Hold'em. Rather than relying on pre-trained neural networks or hardcoded rule tables, the agent uses Monte Carlo equity simulation combined with game-theoretic concepts (pot odds, implied odds, SPR, board texture) to make mathematically justified decisions at every street. The agent has demonstrated competitive performance, peaking at **rank #4** in Tournament S2 and **rank #9 out of ~800 agents** in Playground S1 from a starting stack of 1,000 chips.

---

## Approach

### Core Decision Engine
The agent's postflop decisions are driven by a statistical equity engine:

1. **Monte Carlo Simulation** — 600 random simulations per hand to estimate win probability against opponents
2. **Pot Odds** — minimum equity required = call_amount / (pot + call_amount)
3. **Implied Odds** — future street multipliers (1.25x turn, 1.0 + 0.15 × opponents on flop) reward drawing hands
4. **Stack-to-Pot Ratio (SPR)** — adjusts aggression when committed to a pot
5. **Board Texture** — wet boards (flush/straight draws possible) demand 2–4% higher equity threshold
6. **Expected Value (EV)** — final gate: only call if EV = equity × pot − (1 − equity) × call > 0

### Preflop Model
A Chen-inspired hand strength scoring system (0–1 scale) ranks all 169 hand classes. Key rules:
- Premium hands (AA, KK, QQ, JJ, AK, AQ) always play
- Suited connectors with royal flush potential (AKs, KQs, QJs, JTs etc.) are slow played preflop to trap opponents
- Raises capped at 30 chips preflop to keep opponents in the pot
- Facing raises: call if strength ≥ 0.55, fold otherwise — no re-raising preflop

### Opponent Modeling
The agent tracks each opponent's action history (raises, calls, folds) across hands:
- **Aggressive tag** (raise rate > 45%) → demand 5% more equity before calling their bets
- **Passive tag** (fold rate > 55%) → trigger bluffing conditions on dry boards

### Deception Layer
- **Bluffing** — 20% probability on dry boards (no flush/straight draws), heads up, against passive opponents only
- **Royal flush trap** — when holding suited royal cards, check/call all streets until the flush completes, then raise only if opponent bets
- **River blast** — 75% pot bet when equity ≥ 90% (near-unbeatable hand on final street)

---

## Results

| Competition | Peak Rank | Peak Chips | Starting Chips |
|-------------|-----------|------------|----------------|
| Playground S1 | #9 / 800 | 44,242 | 1,000 |
| Tournament S1 | #11 | — | 1,000 |
| Tournament S2 | #4 | ~3,000 | 1,000 |
| Playground S3 | #62 | 3,676 | 1,000 |

The agent consistently outperforms the majority of agents through disciplined fold equity and mathematically grounded call decisions rather than aggression alone.

---

## Key Findings

### 1. Raise sizing matters more than hand strength
Raising too large preflop (6x BB) caused opponents to fold, reducing pot size and eliminating implied odds for strong draws. Capping preflop raises at 30 chips significantly improved pot building.

### 2. Passive folding is more costly than calling too much
The agent went through phases of over-folding (70% equity threshold on flop) that caused chip bleed purely from blind losses. The optimal threshold appears to be 50% with stack-size adjustments.

### 3. Agent reading and counter-play
A core part of our strategy is actively reading opponent agents and counter-playing them. The agent tracks every opponent's action history across hands — raise rate, call rate, and fold rate — and classifies them in real time:

- **Aggressive agents** (raise rate > 45%) — we tighten our calling range, demand 5% more equity, and let them bluff into our strong hands rather than inflating pots ourselves
- **Passive agents** (fold rate > 55%) — we exploit their weakness with well-timed bluffs on dry boards, representing strength they are unlikely to challenge
- **Calling stations** (high call rate, low fold rate) — we stop bluffing entirely and only bet for value, extracting chips when we hold strong hands

This counter-play system means the agent doesn't play a fixed strategy — it adapts its aggression, bluff frequency, and calling thresholds based on who is sitting at the table. The goal is to identify each agent's pattern within the first 6–10 hands and exploit it for the remainder of the session. This approach mirrors how experienced human players profile opponents and shift gears accordingly.

### 4. Slow play is situational
Suited royal slow play keeps opponents in the pot but can backfire when opponents hit better draws. Conditional slow play (board texture dependent) would improve outcomes.

### 5. Monte Carlo accuracy vs speed tradeoff
600 simulations give ~95% accuracy but cost ~2–3 seconds per decision. Reducing to 350 sims under time pressure (< 8 seconds) introduces variance but avoids timeouts. Future work could explore faster equity approximation methods.

---

## Open Research Questions

### 1. Dynamic opponent modeling
Can we build richer opponent profiles — not just aggression rate but bet sizing patterns, position tendencies, and showdown frequencies — to further refine our calling and bluffing decisions?

### 2. GTO vs Exploitative play
The current agent is purely exploitative (adjusts to opponents). How much EV is lost by not playing a Game Theory Optimal (GTO) baseline? Can a hybrid approach (GTO default, exploit when reads are confident) outperform both?

### 3. Multi-street planning
Currently decisions are made street by street. Can we improve EV by planning across streets — e.g., deciding on the flop how we intend to play the turn and river based on card runouts?

### 4. Stack preservation vs chip accumulation
In tournaments, survival matters as much as chip growth. How should equity thresholds adjust as the tournament progresses and blind levels increase?

### 5. Bluff frequency optimization
The current 20% bluff frequency on qualifying conditions is arbitrary. What is the optimal bluff frequency against different opponent types to maximize EV without becoming predictable?

### 6. Neural equity estimation
Could a lightweight neural network trained on hand histories replace Monte Carlo simulation, providing faster and potentially more accurate equity estimates?

---

## Conclusion

A statistically grounded poker agent built on Monte Carlo simulation and classical game theory concepts is competitive against a broad field of AI agents. The key insight is that **disciplined mathematical decision-making combined with adaptive opponent reading outperforms both pure aggression and pure passivity.** The agent's performance demonstrates that even without deep learning, real-time statistical reasoning can achieve top-tier results in multi-agent poker competition.

Future research will focus on multi-street planning, richer opponent modeling, and exploring the GTO vs exploitative tradeoff in tournament settings.

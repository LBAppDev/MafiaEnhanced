# 🕵️ Mafia Enhanced - Discord Psychological Deduction Bot

A sophisticated Discord bot implementing **Mafia/Werewolf** with an advanced **Suspicion Matrix** engine that simulates realistic psychological dynamics, confirmation bias, and memory decay.

## 🎮 Game Overview

Mafia Enhanced transforms the classic party game by introducing a mathematical psychology system. Every action, accusation, and vote shapes a **web of suspicion** that evolves throughout the game.

### Core Features

- **Suspicion Matrix**: Dynamic trust/suspicion values (0-100) for each player's relationships
- **Psychological Realism**: Confirmation bias, memory drift, intuition leaks
- **Phase-Specific Mechanics**: Different suspicion rules for discussion, voting, and night phases
- **Advanced Role Interactions**: Doctor saves, Detective investigations with intuition propagation
- **Historical Analysis**: Vindication when Mafia exposed, penalties for wrong votes
- **Rumor Mill System**: Organic conversation starters via random suspicion shifts

## 📊 The Suspicion Matrix

At the heart of the engine is the **SuspicionMatrix** - a mathematical representation of who suspects whom:

```
matrix[observer_id][target_id] = suspicion_value (0-100)
```

### Suspicion Scale
- **0-5% (Trust)**: "I believe you're my teammate/confirmed innocent"
- **35% (Baseline)**: "Stranger danger - normal uncertainty"
- **95-100% (Conviction)**: "I'm certain you're Mafia"

### Initialization Rules
- **Mafia Members**: Start with 0 suspicion of each other (they know each other)
- **Everyone Else**: Start at 35 ± random noise (simulates irrational biases)

## 🧠 The Mathematical Core

### updateBelief() Function

Every interaction runs through the core psychology engine:

```
1. Base Weight: Standard impact of action (e.g., +20% for accusations)
2. Noise Multiplier: Random 0.6x to 1.4x variation
3. Misinterpretation: 5% chance to flip polarity ("You look too innocent!")
4. Confirmation Bias:
   - If I suspect you (>60%): Bad actions hurt more (x1.4)
   - If I trust you (<40%): Bad actions are excused (x0.5)
5. Clamping: Values stay between 5-95 (no absolute certainty except roles)
```

### Memory Drift

Every round, suspicion naturally drifts back toward baseline:

```
NewValue = (OldValue × 0.85) + (Baseline × 0.15)
```

This ensures one bad round doesn't doom a player forever.

## 📋 Phase-Specific Mechanics

### Day/Discussion Phase 🗣️

**Actions**: Accuse, Defend, Discuss

- **Trust-Weighted Influence**: Accusations from trusted players impact you more
- **Reverse Psychology**: If I suspect the accuser (>60%), their accusation makes me trust the target
- **Lurker Penalty**: Players with zero actions gain suspicion (+0.12 weight)
- **Guilt by Association**: Defending a highly suspicious player makes you suspicious

### Voting Phase 🗳️

**Actions**: Cast vote to eliminate

- **Hypocrisy Check**: Accused X but voted Y? → +0.30 suspicion
- **Consistency Bonus**: Accused X and voted X? → -0.10 suspicion
- **Bandwagon Effect**: Voted late (last 40%)? → +0.15 suspicion
- **Wrong Accusation**: Voted for innocent who dies? → +0.25 suspicion

### Night Phase 🌙

**Actions**: Role abilities activate

#### Doctor 💊
- Saves one person, preventing Mafia kill
- **Doctor Bias**: Trusts saved person (suspicion → 0)
- **Guardian Angel**: Saved person trusts doctor back

#### Detective 🔍
- Investigates one player, learns true role
- **Certainty**: Sets suspicion to 99 (Mafia) or 5 (Innocent)
- **Intuition Leak**: 15% of knowledge spreads to others via body language

#### Mafia 💀
- Votes on victim to kill
- **Frame-up**: 40% chance to plant suspicion on random innocent

#### Villager 🏘️
- Sleeps, cannot act

## 🎯 Advanced Systems

### Historical Vindication

When a player dies, the engine analyzes all previous voting:

**If Mafia Dies:**
- Those who voted for them gain massive trust (-0.40 weight)
- Those who never voted for them gain suspicion (+0.25 weight)

**If Innocent Dies:**
- All voters lose trust (+0.25 weight)

### Rumor Mill

30% chance each round:
- Randomly selects a target player
- Applies ±7% suspicion shift to all observers
- Creates organic conversation: "Why is everyone suddenly talking about Player X?"

### Intuition Propagation

Detective's certainty isn't completely hidden:
- Small suspicion nudges leak to other players
- Makes Detective act slightly more confident/nervous
- Other players subconsciously shift their views

## 📊 Weight Summary

| Action | Weight | Logic |
|--------|--------|-------|
| Detective Finds Mafia | +1.2 | Absolute Certainty |
| Voted for Mafia (Vindication) | -0.40 | You helped town |
| Defended a Mafia | +0.35 | You're an accomplice |
| Hypocrisy | +0.30 | Words don't match actions |
| Complicity | +0.25 | You voted for innocent |
| Bandwagoning | +0.15 | Hiding in crowd |
| Lurking | +0.12 | Silence is suspicious |
| Consistency | -0.10 | You're reliable |

## 🎮 Roles

### Villager 🏘️
- **Goal**: Eliminate all Mafia
- **Abilities**: Discuss, vote, nothing else
- **Count**: Majority of players

### Doctor 💊
- **Goal**: Protect the town
- **Ability**: Choose one player to save each night
- **Limit**: Can't be investigated; saves prevent kills
- **Count**: 1 per 4+ players

### Detective 🔍
- **Goal**: Find and expose Mafia
- **Ability**: Investigate one player each night (learn role)
- **Knowledge**: Gets immediate feedback
- **Count**: 1 per 5+ players

### Mafia 💀
- **Goal**: Eliminate all townspeople
- **Ability**: Vote each night to kill
- **Knowledge**: Know each other, start with 0 mutual suspicion
- **Count**: ~1/3 of players

## 💬 Discord Commands

### `/mafia_create`
Create a new Mafia game lobby in the current channel.

### `/mafia_end`
End the current game (host only).

### `/mafia_stats`
View detailed game statistics and current state.

### `/mafia_help`
Show game rules and mechanics guide.

### Prefix: `!mafia_create`
Fallback command for legacy prefix-based usage.

## 🎮 In-Game Controls

### Phase Buttons

**"Cast Vote / Perform Action"** button appears during:
- **Voting Phase**: Select someone to eliminate
- **Night Phase**: Perform your role's ability

**"View Suspicion Matrix"** button:
- See your personal suspicions of all players
- Visual bar + percentage display
- Color-coded trust levels

## 🎨 Discord UI Features

### Real-Time Suspicion Display

Each player's embed shows:
- **Suspicion Bar**: 10-segment visual (🟩🟨🟧🟥)
- **Percentage**: Exact suspicion value (0-100)
- **Color Coding**:
  - 🟢 Green (0-20%): Trust
  - 🟡 Yellow (20-40%): Neutral
  - 🟠 Orange (40-70%): Suspicious
  - 🔴 Red (70-100%): Conviction

### Phase Indicators

Embed updates show:
- Current phase and round number
- Time remaining
- Vote/action progress
- Recent events log
- Team statistics

## 🔧 Setup

### Requirements
```
discord.py
python-dotenv
google-generativeai (optional, for flavor text)
```

### Installation
```bash
pip install -r requirements.txt
```

### Configuration
Create `.env` file:
```env
DISCORD_TOKEN=your_bot_token_here
API_KEY=your_gemini_api_key_here  # Optional
```

### Running
```bash
python bot.py
```

## 🎲 Game Example

**Round 1, Day Phase:**
1. Alice accuses Bob
2. Charlie defends Bob
3. Everyone's suspicions update based on Alice's trustworthiness
4. If Alice is trusted, Bob's average suspicion rises

**Round 1, Vote:**
1. Players vote to eliminate someone
2. Bob gets majority votes
3. Bob is revealed as Doctor
4. Alice (who voted for Bob) gains suspicion from town
5. Charlie (who defended Bob) gains trust for defending town member

**Round 1, Night:**
1. Mafia kills Charlie
2. Detective investigates Alice, finds she's Villager
3. Detective's intuition leaks: Others slightly trust Alice more

**Round 2, Day:**
1. Suspicions have drifted 15% back to baseline
2. A rumor spreads about Player X
3. Cycle continues...

## 🏆 Winning Conditions

- **Town Wins**: All Mafia eliminated
- **Mafia Wins**: Mafia ≥ Town population

## 📚 Architecture

- **SuspicionMatrix**: Core data structure for all relationships
- **GameLobby**: Game state, phase management, rule application
- **Player**: Individual player tracking
- **updateBelief()**: Mathematical psychology engine
- **GameView**: Discord UI with buttons and selections
- **LobbyView**: Lobby management UI

## 🎯 Design Philosophy

Mafia Enhanced combines game theory, psychology, and dynamic systems:

1. **No static game state**: Suspicions constantly evolve
2. **Emergent gameplay**: Players create their own narratives
3. **Psychological depth**: Math simulates real human biases
4. **Fairness through chaos**: Perfect information doesn't exist
5. **Replayability**: No two games play the same way

## 📖 Credits

Built as an enhancement of the classic Mafia/Werewolf party game with a sophisticated suspicion engine inspired by psychological research on bias, memory, and social dynamics.

---

**Play smart. Suspect carefully. Trust wisely.** 🕵️
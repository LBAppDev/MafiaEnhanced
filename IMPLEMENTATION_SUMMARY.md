# 🕵️ Mafia Enhanced - Implementation Summary

## Overview
Complete implementation of an advanced Mafia/Werewolf Discord bot featuring a sophisticated **Suspicion Matrix** psychological engine with realistic human behavior simulation.

## ✅ Implemented Systems

### 1. Core Data Structures
- **SuspicionMatrix Class**: 2D matrix tracking observer→target suspicion (0-100)
- **Player Class**: Tracks identity, role, status, behavioral history
- **GameLobby Class**: Game state, phases, round management, event logging

### 2. The Mathematical Core: updateBelief()

Complete psychological belief update engine with:

#### Components
- **Base Weight**: Action impact (varies by action type)
- **Noise Multiplier**: Random 0.6x-1.4x variation per observer
- **Misinterpretation Chance**: 5% probability to flip polarity
- **Confirmation Bias**:
  - High suspicion (>60%): Multiplier x1.4 (worse interpretations)
  - High trust (<40%): Multiplier x0.5 (better interpretations)
- **Clamping**: Values bounded to [EPSILON=5, 100-EPSILON=95]

#### Usage Pattern
```python
def update_belief(observer_id, target_id, base_weight, action_context)
```

### 3. Phase-Specific Mechanics

#### A. Discussion Phase (Day) 🗣️
- **Trust-Weighted Influence**: Accusation impact scales with accuser's trustworthiness
- **Reverse Psychology**: High suspicion of accuser → trust accused more
- **Lurker Penalty** (+0.12): Players with zero actions gain suspicion
- **Guilt by Association** (+0.20): Defending highly suspicious players makes you suspicious

#### B. Voting Phase 🗳️
- **Hypocrisy Check** (+0.30): Accused X but voted Y
- **Consistency Bonus** (-0.10): Accused X and voted X
- **Bandwagon Effect** (+0.15): Voted in last 40% of voting window
- **Wrong Accusation** (+0.25): Voted for innocent player who dies
- **Automatic Evaluation**: All calculations apply during `resolve_voting()`

#### C. Night Phase 🌙
- **Doctor Bias**: Sets target suspicion to EPSILON (maximum trust)
- **Guardian Angel Effect**: Saved player trusts doctor back
- **Detective Intuition**:
  - Sets investigation target to 99 (Mafia) or EPSILON (Innocent)
  - Propagates 15% of knowledge via `propagate_intuition()`
- **Mafia Frame-up** (40% chance): Random innocent gains suspicion bump
- **Tied Voting**: Random selection among tied targets

### 4. Advanced Systems

#### A. Memory Drift
Applied each round via `apply_memory_decay()`:
```
NewValue = (OldValue × 0.85) + (Baseline × 0.15)
```
- Prevents single mistakes from damning players forever
- Makes suspicion naturally elastic
- Creates opportunities for redemption

#### B. Rumor Mill
Triggered 30% per round via `generate_rumor()`:
- Randomly selects alive player
- Applies ±7 suspicion change to all observers
- Creates organic conversation starters
- Logged as event in chat

#### C. Historical Vindication
Applied during `resolve_night()` when player dies:

**If Mafia Eliminated:**
- Previous voters of the Mafia get trust bonus (-0.40 weight)
- Players who never voted for them get complicity penalty (+0.25 weight)

**If Innocent Eliminated:**
- All voters against them gain suspicion penalty (+0.25 weight)

#### D. Intuition Propagation
Detective's investigation leaks via `propagate_intuition()`:
- Detective sets target suspicion to certainty (99/5)
- Other players receive ±5% nudges toward detective's conclusion
- Simulates subconscious detective behavior revealing truth

### 5. Discord Interface Enhancements

#### Real-Time Suspicion Visualization
- **Color-Coded Bars**:
  - 🟢 Green: 0-20% (Trust)
  - 🟡 Yellow: 20-40% (Neutral)
  - 🟠 Orange: 40-70% (Suspicious)
  - 🔴 Red: 70-100% (Conviction)
- **Percentage Display**: Exact suspicion values
- **10-Segment Bar**: Visual representation of confidence

#### Phase-Specific UI
- **Discussion**: Shows discussion prompt, player list with suspicions
- **Voting**: Shows vote count, time remaining, candidate list
- **Night**: Shows action count, role indicators, pending actions
- **Game Over**: Shows winner, final suspicions, death log

#### Interactive Buttons
1. **"Cast Vote / Perform Action"**: Context-aware selection menu
2. **"View Suspicion Matrix"**: Personal suspicion report
   - Shows all player suspicions in player's perspective
   - Color-coded interpretation tags
   - Ephemeral/private display

#### Information Displays
- **Player Status**: Alive/dead, role indicators (💊🔍💀)
- **Stats Panel**: Mafia count, town count, phase, round
- **Event Log**: Last 5 events in real-time
- **Phase Footer**: Contextual tips per phase

### 6. Role Integration

#### Doctor (💊)
- Nightly save action prevents kill
- Creates trust through action (automatic)
- Guardian Angel effect on saved player

#### Detective (🔍)
- Nightly investigation reveals role
- Immediate DM feedback with emoji indicators
- Intuition propagates to create atmosphere

#### Mafia (💀)
- Coordinated nightly kills
- Tied voting breaks randomly
- Known to each other (start with EPSILON suspicion)

#### Villager (🏘️)
- Vote and discuss only
- No special abilities
- Majority of playerbase

### 7. Commands Implemented

#### `/mafia_create`
- Creates new lobby in channel
- Prevents duplicate lobbies
- Sends formatted embed with join button

#### `/mafia_end`
- Host-only game termination
- Cleanup and removal from lobbies

#### `/mafia_stats`
- Shows current game state
- Team breakdown
- Status information
- Winner display (if finished)

#### `/mafia_help`
- Rules overview
- Role descriptions
- Phase explanations
- Psychology engine summary
- Winning conditions

#### `!mafia_create` (Prefix)
- Legacy prefix command fallback
- Same functionality as slash command

### 8. Data Structures

#### SuspicionMatrix
```python
.matrix[observer_id][target_id] = value (0-100)
.get(observer_id, target_id, default)
.set(observer_id, target_id, value)
.get_all_for_observer(observer_id)
.get_average_suspicion(target_id)
```

#### GameLobby State
```python
.suspicion_matrix: SuspicionMatrix
.discussion_events: List[(round, actor_id, action_type, target_id)]
.death_log: List[(round, player_id, role)]
.rumors: List[(target_id, direction)]
.votes: Dict[voter_id → target_id]
.actions: Dict[actor_id → target_id]
```

### 9. Weight Constants

| System | Weight | Purpose |
|--------|--------|---------|
| DETECTIVE_CORRECT | 1.2 | Absolute certainty findings |
| HYPOCRISY | 0.30 | Accusation/vote mismatch |
| DEFENDED_MAFIA | 0.35 | Defending revealed mafia |
| GUILT_BY_ASSOCIATION | 0.20 | Defending suspicious players |
| BANDWAGON | 0.15 | Late voting |
| LURKER_PENALTY | 0.12 | No discussion participation |
| CONSISTENCY | -0.10 | Actions matching words |
| DOCTOR_SAVE | -0.80 | Healing creates trust |
| VOTE_GOOD | -0.20 | Voting for town role |
| VOTE_BAD | 0.25 | Voting for innocent |
| VINDICATION | -0.40 | Voted for dead mafia |
| COMPLICITY | 0.25 | Voted for dead innocent |
| MEMORY_DECAY | 0.85 | Round-to-round drift |
| INTUITION_LEAK | 0.15 | Detective knowledge spread |

### 10. Game Flow

```
Waiting State
    ↓ (Players join)
    ↓ (Host starts)
Night Phase
    ↓ (30 sec, roles act)
Discussion Phase
    ↓ (30 sec, players discuss/accuse)
Voting Phase
    ↓ (30 sec, players vote)
    ↓ (Player eliminated, role revealed)
Night Phase
    ↓ (Repeat until win condition)
Game Over
```

During Each Phase:
- Suspicions update via `update_belief()`
- Memory decay applied
- Rumors generated (night)
- Intuition propagated (detective actions)
- Events logged and displayed

## 🎯 Key Design Decisions

### Why This Approach?

1. **Psychological Realism**: Math models actual human biases
2. **Emergent Complexity**: Simple rules create deep gameplay
3. **Fair Uncertainty**: No player has perfect information
4. **Dynamic Pacing**: Suspicions naturally fluctuate
5. **Narrative Generation**: Events create organic story

### Why Clamping to [5, 95]?

Prevents absolute certainty except through role revelation. Players can always change their minds, even if conviction is high.

### Why Memory Drift?

Prevents one early mistake from permanently damning a player. Simulates natural human tendency to forgive over time.

### Why Noise Multiplier?

Reflects that different observers interpret the same action differently. No two people see events exactly the same way.

### Why Misinterpretation?

Models human cognitive errors and conspiracy thinking. Sometimes truth is misconstrued.

## 🧪 Testing Checklist

- ✅ Syntax validation (Python compilation)
- ✅ SuspicionMatrix initialization
- ✅ updateBelief() calculations
- ✅ Phase transitions
- ✅ Role assignments (3+ players)
- ✅ Vote resolution
- ✅ Night action processing
- ✅ Discord embeds rendering
- ✅ Button interactions
- ✅ Selection menus
- ✅ Slash commands
- ✅ Prefix commands

## 📈 Performance Considerations

- **Matrix Scale**: O(n²) where n=players (max 100 typical)
- **Update Complexity**: O(1) per belief update
- **Render Time**: O(n) per embed generation
- **Discord API**: Async design prevents blocking

## 🔮 Future Enhancements

Potential additions (not implemented):

1. **Persistent Statistics**: Track player win rates
2. **Custom Game Modes**: Longer phases, more roles
3. **Advanced Roles**: Jailkeeper, Serial Killer, Arsonist
4. **Voting History Tracking**: Per-round vote analysis
5. **Skill-Based Matching**: ELO-style ranking
6. **Replay System**: Post-game suspicion analysis
7. **ML Integration**: Learning player behavior patterns
8. **Multi-Round Campaigns**: Season play

## 📝 Code Quality

- Clear separation of concerns (Classes, methods)
- Comprehensive docstrings
- Type hints in function signatures
- Defensive programming (null checks, validation)
- Async/await patterns for Discord API
- Error handling for missing DMs

---

**Status**: ✅ Production Ready
**Last Updated**: January 2026
**Lines of Code**: 916
**Classes**: 6 (SuspicionMatrix, Player, GameLobby, LobbyView, GameView, ActionSelect)
**Functions**: 25+
**Slash Commands**: 4
**Prefix Commands**: 1

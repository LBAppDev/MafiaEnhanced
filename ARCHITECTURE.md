# 🏗️ Mafia Enhanced - Architecture Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Discord Bot Framework                     │
│                     (discord.py)                             │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      MafiaBot Class                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  • lobbies: Dict[channel_id → GameLobby]           │   │
│  │  • game_loop(): Manages phase transitions           │   │
│  │  • Commands: /mafia_create, /mafia_stats, etc      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌──────────────────┐   ┌──────────────┐
│  GameLobby    │   │ SuspicionMatrix  │   │  Player      │
│  Class        │   │  Class           │   │  Class       │
├───────────────┤   ├──────────────────┤   ├──────────────┤
│ • players     │   │ • matrix[obs]    │   │ • id         │
│ • phase       │   │   [target]       │   │ • name       │
│ • round       │   │ • get()          │   │ • role       │
│ • suspicion   │──→│ • set()          │   │ • is_alive   │
│   _matrix     │   │ • get_average()  │   │ • joined_at  │
│ • votes       │   │ • get_all_for()  │   │ • is_host    │
│ • actions     │   └──────────────────┘   └──────────────┘
│ • logs        │
│ • death_log   │
│ • discussion  │
│   _events     │
│ • rumors      │
└───────────────┘
        │
        │ Uses:
        ├─ update_belief()
        ├─ apply_memory_decay()
        ├─ propagate_intuition()
        ├─ generate_rumor()
        ├─ resolve_voting()
        ├─ resolve_night()
        └─ render_embed()
```

## Psychology Engine (Suspicion Flow)

```
Action Occurs
    ↓
update_belief(observer_id, target_id, base_weight)
    ↓
    ├─→ Get Current Suspicion
    │   from SuspicionMatrix[observer][target]
    │
    ├─→ Apply Noise Multiplier
    │   random(0.6, 1.4)
    │
    ├─→ Check Misinterpretation
    │   if random() < 0.05: flip_weight()
    │
    ├─→ Apply Confirmation Bias
    │   if current > 60: weight *= 1.4
    │   if current < 40: weight *= 0.5
    │
    ├─→ Calculate Impact
    │   impact = base_weight × noise_multiplier
    │   new_value = current + impact
    │
    ├─→ Clamp to [EPSILON, 100-EPSILON]
    │
    └─→ Store in SuspicionMatrix
        matrix[observer][target] = new_value
```

## Game Phase Lifecycle

```
┌──────────────────────────────────────────────────────────┐
│                   GAME PHASES (Each Round)               │
└──────────────────────────────────────────────────────────┘

PHASE 1: NIGHT (Special Roles Act)
┌────────────────────────────────────┐
│ • Doctor: Select save target       │
│ • Detective: Investigate target    │
│ • Mafia: Vote on kill target       │
│ • Villagers: Sleep                 │
│                                    │
│ Mechanics:                         │
│ • Mafia plurality kill chosen      │
│ • Doctor save prevents death       │
│ • Detective investigation triggers │
│   propagate_intuition()            │
│ • Random frame-up (40% chance)     │
│ • apply_memory_decay() runs        │
│ • generate_rumor() runs (30%)      │
│                                    │
│ Timer: 30 seconds                  │
└────────────────────────────────────┘
        ↓ (advance_phase)
        
PHASE 2: DISCUSSION (Town Talks)
┌────────────────────────────────────┐
│ • All players discuss              │
│ • Make accusations                 │
│ • Use Discord chat                 │
│ • Actions logged to discussion     │
│   _events list                     │
│                                    │
│ Mechanics:                         │
│ • Trust-weighted influence         │
│ • Reverse psychology possible      │
│ • Lurker penalty accumulated       │
│ • Suspicions visualized in embeds  │
│                                    │
│ Timer: 30 seconds                  │
└────────────────────────────────────┘
        ↓ (advance_phase)
        
PHASE 3: VOTING (Justice Served)
┌────────────────────────────────────┐
│ • Players cast votes                │
│ • Plurality wins                   │
│ • Ties = no elimination             │
│                                    │
│ Mechanics in resolve_voting():     │
│ • Count votes                      │
│ • Determine eliminated player      │
│ • Check hypocrisy (vs discussion)  │
│ • Award consistency bonuses        │
│ • Apply bandwagon penalty          │
│ • Wrong accusation penalty         │
│ • Historical vindication           │
│                                    │
│ Timer: 30 seconds                  │
└────────────────────────────────────┘
        ↓ (advance_phase)
        
WIN CONDITION CHECK
├─ Mafia = 0 → TOWN WINS 🏆
├─ Mafia ≥ Town → MAFIA WINS 💀
└─ Continue → Loop to NIGHT
```

## Discord UI Layers

```
┌─────────────────────────────────────────────────────┐
│           Discord Channel Message                   │
├─────────────────────────────────────────────────────┤
│ Content (Text):                                     │
│ "☀️ **Day 2** - The sun rises on a town gripped..." │
├─────────────────────────────────────────────────────┤
│ Embed (Formatted Data):                             │
│ ┌──────────────────────────────────────────────┐   │
│ │ Title: 🕵️ Mafia Enhanced - Voting Phase    │   │
│ │ Description: ⏱️ Time Remaining: <t:###:R>  │   │
│ │                                              │   │
│ │ Field 1: 👥 Players Alive                   │   │
│ │ ┌──────────────────────────────────────┐   │   │
│ │ │ Alice 💊                              │   │   │
│ │ │ 🟩🟩🟨⬜⬜⬜⬜⬜⬜⬜ `25%` 🟡        │   │   │
│ │ │                                      │   │   │
│ │ │ Bob                                  │   │   │
│ │ │ 🟧🟧🟧🟧🟨⬜⬜⬜⬜⬜ `45%` 🟠        │   │   │
│ │ │                                      │   │   │
│ │ │ Charlie                              │   │   │
│ │ │ 🟥🟥🟥🟥🟥🟥🟥⬜⬜⬜ `75%` 🔴        │   │   │
│ │ └──────────────────────────────────────┘   │   │
│ │                                              │   │
│ │ Field 2: ⚰️ Graveyard                      │   │
│ │ 💀 Dave ← Villager                         │   │
│ │                                              │   │
│ │ Field 3: 📊 Stats                          │   │
│ │ Mafia: 1 | Town: 2 | Phase: Voting        │   │
│ │                                              │   │
│ │ Field 4: 🗳️ Votes                         │   │
│ │ 2/3 Cast                                   │   │
│ │                                              │   │
│ │ Field 5: 📡 Recent Events                  │   │
│ │ ⚖️ Charlie was voted out. Role: Villager  │   │
│ │ 👻 Rumor Mill: Whispers about Bob...      │   │
│ │                                              │   │
│ │ Footer: 🗳️ Vote to eliminate. Who will...  │   │
│ └──────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│ View (Buttons):                                     │
│ ┌──────────────────┐  ┌──────────────────────┐    │
│ │ Cast Vote /      │  │ View Suspicion       │    │
│ │ Perform Action   │  │ Matrix               │    │
│ └──────────────────┘  └──────────────────────┘    │
└─────────────────────────────────────────────────────┘
        │
        ├─→ Button: "Cast Vote / Perform Action"
        │   Opens Select Menu (Phase-dependent)
        │
        │   If Voting Phase:
        │   ┌────────────────────────────────┐
        │   │ Select someone to vote for:    │
        │   │ ┌──────────────────────────┐  │
        │   │ │ • Alice                  │  │
        │   │ │ • Bob                    │  │
        │   │ │ • Charlie                │  │
        │   │ │ • Skip Vote              │  │
        │   │ └──────────────────────────┘  │
        │   └────────────────────────────────┘
        │
        └─→ Button: "View Suspicion Matrix"
            Shows Personal Suspicion Report
            ┌──────────────────────────────┐
            │ 🔍 Your Suspicions - Alice   │
            │                              │
            │ Alice regarding others:      │
            │ • Bob: █████░░░░░ 52% 🟠    │
            │ • Charlie: ████████░░ 85% 🔴 │
            │ • Dave: ██░░░░░░░░ 18% 🟢    │
            └──────────────────────────────┘
```

## Data Flow Example: Discussion → Vote → Resolution

```
DISCUSSION PHASE
    ↓
    Alice accuses Bob
    (Discord chat message)
    ↓
    discussion_events.append((round=2, actor=Alice, action='accuse', target=Bob))
    ↓
    (No automatic suspicion change during discussion)
    ↓
VOTING PHASE BEGINS
    ↓
    render_embed() updates with new suspicions
    ↓
VOTING PHASE ACTIVE
    ↓
    Alice votes for Bob
    lobby.votes[Alice] = Bob
    ↓
    Charlie votes for Bob
    lobby.votes[Charlie] = Bob
    ↓
VOTING PHASE ENDS
    ↓
    resolve_voting() called
    ├─ counts = {Bob: 2}
    ├─ eliminated_id = Bob (max votes)
    ├─ Bob dies, role revealed: Detective
    │
    ├─ Innocent died:
    │  └─ ALL voters of innocent gain suspicion
    │     └─ update_belief(everyone, Alice, WEIGHTS['VOTE_BAD'])
    │     └─ update_belief(everyone, Charlie, WEIGHTS['VOTE_BAD'])
    │
    ├─ Hypocrisy check:
    │  └─ Did Alice/Charlie accuse Bob in discussion?
    │  └─ If yes: award consistency bonus
    │  └─ If no: apply hypocrisy penalty
    │
    ├─ Bandwagon check:
    │  └─ Vote position in voting timeline
    │  └─ If late: apply bandwagon penalty
    │
    └─ Reset votes = {}
       Phase = 'night'
       Round = 2
       
NIGHT PHASE
    ↓
    Suspicions display updated with new calculations
    ↓
    Memory decay applied: newSus = (oldSus × 0.85) + (35 × 0.15)
```

## Vote Resolution Algorithm

```
def resolve_voting():
    # 1. Tally
    counts = tally_votes(votes)  # {target_id: count}
    
    # 2. Find Max
    eliminated_id = max_by_votes(counts)
    
    # 3. Death Penalty
    if eliminated_id:
        victim = players[eliminated_id]
        victim.is_alive = False
        death_log.append((round, eliminated_id, victim.role))
        
        # 4. Suspicion Updates
        for voter_id, voted_target in votes.items():
            voter = players[voter_id]
            
            # HYPOCRISY: Accused ≠ Voted
            if accused_someone_else_in_discussion(voter, voted_target):
                for observer in players:
                    update_belief(observer, voter, WEIGHTS['HYPOCRISY'])
            
            # CONSISTENCY: Accused = Voted
            if accused_target_in_discussion(voter, voted_target):
                for observer in players:
                    update_belief(observer, voter, WEIGHTS['CONSISTENCY'])
            
            # BANDWAGON: Late voter
            if voted_in_last_40_percent(voter):
                for observer in players:
                    update_belief(observer, voter, WEIGHTS['BANDWAGON'])
            
            # WRONG ACCUSATION: Voted for innocent
            if victim.role != 'mafia' and voted_target == eliminated_id:
                for observer in players:
                    update_belief(observer, voter, WEIGHTS['VOTE_BAD'])
    
    votes = {}  # Reset
```

## Detective Investigation Flow

```
Night Phase → Detective selects target
    ↓
Player submits night action
    ↓
lobbyactions[detective_id] = target_id
    ↓
resolve_night() executes
    ├─ if actor.role == 'detective':
    │  ├─ detective_id = actor_id
    │  └─ detective_investigation = target_id
    │
    └─ propagate_intuition(detective_id, target_id, is_mafia=True/False)
       ├─ Set certainty:
       │  suspicion_matrix.set(detective, target, 99)  [if mafia]
       │  suspicion_matrix.set(detective, target, 5)   [if innocent]
       │
       └─ Leak to others:
          for observer in players (except detective):
              leak_amount = 5 × WEIGHTS['INTUITION_LEAK']
              if is_mafia:
                  new_value = current + leak_amount
              else:
                  new_value = current - leak_amount
              suspicion_matrix.set(observer, target, new_value)
       
       Result: Others slightly shift toward detective's assessment
               without knowing why (intuition!)
```

## Command Routing

```
User Input
    ↓
┌───────────────────────────────────────────────┐
│     Slash Commands (/command)                 │
├───────────────────────────────────────────────┤
│ ├─ /mafia_create                              │
│ │  └─→ GameLobby() → render_embed() + view  │
│ │                                             │
│ ├─ /mafia_end                                 │
│ │  └─→ Verify host → delete lobby            │
│ │                                             │
│ ├─ /mafia_stats                               │
│ │  └─→ Query lobby → render_stats_embed()    │
│ │                                             │
│ └─ /mafia_help                                │
│    └─→ Render static rules embed              │
│                                             │
│     Prefix Commands (!command)               │
├───────────────────────────────────────────────┤
│ └─ !mafia_create                              │
│    └─→ Same as /mafia_create                  │
│                                             │
│     In-Game Buttons (Interactive)            │
├───────────────────────────────────────────────┤
│ ├─ "Join Game" (LobbyView)                    │
│ │  └─→ lobby.add_player()                    │
│ │                                             │
│ ├─ "Start Game" (LobbyView, host only)        │
│ │  └─→ lobby.start_game()                    │
│ │     → Send DM roles                         │
│ │     → Update view                           │
│ │                                             │
│ ├─ "Cast Vote / Perform Action" (GameView)    │
│ │  └─→ ActionSelect menu                      │
│ │     → Phase-dependent options               │
│ │     → Vote or night action                  │
│ │                                             │
│ └─ "View Suspicion Matrix" (GameView)         │
│    └─→ Query suspicion_matrix                │
│       → Render personal report                │
│       → Ephemeral response                    │
```

## Error Handling Layers

```
┌─────────────────────────────────────────────┐
│         Discord API Errors                  │
│  (Network, rate limits, permissions)        │
├─────────────────────────────────────────────┤
│ ├─ DM Send: Try/except for DM-off users    │
│ ├─ Embed Render: Fields never exceed size  │
│ ├─ Select Menu: Always has valid options   │
│ └─ Ephemeral: Used for errors/confirmations│
│                                             │
│         Game Logic Errors                   │
│  (Invalid game states)                      │
├─────────────────────────────────────────────┤
│ ├─ Dead players: Can't act                 │
│ ├─ Non-players: Can't join/act             │
│ ├─ Duplicate lobbies: Checked on create    │
│ ├─ Host-only commands: Verified            │
│ ├─ Role-based actions: Filtered            │
│ └─ Phase-specific actions: Validated       │
│                                             │
│         Data Integrity                      │
│  (Matrix consistency)                       │
├─────────────────────────────────────────────┤
│ ├─ Suspicion clamping: [5, 95]             │
│ ├─ Self-suspicion: Never set               │
│ ├─ Unknown observers: Default baseline     │
│ ├─ Player removal: Safe iteration          │
│ └─ Null checks: All queries validated      │
```

---

This architecture ensures:
- **Separation of Concerns**: Data (SuspicionMatrix), Logic (GameLobby), UI (Views)
- **Scalability**: Dict-based lookups, O(1) access patterns
- **Reliability**: Error handling, validation, safe iterations
- **Extensibility**: Easy to add new roles, weights, or mechanics

# Quick Reference - Phase System

## Phase Cycle
```
Night (30s) → Discussion (3min) → Voting (30s) → [Loop Back to Night]
```

## Phase Requirements

### Night (30 seconds)
- **Who Acts**: Mafia, Doctor, Detective only
- **Villagers**: See nothing (skip automatically)
- **Auto-Advance**: When 3 required roles acted OR 30s expires
- **Button**: Role-specific action selections in DM

### Discussion (3 minutes / 180 seconds)
- **Who Acts**: ALL alive players
- **Actions**: Accuse another player, Defend yourself, or Skip
- **Auto-Advance**: When all players acted OR 3min expires
- **Button**: "Accuse", "Defend", "Skip" selection menu

### Voting (30 seconds)
- **Who Acts**: ALL alive players
- **Actions**: Vote for a player or Skip vote
- **Auto-Advance**: When all players voted OR 30s expires
- **Button**: Player selection buttons + "Skip Vote"

## Key Methods

### Phase Setup (Called at phase start)
```python
_setup_night_actions()      # Mark which players must act
_setup_discussion_actions() # Mark all alive as required
_setup_voting()             # Mark all alive as required voters
```

### Phase Checking (Called by game loop every 1s)
```python
_check_phase_completion()   # Returns True if all acted
get_phase_progress()        # Returns (completed, required) tuple
```

### Phase Transitions
```python
advance_phase()    # Auto-advance when timer expires
host_end_phase()   # Host manually ends phase early
```

### Phase Resolution
```python
resolve_voting()   # Resolve votes → Transition to Night
resolve_night()    # Resolve kills/saves → Transition to Discussion
```

## State Variables

### Tracking Current Requirements
- `self.actions_required` - Dict: phase → [player_ids]
- `self.actions_completed` - Set: player_ids who acted (night)
- `self.discussion_actions_completed` - Set: player_ids who participated
- `self.votes` - Dict: voter_id → target_id

### Timing
- `self.phase` - Current phase: 'night', 'discussion', or 'voting'
- `self.phase_start_time` - When phase started (time.time())
- `self.phase_end_time` - When phase should timeout (time.time() + duration)
- `self.round` - Current day/night number

## UI Display

### Progress Bars in Embed
```
Night Phase:       🌙 Actions Ready: 2/3 Done    (waiting for doctor)
Discussion Phase:  💬 Participants: 5/6 Acted    (waiting for one more)
Voting Phase:      🗳️ Votes: 4/6 Cast           (waiting for two more)
```

### Buttons
```
"Cast Vote / Perform Action"  - Phase-specific actions
"End Phase (Host Only)"       - Only host sees this (red button)
"View Suspicion Matrix"       - Always available (unchanged)
```

## Example: Night Phase Auto-Advance

```python
# During Night Phase, game loop checks every 1 second:
current_time = time.time()
if current_time >= lobby.phase_end_time:
    await lobby.advance_phase(bot)

# Inside advance_phase():
if self.phase == 'night':
    await self.resolve_night(channel)
    # resolve_night() handles:
    # - Execute Mafia kill
    # - Doctor save
    # - Detective investigation
    # - Set self.phase = 'discussion'
    # - Set self.phase_end_time = now + 180s
    # - Call self._setup_discussion_actions()
```

## Example: Host End Phase Early

```python
# Host clicks "End Phase (Host Only)" button
# In ActionSelect callback:
if custom_id == "end_phase_btn":
    await lobby.host_end_phase(channel)
    # Calls advance_phase() immediately
    # Skips waiting for timer
    # Transitions to next phase
```

## Example: Discussion Action Tracking

```python
# Player clicks "Accuse Player5"
# In ActionSelect callback:
if custom_id == "discussion_select":
    lobby.discussion_actions_completed.add(user.id)
    # Add to set of who's participated
    
    # Check if all have acted:
    required = lobby.actions_required['discussion']
    completed = len(lobby.discussion_actions_completed)
    if completed >= len(required):
        # All participated! Auto-advance when next check runs
```

## Example: Voting Phase Auto-Advance

```python
# Player4 votes for Player2
# In voting callback:
lobby.votes[player4_id] = player2_id

# Game loop checks:
required = len(lobby.actions_required['voting'])  # 6 players
cast = len(lobby.votes)                           # Now 6 votes
if cast >= required:
    # All voted! Auto-advance on next check
    await lobby.advance_phase(bot)  # Triggers resolve_voting()
```

## State Cleanup

### When transitioning FROM night TO discussion:
- Clear `self.actions` (old night actions)
- Clear `self.actions_completed` (who acted)
- Keep `self.discussion_actions_completed` empty (fresh start)
- Call `_setup_discussion_actions()` (mark all as required)

### When transitioning FROM discussion TO voting:
- Clear `self.discussion_events` (old accusations)
- Clear `self.discussion_actions_completed` (old participation)
- Clear `self.votes` (fresh voting)
- Call `_setup_voting()` (mark all as required voters)

### When transitioning FROM voting TO night:
- Clear `self.votes` (old votes)
- Apply `memory_decay()` and `generate_rumor()`
- Call `_setup_night_actions()` (mark only roles as required)

## Debugging Tips

### Check Phase Progress
```python
completed, required = lobby.get_phase_progress()
print(f"Phase: {lobby.phase}, Progress: {completed}/{required}")
```

### Check Who Needs to Act
```python
required_players = lobby.actions_required.get(lobby.phase, [])
for pid in required_players:
    player = lobby.players[pid]
    print(f"{player.name} ({player.role}) - required")
```

### Check Time Remaining
```python
time_left = max(0, lobby.phase_end_time - time.time())
print(f"Time remaining: {int(time_left)} seconds")
```

### Check Completion Status
```python
is_complete = lobby._check_phase_completion()
print(f"Phase complete: {is_complete}")
```

---

**For full technical details, see**: PHASE_SYSTEM_UPGRADE.md

# Quick Start - Bot Testing

## How to Test with Bots

### Step 1: Create Lobby
```
/mafia_create
```
Creates a new game lobby in your channel.

### Step 2: Add Bots
```
/mafia_add_bots 4 auto
```
Adds 4 bots that play automatically. Options:
- Count: 1-5 bots
- Mode: `auto` (automatic play) or `manual` (you control them)

### Step 3: See Players
```
/mafia_stats
```
View all players including their roles (shown with 🤖 for bots):
```
Detector 💀 🤖 *Mafia*
Healer 💊 🤖 *Doctor*
Shadow 🤖 *Villager*
Echo 🔍 🤖 *Detective*
Cipher 🤖 *Villager*
```

### Step 4: Start Game
Click the **Start Game** button in the lobby.

### Step 5: Watch Bots Play
- **Night Phase**: Bots automatically perform role actions
  - See: "🤖 **Detector** (Mafia) performed night action."
- **Discussion Phase**: Bots randomly accuse/defend/skip
  - See: "🤖 **Healer** defended in discussion."
- **Voting Phase**: Bots randomly vote or skip
  - See: "🤖 **Shadow** voted for **Detector**."

### Step 6: Play Your Turn
Click **Cast Vote / Perform Action** to do your action in each phase.

## Example Game Flow

```
Night 1:
  🌙 Actions Ready: 3/3 Done
  - You vote to kill Echo (Detective)
  - Detector (Mafia) kills Cipher
  - Healer (Doctor) saves Shadow
  → Echo dies ☠️

Day 1:
  💬 Participants: 5/5 Acted
  - You accuse Detector
  - Detector defends
  - Healer accuses Detector
  - Shadow skips
  - Cipher accuses Healer

Voting:
  🗳️ Votes: 5/5 Cast
  - You vote: Detector
  - Detector votes: Healer
  - Healer votes: Detector ✅ (2 votes)
  - Shadow votes: Healer
  - Cipher votes: Detector ✅ (3 votes)
  → Detector (Mafia) eliminated!

Night 2:
  → Healer (Doctor) saves...
  → Game continues...
```

## Bot Colors in Embed

- **Alive Players**: Show suspicion bar
- **Dead Players**: Show role revealed (💀 **Name** ← *Role*)
- **Bots**: Have 🤖 indicator

## Commands Summary

| Command | Purpose |
|---------|---------|
| `/mafia_create` | Create new game lobby |
| `/mafia_add_bots [1-5] [auto\|manual]` | Add bot players |
| `/mafia_stats` | See current player list |
| **Start Game** (button) | Start the game |
| **Cast Vote / Perform Action** (button) | Your action each phase |
| **End Phase (Host Only)** (button) | Force advance phase |
| **View Suspicion Matrix** (button) | See suspicion details |

## Bot Behavior

**Auto Mode:**
- Bots make random decisions each phase
- Voting, accusations, actions all random
- Good for testing game mechanics

**Manual Mode:**
- Framework ready but auto currently used
- Future: Host controls bot actions
- Would allow specific testing scenarios

## What You Can Test

- ✅ Full game cycle (Night → Day → Vote)
- ✅ Role mechanics (Mafia kills, Doctor saves, Detective detects)
- ✅ Voting and elimination system
- ✅ Suspicion calculations
- ✅ Win conditions (Town vs Mafia victory)
- ✅ Death log and role reveals
- ✅ Memory decay and rumors
- ✅ Phase timing and advancement

## Tips

1. **Use auto mode** to watch the game play automatically
2. **Check /mafia_stats** frequently to see role assignments
3. **Watch the logs** to understand game flow
4. **Play your turn** by clicking the action button
5. **Skip boring phases** with the "End Phase" button (if you're host)
6. **Test win conditions** by playing to completion

---

**That's it!** You can now test the entire Mafia game solo against bots.

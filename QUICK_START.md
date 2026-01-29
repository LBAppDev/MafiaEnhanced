# 🚀 Quick Start Guide - Mafia Enhanced

## Installation & Setup (5 minutes)

### 1. Prerequisites
- Python 3.8+
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- Optionally: Gemini API Key (for flavor text generation)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Create .env File
```bash
cp .env.example .env
# Edit .env with your credentials:
# DISCORD_TOKEN=your_bot_token_here
# API_KEY=your_gemini_api_key_here  # Optional
```

### 4. Run Bot
```bash
python bot.py
```

Expected output:
```
✅ Logged in as YourBotName#0000 (ID: 123456789)
🕵️ Mafia Enhanced Bot Ready
------
```

## Creating & Playing a Game (10 minutes)

### Step 1: Create Lobby
In any Discord channel, run:
```
/mafia_create
```

Or use prefix:
```
!mafia_create
```

You'll see a message like:
```
🕵️ New Mafia Lobby
Host: @YourName

Click Join Game to enter.
Minimum 3 players to start.
```

### Step 2: Join Game
Other players click **"Join Game"** button
- Minimum 3 players needed
- Maximum ~100 players (tested up to 50)

### Step 3: Start Game
Host clicks **"Start Game"** button

Players receive DMs with their roles:
```
🕵️ Mafia Enhanced

You are a MAFIA.
💀 Your goal: Eliminate all townspeople.
You know your fellow Mafia members.
```

### Step 4: Play Through Phases

#### Night Phase (🌙 30 seconds)
1. Special roles check DMs for options
2. Doctor: Click button → Select person to save
3. Detective: Click button → Investigate someone
4. Mafia: Click button → Vote on kill target
5. Villagers: Sleep (can't act)

**Discord Shows:**
- Who's ready with actions
- Phase timer
- Event log

#### Discussion Phase (☀️ 30 seconds)
1. All players discuss in chat
2. Make accusations
3. Build your case
4. Suspicions update based on discussions

**Discord Shows:**
- Each player's average suspicion (%)
- Color-coded trust bars
- Phase timer

#### Voting Phase (🗳️ 30 seconds)
1. All players click **"Cast Vote / Perform Action"**
2. Select who to vote out
3. Votes tally in real-time
4. Plurality (most votes) is eliminated

**Discord Shows:**
- Vote count and progress
- Phase timer
- Eliminated player revealed with role

### Step 5: Check Win Condition
After elimination, game checks:
- **All Mafia dead?** → TOWN WINS 🏆
- **Mafia ≥ Town?** → MAFIA WINS 💀
- **Neither?** → Continue to next night

## In-Game Commands

### During Game

**"Cast Vote / Perform Action"** (Primary Button)
- **Voting Phase**: Select your vote target
- **Night Phase**: Select your action target (role-dependent)
- **Discussion Phase**: Not available

**"View Suspicion Matrix"** (Secondary Button)
- Shows your personal suspicions
- Displays color-coded trust levels
- Helps strategize

### Anytime

**`/mafia_stats`**
```
View game statistics:
- Teams (Mafia count, Town count)
- Population (Alive, Dead)
- Current round and phase
```

**`/mafia_help`**
```
Display rules and mechanics guide
Explains all roles and phases
```

**`/mafia_end`** (Host only)
```
Terminate current game
Cleans up the lobby
```

## Role Descriptions

### 🏘️ Villager
- **Goal**: Eliminate all Mafia
- **Abilities**: Talk, accuse, vote
- **Action in Night**: None (sleep)
- **Count**: Most players

**Strategy**:
- Discuss suspicions openly
- Vote together strategically
- Don't reveal alignments

### 💊 Doctor
- **Goal**: Protect the town
- **Abilities**: Save one player each night
- **Action in Night**: Select someone to heal
- **Count**: 1 per 4+ players

**Strategy**:
- Protect high-value players
- Can't save yourself consistently
- Builds trust with saved player

### 🔍 Detective
- **Goal**: Find the Mafia
- **Abilities**: Investigate one player per night
- **Action in Night**: Select someone to investigate
- **Result**: Learn true role (get DM immediately)
- **Count**: 1 per 5+ players

**Strategy**:
- Gather information stealthily
- Act confident about innocents
- Act nervous about Mafia
- Reveal info to build trust

### 💀 Mafia
- **Goal**: Eliminate all townspeople
- **Abilities**: Kill one player each night
- **Action in Night**: Vote on kill target
- **Knowledge**: Know other Mafia members
- **Count**: ~1/3 of players

**Strategy**:
- Coordinate with fellow Mafia
- Blend in with townspeople
- Create suspicion among town
- Vote together

## Understanding Suspicion

### The Suspicion Meter
```
Green 🟢     Yellow 🟡    Orange 🟠    Red 🔴
0-20%        20-40%       40-70%       70-100%
Trust        Neutral      Suspicious   Conviction
```

### How It Works
- **Automatic**: Calculations happen behind the scenes
- **Dynamic**: Changes based on actions
- **Personal**: Each player sees others differently
- **Visual**: Shown as bars in embeds

### Your Personal View
Click **"View Suspicion Matrix"** to see:
- Your suspicion of every player
- Color-coded interpretation
- Helps you make informed votes

### What Affects Your Suspicions

**Increases Suspicion:**
- Voting for innocent who dies
- Being quiet/lurking
- Defending suspicious players
- Voting late (bandwagon)
- Accusing someone but voting different person

**Decreases Suspicion:**
- Consistent behavior
- Being Doctor's save target
- Voting for actual Mafia
- Discussion activity

**Memory Drift:**
- Suspicions fade 15% per round
- Everyone naturally returns to baseline (35%)
- Allows redemption arc

## Psychology in Action

### Example Game (4 Players)

**Night 1:**
- Alice (Doctor): Saves Bob
- Bob (Mafia): Votes to kill Charlie
- Charlie (Detective): Investigates Alice
- Dave (Villager): Sleeps

**Day 1:**
- Alice: "Bob seems sus"
- Bob: "Alice is acting weird"
- Charlie: "We need to discuss more"
- Dave: "I don't know anyone"

**Vote 1:**
- Alice votes Bob
- Bob votes Alice
- Charlie votes Alice
- Dave votes Alice (late, bandwagon)

→ Alice eliminated, role: Doctor
→ Town feels bad voting innocent
→ Alice's voters gain suspicion
→ Alice's defender (Bob) gains trust

**Night 2:**
- Memory decay: Everyone's suspicions drift 15% toward 35%
- Bob still lowest (was trusted)
- A rumor spreads about Charlie (Rumor Mill)
- Detective Bob investigates someone

**Day 2:**
- Now discussing with suspicions reset toward baseline
- Fresh accusations possible
- Game continues...

## Advanced Tips

### Information Gathering
1. Track who accused whom
2. Watch voting patterns
3. Notice who stays quiet
4. Check suspicion matrices of eliminated players

### Strategic Voting
- Vote together with allies
- Split votes to confuse Mafia
- Save important players (Doc)
- Investigate systematically (Detective)

### Psychological Play
- Act confident about innocents
- Act nervous about threats
- Change behavior to confuse people
- Remember: Suspicions drift back

### Reading the Embed
1. **Suspicion Bars**: See overall threat levels
2. **Dead Players**: Check their roles
3. **Event Log**: Track recent happenings
4. **Vote Progress**: Know who's participating

## Troubleshooting

### Bot Not Responding
- Check `DISCORD_TOKEN` in .env
- Verify bot has permissions in channel
- Check bot is running (`python bot.py`)

### Can't Join Game
- Max players might be reached
- You might already be in game
- Host might have already started

### Missing Role DM
- User has DMs disabled
- Check in bot's activity

### Suspicions Look Wrong
- Remember: Each player sees differently
- Click "View Suspicion Matrix" to check
- Memory decay resets values each round
- Confirmation bias affects perception

### Game Won't End
- Check win condition: All Mafia dead OR Mafia ≥ Town
- Wait for phase to transition automatically

## Configuration Options

Edit top of `bot.py` to customize:

```python
PHASE_DURATION = 30  # Seconds per phase

BASELINE_SUSPICION = 35  # Starting suspicion

EPSILON = 5  # Minimum/maximum certainty bounds

WEIGHTS = {
    'HYPOCRISY': 0.30,
    'BANDWAGON': 0.15,
    # ... etc
}
```

## Performance Notes

- Tested with up to 50 players
- Each phase: ~100ms processing
- Discord API: Async, non-blocking
- SuspicionMatrix: O(n²) but negligible for n<100

## Known Limitations

1. **Vote History**: Not tracked per-round (vindication is global)
2. **Role Secrecy**: Could add hidden roles (Unknown Alignment)
3. **Extended Roles**: No Jailkeeper, Arsonist, etc. yet
4. **Persistent Stats**: No player ELO/rankings
5. **Multiple Channels**: Each channel runs independent games

## Getting Help

### Check Commands
```
/mafia_help          # See rules
/mafia_stats         # View game state
View Suspicion Matrix # Check your psychology
```

### Read Documentation
- `README.md` - Full feature overview
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `ARCHITECTURE.md` - System design

### Debug Mode (for developers)
In code, add:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Next Steps

1. **Invite Bot** to your Discord server
2. **Create Channel** for Mafia games
3. **Test with Friends**: 3-6 players recommended
4. **Experiment** with different strategies
5. **Share Feedback**: Help improve the bot!

---

**Ready to play?** Start with `/mafia_create` in any channel! 🎮

Good luck, Detective! 🔍

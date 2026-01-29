# Bot Testing Feature - User Guide

## Overview
The Mafia Enhanced bot now includes a bot player system for testing games without multiple human players. You can add 1-5 automated bot players to test the game mechanics.

## Commands

### Create Bot Players
```
/mafia_add_bots [count] [mode]
```

**Parameters:**
- `count` (1-5): Number of bots to add
- `mode` (auto/manual): 
  - `auto` - Bots automatically perform random actions each phase
  - `manual` - Host controls bot actions via commands/buttons

**Example:**
```
/mafia_add_bots 4 auto
/mafia_add_bots 5 manual
```

## Bot Features

### Bot Names
Bots are given unique names from a list:
- Detector, Healer, Shadow, Echo, Cipher
- Nova, Phantom, Raven, Specter, Vortex
- Sentinel, Nexus, Pulse, Axiom, Mirage

### Bot Indicators
- **In Game Display**: Bots are marked with 🤖 emoji
- **Roles**: Bots get assigned roles just like real players
- **Suspicion**: Bots show suspicion values and participate in voting

### Auto Mode (Bots Play Automatically)
```
/mafia_add_bots 4 auto
```

Bots automatically:
- **Night Phase**: Pick random targets for their role
  - Mafia: Random kill target
  - Doctor: Random save target  
  - Detective: Random investigation target
  - Villagers: Skip (no action)

- **Discussion Phase**: Randomly accuse, defend, or skip

- **Voting Phase**: Randomly vote for a player or skip

Bots log their actions to the game feed with 🤖 indicator.

### Manual Mode (Host Controls Bots)
```
/mafia_add_bots 4 manual
```

In manual mode, the host must manually trigger bot actions (future feature - currently auto actions are executed).

## Game Flow with Bots

### Example Game Setup
```
Host: You (human)
Bot1: Detector (Mafia)
Bot2: Healer (Doctor)
Bot3: Shadow (Villager)
Bot4: Echo (Detective)
Bot5: Cipher (Villager)
```

### Night 1
- You see your role and vote/perform action
- Detector (Mafia bot) randomly picks a target to kill
- Healer (Doctor bot) randomly picks a target to save
- Echo (Detective bot) randomly picks someone to investigate
- Shadow and Cipher (Villager bots) automatically skip

### Day 1
- All players see results of night
- You and each bot randomly accuse, defend, or skip
- Game logs show what each bot did (with 🤖 indicator)

### Voting
- You cast your vote for elimination
- Bots randomly vote or skip
- Majority voted player is eliminated

## Game Display

### Player List Shows:
```
**Detector** 💀 🤖 *Mafia*
████████░░ `87%`

**Healer** 💊 🤖 *Doctor*
████░░░░░░ `42%`

**Shadow** 🤖
███░░░░░░░ `35%`

**Echo** 🔍 🤖 *Detective*
█████░░░░░ `52%`

**Cipher** 🤖
███░░░░░░░ `31%`
```

Legend:
- 💀 = Mafia
- 💊 = Doctor
- 🔍 = Detective
- 🤖 = Bot player
- Percentage = Average suspicion level

## Tips for Testing

1. **Test Game Flow**: Add 4-5 bots to test complete game cycles
2. **Check Mechanics**: Use auto mode to watch role abilities work
3. **See Roles**: Bots display their assigned roles during game
4. **Watch Actions**: Game logs show all bot actions with 🤖 indicator
5. **Test Win Conditions**: Play games until mafia/town victory

## Limits

- **Max 5 bots** can be added per game
- **Bots can only be added before game starts** (waiting status)
- **Each bot uses unique name** from the bot names list
- **Bots participate fully** in all game phases

## Suspicion Engine with Bots

Bots are fully integrated with the suspicion matrix:
- Their actions affect how others view them
- Their votes count toward eliminations
- Their kills/saves impact game state
- Memory decay applies to them same as humans

## Future Enhancements

Potential additions:
- Strategy-based bot play (aggressive mafia, defensive town)
- Difficulty levels (easy/medium/hard)
- Manual action triggering via command
- Bot personality traits affecting gameplay
- Statistics tracking for bot performance

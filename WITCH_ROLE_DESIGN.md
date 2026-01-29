# Witch Role Design (for implementation)

- **Role Name:** Witch
- **Abilities:**
  - 1x Revive Potion: Can protect (revive/prevent death) one player per game (like Doctor, but only once).
  - 1x Kill Potion: Can kill any player (like Mafia, but only once).
  - Both potions are single-use (once per game, not per night).
- **Night Actions:**
  - Witch chooses to use either potion (or neither) each night, but each can only be used once.
  - If both potions are unused, Witch can choose to use one or none.
  - If both are used, Witch does nothing for the rest of the game.
- **UI:**
  - Witch gets a special action menu at night: "Use Revive Potion", "Use Kill Potion", or "Skip".
  - If a potion is already used, that option is disabled/hidden.
- **Win Condition:**
  - Witch is on the Town team (wins with Town).

# Host Role Selection
- When creating a lobby, the host can choose which special roles are enabled (Doctor, Detective, Witch).
- Mafia is always included.
- Only enabled roles are assigned at game start.
- UI: Add a role selection menu for the host before starting the game.

---

**Next steps:**
- Add 'witch' to the roles system and implement her night actions and single-use logic.
- Add host role selection UI and logic to only assign enabled roles at game start.

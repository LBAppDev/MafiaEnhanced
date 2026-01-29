import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import asyncio
import random
import time
import math
import google.generativeai as genai
from dotenv import load_dotenv
from collections import defaultdict

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
API_KEY = os.getenv('API_KEY')

# Configure Gemini
if API_KEY:
    genai.configure(api_key=API_KEY)

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MafiaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.lobbies = {}  # channel_id -> GameLobby
        self.lobbies_lock = asyncio.Lock()

    async def setup_hook(self):
        await self.tree.sync()
        self.game_loop.start()

    @tasks.loop(seconds=1)
    async def game_loop(self):
        """Main Game Loop: Checks timers and auto-advances phases."""
        current_time = time.time()
        # Create a copy of keys to avoid modification during iteration issues
        for channel_id in list(self.lobbies.keys()):
            lobby = self.lobbies.get(channel_id)
            if not lobby or lobby.status != 'in-game':
                continue

            # Handle auto bot actions
            if lobby.bot_mode == 'auto':
                await lobby.process_auto_bot_actions(self)
            
            # Check for early phase advancement (discussion with all actions complete)
            should_advance = False
            if current_time >= lobby.phase_end_time:
                should_advance = True
            elif lobby.phase == 'discussion' and lobby.should_auto_advance_discussion():
                should_advance = True
            
            if should_advance:
                await lobby.advance_phase(self)
            else:
                # Update display every 3 seconds to show timer changes (EDIT message, don't send new)
                if not hasattr(lobby, 'last_display_update'):
                    lobby.last_display_update = 0
                
                if current_time - lobby.last_display_update >= 3:
                    lobby.last_display_update = current_time
                    channel = self.get_channel(lobby.channel_id)
                    if channel and lobby.last_message:
                        # Edit the existing message to update timer
                        embed = lobby.render_embed()
                        view = GameView(lobby)
                        try:
                            await lobby.last_message.edit(embed=embed, view=view)
                        except:
                            pass  # Message might be deleted

bot = MafiaBot()

# --- TYPES & CONSTANTS ---

ROLES = ['villager', 'mafia', 'doctor', 'detective']

# Phase Durations (in seconds)
PHASE_DURATION = {
    'night': 30,
    'discussion': 180,  # 3 minutes
    'voting': 30
}

EPSILON = 5  # Min/max boundaries for suspicion
BASELINE_SUSPICION = 35  # Initial suspicion for unknowns

# Suspicion Engine Weights (Full Psychology Model)
WEIGHTS = {
    'VOTE_BAD': 0.25,
    'VOTE_GOOD': -0.20,
    'DETECTIVE_CORRECT': 1.2,
    'DETECTIVE_WRONG': -1.0,
    'DOCTOR_SAVE': -0.8,
    'HYPOCRISY': 0.30,  # Accused X but voted Y
    'CONSISTENCY': -0.10,  # Accused X and voted X
    'BANDWAGON': 0.15,  # Late voting
    'LURKER_PENALTY': 0.12,  # No actions
    'GUILT_BY_ASSOCIATION': 0.20,  # Defended high-sus player
    'VINDICATION': -0.40,  # Voted for dead mafia
    'COMPLICITY': 0.25,  # Never voted for dead mafia
    'DEFENDED_MAFIA': 0.35,  # Defended someone who was mafia
    'NOISE_MULTIPLIER_MIN': 0.6,
    'NOISE_MULTIPLIER_MAX': 1.4,
    'MISINTERPRETATION_CHANCE': 0.05,  # 5% chance
    'CONFIRMATION_BIAS_HIGH': 1.4,  # When suspicious of target (>60%)
    'CONFIRMATION_BIAS_LOW': 0.5,  # When trusting target (<40%)
    'MEMORY_DECAY': 0.85,  # Suspicion drifts back to baseline each round
    'INTUITION_LEAK': 0.15,  # Detective intuition spreads to others
}

# Bot names for testing
BOT_NAMES = [
    "Detector", "Healer", "Shadow", "Echo", "Cipher",
    "Nova", "Phantom", "Raven", "Specter", "Vortex",
    "Sentinel", "Nexus", "Pulse", "Axiom", "Mirage"
]

class Player:
    def __init__(self, user: discord.User = None, is_host=False, is_bot=False, bot_name=None):
        if is_bot:
            # For bot players
            self.id = random.randint(1000000000, 9999999999)
            self.name = bot_name or random.choice(BOT_NAMES)
            self.user = None
            self.is_bot = True
        else:
            # For real players
            self.id = user.id
            self.name = user.display_name
            self.user = user
            self.is_bot = False
        
        self.is_host = is_host
        self.is_alive = True
        self.role = 'villager'
        self.joined_at = time.time()
        
        # Behavioral tracking
        self.discussion_actions = []  # List of (action_type, target_id) tuples from discussion
        self.votes_cast = []  # History of votes this game
        self.night_actions = []  # History of night actions


class SuspicionMatrix:
    """Core data structure representing who suspects whom."""
    def __init__(self):
        self.matrix = defaultdict(lambda: defaultdict(float))
    
    def get(self, observer_id, target_id, default=BASELINE_SUSPICION):
        """Get suspicion value (0-100)."""
        if observer_id == target_id:
            return None  # Can't suspect yourself
        return self.matrix[observer_id][target_id] if self.matrix[observer_id][target_id] != 0 else default
    
    def set(self, observer_id, target_id, value):
        """Set suspicion value with clamping."""
        if observer_id == target_id:
            return
        self.matrix[observer_id][target_id] = max(EPSILON, min(100 - EPSILON, value))
    
    def get_all_for_observer(self, observer_id):
        """Get all suspicion values for an observer."""
        return dict(self.matrix[observer_id])
    
    def get_average_suspicion(self, target_id, exclude_id=None):
        """Get average suspicion across all observers."""
        values = []
        for obs_id in self.matrix:
            if exclude_id and obs_id == exclude_id:
                continue
            if target_id in self.matrix[obs_id] and self.matrix[obs_id][target_id] != 0:
                values.append(self.matrix[obs_id][target_id])
        return sum(values) / len(values) if values else BASELINE_SUSPICION

class GameLobby:
    def __init__(self, channel_id, host: discord.User):
        self.channel_id = channel_id
        self.host_id = host.id
        self.status = 'waiting' # waiting, in-game, finished
        self.players = {host.id: Player(host, is_host=True)}
        
        # Game State
        self.phase = 'night'
        self.round = 0
        self.phase_end_time = 0
        self.phase_start_time = 0  # Track when phase started
        self.mafia_count = 0
        self.villager_count = 0
        self.winner = None
        
        # Storage
        self.votes = {}     # voter_id -> target_id (current phase)
        self.actions = {}   # actor_id -> target_id (Night)
        self.suspicion_matrix = SuspicionMatrix()  # Core psychometric engine
        
        # Action tracking for phase completion
        self.actions_required = {}  # phase -> list of player_ids who must act
        self.actions_completed = set()  # Set of player_ids who have acted
        self.discussion_actions_completed = set()  # Discussion phase actions
        
        # Behavioral tracking
        self.discussion_events = []  # [(round, actor_id, action_type, target_id), ...]
        self.death_log = []  # [(round, player_id, role), ...]
        self.logs = []      # List of strings for public logs
        self.rumors = []  # [(target_id, direction), ...] direction: +1 or -1
        
        # Stats tracking
        self.accusation_count = {}  # target_id -> count of accusations
        self.defense_count = {}  # target_id -> count of defenses
        self.vote_count = {}  # target_id -> count of votes
        
        # Bot testing mode
        self.bot_mode = None  # 'auto' or 'manual' (None = no bots)
        self.used_bot_names = set()  # Track which bot names are in use
        self.player_list = []  # Ordered list of player IDs for index-based lookups
        self.recently_joined = []  # Track recently joined players for UI display
        self.last_message = None  # Track last game message for editing instead of sending new ones
        self.last_panel_phase = None  # Track which phase was used for the last panel message (to resend on phase change)
        self.lock = asyncio.Lock()  # Prevent concurrent operations on this lobby
        self.last_panel_phase = None  # Track which phase was last shown on the panel

    def get_player_by_index(self, index: int):
        """Get player by their index in the player list."""
        if 0 <= index < len(self.player_list):
            player_id = self.player_list[index]
            return self.players.get(player_id)
        return None
    
    def get_player_index(self, player_id):
        """Get a dynamic index for any player based on current players dict."""
        # Create a sorted list of current player IDs to ensure consistent indexing
        current_players = sorted(self.players.keys())
        if player_id in current_players:
            return current_players.index(player_id)
        return -1

    async def add_player(self, user: discord.User):
        if user.id not in self.players:
            self.players[user.id] = Player(user)
            # Track recently joined
            self.recently_joined.append(user.name)
            if len(self.recently_joined) > 3:
                self.recently_joined.pop(0)  # Keep last 3
            return True
        return False
    
    def add_bots(self, count: int, mode: str = 'auto'):
        """Add bot players for testing. Mode: 'auto' or 'manual'."""
        if self.status != 'waiting':
            return False, "Game already started."
        
        count = min(count, 5)  # Max 5 bots
        added = 0
        
        for _ in range(count):
            available_names = [n for n in BOT_NAMES if n not in self.used_bot_names]
            if not available_names:
                break
            
            bot_name = available_names[0]
            self.used_bot_names.add(bot_name)
            
            bot_id = random.randint(1000000000, 9999999999)
            while bot_id in self.players:
                bot_id = random.randint(1000000000, 9999999999)
            
            self.players[bot_id] = Player(is_bot=True, bot_name=bot_name)
            # Track recently joined bots
            self.recently_joined.append(f"🤖 {bot_name}")
            if len(self.recently_joined) > 3:
                self.recently_joined.pop(0)
            added += 1
        
        if added > 0:
            self.bot_mode = mode
            return True, f"Added {added} bot(s) in {mode} mode."
        
        return False, "Could not add bots."
    
    def get_bot_action(self, bot_id: int, alive_players: list):
        """Generate automatic action for a bot."""
        if not alive_players:
            return None
        
        if bot_id not in self.players:
            return None  # Bot no longer exists
        
        bot = self.players[bot_id]
        
        if self.phase == 'night':
            # Night action: pick random target
            if bot.role == 'villager':
                return None  # Villagers don't act
            targets = [p for p in alive_players if p.id != bot_id]
            return random.choice(targets).id if targets else None
        
        elif self.phase == 'discussion':
            # Discussion: accuse, defend, or skip randomly
            return random.choice(['accuse', 'defend', 'skip'])
        
        elif self.phase == 'voting':
            # Voting: vote for someone or skip
            targets = [p.id for p in alive_players if p.id != bot_id]
            return random.choice(targets + ['SKIP']) if targets else 'SKIP'
        
        return None
    
    async def process_auto_bot_actions(self, bot_instance):
        """Process automatic actions for bots in auto mode."""
        alive_players = [p for p in self.players.values() if p.is_alive]
        
        for player in self.players.values():
            if not player.is_bot or not player.is_alive:
                continue
            
            # Skip if bot already acted in this phase
            if self.phase == 'night' and player.id in self.actions_completed:
                continue
            elif self.phase == 'discussion' and player.id in self.discussion_actions_completed:
                continue
            elif self.phase == 'voting' and player.id in self.votes:
                continue
            
            # Get bot action
            action = self.get_bot_action(player.id, alive_players)
            if action is None:
                continue
            
            # Execute bot action
            if self.phase == 'night':
                self.actions[player.id] = action
                self.actions_completed.add(player.id)
                self.logs.append(f"🤖 **{player.name}** ({player.role.title()}) performed night action.")
            
            elif self.phase == 'discussion':
                self.discussion_actions_completed.add(player.id)
                action_text = "accused" if action == 'accuse' else "defended" if action == 'defend' else "skipped"
                self.logs.append(f"🤖 **{player.name}** {action_text} in discussion.")
            
            elif self.phase == 'voting':
                self.votes[player.id] = action
                if action == 'SKIP':
                    self.logs.append(f"🤖 **{player.name}** skipped vote.")
                else:
                    target_name = self.players.get(action, None)
                    if target_name:
                        self.logs.append(f"🤖 **{player.name}** voted for **{target_name.name}**.")

    def start_game(self):
        if len(self.players) < 3:
            return False, "Need at least 3 players."
        
        # Cancel auto-start task if it exists
        if hasattr(self, 'auto_start_task') and self.auto_start_task and not self.auto_start_task.done():
            try:
                self.auto_start_task.cancel()
            except:
                pass
        
        self.status = 'in-game'
        player_ids = list(self.players.keys())
        self.player_list = player_ids  # Store ordered list for index-based lookups
        count = len(player_ids)
        
        # Assign Roles
        mafia_num = max(1, count // 3)
        roles = ['mafia'] * mafia_num
        if count >= 4: roles.append('doctor')
        if count >= 5: roles.append('detective')
        while len(roles) < count:
            roles.append('villager')
        
        random.shuffle(roles)
        
        for i, pid in enumerate(player_ids):
            self.players[pid].role = roles[i]
            self.players[pid].is_alive = True

        self.mafia_count = mafia_num
        self.villager_count = count - mafia_num
        
        # Initialize Suspicion Matrix (High Entropy Model)
        for obs_id in player_ids:
            for target_id in player_ids:
                if obs_id == target_id: 
                    continue
                # Mafia know each other (0 suspicion), everyone else starts ~35 ± noise
                if (self.players[obs_id].role == 'mafia' and 
                    self.players[target_id].role == 'mafia'):
                    self.suspicion_matrix.set(obs_id, target_id, EPSILON)
                else:
                    noise = random.uniform(-10, 10)
                    self.suspicion_matrix.set(obs_id, target_id, BASELINE_SUSPICION + noise)

        self.phase = 'night'
        self.round = 1
        self.phase_start_time = time.time()
        self.phase_end_time = time.time() + PHASE_DURATION['night']
        
        # Set up actions required for night phase
        self._setup_night_actions()
        
        self.logs.append("🌙 Night 1 has begun. Roles, perform your actions...")
        return True, "Game Started"
    
    async def send_role_reveals(self, channel):
        """Send role reveal embeds to each player in the channel."""
        for pid, p in self.players.items():
            if not p.user:
                continue
            role_desc = f"You are a **{p.role.upper()}**."
            if p.role == 'mafia': 
                role_desc += "\n💀 Your goal: Eliminate all townspeople."
                # Show fellow mafia members
                mafia_teammates = [player.name for player_id, player in self.players.items() 
                                  if player.role == 'mafia' and player_id != pid]
                if mafia_teammates:
                    role_desc += f"\n\n🤝 **Your Mafia Team:**\n" + "\n".join(f"  • {name}" for name in mafia_teammates)
            elif p.role == 'doctor': 
                role_desc += "\n💊 Your goal: Save the town.\nEach night, choose someone to protect."
            elif p.role == 'detective': 
                role_desc += "\n🔍 Your goal: Find the Mafia.\nEach night, investigate one player's true role."
            else:
                role_desc += "\n🏘️ Your goal: Eliminate the Mafia.\nYou have only discussion and voting."
            
            # Create an embed for the role reveal
            role_embed = discord.Embed(
                title=f"🕵️ Mafia Enhanced - Your Role",
                description=role_desc,
                color=discord.Color.blurple()
            )
            
            try:
                # Store role reveal embed for ephemeral access via the 'Reveal Role' button
                if not hasattr(self, 'role_reveals'):
                    self.role_reveals = {}
                self.role_reveals[pid] = role_embed
            except:
                pass

    async def update_lobby_panel(self, channel=None, status_text: str = None, view=None):
        """Edit the original lobby panel message to reflect current players or send it if missing."""
        embed = self.render_lobby_embed(status_text)
        use_view = view if view is not None else LobbyView(self)
        # If transitioning into a game panel (GameView) or the lobby has started, send a new panel message and keep old ones
        # Avoid importing this module (prevents circular-import side effects).
        is_game_view = getattr(use_view, '__class__', None).__name__ == 'GameView'

        if channel and (is_game_view or self.status != 'waiting' or not self.last_message):
            try:
                msg = await channel.send(embed=embed, view=use_view)
                self.last_message = msg
                self.last_panel_phase = self.phase
                try:
                    print(f"[DEBUG] Sent lobby panel msg id={getattr(msg, 'id', None)} phase={self.phase}")
                except:
                    pass
                return
            except:
                pass

        # Otherwise, try editing the existing lobby message safely
        if self.last_message:
            try:
                await self.last_message.edit(embed=embed, view=use_view)
                try:
                    print(f"[DEBUG] Edited lobby panel msg id={getattr(self.last_message, 'id', None)} phase={self.phase}")
                except:
                    pass
                return
            except Exception as e:
                print(f"[DEBUG] Lobby edit failed: {e}")

        # Fallback: send a new message if editing failed
        if channel:
            try:
                msg = await channel.send(embed=embed, view=use_view)
                self.last_message = msg
                self.last_panel_phase = self.phase
                try:
                    print(f"[DEBUG] Lobby fallback sent new panel msg id={getattr(msg, 'id', None)} phase={self.phase}")
                except:
                    pass
            except Exception as e2:
                print(f"[DEBUG] Lobby fallback send failed: {e2}")

    def start_auto_start(self, bot_instance, countdown: int = 30):
        """Schedule an auto-start countdown; no-op if already scheduled."""
        if hasattr(self, 'auto_start_task') and self.auto_start_task and not self.auto_start_task.done():
            return
        self.auto_start_task = asyncio.create_task(self._auto_start_countdown(bot_instance, countdown))

    async def _auto_start_countdown(self, bot_instance, countdown: int = 30):
        """Wait countdown seconds and auto-start the game if conditions are met."""
        try:
            await asyncio.sleep(countdown)
            # If lobby still waiting and enough players, start the game
            if self.status == 'waiting' and len(self.players) >= 5:
                async with self.lock:
                    if self.status != 'waiting':
                        return
                    success, msg = self.start_game()
                    if success:
                        channel = bot_instance.get_channel(self.channel_id) if bot_instance else None
                        # Store role_reveals and send initial game panel (use update_view to create the panel)
                        if channel:
                            await self.send_role_reveals(channel)
                            await self.update_view(channel, msg)
        except asyncio.CancelledError:
            return
        except Exception:
            pass
    
    def _setup_night_actions(self):
        """Setup which players must act during night phase."""
        self.actions_required = {}
        self.actions_completed = set()
        
        required = []
        for pid, p in self.players.items():
            if not p.is_alive:
                continue
            if p.role == 'mafia':
                required.append(pid)
            elif p.role == 'doctor':
                required.append(pid)
            elif p.role == 'detective':
                required.append(pid)
        
        self.actions_required['night'] = required
    
    def _setup_discussion_actions(self):
        """Setup which players must act during discussion phase."""
        self.discussion_actions_completed = set()
        # All alive players should participate
        required = [p.id for p in self.players.values() if p.is_alive]
        self.actions_required['discussion'] = required
    
    def _setup_voting(self):
        """Setup voting for voting phase."""
        self.votes = {}
        # All alive players must vote
        required = [p.id for p in self.players.values() if p.is_alive]
        self.actions_required['voting'] = required
    
    def _check_phase_completion(self):
        """Check if all required actions are completed for current phase."""
        required = self.actions_required.get(self.phase, [])
        
        if self.phase == 'night':
            return len(self.actions_completed) >= len(required)
        elif self.phase == 'discussion':
            return len(self.discussion_actions_completed) >= len(required)
        elif self.phase == 'voting':
            return len(self.votes) >= len(required)
        
        return False
    
    def get_phase_progress(self):
        """Get current phase progress (completed/required)."""
        required = self.actions_required.get(self.phase, [])
        
        if self.phase == 'night':
            return len(self.actions_completed), len(required)
        elif self.phase == 'discussion':
            return len(self.discussion_actions_completed), len(required)
        elif self.phase == 'voting':
            return len(self.votes), len(required)
        
        return 0, 0
    
    def should_auto_advance_discussion(self):
        """Check if discussion phase should auto-advance (all players acted)."""
        if self.phase != 'discussion':
            return False
        required_players = self.actions_required.get('discussion', [])
        return required_players and set(required_players).issubset(self.discussion_actions_completed)
    
    # --- SUSPICION ENGINE: Mathematical Core ---
    
    def clamp_suspicion(self, value):
        """Clamp suspicion to valid range."""
        return max(EPSILON, min(100 - EPSILON, value))
    
    def update_belief(self, observer_id, target_id, base_weight, action_context=None):
        """
        Core psychological belief update engine.
        
        Parameters:
        - observer_id: Who is updating their belief
        - target_id: Who they're forming beliefs about
        - base_weight: Base impact of the action (can be positive or negative)
        - action_context: Dict with additional context (action_type, etc.)
        """
        if observer_id == target_id or observer_id not in self.players or target_id not in self.players:
            return
        
        context = action_context or {}
        current = self.suspicion_matrix.get(observer_id, target_id)
        
        # 1. Noise Multiplier: No two observers interpret the same way
        noise_multiplier = random.uniform(
            WEIGHTS['NOISE_MULTIPLIER_MIN'],
            WEIGHTS['NOISE_MULTIPLIER_MAX']
        )
        
        # 2. Misinterpretation Chance: Flip polarity occasionally
        if random.random() < WEIGHTS['MISINTERPRETATION_CHANCE']:
            base_weight = -base_weight
        
        # 3. Confirmation Bias: If I already suspect you, bad looks worse
        if current > 60:  # High suspicion
            base_weight *= WEIGHTS['CONFIRMATION_BIAS_HIGH']
        elif current < 40:  # High trust
            base_weight *= WEIGHTS['CONFIRMATION_BIAS_LOW']
        
        # 4. Apply weight and noise
        impact = base_weight * noise_multiplier
        new_value = current + impact
        
        # 5. Clamp to valid range
        new_value = self.clamp_suspicion(new_value)
        self.suspicion_matrix.set(observer_id, target_id, new_value)
    
    def apply_memory_decay(self):
        """
        Every round, suspicion drifts back toward baseline.
        NewValue = (OldValue * 0.85) + (35 * 0.15)
        """
        for obs_id in self.players:
            for target_id in self.players:
                if obs_id == target_id:
                    continue
                current = self.suspicion_matrix.get(obs_id, target_id)
                decayed = (current * WEIGHTS['MEMORY_DECAY'] + 
                          BASELINE_SUSPICION * (1 - WEIGHTS['MEMORY_DECAY']))
                self.suspicion_matrix.set(obs_id, target_id, decayed)
    
    def propagate_intuition(self, detective_id, target_id, is_mafia):
        """
        Detective's intuition leaks to others via subconscious cues.
        Small fraction spreads throughout the player base.
        """
        # Detective sets certainty
        certainty = 99 if is_mafia else EPSILON
        self.suspicion_matrix.set(detective_id, target_id, certainty)
        
        # Leak to others: move slightly toward detective's assessment
        leak_amount = 5 * WEIGHTS['INTUITION_LEAK']
        for obs_id in self.players:
            if obs_id == detective_id:
                continue
            current = self.suspicion_matrix.get(obs_id, target_id, BASELINE_SUSPICION)
            if current is None:
                current = BASELINE_SUSPICION
            if is_mafia:
                new_val = current + leak_amount
            else:
                new_val = current - leak_amount
            self.suspicion_matrix.set(obs_id, target_id, new_val)
    
    def generate_rumor(self):
        """
        Occasionally generate a rumor that affects all players' views of someone.
        Creates organic conversation starters.
        """
        if random.random() > 0.3:  # 30% chance per round
            return
        
        alive_players = [p for p in self.players.values() if p.is_alive]
        if not alive_players:
            return
        
        target = random.choice(alive_players)
        direction = random.choice([1, -1])  # +1 (sus) or -1 (trust)
        
        for obs_id in self.players:
            if obs_id == target.id:
                continue
            current = self.suspicion_matrix.get(obs_id, target.id)
            new_val = current + (direction * 7)
            self.suspicion_matrix.set(obs_id, target.id, new_val)
        
        self.rumors.append((target.id, direction))
        if direction > 0:
            self.logs.append(f"👻 **Rumor Mill**: Whispers about **{target.name}** being untrustworthy...")
        else:
            self.logs.append(f"👻 **Rumor Mill**: **{target.name}** speaks well of the town...")

    async def add_player(self, user: discord.User):
        if user.id not in self.players:
            self.players[user.id] = Player(user)
            return True
        return False

    async def advance_phase(self, bot_instance):
        channel = bot_instance.get_channel(self.channel_id)
        if not channel: return

        if self.phase == 'night':
            # Resolve night and move to discussion
            await self.resolve_night(channel)
            return  # resolve_night calls update_view, don't send duplicate

        elif self.phase == 'discussion':
            # Discussion phase is ending - move to voting (either by timer or early completion)
            self.phase = 'voting'
            self.phase_start_time = time.time()
            self.phase_end_time = time.time() + PHASE_DURATION['voting']
            self._setup_voting()
            await self.update_view(channel, "🗳️ **Voting Phase (30 sec)** - Cast your votes!")
            return

        elif self.phase == 'voting':
            # Resolve voting and move to night
            await self.resolve_voting(channel)
            return  # resolve_voting calls update_view, don't send duplicate
        
        # Check Win Condition
        if self.mafia_count == 0:
            self.winner = 'villager'
            self.status = 'finished'
            await self.update_view(channel, "🏆 **TOWN WINS!** All Mafia eliminated.")
            try:
                survivors = [getattr(p.user, 'mention', f"**{p.name}**") for p in self.players.values() if p.is_alive]
                kicked = getattr(self, 'recent_kicked', [])
                extra = f"\n⚠️ Eliminated for failing to act: {', '.join(kicked)}" if kicked else ""
                await channel.send(f"🏆 **TOWN WINS!** Final Survivors: {', '.join(survivors)}{extra}")
            except:
                pass
        elif self.mafia_count  >= self.villager_count:
            self.winner = 'mafia'
            self.status = 'finished'
            await self.update_view(channel, "💀 **MAFIA WINS!** They have taken over the town.")
            try:
                survivors = [getattr(p.user, 'mention', f"**{p.name}**") for p in self.players.values() if p.is_alive]
                kicked = getattr(self, 'recent_kicked', [])
                extra = f"\n⚠️ Eliminated for failing to act: {', '.join(kicked)}" if kicked else ""
                await channel.send(f"💀 **MAFIA WINS!** Final Survivors: {', '.join(survivors)}{extra}")
            except:
                pass
        elif self.status == 'in-game':
             await self.update_view(channel)
    
    async def host_end_phase(self, channel):
        """Host can manually end current phase early."""
        if self.phase == 'night':
            await self.resolve_night(channel)

        elif self.phase == 'discussion':
            self.phase = 'voting'
            self.phase_start_time = time.time()
            self.phase_end_time = time.time() + PHASE_DURATION['voting']
            self._setup_voting()
            await self.update_view(channel, "🗳️ **Voting Phase (30 sec)** - Host ended discussion early!")

        elif self.phase == 'voting':
            await self.resolve_voting(channel)

    async def resolve_voting(self, channel):
        """
        Resolve voting phase with advanced analysis.
        Checks: Hypocrisy, Consistency, Bandwagoning effects.
        """
        # Tally Votes - filter out invalid votes
        counts = {}
        valid_votes = {}
        for voter_id, target in self.votes.items():
            # Skip vote if voter or target no longer exists
            if target == 'SKIP':
                valid_votes[voter_id] = target
                counts[target] = counts.get(target, 0) + 1
            elif voter_id in self.players and target in self.players:
                valid_votes[voter_id] = target
                counts[target] = counts.get(target, 0) + 1
        
        self.votes = valid_votes  # Update votes to only valid ones
        
        eliminated_id = None
        max_votes = 0
        
        # Simple majority/plurality logic
        for target, count in counts.items():
            if count > max_votes:
                max_votes = count
                eliminated_id = target
            elif count == max_votes and eliminated_id is not None:
                eliminated_id = None  # Tie
        
        if eliminated_id and eliminated_id != 'SKIP':
            if eliminated_id not in self.players:
                self.logs.append("⚖️ Target no longer in game.")
            else:
                victim = self.players[eliminated_id]
                victim.is_alive = False
                
                mention = getattr(victim.user, 'mention', None) or f"**{victim.name}**"
                announcement = f"⚖️ {mention} was executed. Role: **{victim.role.upper()}**"
                self.logs.append(announcement)
                self.death_log.append((self.round, eliminated_id, victim.role))
                
                # Announce publicly as requested (mentions when possible)
                try:
                    await channel.send(announcement)
                except:
                    pass
                
                if victim.role == 'mafia':
                    self.mafia_count -= 1
                else:
                    self.villager_count -= 1
            # --- VOTING ANALYSIS ---
            # 1. Hypocrisy Check: Did you accuse X but vote Y?
            for voter_id, voted_target in self.votes.items():
                voter = self.players.get(voter_id)
                if not voter or not voter.is_alive:
                    continue
                
                # Check discussion events for accusations
                accused_anyone_else = any(
                    evt[1] == voter_id and evt[2] == 'accuse' and evt[3] != voted_target 
                    for evt in self.discussion_events
                )
                
                if accused_anyone_else and voted_target != eliminated_id:
                    # Hypocrite!
                    for obs_id in self.players:
                        if obs_id != voter_id:
                            self.update_belief(obs_id, voter_id, WEIGHTS['HYPOCRISY'])
                
                # 2. Consistency Bonus: Did you accuse AND vote the same?
                if any(evt[1] == voter_id and evt[2] == 'accuse' and evt[3] == voted_target 
                       for evt in self.discussion_events):
                    for obs_id in self.players:
                        if obs_id != voter_id:
                            self.update_belief(obs_id, voter_id, WEIGHTS['CONSISTENCY'])
                
                # 3. Bandwagon Penalty: Voting late (last 40% of vote order)
                vote_position = list(self.votes.values()).index(voted_target) if voted_target in self.votes.values() else -1
                if vote_position >= len(self.votes) * 0.6:  # Last 40%
                    for obs_id in self.players:
                        if obs_id != voter_id:
                            self.update_belief(obs_id, voter_id, WEIGHTS['BANDWAGON'])
            
            # --- INNOCENCE/MAFIA PENALTY ---
            # If Innocent dies: everyone who voted for them gains suspicion
            if victim.role != 'mafia':
                for voter_id, voted_target in self.votes.items():
                    if voted_target == eliminated_id:
                        for obs_id in self.players:
                            if obs_id != voter_id:
                                self.update_belief(obs_id, voter_id, WEIGHTS['VOTE_BAD'])
        else:
            announcement = "⚖️ No consensus reached. No one died."
            self.logs.append(announcement)
            try:
                await channel.send(announcement)
            except:
                pass
        self.votes = {}
        self.discussion_events = []  # Reset for next round
        self.discussion_actions_completed = set()  # Reset discussion tracking
        
        # Reset accountability stats for next cycle
        self.accusation_count = {}
        self.defense_count = {}
        self.vote_count = {}
        
        # Check Win Condition after voting resolution
        if self.mafia_count == 0:
            self.winner = 'villager'
            self.status = 'finished'
            await self.update_view(channel, "🏆 **TOWN WINS!** All Mafia eliminated.")
            # Public final message with survivors and any kicked players
            try:
                survivors = [getattr(p.user, 'mention', f"**{p.name}**") for p in self.players.values() if p.is_alive]
                kicked = getattr(self, 'recent_kicked', [])
                extra = f"\n⚠️ Eliminated for failing to act: {', '.join(kicked)}" if kicked else ""
                await channel.send(f"🏆 **TOWN WINS!** Final Survivors: {', '.join(survivors)}{extra}")
            except:
                pass
            return
        elif self.mafia_count >= self.villager_count:
            self.winner = 'mafia'
            self.status = 'finished'
            await self.update_view(channel, "💀 **MAFIA WINS!** They have taken over the town.")
            try:
                survivors = [getattr(p.user, 'mention', f"**{p.name}**") for p in self.players.values() if p.is_alive]
                kicked = getattr(self, 'recent_kicked', [])
                extra = f"\n⚠️ Eliminated for failing to act: {', '.join(kicked)}" if kicked else ""
                await channel.send(f"💀 **MAFIA WINS!** Final Survivors: {', '.join(survivors)}{extra}")
            except:
                pass
            return
        
        self.phase = 'night'
        self.phase_start_time = time.time()
        self.phase_end_time = time.time() + PHASE_DURATION['night']
        self._setup_night_actions()  # Initialize night actions for new phase
        
        # Apply memory decay and rumors at night transition
        self.apply_memory_decay()
        self.generate_rumor()
        
        await self.update_view(channel, f"🌙 **Night {self.round}** - Roles perform your actions.")

    async def resolve_night(self, channel):
        """
        Resolve night phase with advanced mechanics:
        - Doctor saves and trusts
        - Detective investigation
        - Mafia frame-ups
        - Historical Vindication
        """
        # Process Actions
        mafia_target = None
        doc_target = None
        detective_id = None
        detective_investigation = None
        
        # 1. Tally Mafia Votes
        mafia_votes = {}
        for actor_id, target_id in self.actions.items():
            actor = self.players.get(actor_id)
            if not actor or not actor.is_alive: 
                continue
            
            if actor.role == 'mafia':
                mafia_votes[target_id] = mafia_votes.get(target_id, 0) + 1
            elif actor.role == 'doctor':
                doc_target = target_id
            elif actor.role == 'detective':
                detective_id = actor_id
                detective_investigation = target_id

        # Determine Mafia Kill
        if mafia_votes:
            max_m_votes = max(mafia_votes.values())
            candidates = [t for t, c in mafia_votes.items() if c == max_m_votes]
            mafia_target = random.choice(candidates) if candidates else None
        
        # --- NIGHT RESOLUTION ---
        killed_this_night = False
        if mafia_target and mafia_target != 'SKIP':
            if mafia_target == doc_target:
                self.logs.append("✨ The **Doctor** intervened and saved a life tonight!")
                # Announce the doctor save publicly (mention when possible)
                if doc_target in self.players:
                    saved_player = self.players[doc_target]
                    mention = getattr(saved_player.user, 'mention', None) or f"**{saved_player.name}**"
                    try:
                        await channel.send(f"✨ The **Doctor** saved {mention} tonight! 👏")
                    except:
                        pass
                # Doctor Bias: Doctor trusts the person they saved (with margin of error)
                if doc_target in self.players:
                    doctor_id = next((p.id for p in self.players.values() if p.role == 'doctor' and p.is_alive), None)
                    if doctor_id:
                        # Doctor's trust in saved target (usually -25 suspicion, 25% error reverses it)
                        trust_change = -25
                        if random.random() < 0.25:
                            trust_change = 15  # Doctor misjudges!
                        current_sus = self.suspicion_matrix.get(doctor_id, doc_target)
                        self.suspicion_matrix.set(doctor_id, doc_target, self.clamp_suspicion(current_sus + trust_change))
                        
                        # Saved person gains trust in doctor (with margin of error)
                        saved_trust_change = -20
                        if random.random() < 0.2:
                            saved_trust_change = 10  # Misjudgment by saved person
                        current_sus = self.suspicion_matrix.get(doc_target, doctor_id)
                        self.suspicion_matrix.set(doc_target, doctor_id, self.clamp_suspicion(current_sus + saved_trust_change))
            else:
                victim = self.players[mafia_target]
                victim.is_alive = False
                killed_this_night = True
                mention = getattr(victim.user, 'mention', None) or f"**{victim.name}**"
                announcement = f"💀 {mention} was found dead. Role: **{victim.role.upper()}**"
                self.logs.append(announcement)
                self.death_log.append((self.round, mafia_target, victim.role))
                try:
                    await channel.send(announcement)
                except:
                    pass
                if victim.role == 'mafia': 
                    self.mafia_count -= 1
                else: 
                    self.villager_count -= 1
        else:
            announcement = "🌙 A quiet night. No one died."
            self.logs.append(announcement)
            try:
                await channel.send(announcement)
            except:
                pass
        
        # --- FAILED KILL SUSPICION: If protection succeeded, town blames someone else ---
        if mafia_target and mafia_target == doc_target and mafia_target in self.players:
            # A failed kill attempt happened - town will suspect someone was protecting
            # Randomly make town slightly suspicious of another player
            other_players = [p for p in self.players.values() if p.id != mafia_target and p.is_alive]
            if other_players:
                suspected_protector = random.choice(other_players)
                # All town slightly suspects this player (might be the doctor/protector)
                for observer_id in self.players:
                    if observer_id not in (mafia_target, suspected_protector.id):
                        current_sus = self.suspicion_matrix.get(observer_id, suspected_protector.id)
                        # Raise suspicion (looks like they protected someone!)
                        change = 12
                        if random.random() < 0.35:  # 35% chance to be wrong
                            change = -8
                        self.suspicion_matrix.set(observer_id, suspected_protector.id, self.clamp_suspicion(current_sus + change))
        
        # --- DETECTIVE INVESTIGATION ---
        if detective_id and detective_investigation:
            target = self.players.get(detective_investigation)
            if target:
                is_mafia = target.role == 'mafia'
                self.propagate_intuition(detective_id, detective_investigation, is_mafia)
                self.logs.append(f"🔍 Detective investigates in shadow...")
        
        # --- MAFIA FRAME-UP (Random Innocent Gets Suspicion) ---
        if random.random() < 0.4:  # 40% chance
            innocent_players = [
                p.id for p in self.players.values() 
                if p.is_alive and p.role != 'mafia'
            ]
            if innocent_players:
                framed = random.choice(innocent_players)
                for obs_id in self.players:
                    if obs_id != framed:
                        self.update_belief(obs_id, framed, 0.10)  # Small bump
        
        # --- HISTORICAL VINDICATION ---
        # Check all dead players from previous rounds
        for round_num, dead_id, dead_role in self.death_log:
            if round_num == self.round:  # Just died this round
                if dead_role == 'mafia':
                    # Those who voted for this mafia get Vindication boost
                    for voter_history in self.players.values():
                        # This would require tracking votes per round. For now, global boost:
                        if dead_id in self.players:
                            for obs_id in self.players:
                                if obs_id != dead_id:
                                    self.update_belief(obs_id, obs_id, WEIGHTS['VINDICATION'])
                else:
                    # Innocent died: those who voted for them lose trust
                    for obs_id in self.players:
                        if obs_id != dead_id:
                            self.update_belief(obs_id, obs_id, WEIGHTS['COMPLICITY'])

        # --- ACCOUNTABILITY: Eliminate special roles that didn't act ---
        kicked_players = []
        required_to_act = self.actions_required.get('night', [])
        
        for player_id in required_to_act:
            player = self.players.get(player_id)
            if not player or not player.is_alive:
                continue
            if player_id not in self.actions_completed:
                # Special role didn't act - they're eliminated
                player.is_alive = False
                self.logs.append(f"⚠️ **{player.name}** ({player.role.upper()}) failed to act and was eliminated!")
                self.death_log.append((self.round, player_id, player.role))
                if player.role == 'mafia':
                    self.mafia_count -= 1
                else:
                    self.villager_count -= 1
                # Append mention if available, otherwise fall back to bold name
                kicked_players.append(getattr(player.user, 'mention', None) or f"**{player.name}**")

        # If someone was kicked, announce and restart the night phase
        if kicked_players:
            # Store mentions for final report
            self.recent_kicked = kicked_players

            try:
                await channel.send(f"⚠️ The following players were eliminated for failing to act: {', '.join(kicked_players)}")
            except:
                pass

            self.actions = {}
            self.actions_completed = set()
            self._setup_night_actions()
            
            # Check if game is still active after eliminations
            if self.mafia_count == 0:
                self.winner = 'villager'
                self.status = 'finished'
                await self.update_view(channel, "🏆 **TOWN WINS!** All Mafia eliminated.")
                # Send an explicit final message tagging survivors and kicked players
                try:
                    survivors = [getattr(p.user, 'mention', f"**{p.name}**") for p in self.players.values() if p.is_alive]
                    kicked = getattr(self, 'recent_kicked', [])
                    extra = f"\n⚠️ Eliminated for failing to act: {', '.join(kicked)}" if kicked else ""
                    await channel.send(f"🏆 **TOWN WINS!** Final Survivors: {', '.join(survivors)}{extra}")
                except:
                    pass
                return
            elif self.mafia_count >= self.villager_count:
                self.winner = 'mafia'
                self.status = 'finished'
                await self.update_view(channel, "💀 **MAFIA WINS!** They have taken over the town.")
                try:
                    survivors = [getattr(p.user, 'mention', f"**{p.name}**") for p in self.players.values() if p.is_alive]
                    kicked = getattr(self, 'recent_kicked', [])
                    extra = f"\n⚠️ Eliminated for failing to act: {', '.join(kicked)}" if kicked else ""
                    await channel.send(f"💀 **MAFIA WINS!** Final Survivors: {', '.join(survivors)}{extra}")
                except:
                    pass
                return
            
            await self.update_view(channel, f"🌙 **Night {self.round}** (Restart) - Acting roles must choose!")
            return

        self.actions = {}
        self.actions_completed = set()  # Reset action tracking
        
        # Check Win Condition after night resolution
        if self.mafia_count == 0:
            self.winner = 'villager'
            self.status = 'finished'
            await self.update_view(channel, "🏆 **TOWN WINS!** All Mafia eliminated.")
            return
        elif self.mafia_count >= self.villager_count:
            self.winner = 'mafia'
            self.status = 'finished'
            await self.update_view(channel, "💀 **MAFIA WINS!** They have taken over the town.")
            return
        
        self.round += 1
        self.phase = 'discussion'
        self.phase_start_time = time.time()
        self.phase_end_time = time.time() + PHASE_DURATION['discussion']
        self._setup_discussion_actions()  # Initialize discussion participation tracking
        
        # Flavor Text
        intro = "The sun rises on a town gripped by paranoia."
        if API_KEY and killed_this_night:
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(f"Write a 1-sentence gritty noir intro for Day {self.round} of a mafia game with a fresh murder.")
                intro = response.text
            except: 
                pass
            
        await self.update_view(channel, f"☀️ **Day {self.round}** - {intro}")

    async def update_view(self, channel, message_content=None):
        embed = self.render_embed()
        view = GameView(self)

        # Keep logs briefly then clear at next update
        if self.logs and len(self.logs) > 8:
            self.logs = self.logs[-8:]  # Keep last 8 logs

        # If the phase has changed since the last panel we displayed, resend a fresh panel message
        send_new_panel = (self.last_panel_phase != self.phase)

        if send_new_panel or not self.last_message:
            try:
                # Send a fresh panel message for the new phase and keep previous panels in the channel
                msg = await channel.send(content=message_content, embed=embed, view=view)
                self.last_message = msg
                self.last_panel_phase = self.phase
                try:
                    print(f"[DEBUG] Sent lobby panel msg id={getattr(msg, 'id', None)} phase={self.phase}")
                except:
                    pass
                return
            except:
                pass

        # Otherwise try to edit the existing message
        try:
            await self.last_message.edit(content=message_content, embed=embed, view=view)
            try:
                print(f"[DEBUG] Edited panel msg id={getattr(self.last_message, 'id', None)} phase={self.phase} embed_present={embed is not None}")
            except:
                pass
        except Exception as e:
            print(f"[DEBUG] Edit failed: {e}")
            # If edit fails, fall back to sending a new message (keep previous panels)
            try:
                msg = await channel.send(content=message_content, embed=embed, view=view)
                self.last_message = msg
                self.last_panel_phase = self.phase
                try:
                    print(f"[DEBUG] Fallback sent new panel msg id={getattr(msg, 'id', None)} phase={self.phase}")
                except:
                    pass
            except Exception as e2:
                print(f"[DEBUG] Fallback send failed: {e2}")

    def render_embed(self):
        """Enhanced Discord embed with detailed suspicion analytics."""
        color = discord.Color.blue()
        if self.phase == 'night': 
            color = discord.Color.purple()
        elif self.phase == 'voting': 
            color = discord.Color.red()
        elif self.phase == 'discussion':
            color = discord.Color.orange()
        elif self.status == 'finished': 
            color = discord.Color.gold()

        # Calculate time remaining in seconds
        time_remaining = max(0, self.phase_end_time - time.time())
        
        phase_durations = {
            'night': '(30 sec)',
            'discussion': '(3 min)',
            'voting': '(30 sec)'
        }
        duration_text = phase_durations.get(self.phase, '')

        embed = discord.Embed(
            title=f"🕵️ Mafia Enhanced - {self.phase.title()} {duration_text}",
            description=f"⏱️ Time Remaining: {int(time_remaining)}s",
            color=color
        )

        alive_txt = ""
        dead_txt = ""
        
        # --- ALIVE PLAYERS (without role indicators) ---
        for pid, p in self.players.items():
            if p.is_alive:
                # Bot indicator only
                bot_indicator = " 🤖" if p.is_bot else ""
                
                # Don't show any role info on shared board for alive players
                alive_txt += f"**{p.name}**{bot_indicator}\n"
            else:
                role_emoji = "💀"
                bot_emoji = " 🤖" if p.is_bot else ""
                dead_txt += f"{role_emoji} **{p.name}**{bot_emoji} ← *{p.role.title()}*\n"

        embed.add_field(name="👥 Players Alive", value=alive_txt if alive_txt else "None", inline=False)
        
        if dead_txt:
            embed.add_field(name="⚰️ Graveyard", value=dead_txt, inline=False)
        
        # --- RECENTLY JOINED ---
        if self.recently_joined:
            joined_txt = ", ".join(self.recently_joined)
            embed.add_field(name="✨ Recently Joined", value=joined_txt, inline=False)
        
        # --- GAME STATS ---
        stats_txt = f"**Mafia:** {self.mafia_count}\n**Town:** {self.villager_count}\n**Round:** {self.round}"
        embed.add_field(name="📊 Stats", value=stats_txt, inline=False)
        
        # --- PHASE-SPECIFIC INFO ---
        completed, required = self.get_phase_progress()
        if self.phase == 'night':
            embed.add_field(name="🌙 Actions Ready", value=f"{completed}/{required} Done", inline=True)
        elif self.phase == 'discussion':
            embed.add_field(name="💬 Participants", value=f"{completed}/{required} Acted", inline=True)
        elif self.phase == 'voting':
            embed.add_field(name="🗳️ Votes", value=f"{completed}/{required} Cast", inline=True)
        
        # --- PLAYER ACCOUNTABILITY STATS ---
        if self.accusation_count or self.defense_count or self.vote_count:
            stats_lines = []
            for pid, player in self.players.items():
                if not player.is_alive:
                    continue
                accusations = self.accusation_count.get(pid, 0)
                defenses = self.defense_count.get(pid, 0)
                votes = self.vote_count.get(pid, 0)
                
                # Only show if they have any stats
                if accusations > 0 or defenses > 0 or votes > 0:
                    stat_str = f"**{player.name}**: "
                    stat_parts = []
                    if accusations > 0:
                        stat_parts.append(f"🎯{accusations}")
                    if defenses > 0:
                        stat_parts.append(f"🛡️{defenses}")
                    if votes > 0:
                        stat_parts.append(f"🗳️{votes}")
                    stat_str += " ".join(stat_parts)
                    stats_lines.append(stat_str)
            
            if stats_lines:
                stats_text = "\n".join(stats_lines)
                embed.add_field(name="📊 Accountability", value=stats_text, inline=False)
        
        # --- RECENT EVENTS LOG ---
        if self.logs:
            log_text = "\n".join(self.logs[-5:])  # Last 5 events
            embed.add_field(name="📡 Recent Events", value=log_text, inline=False)
        
        # --- FOOTER WITH PHASE INFO ---
        if self.phase == 'discussion':
            embed.set_footer(text="💬 Discuss. Accuse. Defend. Build your case.")
        elif self.phase == 'voting':
            embed.set_footer(text="🗳️ Vote to eliminate. Who will you condemn?")
        elif self.phase == 'night':
            embed.set_footer(text="🌙 Special roles act in secret. Click 'Reveal Role (Only you)' to view your role.")
        
        # Add a role-reveal hint for in-game players regardless of phase
        if self.status == 'in-game':
            embed.add_field(name="🔒 Role Reveal", value="Click the 'Reveal Role (Only you)' button to see your role (this message is only visible to you).", inline=False)

        return embed
    def render_lobby_embed(self, status_text: str = None):
        """Render the waiting lobby panel showing current players and host."""
        embed = discord.Embed(
            title="🕵️ Mafia Enhanced - Lobby",
            description=status_text or "Click **Join Game** to enter. Minimum 3 players to start.",
            color=discord.Color.dark_grey()
        )

        # List players
        players_txt = "\n".join(
            [f"{('*' if p.is_host else '')} {getattr(p.user, 'mention', p.name)}" if not p.is_bot else f"🤖 {p.name}" for p in self.players.values()]
        )

        if not players_txt:
            players_txt = "No players yet."

        embed.add_field(name="👥 Players", value=players_txt, inline=False)
        embed.set_footer(text=f"Host: {getattr(self.players.get(self.host_id), 'name', 'Unknown')}")
        return embed

        return embed

# --- DISCORD UI VIEWS ---

class LobbyView(discord.ui.View):
    def __init__(self, lobby):
        super().__init__(timeout=None)
        self.lobby = lobby

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.primary, custom_id="join_btn")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.lobby.status != 'waiting':
            return await interaction.response.send_message("Game already started!", ephemeral=True)
        
        if await self.lobby.add_player(interaction.user):
            player_count = len(self.lobby.players)
            await interaction.response.send_message(
                f"✅ **{interaction.user.name}** joined! ({player_count} players now)",
                ephemeral=False
            )
            # Update the lobby panel to reflect new players
            try:
                await self.lobby.update_lobby_panel(interaction.channel)
                # If now 5 or more players, ensure auto-start is scheduled
                if len(self.lobby.players) >= 5:
                    self.lobby.start_auto_start(bot, countdown=30)
            except:
                pass
        else:
            await interaction.response.send_message("You are already in the lobby.", ephemeral=True)

    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.success, custom_id="start_btn")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.lobby.host_id:
            return await interaction.response.send_message("Only the host can start the game.", ephemeral=True)
        
        async with self.lobby.lock:
            if self.lobby.status != 'waiting':
                return await interaction.response.send_message("❌ Game already started or in progress.", ephemeral=True)
            
            success, msg = self.lobby.start_game()
            if success:
                await interaction.response.send_message("🎮 **Game Starting...**", ephemeral=True)
                # Log start
                print(f"[DEBUG] Host {interaction.user.id} triggered start_game in channel {interaction.channel.id}")
                # Store role_reveals (no DM)
                await self.lobby.send_role_reveals(interaction.channel)
                # Send the initial game panel (update_view will create a fresh panel for the current phase)
                await self.lobby.update_view(interaction.channel, msg)
            else:
                await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

class GameView(discord.ui.View):
    def __init__(self, lobby):
        super().__init__(timeout=None)
        self.lobby = lobby

    @discord.ui.button(label="Cast Vote / Perform Action", style=discord.ButtonStyle.primary, custom_id="action_menu_btn")
    async def action_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Block all interactions if game is finished
        if self.lobby.status == 'finished':
            return await interaction.response.send_message(
                f"🏁 Game has ended. **{self.lobby.winner.upper()} WINS!**",
                ephemeral=True
            )
        
        player = self.lobby.players.get(interaction.user.id)
        if not player or not player.is_alive:
            return await interaction.response.send_message("You are dead or not playing.", ephemeral=True)

        # Dynamic Select Menu based on phase/role
        alive_players = [p for p in self.lobby.players.values() if p.is_alive]
        options = []

        if self.lobby.phase == 'discussion':
            # Discussion: Accuse, Defend, or Skip
            options = [
                discord.SelectOption(label="Accuse Someone", value="accuse", description="Make an accusation"),
                discord.SelectOption(label="Defend Someone", value="defend", description="Defend a player"),
                discord.SelectOption(label="Skip", value="skip", description="Pass this round")
            ]
            placeholder = "What do you do during discussion?"
            custom_id = "discussion_select"
        
        elif self.lobby.phase == 'voting':
            # Cannot vote for yourself in voting phase
            for i, p in enumerate(alive_players):
                if p.id == player.id:
                    continue
                idx = self.lobby.get_player_index(p.id)
                if idx >= 0:
                    options.append(discord.SelectOption(label=p.name, value=str(idx)))
            options.append(discord.SelectOption(label="Skip Vote", value="SKIP"))
            placeholder = "Cast your vote to eliminate..."
            custom_id = "vote_select"

        elif self.lobby.phase == 'night':
            # Role check
            if player.role == 'villager':
                return await interaction.response.send_message("Villagers sleep at night.", ephemeral=True)
            
            for i, p in enumerate(alive_players):
                # Mafia cannot target themselves or other mafia members
                if player.role == 'mafia' and (p.id == player.id or p.role == 'mafia'):
                    continue
                # All other roles cannot target themselves
                if p.id == player.id:
                    continue
                idx = self.lobby.get_player_index(p.id)
                if idx >= 0:
                    options.append(discord.SelectOption(label=p.name, value=str(idx)))
            
            if player.role == 'mafia': 
                placeholder = "Select victim..."
            elif player.role == 'doctor': 
                placeholder = "Select person to save..."
            elif player.role == 'detective': 
                placeholder = "Select person to investigate..."
            else: 
                placeholder = "Select target..."
            custom_id = "night_select"
        
        else:
            return await interaction.response.send_message("Invalid phase for actions.", ephemeral=True)

        # Guard against empty option lists (Discord requires at least one option)
        if not options:
            return await interaction.response.send_message("❌ No valid targets available right now.", ephemeral=True)

        view = discord.ui.View(timeout=60)
        select = ActionSelect(self.lobby, options, placeholder, custom_id)
        view.add_item(select)
        
        # Show player's role in the action message
        role_emoji = ""
        mandatory_msg = ""
        if player.role == 'mafia':
            role_emoji = " 💀"
            mandatory_msg = "\n⚠️ **You MUST choose a target!** Failure to act will get you eliminated."
        elif player.role == 'doctor':
            role_emoji = " 💊"
            mandatory_msg = "\n⚠️ **You MUST choose a target!** Failure to act will get you eliminated."
        elif player.role == 'detective':
            role_emoji = " 🔍"
            mandatory_msg = "\n⚠️ **You MUST choose a target!** Failure to act will get you eliminated."
        else:
            role_emoji = " 👤"
        
        action_msg = f"You are a **{player.role.title()}**{role_emoji}\n\nSelect your action:{mandatory_msg}"
        await interaction.response.send_message(action_msg, view=view, ephemeral=True)

    @discord.ui.button(label="Reveal Role (Only you)", style=discord.ButtonStyle.secondary, custom_id="reveal_role_btn")
    async def reveal_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Send a one-off ephemeral message showing the player's role and mention
        player = self.lobby.players.get(interaction.user.id)
        if not player or not player.is_alive:
            return await interaction.response.send_message("You are dead or not playing.", ephemeral=True)

        # Prefer stored role reveal embed (one-time) if present, otherwise send a small text reveal
        if hasattr(self.lobby, 'role_reveals') and player.id in self.lobby.role_reveals:
            role_embed = self.lobby.role_reveals[player.id]
            await interaction.response.send_message(embed=role_embed, ephemeral=True)
            # Remove to avoid re-sending
            del self.lobby.role_reveals[player.id]
            return

        mention = getattr(player.user, 'mention', None) or f"**{player.name}**"
        role = player.role.upper()
        await interaction.response.send_message(f"🔒 {mention} — Your role is **{role}**. (This message is only visible to you)", ephemeral=True)
    
    @discord.ui.button(label="End Phase (Host Only)", style=discord.ButtonStyle.danger, custom_id="end_phase_btn")
    async def end_phase_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Block if game is finished
        if self.lobby.status == 'finished':
            return await interaction.response.send_message(
                f"🏁 Game has ended. **{self.lobby.winner.upper()} WINS!**",
                ephemeral=True
            )
        
        if interaction.user.id != self.lobby.host_id:
            return await interaction.response.send_message("Only the host can end phases.", ephemeral=True)
        
        await interaction.response.send_message(f"⏭️ Phase ended by host.", ephemeral=True)
        await self.lobby.host_end_phase(interaction.channel)
    
    @discord.ui.button(label="View Suspicion Matrix", style=discord.ButtonStyle.secondary, custom_id="view_sus_btn")
    async def view_suspicion(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Block if game is finished
        if self.lobby.status == 'finished':
            return await interaction.response.send_message(
                f"🏁 Game has ended. **{self.lobby.winner.upper()} WINS!**",
                ephemeral=True
            )
        
        player = self.lobby.players.get(interaction.user.id)
        if not player or not player.is_alive:
            return await interaction.response.send_message("You are dead.", ephemeral=True)
        
        # Show player's personal suspicion view
        embed = discord.Embed(
            title=f"🔍 Your Suspicions - {player.name}",
            description="How suspicious you find each player:",
            color=discord.Color.blurple()
        )
        
        sus_map = self.lobby.suspicion_matrix.get_all_for_observer(player.id)
        
        for target_id, sus_value in sus_map.items():
            target = self.lobby.players.get(target_id)
            if not target:
                continue
            
            # Interpretation
            if sus_value < 20:
                interpretation = "🟢 Trust"
            elif sus_value < 40:
                interpretation = "🟡 Neutral"
            elif sus_value < 70:
                interpretation = "🟠 Suspicious"
            else:
                interpretation = "🔴 Conviction"
            
            bar_filled = int(sus_value // 10)
            bar_empty = 10 - bar_filled
            sus_bar = "█" * bar_filled + "░" * bar_empty
            
            embed.add_field(
                name=f"{target.name}",
                value=f"{sus_bar} `{int(sus_value)}%` {interpretation}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TargetSelect(discord.ui.Select):
    """Select target for accuse/defend in discussion."""
    def __init__(self, lobby, user_id, action_type, options):
        super().__init__(placeholder=f"Select target to {action_type}...", min_values=1, max_values=1, options=options, custom_id=f"{action_type}_target")
        self.lobby = lobby
        self.user_id = user_id
        self.action_type = action_type
    
    async def callback(self, interaction: discord.Interaction):
        # Block if game is finished
        if self.lobby.status == 'finished':
            return await interaction.response.send_message(
                f"🏁 Game has ended. **{self.lobby.winner.upper()} WINS!**",
                ephemeral=True
            )
        
        target_idx = int(self.values[0])
        # Convert dynamic index back to player ID
        current_players = sorted(self.lobby.players.keys())
        if target_idx >= len(current_players):
            return await interaction.response.send_message("❌ Target no longer in game.", ephemeral=True)
        
        target_id = current_players[target_idx]
        target_player = self.lobby.players.get(target_id)
        
        if not target_player:
            return await interaction.response.send_message("❌ Target no longer in game.", ephemeral=True)
        
        # Record the accusation/defense
        action_text = "accused" if self.action_type == 'accuse' else "defended"
        self.lobby.discussion_events.append((self.lobby.round, self.user_id, self.action_type, target_id))
        self.lobby.discussion_actions_completed.add(self.user_id)
        
        # Track stats
        if self.action_type == 'accuse':
            self.lobby.accusation_count[target_id] = self.lobby.accusation_count.get(target_id, 0) + 1
        elif self.action_type == 'defend':
            self.lobby.defense_count[target_id] = self.lobby.defense_count.get(target_id, 0) + 1
        
        await interaction.response.send_message(
            f"✅ You {action_text} **{target_player.name}**.",
            ephemeral=True
        )

class ActionSelect(discord.ui.Select):
    def __init__(self, lobby, options, placeholder, custom_id):
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, custom_id=custom_id)
        self.lobby = lobby

    async def callback(self, interaction: discord.Interaction):
        # Block all actions if game is finished
        if self.lobby.status == 'finished':
            return await interaction.response.send_message(
                f"🏁 Game has ended. **{self.lobby.winner.upper()} WINS!**",
                ephemeral=True
            )
        
        target_id = self.values[0]
        user_id = interaction.user.id
        player = self.lobby.players.get(user_id)
        
        if self.custom_id == "discussion_select":
            action_type = target_id
            if action_type == 'skip':
                await interaction.response.send_message(f"⏭️ You chose to skip discussion.", ephemeral=True)
                self.lobby.discussion_actions_completed.add(user_id)
            elif action_type in ['accuse', 'defend']:
                # Need to select a target
                alive_targets = [p for p in self.lobby.players.values() if p.is_alive and p.id != user_id]
                if not alive_targets:
                    return await interaction.response.send_message("No targets available.", ephemeral=True)
                
                # Create target selection menu with dynamic index lookup
                options = [discord.SelectOption(label=p.name, value=str(self.lobby.get_player_index(p.id))) for p in alive_targets if self.lobby.get_player_index(p.id) >= 0]
                view = discord.ui.View(timeout=60)
                select = TargetSelect(self.lobby, user_id, action_type, options)
                view.add_item(select)
                
                action_text = "accuse" if action_type == 'accuse' else "defend"
                await interaction.response.send_message(f"Who do you want to {action_text}?", view=view, ephemeral=True)
        
        elif self.custom_id == "vote_select":
            if target_id == 'SKIP':
                self.lobby.votes[user_id] = 'SKIP'
                target_name = 'SKIP'
            else:
                target_idx = int(target_id)
                # Convert dynamic index back to player ID
                current_players = sorted(self.lobby.players.keys())
                if target_idx >= len(current_players):
                    return await interaction.response.send_message(f"❌ Target no longer in game.", ephemeral=True)
                target_id_actual = current_players[target_idx]
                if target_id_actual not in self.lobby.players:
                    return await interaction.response.send_message(f"❌ Target no longer in game.", ephemeral=True)
                self.lobby.votes[user_id] = target_id_actual
                target_name = self.lobby.players[target_id_actual].name
                
                # Track vote stats
                self.lobby.vote_count[target_id_actual] = self.lobby.vote_count.get(target_id_actual, 0) + 1
            
            await interaction.response.send_message(f"✅ Vote cast for **{target_name}**.", ephemeral=True)
            
            # Track voting completion
            completed, required = self.lobby.get_phase_progress()
            if completed >= required:
                # All players have voted - phase can auto-advance
                pass
        
        elif self.custom_id == "night_select":
            target_idx = int(target_id)
            # Convert dynamic index back to player ID
            current_players = sorted(self.lobby.players.keys())
            if target_idx >= len(current_players):
                return await interaction.response.send_message(f"❌ Target no longer in game.", ephemeral=True)
            
            target_id_actual = current_players[target_idx]
            if target_id_actual not in self.lobby.players:
                return await interaction.response.send_message(f"❌ Target no longer in game.", ephemeral=True)
            
            self.lobby.actions[user_id] = target_id_actual
            self.lobby.actions_completed.add(user_id)
            target_player = self.lobby.players[target_id_actual]
            # Check player is still in lobby
            if not player or not player.is_alive:
                return await interaction.response.send_message("You are dead or not in the game.", ephemeral=True)
            
            # Immediate Detective Feedback (suspicion-based, not hard role confirmation)
            if player.role == 'detective':
                # Detective investigates: adjust suspicion based on role with margin of error
                target_role = target_player.role
                if target_role == 'mafia':
                    # Lower suspicion (innocent appearing), but with 30% error rate
                    base_change = -25  # Mafia looks innocent
                    if random.random() < 0.3:
                        base_change = 15  # But sometimes the investigation is wrong!
                else:
                    # Raise suspicion (appears suspicious due to role mismatch), with 20% error rate
                    base_change = -20  # Innocent appears innocent
                    if random.random() < 0.2:
                        base_change = 20  # But sometimes readings are inverted!
                
                # Apply to detective's personal suspicion
                current_sus = self.lobby.suspicion_matrix.get(user_id, target_id_actual)
                new_sus = self.lobby.clamp_suspicion(current_sus + base_change)
                self.lobby.suspicion_matrix.set(user_id, target_id_actual, new_sus)
                
                # Feedback message (shows suspicion change, not actual role)
                if base_change < -10:
                    feedback = "🟢 Seems trustworthy"
                elif base_change > 10:
                    feedback = "🔴 Seems suspicious"
                else:
                    feedback = "🟡 Unclear"
                
                await interaction.response.send_message(
                    f"🔍 Investigation of **{target_player.name}**: {feedback}",
                    ephemeral=True
                )
            else:
                action_verb = "Kill" if player.role == 'mafia' else "Save" if player.role == 'doctor' else "Investigate"
                await interaction.response.send_message(f"✅ Night action confirmed: {action_verb} **{target_player.name}**.", ephemeral=True)

# --- COMMANDS ---

@bot.tree.command(name="mafia_create", description="Create a new Mafia lobby")
async def create_lobby(interaction: discord.Interaction):
    """Create a new Mafia game lobby in this channel."""
    async with bot.lobbies_lock:
        if interaction.channel_id in bot.lobbies:
            existing_lobby = bot.lobbies[interaction.channel_id]
            # Allow creating new lobby if the existing one is finished
            if existing_lobby.status != 'finished':
                await interaction.response.send_message("❌ A lobby already exists in this channel.", ephemeral=True)
                return
            # Remove the finished lobby
            del bot.lobbies[interaction.channel_id]
        
        lobby = GameLobby(interaction.channel_id, interaction.user)
        bot.lobbies[interaction.channel_id] = lobby
    
    embed = discord.Embed(
        title="🕵️ New Mafia Lobby", 
        description=f"**Host:** {interaction.user.mention}\n\nClick **Join Game** to enter.\nMinimum 3 players to start.",
        color=discord.Color.dark_grey()
    )
    embed.set_footer(text="Created by Mafia Enhanced Bot")
    view = LobbyView(lobby)
    await interaction.response.send_message(embed=embed, view=view)
    try:
        # Save the message so we can edit the original lobby panel later
        msg = await interaction.original_response()
        lobby.last_message = msg
        # Schedule auto-start countdown (30 sec) that activates if 5+ players
        lobby.start_auto_start(bot, countdown=30)
    except:
        pass

@bot.tree.command(name="mafia_end", description="End the current game (host only)")
async def end_game(interaction: discord.Interaction):
    """End the game in this channel."""
    lobby = bot.lobbies.get(interaction.channel_id)
    if not lobby:
        await interaction.response.send_message("❌ No game in this channel.", ephemeral=True)
        return
    
    if interaction.user.id != lobby.host_id:
        await interaction.response.send_message("❌ Only the host can end the game.", ephemeral=True)
        return
    
    del bot.lobbies[interaction.channel_id]
    await interaction.response.send_message("🛑 Game ended.", ephemeral=False)

@bot.tree.command(name="mafia_add_bots", description="Add bot players for testing (host only)")
async def add_bots(interaction: discord.Interaction, count: int, mode: str = "auto"):
    """Add bots to the game. Mode: 'auto' (auto-play) or 'manual' (host controls)."""
    lobby = bot.lobbies.get(interaction.channel_id)
    if not lobby:
        await interaction.response.send_message("❌ No game in this channel.", ephemeral=True)
        return
    
    if interaction.user.id != lobby.host_id:
        await interaction.response.send_message("❌ Only the host can add bots.", ephemeral=True)
        return
    
    if count < 1 or count > 5:
        await interaction.response.send_message("❌ Please specify 1-5 bots.", ephemeral=True)
        return
    
    if mode.lower() not in ['auto', 'manual']:
        await interaction.response.send_message("❌ Mode must be 'auto' or 'manual'.", ephemeral=True)
        return
    
    success, message = lobby.add_bots(count, mode.lower())
    await interaction.response.send_message(f"{'✅' if success else '❌'} {message}", ephemeral=True)

@bot.tree.command(name="mafia_stats", description="View detailed game statistics")
async def game_stats(interaction: discord.Interaction):
    """View detailed game statistics."""
    lobby = bot.lobbies.get(interaction.channel_id)
    if not lobby:
        await interaction.response.send_message("❌ No game in this channel.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📊 Game Statistics",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="Game State",
        value=f"**Status:** {lobby.status}\n**Round:** {lobby.round}\n**Phase:** {lobby.phase.title()}",
        inline=False
    )
    
    embed.add_field(
        name="Teams",
        value=f"🕷️ **Mafia:** {lobby.mafia_count}\n🏘️ **Town:** {lobby.villager_count}\n👥 **Total:** {len(lobby.players)}",
        inline=True
    )
    
    alive_count = len([p for p in lobby.players.values() if p.is_alive])
    dead_count = len([p for p in lobby.players.values() if not p.is_alive])
    embed.add_field(
        name="Population",
        value=f"👤 **Alive:** {alive_count}\n💀 **Dead:** {dead_count}",
        inline=True
    )
    
    if lobby.status == 'finished':
        winner = "🏆 TOWN" if lobby.winner == 'villager' else "💀 MAFIA"
        embed.add_field(name="Winner", value=winner, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="mafia_help", description="Show game rules and mechanics")
async def game_help(interaction: discord.Interaction):
    """Display game rules and mechanics."""
    embed = discord.Embed(
        title="🕵️ Mafia Enhanced - Rules & Mechanics",
        color=discord.Color.gold(),
        description="A game of deception, psychology, and deduction."
    )
    
    embed.add_field(
        name="🎮 Roles",
        value="""**Villager:** Discuss and vote. Win if Mafia eliminated.
**Doctor:** Heal one player each night. Prevents kills.
**Detective:** Investigate players. Learn their true role.
**Mafia:** Eliminate villagers at night. Hidden from others.""",
        inline=False
    )
    
    embed.add_field(
        name="📋 Phases",
        value="""**Day/Discussion:** Discuss and accuse others.
**Voting:** Vote to eliminate someone.
**Night:** Special roles perform secret actions.""",
        inline=False
    )
    
    embed.add_field(
        name="🧠 Psychology Engine",
        value="""• **Suspicion Matrix:** Your personal views evolve
• **Memory Decay:** Suspicions fade over time
• **Confirmation Bias:** Your beliefs shape perception
• **Intuition Leak:** Detective knowledge spreads subconsciously
• **Rumor Mill:** Gossip influences the town""",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Winning",
        value="""**Town Wins:** Eliminate all Mafia
**Mafia Wins:** Equal or outnumber Town""",
        inline=False
    )
    
    embed.set_footer(text="Use /mafia_create to start a new game!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print('🕵️ Mafia Enhanced Bot Ready')
    print('------')

@bot.command(name="mafia_create")
async def mafia_create_prefix(ctx):
    """Create a new Mafia lobby using &mafia_create"""
    async with bot.lobbies_lock:
        if ctx.channel.id in bot.lobbies:
            existing_lobby = bot.lobbies[ctx.channel.id]
            # Allow creating new lobby if the existing one is finished
            if existing_lobby.status != 'finished':
                await ctx.send("❌ A lobby already exists in this channel.")
                return
            # Remove the finished lobby
            del bot.lobbies[ctx.channel.id]
        
        lobby = GameLobby(ctx.channel.id, ctx.author)
        bot.lobbies[ctx.channel.id] = lobby
    
    embed = discord.Embed(
        title="🕵️ New Mafia Lobby", 
        description=f"**Host:** {ctx.author.mention}\n\nClick **Join Game** to enter.\nMinimum 3 players to start.",
        color=discord.Color.dark_grey()
    )
    embed.set_footer(text="Created by Mafia Enhanced Bot")
    view = LobbyView(lobby)
    msg = await ctx.send(embed=embed, view=view)
    # Save the message so we can edit the original lobby panel later
    lobby.last_message = msg
    # Schedule auto-start countdown (30 sec) that activates if 5+ players
    lobby.start_auto_start(bot, countdown=30)

@bot.command(name="mafia_end")
async def mafia_end_prefix(ctx):
    """End the current game using &mafia_end"""
    lobby = bot.lobbies.get(ctx.channel.id)
    if not lobby:
        await ctx.send("❌ No active game in this channel.", delete_after=5)
        return
    
    if ctx.author.id != lobby.host_id:
        await ctx.send("❌ Only the host can end the game.", delete_after=5)
        return
    
    del bot.lobbies[ctx.channel.id]
    await ctx.send("🛑 Game ended.")

@bot.command(name="mafia_add_bots")
async def add_bots_prefix(ctx, count: int = 1, mode: str = "auto"):
    """Add bot players using &mafia_add_bots <count> [auto/manual]"""
    lobby = bot.lobbies.get(ctx.channel.id)
    if not lobby:
        await ctx.send("❌ No active game in this channel.", delete_after=5)
        return
    
    if ctx.author.id != lobby.host_id:
        await ctx.send("❌ Only the host can add bots.", delete_after=5)
        return
    
    if count < 1 or count > 5:
        await ctx.send("❌ Count must be between 1 and 5.", delete_after=5)
        return
    
    if mode.lower() not in ['auto', 'manual']:
        await ctx.send("❌ Mode must be 'auto' or 'manual'.", delete_after=5)
        return
    
    success, message = lobby.add_bots(count, mode.lower())
    await ctx.send(f"{'✅' if success else '❌'} {message}")

@bot.command(name="mafia_stats")
async def game_stats_prefix(ctx):
    """View game statistics using &mafia_stats"""
    lobby = bot.lobbies.get(ctx.channel.id)
    if not lobby:
        await ctx.send("❌ No active game in this channel.", delete_after=5)
        return
    
    embed = discord.Embed(
        title="📊 Game Statistics",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="Game State",
        value=f"**Status:** {lobby.status}\n**Round:** {lobby.round}\n**Phase:** {lobby.phase.title()}",
        inline=False
    )
    
    embed.add_field(
        name="Teams",
        value=f"🕷️ **Mafia:** {lobby.mafia_count}\n🏘️ **Town:** {lobby.villager_count}\n👥 **Total:** {len(lobby.players)}",
        inline=True
    )
    
    alive_count = len([p for p in lobby.players.values() if p.is_alive])
    dead_count = len([p for p in lobby.players.values() if not p.is_alive])
    embed.add_field(
        name="Population",
        value=f"👤 **Alive:** {alive_count}\n💀 **Dead:** {dead_count}",
        inline=True
    )
    
    if lobby.status == 'finished':
        embed.add_field(name="🏆 Winner", value=f"**{lobby.winner.upper()}**", inline=False)
    
    await ctx.send(embed=embed)

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN not found in .env file")
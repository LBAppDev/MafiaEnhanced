#!/usr/bin/env python3
"""Test the index-based player ID system"""
import sys
sys.path.insert(0, '/workspaces/MafiaEnhanced')

# Mock discord objects
import random
class MockUser:
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name
        self.display_name = name
        self.mention = f"<@{user_id}>"
        self.messages = []
    async def send(self, content=None, embed=None):
        # Capture DM-like messages for assertions; prefer content, else embed.description
        if content is not None:
            self.messages.append(content)
        elif embed is not None:
            # Some tests will check embed.description or embed.title
            self.messages.append(getattr(embed, 'description', '') or getattr(embed, 'title', ''))
        else:
            self.messages.append(None)
        return None

# Test the Player and GameLobby classes
from bot import Player, GameLobby

def test_index_based_ids():
    """Test index-based player lookups"""
    print("Testing index-based ID system...")
    
    # Create a mock lobby
    channel_id = 12345
    host = MockUser(99999, "TestHost")
    lobby = GameLobby(channel_id, host)
    
    # Add some human players
    user1 = MockUser(11111, "Player1")
    user2 = MockUser(22222, "Player2")
    user3 = MockUser(33333, "Player3")
    
    lobby.players[user1.id] = Player(user1)
    lobby.players[user2.id] = Player(user2)
    lobby.players[user3.id] = Player(user3)
    
    # Add bots
    success, msg = lobby.add_bots(2, 'auto')
    print(f"Bot add result: {success}, {msg}")
    
    # Start the game to initialize player_list
    success, msg = lobby.start_game()
    print(f"Game start result: {success}, {msg}")
    
    # Test player_list
    print(f"\nPlayer list (indices): {list(range(len(lobby.player_list)))}")
    print(f"Player IDs in order: {lobby.player_list}")
    
    # Test get_player_by_index
    for i in range(len(lobby.player_list)):
        player = lobby.get_player_by_index(i)
        player_id = lobby.player_list[i]
        print(f"Index {i}: {player.name} (ID: {player_id})")
    
    # Test get_player_index
    for pid in lobby.player_list:
        idx = lobby.get_player_index(pid)
        print(f"Player ID {pid} -> Index {idx}")
    
    print("\n✅ All index-based ID tests passed!")

if __name__ == "__main__":
    test_index_based_ids()


# --- Additional tests for announcements ---
import asyncio

class MockMessage:
    def __init__(self, channel, content=None, embed=None, view=None):
        self.channel = channel
        self.content = content
        self.embed = embed
        self.view = view
        self.deleted = False
    async def edit(self, content=None, embed=None, view=None):
        self.content = content or self.content
        self.embed = embed or self.embed
        self.view = view or self.view
        # Record the edit as a message text for assertions
        self.channel.messages.append((self.content if self.content is not None else (self.embed.title if self.embed else None)))
    async def delete(self):
        self.deleted = True
        # record deletion for assertions
        self.channel.messages.append("<deleted>")

class MockChannel:
    def __init__(self):
        self.messages = []
    async def send(self, content=None, embed=None, view=None):
        # Store textual content for assertions (prefer content over embed)
        self.messages.append(content if content is not None else (embed.title if embed else None))
        return MockMessage(self, content=content, embed=embed, view=view)


def test_resolve_voting_announces():
    print("Testing resolve_voting announcements...")
    random.seed(0)
    channel_id = 22222
    host = MockUser(99999, "Host")
    lobby = GameLobby(channel_id, host)

    # Add players
    u1 = MockUser(11111, "Alice")
    u2 = MockUser(22222, "Bob")
    u3 = MockUser(33333, "Charlie")
    lobby.players[u1.id] = Player(u1)
    lobby.players[u2.id] = Player(u2)
    lobby.players[u3.id] = Player(u3)

    # Set votes so Bob is executed
    lobby.votes = {u1.id: u2.id, u3.id: u2.id}

    # Ensure alive flags
    for p in lobby.players.values():
        p.is_alive = True

    ch = MockChannel()
    asyncio.run(lobby.resolve_voting(ch))

    assert any("was executed" in (m or "") for m in ch.messages), "Expected execution announcement"
    print("✅ resolve_voting announcement test passed")


def test_resolve_night_announcements_and_kicks():
    print("Testing resolve_night announcements and kicks...")
    random.seed(0)
    channel_id = 33333
    host = MockUser(99999, "Host")
    lobby = GameLobby(channel_id, host)

    # Add players and assign roles
    mafia = MockUser(44444, "Mafioso")
    doctor = MockUser(55555, "Doc")
    vill = MockUser(66666, "Townie")
    sleepy = MockUser(77777, "Sleepy")

    lobby.players[mafia.id] = Player(mafia)
    lobby.players[doctor.id] = Player(doctor)
    lobby.players[vill.id] = Player(vill)
    lobby.players[sleepy.id] = Player(sleepy)

    # Assign roles explicitly
    lobby.players[mafia.id].role = 'mafia'
    lobby.players[doctor.id].role = 'doctor'
    lobby.players[vill.id].role = 'villager'
    lobby.players[sleepy.id].role = 'detective'

    # Night actions: mafia and doctor both target Townie (save)
    lobby.actions = {mafia.id: vill.id, doctor.id: vill.id}
    lobby.actions_completed = {mafia.id, doctor.id}
    lobby.actions_required['night'] = [mafia.id, doctor.id, sleepy.id]

    ch = MockChannel()
    asyncio.run(lobby.resolve_night(ch))

    # Expect a doctor save message
    assert any("saved" in (m or "") for m in ch.messages), "Expected doctor save announcement"
    # Expect Sleepy (detective) to be kicked for not acting
    assert any("eliminated for failing to act" in (m or "") for m in ch.messages), "Expected kicked players announcement"
    print("✅ resolve_night announcements and kicks test passed")


def test_send_role_reveals_dms():
    print("Testing send_role_reveals DM behavior...")
    channel_id = 44444
    host = MockUser(99999, "Host")
    lobby = GameLobby(channel_id, host)

    # Add players
    u1 = MockUser(11111, "Alice")
    u2 = MockUser(22222, "Bob")
    lobby.players[u1.id] = Player(u1)
    lobby.players[u2.id] = Player(u2)

    # Assign roles
    lobby.players[u1.id].role = 'mafia'
    lobby.players[u2.id].role = 'villager'

    # Ensure mock users capture DMs
    asyncio.run(lobby.send_role_reveals(None))

    # Check that both users have received at least one DM
    assert len(u1.messages) >= 1, "Alice should have received a DM"
    assert len(u2.messages) >= 1, "Bob should have received a DM"
    # Verify that Alice (mafia) DM mentions role
    assert any("MAFIA" in (m or "") for m in u1.messages), "Alice DM should include role"
    print("✅ send_role_reveals DM test passed")


def test_update_view_resends_on_phase_change():
    print("Testing update_view resends panel on phase change...")
    channel = MockChannel()
    host = MockUser(99999, "Host")
    lobby = GameLobby(77777, host)

    # Create a prior message and set last_panel_phase to 'night'
    mock_msg = MockMessage(channel, content="old panel")
    lobby.last_message = mock_msg
    lobby.last_panel_phase = 'night'

    # Switch to discussion phase and call update_view
    lobby.phase = 'discussion'
    asyncio.run(lobby.update_view(channel, "Phase changed"))

    # After phase change, the channel should have received a new message and the old one deleted
    assert any("Phase changed" in (m or "") for m in channel.messages), "Expected new panel message when phase changed"
    assert any(m == "<deleted>" for m in channel.messages), "Expected previous panel to be deleted"
    print("✅ update_view resend test passed")


def test_reveal_role_button_ephemeral():
    print("Testing Reveal Role (ephemeral) button behavior...")
    channel = MockChannel()
    host = MockUser(99999, "Host")
    lobby = GameLobby(88888, host)

    # Add a player and start the game
    u1 = MockUser(11111, "Alice")
    lobby.players[u1.id] = Player(u1)
    # ensure player is alive and assigned role
    lobby.players[u1.id].is_alive = True
    lobby.players[u1.id].role = 'detective'

    # Create a GameView and invoke reveal_role_button
    view = None
    gv = None
    from bot import GameView
    gv = GameView(lobby)

    # Mock Interaction and Button
    class MockResponse:
        def __init__(self):
            self.sent = []
        async def send(self, content=None, embed=None, ephemeral=False):
            self.sent.append((content, ephemeral))
    class MockInteraction:
        def __init__(self, user):
            self.user = user
            self.response = MockResponse()

    mi = MockInteraction(u1)
    # Call the button handler directly
    asyncio.run(gv.reveal_role_button(mi, None))

    # Verify an ephemeral response was sent containing the role
    assert mi.response.sent, "Expected an ephemeral response"
    content, ephemeral_flag = mi.response.sent[0]
    assert "DETECTIVE" in content and ephemeral_flag is True, "Expected ephemeral message with role"
    print("✅ Reveal Role ephemeral button test passed")


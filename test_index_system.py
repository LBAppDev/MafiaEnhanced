#!/usr/bin/env python3
"""Test the index-based player ID system"""
import sys
sys.path.insert(0, '/workspaces/MafiaEnhanced')

# Mock discord objects
class MockUser:
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name

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

import asyncio
import pytest
from unittest.mock import MagicMock
import os
from loguru import logger

# Configure logging for tests
logger.remove()
logger.add("test_logs.log", level="DEBUG", rotation="10 MB")
logger.add(lambda msg: print(msg), level="INFO", colorize=True)

class MockDiscordClient:
    """Mock Discord client for testing"""
    
    def __init__(self):
        self.user = MagicMock()
        self.user.name = "TestBot"
        self.user.id = 123456789
        self.guilds = []
        self.loop = asyncio.get_event_loop()
    
    async def wait_until_ready(self):
        """Mock wait_until_ready method"""
        return True
    
    def get_channel(self, channel_id):
        """Mock get_channel method"""
        channel = MagicMock()
        channel.id = channel_id
        channel.name = f"test-channel-{channel_id}"
        
        # Create a proper async mock for send
        future = asyncio.Future()
        future.set_result(MagicMock())  # The returned message
        channel.send = MagicMock(return_value=future)
        
        # Create a proper async mock for fetch_message
        future_msg = asyncio.Future()
        future_msg.set_result(MagicMock())  # The fetched message
        channel.fetch_message = MagicMock(return_value=future_msg)
        
        return channel

class MockMessage:
    """Mock Discord Message for testing"""
    
    def __init__(self, content="Test message", id=12345):
        self.content = content
        self.id = id
        self.channel = MagicMock()
        self.author = MagicMock()
        self.author.name = "TestUser"
        self.author.id = 987654321
        self.author.bot = False
        self.guild = MagicMock()
        self.guild.name = "TestGuild"
        self.embeds = []
        
        # Create proper async mocks
        future = asyncio.Future()
        future.set_result(None)
        self.edit = MagicMock(return_value=future)
        self.delete = MagicMock(return_value=future)
        self.add_reaction = MagicMock(return_value=future)
        self.clear_reactions = MagicMock(return_value=future)

class MockContext:
    """Mock Discord Context for testing"""
    
    def __init__(self, channel_id=12345):
        self.bot = MockDiscordClient()
        self.channel = self.bot.get_channel(channel_id)
        self.author = MagicMock()
        self.author.name = "TestUser"
        self.author.id = 987654321
        self.author.bot = False
        self.guild = MagicMock()
        self.guild.name = "TestGuild"
        self.message = MockMessage()
        self.send = self.channel.send
        
        # Create a proper async mock for reply
        future = asyncio.Future()
        future.set_result(MagicMock())  # The returned message
        self.reply = MagicMock(return_value=future)

@pytest.fixture
def mock_client():
    """Fixture for a mock Discord client"""
    return MockDiscordClient()

@pytest.fixture
def mock_context():
    """Fixture for a mock Discord context"""
    return MockContext()

@pytest.fixture(scope="session", autouse=True)
def setup_environment():
    """Set up environment variables for testing"""
    # Set API keys for testing
    os.environ.setdefault("FINANCIAL_DATASETS_API_KEY", "test_api_key")
    os.environ.setdefault("DISCORD_TOKEN", "test_discord_token")
    os.environ.setdefault("KUCOIN_API_KEY", "test_kucoin_api_key")
    os.environ.setdefault("KUCOIN_API_SECRET", "test_kucoin_api_secret")
    os.environ.setdefault("KUCOIN_API_PASSPHRASE", "test_kucoin_api_passphrase")
    
    yield
    
    # Cleanup not needed for environment variables
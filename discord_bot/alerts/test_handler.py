"""
Test functionality for the alert system.
Provides testing utilities to verify alert notifications work correctly.
"""

import discord
from discord.ext import commands
import asyncio
from loguru import logger


class TestHandler:
    """Manage test functionality for alerts system"""
    
    def __init__(self, bot: discord.ext.commands.Bot):
        """
        Initialize the test handler.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.test_tasks = {}  # {channel_id: task}
        logger.debug("Initialized TestHandler")
    
    async def start_test(self, ctx: commands.Context) -> None:
        """Start a test to verify alert functionality"""
        logger.info(f"{ctx.author} starting alert system test")
        channel_id = ctx.channel.id
        
        # Check if a test is already running in this channel
        if channel_id in self.test_tasks and not self.test_tasks[channel_id].done():
            logger.warning(f"Test already running in channel {channel_id}")
            await ctx.send(
                "❌ A test is already running in this channel. Use `!end test` to stop it."
            )
            return
            
        await ctx.send(
            "✅ Starting alert system test. Will send a message every second. Type `!end test` to stop."
        )
        
        # Start the test task
        self.test_tasks[channel_id] = asyncio.create_task(self._run_test(ctx))
        logger.info(f"Test task started for channel {channel_id}")
    
    async def end_test(self, ctx: commands.Context) -> None:
        """End a running test"""
        logger.info(f"{ctx.author} ending alert system test")
        channel_id = ctx.channel.id
        
        if channel_id in self.test_tasks and not self.test_tasks[channel_id].done():
            self.test_tasks[channel_id].cancel()
            logger.info(f"Test task cancelled for channel {channel_id}")
            await ctx.send("✅ Alert system test stopped.")
        else:
            logger.debug(f"No test running in channel {channel_id}")
            await ctx.send("❌ No test is currently running in this channel.")
    
    async def _run_test(self, ctx: commands.Context) -> None:
        """Run the alert test, sending a message every second"""
        counter = 1
        channel_id = ctx.channel.id
        logger.debug(f"Starting test message loop for channel {channel_id}")
        
        try:
            while True:
                embed = discord.Embed(
                    title="🔔 Alert System Test",
                    description=f"This is test message #{counter}",
                    color=discord.Color.gold(),
                )
                embed.set_footer(text="Type !end test to stop this test")
                
                await ctx.send(embed=embed)
                logger.debug(f"Sent test message #{counter} to channel {channel_id}")
                counter += 1
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            # Task was cancelled by end_test command
            logger.debug(f"Test task was cancelled for channel {channel_id}")
            pass
            
        except Exception as e:
            logger.error(f"Error in test task for channel {channel_id}: {str(e)}")
            await ctx.send(f"❌ Test stopped due to error: {str(e)}")
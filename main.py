import discord
from discord import app_commands
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('auto-annoy')

# Load environment variables
load_dotenv()

# Bot initialization
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Global state variable
state = {}

# State management functions
STATE_FILE = 'state.json'
MAX_SAVE_RETRIES = 3
RETRY_DELAY = 0.5  # seconds

def load_state() -> dict:
    """Load state from state.json, return empty dict if file doesn't exist
    
    Implements Requirement 10.2 (load state on startup).
    Handles missing or corrupted state files gracefully by initializing empty state.
    """
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                # Requirement 10.1: Load state from JSON file
                data = json.load(f)
                logger.info(f"Successfully loaded state from {STATE_FILE}")
                return data
        # File doesn't exist yet (first run) - return empty state
        logger.info(f"State file {STATE_FILE} does not exist, initializing with empty state")
        return {}
    except json.JSONDecodeError as e:
        # Requirement 10.3: Handle corrupted state file by reinitializing
        logger.warning(f"State file corrupted (invalid JSON): {e}. Initializing with empty state.")
        return {}
    except IOError as e:
        logger.warning(f"Failed to read state file: {e}. Initializing with empty state.")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading state file: {e}. Initializing with empty state.")
        return {}

def save_state(state: dict) -> None:
    """Write state dictionary to state.json with proper formatting and retry logic
    
    Implements Requirement 10.3 (persist configuration changes to disk).
    Uses retry logic to handle transient file system errors.
    """
    last_error = None
    
    # Retry mechanism to handle transient file system errors
    for attempt in range(MAX_SAVE_RETRIES):
        try:
            with open(STATE_FILE, 'w') as f:
                # Requirement 10.1: Use JSON format for state storage
                json.dump(state, f, indent=2)
            logger.info(f"Successfully saved state to {STATE_FILE}")
            return
        except IOError as e:
            last_error = e
            logger.warning(f"Failed to save state file (attempt {attempt + 1}/{MAX_SAVE_RETRIES}): {e}")
            if attempt < MAX_SAVE_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error saving state file (attempt {attempt + 1}/{MAX_SAVE_RETRIES}): {e}")
            if attempt < MAX_SAVE_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    
    # If we get here, all retries failed - raise error to caller
    logger.error(f"Failed to save state after {MAX_SAVE_RETRIES} attempts: {last_error}")
    raise IOError(f"Failed to save state after {MAX_SAVE_RETRIES} attempts: {last_error}")

def get_guild_state(state: dict, guild_id: int, owner_id: int = None) -> dict:
    """Get or initialize guild state with default structure
    
    This function ensures that each guild has a properly initialized state dictionary.
    It also enforces the requirement that the server owner is always in the admin list.
    
    Args:
        state: The global state dictionary
        guild_id: The guild ID to get state for
        owner_id: The guild owner ID (required for initialization to ensure owner is always admin)
    
    Returns:
        The guild state dictionary
    """
    guild_key = str(guild_id)
    
    # Initialize new guild state if it doesn't exist
    if guild_key not in state:
        admin_ids = []
        if owner_id is not None:
            # Requirement 1.1: Server owner must always be in admin list on initialization
            admin_ids = [owner_id]
            logger.info(f"Initializing guild {guild_id} state with owner {owner_id} as admin")
        state[guild_key] = {
            "adminIDs": admin_ids,
            "targetIDs": [],
            "message": ""
        }
    else:
        # Requirement 1.3: Ensure owner is always in admin list even if state exists
        # This handles cases where state was manually edited or corrupted
        if owner_id is not None and owner_id not in state[guild_key]["adminIDs"]:
            state[guild_key]["adminIDs"].append(owner_id)
            logger.info(f"Added owner {owner_id} to admin list for guild {guild_id}")
            try:
                save_state(state)
            except IOError as e:
                logger.error(f"Failed to save state after adding owner to admin list: {e}")
    
    return state[guild_key]

def is_admin(state: dict, guild_id: int, user_id: int, owner_id: int) -> bool:
    """Check if user is admin (in list or is owner)"""
    if user_id == owner_id:
        return True
    guild_state = get_guild_state(state, guild_id, owner_id)
    return user_id in guild_state["adminIDs"]

def is_target(state: dict, guild_id: int, user_id: int, owner_id: int = None) -> bool:
    """Check if user is in target list"""
    guild_state = get_guild_state(state, guild_id, owner_id)
    return user_id in guild_state["targetIDs"]

# Confirmation manager for self-demotion
pending_confirmations = {}

def request_confirmation(guild_id: int, user_id: int) -> None:
    """Store confirmation request with current timestamp"""
    key = f"{guild_id}_{user_id}"
    pending_confirmations[key] = datetime.now().timestamp()

def check_confirmation(guild_id: int, user_id: int) -> bool:
    """Check if valid confirmation exists within 60-second window
    
    This implements the self-demotion safety mechanism (Requirement 4.4).
    Users must confirm within 60 seconds to prevent accidental privilege loss.
    """
    key = f"{guild_id}_{user_id}"
    if key not in pending_confirmations:
        return False
    
    request_time = pending_confirmations[key]
    current_time = datetime.now().timestamp()
    
    # Requirement 4.4: Check if within 60-second confirmation window
    if current_time - request_time <= 60:
        return True
    else:
        # Requirement 4.4: Discard expired confirmation requests
        del pending_confirmations[key]
        return False

def clear_confirmation(guild_id: int, user_id: int) -> None:
    """Remove confirmation request"""
    key = f"{guild_id}_{user_id}"
    if key in pending_confirmations:
        del pending_confirmations[key]

@client.event
async def on_ready():
    """Bot startup event handler
    
    Loads persistent state from disk and registers slash commands with Discord.
    This implements Requirement 10.2 (load state on startup).
    """
    global state
    # Requirement 10.2: Load existing guild configurations from state file
    state = load_state()
    logger.info(f'Logged in as {client.user}')
    
    try:
        # Sync slash commands with Discord API so they appear in the UI
        await tree.sync()
        logger.info('Commands synced successfully')
    except discord.errors.HTTPException as e:
        logger.error(f"Failed to sync commands (HTTP error): {e}")
    except Exception as e:
        logger.error(f"Failed to sync commands (unexpected error): {e}")

@client.event
async def on_message(message):
    """Message monitoring event handler for auto-reply
    
    This implements the core auto-reply functionality (Requirement 8).
    Monitors all messages and replies to target users with the configured message.
    """
    global state
    
    # Ignore bot's own messages to prevent infinite loops
    if message.author == client.user:
        return
    
    # Only process messages in guilds (not DMs)
    if not message.guild:
        return
    
    guild_id = message.guild.id
    author_id = message.author.id
    owner_id = message.guild.owner_id
    
    # Requirement 8.1: Check if message author is in target list
    if is_target(state, guild_id, author_id, owner_id):
        guild_state = get_guild_state(state, guild_id, owner_id)
        reply_message = guild_state.get("message", "")
        
        # Requirement 8.2: Only reply if a message is configured
        if reply_message:
            try:
                await message.reply(reply_message)
            except discord.errors.HTTPException as e:
                logger.error(f"Failed to send auto-reply in guild {guild_id} (HTTP error): {e}")
            except discord.errors.Forbidden as e:
                logger.error(f"Failed to send auto-reply in guild {guild_id} (missing permissions): {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending auto-reply in guild {guild_id}: {e}")
    # Requirement 8.3: Take no action if user is not in target list

# Command handlers
@tree.command(name="admin", description="Add or remove admin users")
@app_commands.describe(
    action="Choose to add or remove an admin",
    user="The user to add or remove as admin"
)
@app_commands.choices(action=[
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove")
])
async def admin_command(interaction: discord.Interaction, action: app_commands.Choice[str], user: discord.User):
    """Handle /admin command for adding/removing admins"""
    global state
    
    guild_id = interaction.guild_id
    executor_id = interaction.user.id
    owner_id = interaction.guild.owner_id
    target_user_id = user.id
    
    # Requirement 1.1, 2.1, 9.1: Only admins (or server owner) can execute commands
    if not is_admin(state, guild_id, executor_id, owner_id):
        # Requirement 9.2: Send error message for unauthorized access
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    
    guild_state = get_guild_state(state, guild_id)
    
    if action.value == "add":
        # Prevent bots from being added to admin list
        if user.bot:
            await interaction.response.send_message("Cannot add bots to the admin list.", ephemeral=True)
            return
        
        # Requirement 2.2: Check if user is already admin (prevent duplicates)
        if target_user_id in guild_state["adminIDs"] or target_user_id == owner_id:
            await interaction.response.send_message(f"User {user.mention} is already an admin.", ephemeral=True)
            return
        
        # Requirement 2.3: Add user to admin list
        guild_state["adminIDs"].append(target_user_id)
        
        try:
            save_state(state)
            # Requirement 2.4: Send confirmation message
            await interaction.response.send_message(f"Successfully added {user.mention} as an admin.", ephemeral=True)
        except IOError as e:
            logger.error(f"Failed to save state after adding admin in guild {guild_id}: {e}")
            await interaction.response.send_message("Failed to save configuration. Please try again.", ephemeral=True)
    
    elif action.value == "remove":
        # Requirement 1.2 & 3.3: Server owner cannot be removed from admin list
        if target_user_id == owner_id:
            await interaction.response.send_message("Cannot remove the server owner from admin list.", ephemeral=True)
            return
        
        # Requirement 3.2: Check if user is actually in admin list
        if target_user_id not in guild_state["adminIDs"]:
            await interaction.response.send_message(f"User {user.mention} is not an admin.", ephemeral=True)
            return
        
        # Requirement 4: Handle self-demotion with confirmation mechanism
        if target_user_id == executor_id:
            # Check if user has already requested confirmation
            if check_confirmation(guild_id, executor_id):
                # Requirement 4.3: Confirmation received within window, proceed with removal
                guild_state["adminIDs"].remove(target_user_id)
                clear_confirmation(guild_id, executor_id)
                
                try:
                    save_state(state)
                    # Requirement 4.5: Send confirmation of self-demotion
                    await interaction.response.send_message("You have been removed from the admin list.", ephemeral=True)
                except IOError as e:
                    logger.error(f"Failed to save state after self-demotion in guild {guild_id}: {e}")
                    await interaction.response.send_message("Failed to save configuration. Please try again.", ephemeral=True)
            else:
                # Requirement 4.1 & 4.2: Request confirmation for self-demotion
                request_confirmation(guild_id, executor_id)
                await interaction.response.send_message(
                    "Are you sure you want to remove yourself as admin?\nUse the command again within 60 seconds to confirm.",
                    ephemeral=True
                )
        else:
            # Requirement 3.4: Remove another admin (not self, no confirmation needed)
            guild_state["adminIDs"].remove(target_user_id)
            
            try:
                save_state(state)
                # Requirement 3.5: Send confirmation message
                await interaction.response.send_message(f"Successfully removed {user.mention} from admin list.", ephemeral=True)
            except IOError as e:
                logger.error(f"Failed to save state after removing admin in guild {guild_id}: {e}")
                await interaction.response.send_message("Failed to save configuration. Please try again.", ephemeral=True)

@tree.command(name="target", description="Add or remove target users")
@app_commands.describe(
    action="Choose to add or remove a target",
    user="The user to add or remove as target"
)
@app_commands.choices(action=[
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove")
])
async def target_command(interaction: discord.Interaction, action: app_commands.Choice[str], user: discord.User):
    """Handle /target command for adding/removing targets"""
    global state
    
    guild_id = interaction.guild_id
    executor_id = interaction.user.id
    owner_id = interaction.guild.owner_id
    target_user_id = user.id
    
    # Requirement 5.1, 6.1, 9.1: Only admins can execute target commands
    if not is_admin(state, guild_id, executor_id, owner_id):
        # Requirement 9.2: Send error message for unauthorized access
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    
    guild_state = get_guild_state(state, guild_id, owner_id)
    
    if action.value == "add":
        # Prevent bots from being added to target list
        if user.bot:
            await interaction.response.send_message("Cannot add bots to the target list.", ephemeral=True)
            return
        
        # Requirement 5.2: Check if user is already a target (prevent duplicates)
        if target_user_id in guild_state["targetIDs"]:
            await interaction.response.send_message(f"User {user.mention} is already in the target list.", ephemeral=True)
            return
        
        # Requirement 5.3: Add user to target list
        guild_state["targetIDs"].append(target_user_id)
        
        try:
            save_state(state)
            # Requirement 5.4: Send confirmation message
            await interaction.response.send_message(f"Successfully added {user.mention} to the target list.", ephemeral=True)
        except IOError as e:
            logger.error(f"Failed to save state after adding target in guild {guild_id}: {e}")
            await interaction.response.send_message("Failed to save configuration. Please try again.", ephemeral=True)
    
    elif action.value == "remove":
        # Requirement 6.2: Check if user is in target list
        if target_user_id not in guild_state["targetIDs"]:
            await interaction.response.send_message(f"User {user.mention} is not in the target list.", ephemeral=True)
            return
        
        # Requirement 6.3: Remove user from target list
        guild_state["targetIDs"].remove(target_user_id)
        
        try:
            save_state(state)
            # Requirement 6.4: Send confirmation message
            await interaction.response.send_message(f"Successfully removed {user.mention} from the target list.", ephemeral=True)
        except IOError as e:
            logger.error(f"Failed to save state after removing target in guild {guild_id}: {e}")
            await interaction.response.send_message("Failed to save configuration. Please try again.", ephemeral=True)

@tree.command(name="setmessage", description="Set the message that will be sent to target users")
@app_commands.describe(
    text="The message to send to target users"
)
async def setmessage_command(interaction: discord.Interaction, text: str):
    """Handle /setmessage command for setting the auto-reply message"""
    global state
    
    guild_id = interaction.guild_id
    executor_id = interaction.user.id
    owner_id = interaction.guild.owner_id
    
    # Requirement 7.1, 9.1: Only admins can execute setmessage command
    if not is_admin(state, guild_id, executor_id, owner_id):
        # Requirement 9.2: Send error message for unauthorized access
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    
    guild_state = get_guild_state(state, guild_id, owner_id)
    
    # Requirement 7.2: Update message field in guild state
    guild_state["message"] = text
    
    try:
        save_state(state)
        # Requirement 7.3: Send confirmation message
        await interaction.response.send_message(f"Successfully set the message to: {text}", ephemeral=True)
    except IOError as e:
        logger.error(f"Failed to save state after setting message in guild {guild_id}: {e}")
        await interaction.response.send_message("Failed to save configuration. Please try again.", ephemeral=True)

@tree.command(name="info", description="Display current bot configuration")
async def info_command(interaction: discord.Interaction):
    """Handle /info command to display current guild state
    
    This command can be used by anyone (no admin check) to view the current
    bot configuration for the server (Requirement 10.3).
    """
    global state
    
    guild_id = interaction.guild_id
    owner_id = interaction.guild.owner_id
    guild_state = get_guild_state(state, guild_id, owner_id)
    
    # Format Bot Targets section
    if guild_state["targetIDs"]:
        targets_list = [f"<@{user_id}>" for user_id in guild_state["targetIDs"]]
        targets_text = ", ".join(targets_list)
    else:
        targets_text = "None"
    
    # Format Bot Admins section
    admin_ids = set(guild_state["adminIDs"])
    admin_ids.add(owner_id)  # Always include owner
    
    if admin_ids:
        admins_list = [f"<@{user_id}>" for user_id in admin_ids]
        admins_text = ", ".join(admins_list)
    else:
        admins_text = "None"
    
    # Format Message section
    if guild_state["message"]:
        message_text = guild_state["message"]
    else:
        message_text = "No message set"
    
    # Build response
    response = f"**Bot Targets:** {targets_text}\n\n**Bot Admins:** {admins_text}\n\n**Message:** {message_text}"
    
    await interaction.response.send_message(response, ephemeral=True)

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables")
        exit(1)
    
    try:
        client.run(token)
    except discord.errors.LoginFailure as e:
        logger.error(f"Failed to login to Discord (invalid token): {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Unexpected error running bot: {e}")
        exit(1)

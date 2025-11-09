# Auto Annoy Discord Bot

A Discord bot that enables server administrators to designate target users and automatically reply to their messages with a customizable message.

## Features

- Role-based access control (Server Owner and Admins)
- Automatic message replies to designated target users
- Persistent configuration storage per server
- Slash commands for easy management
- Self-demotion protection with confirmation

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- A Discord bot token (see [Discord Developer Portal](https://discord.com/developers/applications))

### Installation

1. Clone or download this repository

2. Install required dependencies:
```bash
pip install discord.py python-dotenv
```

3. Create a `.env` file in the project root:
```bash
cp .env.example .env
```

4. Edit `.env` and add your Discord bot token:
```
DISCORD_TOKEN=your_actual_bot_token_here
```

5. Run the bot:
```bash
python main.py
```

## Discord Bot Setup

### Creating Your Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Navigate to the "Bot" section in the left sidebar
4. Click "Add Bot" to create a bot user
5. Under "Privileged Gateway Intents", enable:
   - **Server Members Intent**
   - **Message Content Intent**
6. Click "Reset Token" to generate your bot token (save this for the `.env` file)

### Inviting the Bot to Your Server

1. In the Developer Portal, go to "OAuth2" → "URL Generator"
2. Select the following scopes:
   - `bot`
   - `applications.commands`
3. Select the following bot permissions:
   - Send Messages
   - Read Message History
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

### Required Permissions

When inviting the bot to your server, ensure it has these permissions:
- **Send Messages** - Required to send auto-replies to target users
- **Read Message History** - Required to monitor messages from target users
- **Use Application Commands** - Required for slash commands to work

### Required Intents

The bot requires these intents (configured in Discord Developer Portal under Bot → Privileged Gateway Intents):
- **Server Members Intent** - Required to access guild member information
- **Message Content Intent** - Required to read message content for monitoring target users

## Commands

All commands are slash commands and require admin privileges. The server owner always has admin access by default.

### `/admin add <user>`
Add a user to the admin list, granting them permission to use bot commands.

**Parameters:**
- `action`: Select "add"
- `user`: The Discord user to add as admin

**Example:** `/admin add @JohnDoe`

**Notes:**
- Cannot add a user who is already an admin
- Server owner is always an admin by default

### `/admin remove <user>`
Remove a user from the admin list, revoking their permission to use bot commands.

**Parameters:**
- `action`: Select "remove"
- `user`: The Discord user to remove from admin list

**Example:** `/admin remove @JohnDoe`

**Notes:**
- Server owners cannot be removed from the admin list
- Self-demotion (removing yourself) requires confirmation within 60 seconds for safety
- To confirm self-demotion, run the same command again within 60 seconds

### `/target add <user>`
Add a user to the target list. The bot will automatically reply to all their messages with the configured message.

**Parameters:**
- `action`: Select "add"
- `user`: The Discord user to add to target list

**Example:** `/target add @Annoying`

**Notes:**
- Cannot add a user who is already in the target list
- A message must be set using `/setmessage` for auto-replies to work

### `/target remove <user>`
Remove a user from the target list. The bot will stop replying to their messages.

**Parameters:**
- `action`: Select "remove"
- `user`: The Discord user to remove from target list

**Example:** `/target remove @Annoying`

### `/setmessage <text>`
Set the custom message that the bot will reply with to target users.

**Parameters:**
- `text`: The message text to send (can include emojis, mentions, etc.)

**Example:** `/setmessage Stop spamming!`

**Notes:**
- The message applies to all target users in the server
- You can change the message at any time
- The message persists across bot restarts

### `/info`
Display the current bot configuration for your server.

**Example:** `/info`

**Shows:**
- List of current target users
- List of current admin users
- Currently configured auto-reply message

**Notes:**
- This command can be used by anyone (no admin privileges required)
- Useful for checking current bot settings

## Configuration Storage

Bot configuration is stored in `state.json` (created automatically on first run). This file persists all settings across bot restarts.

### State File Structure

```json
{
  "123456789012345678": {
    "adminIDs": [111111111111111111, 222222222222222222],
    "targetIDs": [333333333333333333, 444444444444444444],
    "message": "Custom reply message"
  },
  "987654321098765432": {
    "adminIDs": [555555555555555555],
    "targetIDs": [],
    "message": ""
  }
}
```

### Field Descriptions

- **Guild ID (key)**: The Discord server ID (as a string)
- **adminIDs**: Array of user IDs who have admin privileges (can use bot commands)
- **targetIDs**: Array of user IDs who will receive auto-replies
- **message**: The text message that will be sent as auto-reply to target users

### Important Notes

- Each Discord server (guild) has its own independent configuration
- The server owner is always treated as an admin, even if not in the `adminIDs` list
- User IDs are Discord snowflake IDs (18-19 digit numbers)
- The state file is automatically created and updated by the bot
- Manual editing is possible but not recommended (use bot commands instead)
- If the file becomes corrupted, the bot will reinitialize with an empty state

## Troubleshooting

### Bot doesn't respond to commands
- Ensure the bot has "Use Application Commands" permission
- Verify the bot is online and connected
- Check that commands have been synced (should happen automatically on startup)

### "Permission denied" errors
- Only server owners and users in the admin list can use commands
- Server owner always has admin access by default

### Bot doesn't reply to target users
- Ensure a message has been set using `/setmessage`
- Verify the user is in the target list
- Check that the bot has "Send Messages" permission in the channel

## License

This project is provided as-is for educational and personal use.

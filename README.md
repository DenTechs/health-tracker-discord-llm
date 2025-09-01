# Health Tracker Discord Bot

A Discord bot that uses AI to analyze food images, estimate calories, and track your daily nutrition intake.

## Features

- **Image Analysis**: Upload food photos to get calorie estimates
- **Text Input**: Describe food items for calorie tracking
- **Personal Database**: Individual tracking per user
- **Daily/Total Tracking**: View calories for specific dates or all-time totals
- **Channel Permissions**: Configurable access control

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy the example environment file:
```bash
cp example.env .env
```

3. Configure your `.env` file:
```
BOT_API_KEY=your_discord_bot_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ALLOWED_CHANNELS={"channel_id": ["user_id1", "user_id2"]}
OVERRIDE_USERS=[]
```

4. Run the bot:
```bash
python bot.py
```

## Usage

- **Track Food**: Send a photo of your meal or describe what you ate
- **View Daily Calories**: The bot will show your daily intake
- **Get Totals**: Ask for your total calories across all days

## Configuration

- `ALLOWED_CHANNELS`: JSON object mapping channel IDs to allowed user IDs
- `OVERRIDE_USERS`: Array of user IDs that can use the bot in any channel
- Set `null` for a channel's user list to allow all users in that channel

## Files

- `bot.py` - Main Discord bot code
- `config.py` - System prompt and configuration
- `tools.py` - Database functions for health tracking
- `tools.json` - Tool definitions for the AI

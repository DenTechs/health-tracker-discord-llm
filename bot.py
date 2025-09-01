import discord
import os
import json
import base64
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
import logging
import config
import tools
from PIL import Image
import io
load_dotenv()

BOT_API_KEY = os.getenv("BOT_API_KEY")
AI_API_KEY = os.getenv("AI_API_KEY")

# Load and convert ALLOWED_CHANNELS to have integer user IDs
allowed_channels_raw = json.loads(os.getenv("ALLOWED_CHANNELS", "{}"))
ALLOWED_CHANNELS = {}
for channel_id, user_list in allowed_channels_raw.items():
    if user_list is not None:
        ALLOWED_CHANNELS[channel_id] = [int(user_id) for user_id in user_list]
    else:
        ALLOWED_CHANNELS[channel_id] = None

OVERRIDE_USERS = [int(user_id) for user_id in json.loads(os.getenv("OVERRIDE_USERS", "[]"))]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

with open("tools.json") as file:
    TOOLS = json.load(file)

claudeClient = AsyncAnthropic(
    api_key = os.getenv("ANTHROPIC_API_KEY")
)

# Dictionary to store conversation histories per user
user_histories = {}

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)

async def execute_tool(tool_name, tool_input, user_id):
    try:
        if hasattr(tools, tool_name):
            tool_function = getattr(tools, tool_name)
            result = tool_function(tool_input, user_id)
            logger.info(f"Got result from tool: {result}")
            return result
        else:
            logger.warning("Requested function not found in tools.py")
            return "Requested tool not found"
    except Exception as e:
        logger.error(f"Error calling tool: {e}")
        return f"Error calling tool: {e}"
    
async def send_to_ai(conversationToBot: list, message_to_edit: discord.Message, user_id: int) -> str:
    try:
         while True:
            claudeResponse = await claudeClient.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                # thinking={
                #     "type": "enabled",
                #     "budget_tokens": 1024
                # },
                system=[{"type": "text",
                        "text": config.SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"}}],
                messages=conversationToBot,
                tools=TOOLS
            )

            #print(claudeResponse)

            if claudeResponse.stop_reason == "tool_use":
                logger.info("Detected tool call(s)")
                await message_to_edit.edit(content="Processing tool calls")
                conversationToBot.append({"role": "assistant", "content": claudeResponse.content})

                tool_content = []
                for content in claudeResponse.content:
                    logger.debug(f"Found content: {content.type}")
                    if content.type != "tool_use":
                        logger.debug(f"not tool, skipping")
                        continue
                    logger.info(f"Found tool: {content.name}")
                    tool_result = await execute_tool(content.name, content.input, user_id)
                    tool_content.append({"type": "tool_result",
                                         "tool_use_id": content.id,
                                         "content": tool_result})

                conversationToBot.append({"role": "user",
                                          "content": tool_content})

            else:
                # No tool calls, send final message
                for content in claudeResponse.content:
                    if content.type == "text":
                        final_text = content.text
                logger.info(f"Generated: \n{final_text}")
                await message_to_edit.edit(content=final_text)
                # Append assistant's response to history
                conversationToBot.append({"role": "assistant", "content": claudeResponse.content})
                return final_text

    except Exception as e:
        logger.error(f"Error: {e}")
        await message_to_edit.edit(content=f"Error: {e}")

async def handle_chat_request(conversation_history: list, newUserMessage: discord.Message, message_to_edit: discord.Message, user_id: int):
    logger.info(f"Received message '{newUserMessage.content}'")

    try:
        if newUserMessage.attachments:
            for attachment in newUserMessage.attachments:
                if "image" in attachment.content_type:
                    logger.info("Found image attachment in message")
                    image_data = await attachment.read()
                    image = Image.open(io.BytesIO(image_data))

                    # Check if image is larger than 800x800 pixels and resize if needed
                    width, height = image.size
                    if width > 800 or height > 800:
                        logger.info(f"Image size {width}x{height} exceeds 800x800, resizing...")
                        # Calculate new dimensions while maintaining aspect ratio
                        if width > height:
                            new_width = 800
                            new_height = int((height * 800) / width)
                        else:
                            new_height = 800
                            new_width = int((width * 800) / height)

                        # Resize the image
                        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        logger.info(f"Image resized to {new_width}x{new_height}")

                    image_media_type = attachment.content_type

                    # Convert PIL Image to bytes
                    img_byte_arr = io.BytesIO()

                    # Handle different image modes for JPEG compatibility
                    if image.mode in ('RGBA', 'LA', 'P'):
                        # Convert to RGB for JPEG compatibility
                        if image.mode == 'P':
                            # Convert palette mode to RGB
                            image = image.convert('RGB')
                        elif image.mode in ('RGBA', 'LA'):
                            # Convert RGBA/LA to RGB with white background
                            background = Image.new('RGB', image.size, (255, 255, 255))
                            if image.mode == 'RGBA':
                                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                            else:  # LA mode
                                background.paste(image.convert('RGB'), mask=image.split()[-1])
                            image = background

                    # Save as JPEG (now safe since we've converted problematic modes)
                    image.save(img_byte_arr, format='JPEG', quality=85)
                    img_byte_arr = img_byte_arr.getvalue()

                    # Encode to base64 string
                    image_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

                    user_content = {"role": "user",
                                    "content": [
                                        {
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": "image/jpeg",
                                                "data": image_base64
                                            }
                                        },
                                        {
                                            "type": "text",
                                            "text": f"{newUserMessage.content} "
                                        }
                                    ]}

        else:
            user_content = {"role": "user", "content": newUserMessage.content}

    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        user_content = {"role": "user", "content": newUserMessage.content}

    conversation_history.append(user_content)

    await send_to_ai(conversation_history, message_to_edit, user_id)


@client.event
async def on_message(message: discord.Message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Check if message is in allowed channels or from override users
    channel_id = str(message.channel.id)
    user_id_check = message.author.id
    
    logger.info(f"Message from user {user_id_check} in channel {channel_id}")
    logger.debug(f"Allowed channels: {ALLOWED_CHANNELS}")
    logger.debug(f"Override users: {OVERRIDE_USERS}")
    
    # Check if user is in override list (bypasses all channel restrictions)
    if user_id_check in OVERRIDE_USERS:
        logger.debug(f"User {user_id_check} is in override list, processing message")
    else:
        # Check if channel is allowed
        if channel_id not in ALLOWED_CHANNELS:
            logger.debug(f"Channel {channel_id} not in allowed channels, ignoring message")
            return
        
        # If channel has user restrictions, check them
        allowed_users = ALLOWED_CHANNELS[channel_id]
        if allowed_users is not None and user_id_check not in allowed_users:
            logger.debug(f"User {user_id_check} not in allowed users {allowed_users} for channel {channel_id}, ignoring message")
            return
        
        logger.info(f"Message from user {user_id_check} in channel {channel_id} passed filtering, processing")

    user_id = message.author.id

    # Determine if this is a reply to the bot's message
    is_reply_to_bot = False
    if message.reference and message.reference.resolved:
        if message.reference.resolved.author == client.user:
            is_reply_to_bot = True

    # Initialize or reset history
    if user_id not in user_histories or not is_reply_to_bot:
        user_histories[user_id] = []

    # Send initial "Bot is thinking" message
    thinking_message = await message.channel.send("Bot is thinking")

    # Process the message
    await handle_chat_request(user_histories[user_id], message, thinking_message, user_id)

    # After processing, append the assistant's response to history
    # This is done in send_to_ai when editing the message
    
client.run(BOT_API_KEY)

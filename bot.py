import discord
from discord import app_commands
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
ALLOWED_CHANNELS = os.getenv("ALLOWED_CHANNELS")
OVERRIDE_USERS = os.getenv("OVERRIDE_USERS")
ALLOWED_CHANNELS = json.loads(os.getenv("ALLOWED_CHANNELS"))
OVERRIDE_USERS = json.loads(os.getenv("OVERRIDE_USERS"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

with open("tools.json") as file:
    TOOLS = json.load(file)

claudeClient = AsyncAnthropic(
    api_key = os.getenv("ANTHROPIC_API_KEY")
)

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # Sync commands globally for user installs to work in DMs
        # DO NOT SYNC THE SAME COMMAND GLOBALLY AND COPIED TO A GUILD
        await self.tree.sync()

intents = discord.Intents.default()
client = MyClient(intents=intents)

def channel_check(interaction: discord.Interaction) -> bool:
    if interaction.channel_id in ALLOWED_CHANNELS or interaction.user.id in OVERRIDE_USERS:
        return True
    else:
        return False
    
async def execute_tool(tool_name, tool_input):
    try:
        if hasattr(tools, tool_name):
            tool_function = getattr(tools, tool_name)
            result = tool_function(tool_input)
            logger.info(f"Got result from tool: {result}")
            return result
        else:
            logger.warning("Requested function not found in tools.py")
            return "Requested tool not found"
    except Exception as e:
        logger.error(f"Error calling tool: {e}")
        return f"Error calling tool: {e}"
    
async def send_to_ai(conversationToBot: list, interaction: discord.Interaction) -> str:
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
                conversationToBot.append({"role": "assistant", "content": claudeResponse.content})

                tool_content = []
                for content in claudeResponse.content:
                    logger.debug(f"Found content: {content.type}")
                    if content.type != "tool_use":
                        logger.debug(f"not tool, skipping")
                        continue
                    logger.info(f"Found tool: {content.name}")
                    tool_result = await execute_tool(content.name, content.input)
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
                return final_text
            
    except Exception as e:
        logger.error(f"Error: {e}")

async def handle_chat_request(interaction: discord.Interaction, newUserMessage: discord.message, continueConversation = False) -> str:
    logger.info(f"Received message '{newUserMessage.content}'")

    conversationToBot = []
    try:
        if newUserMessage.attachments:
            for attachment in newUserMessage.attachments:
                if "image" in attachment.content_type:
                    logger.info("Found image attchment in message")
                    image_data = await attachment.read()
                    image = Image.open(io.BytesIO(image_data))
                    
                    # Check if image is larger than 1000x1000 pixels and resize if needed
                    width, height = image.size
                    if width > 1000 or height > 1000:
                        logger.info(f"Image size {width}x{height} exceeds 1000x1000, resizing...")
                        # Calculate new dimensions while maintaining aspect ratio
                        if width > height:
                            new_width = 1000
                            new_height = int((height * 1000) / width)
                        else:
                            new_height = 1000
                            new_width = int((width * 1000) / height)
                        
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

                    conversationToBot.append({"role": "user",
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
                                            ]})
                    
        else:
            conversationToBot.append({"role": "user", "content": newUserMessage.content})

    except Exception as e:
        logger.error(f"Failed to process image: {e}")

                
                

    reply = await send_to_ai(conversationToBot, interaction)

    return reply


@client.tree.context_menu(name="Ask JD Tracker")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.check(channel_check)
async def ask_jd(interaction: discord.Interaction, message: discord.Message):
    logger.info(f"User {interaction.user.name} used Ask JD Tracker")
    # Defer the response to prevent timeout during processing
    await interaction.response.defer()

    reply = await handle_chat_request(interaction=interaction, newUserMessage=message, continueConversation=False)
    
    # Send the reply back to Discord
    await interaction.followup.send(reply)

@ask_jd.error
async def ask_denbot_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        logger.info(f"User {interaction.user.name} tried to ask JD Tracker but did not have permission.")
        await interaction.response.send_message("You do not have permission to use this.", ephemeral=True)
    else:
        # Handle other errors or re-raise
        raise error
    
client.run(BOT_API_KEY)

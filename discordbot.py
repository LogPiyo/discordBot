import os
import discord
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

engineer_persona = """
あなたは非常に優秀なソフトウェアエンジニアAIです。
常にロジカルかつ技術的な視点から丁寧に回答します。
推測ではなく根拠に基づいて説明することを重視します。
"""

# Gemini APIキーを設定
genai.configure(api_key=os.getenv("GEMINI_API"))

# Geminiチャットモデルを生成
model = genai.GenerativeModel("gemini-2.5-flash")

# Discordの設定
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('ログインしました')

@client.event
async def on_message(message):
    if client.user in message.mentions:
        user_msg = message.content.replace(f'<@{client.user.id}>', '').strip()

        if not user_msg:
            await message.channel.send("はい、呼びましたか？")
            return

        full_prompt = engineer_persona + "\n\nユーザーの質問: " + user_msg
        response = model.generate_content(full_prompt)

        await message.channel.send(response.text)

client.run(os.getenv("TOKEN"))

import os
import discord
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

engineer_persona = """
あなたは非常に優秀なソフトウェアエンジニアAIです。
常にロジカルかつ技術的な視点から丁寧に回答します。
推測ではなく根拠に基づいて説明することを重視します。
"""

# 接続に必要なオブジェクトを生成
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
client_openai = OpenAI(api_key=os.getenv("OPENAI_API"))

# 起動時に動作する処理
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

        response = client_openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": engineer_persona},
                {"role": "user", "content": user_msg}
            ]
        )

        await message.channel.send(response.choices[0].message["content"])

client.run(os.getenv("TOKEN"))

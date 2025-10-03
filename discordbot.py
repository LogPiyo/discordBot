import discord
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

engineer_persona = """
あなたは優秀なソフトウェアエンジニアAIです。
過去のやり取りを参照し、文脈を理解した上で回答します。
"""
genai.configure(api_key=os.getenv("GEMINI_API"))
model = genai.GenerativeModel("gemini-2.5-flash")
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 履歴管理用辞書 (チャンネルID -> 履歴リスト)
conversation_history = {}

@client.event
async def on_ready():
    print("ログインしました")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if client.user in message.mentions:
        channel_id = message.channel.id
        user_msg = message.content.replace(f"<@{client.user.id}>", "").strip()
        if not user_msg:
            await message.channel.send("はい、呼びましたか？")
            return

        # 履歴初期化
        if channel_id not in conversation_history:
            conversation_history[channel_id] = []

        # 履歴にユーザーメッセージを追加
        conversation_history[channel_id].append(f"ユーザー: {user_msg}")

        # 過去の履歴をまとめてプロンプトにする
        full_prompt = engineer_persona + "\n\n" + "\n".join(conversation_history[channel_id])

        response = model.generate_content(full_prompt)

        bot_reply = response.text
        await message.channel.send(bot_reply)

        # 履歴にBot返答を追加
        conversation_history[channel_id].append(f"AI: {bot_reply}")

client.run(os.getenv("TOKEN"))# GEMINI_API key has been added to .env and code updated to use Gemini API instead of OpenAI.
# engineer.py
import os
import time
import random
import asyncio
import discord
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEN_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("ENGINEER_TOKEN")

# API key validation
if not GEN_API_KEY:
    print("Warning: GEMINI_API_KEY not found in environment variables")
else:
    print("GEMINI_API_KEY loaded successfully")

genai.configure(api_key=GEN_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- Persona ---
PERSONA_PROMPT = """あなたは「エンジニアさん」です。@EngineerBotというメンションは，あなた宛てのものです。若年層のCS専攻卒で、敬語で話します。
常に冷静かつ論理的で、技術的な根拠に基づいて説明します。
とにかく新しい技術が好きなアーリーアダプターであり、時々ブリティッシュジョークを軽く混ぜます。
他メンバーを尊重しつつ、技術的に誤りがあれば訂正してください。"""

# --- memory & rate-limits ---
conversation_log = {}  # channel_id -> list of {role, content, ts}
last_autoreply = {}    # channel_id -> timestamp of last auto msg
autoreply_counts = {}  # channel_id -> list of timestamps (for windowed limit)

AUTOREPLY_COOLDOWN = 20      # seconds between autonomous replies per channel
AUTOREPLY_WINDOW = 60        # seconds window for counting
AUTOREPLY_MAX_IN_WINDOW = 3  # max autonomous replies per window
MENTION_RESPONSE = True

# --- utils ---
def add_log(channel_id, role, content):
    conversation_log.setdefault(channel_id, []).append({"role": role, "content": content, "ts": time.time()})
    # keep last 50 entries
    if len(conversation_log[channel_id]) > 50:
        conversation_log[channel_id] = conversation_log[channel_id][-50:]

def can_autoreply(channel_id):
    now = time.time()
    last = last_autoreply.get(channel_id, 0)
    if now - last < AUTOREPLY_COOLDOWN:
        return False
    # window count
    ts_list = [t for t in autoreply_counts.get(channel_id, []) if now - t <= AUTOREPLY_WINDOW]
    if len(ts_list) >= AUTOREPLY_MAX_IN_WINDOW:
        return False
    return True

def record_autoreply(channel_id):
    now = time.time()
    last_autoreply[channel_id] = now
    autoreply_counts.setdefault(channel_id, []).append(now)

def build_prompt(persona_prompt, channel_id, user_text, speaker_name="エンジニアさん"):
    # include recent history (last 12)
    hist = conversation_log.get(channel_id, [])[-12:]
    prompt = persona_prompt + "\n\n会話履歴（古い順）:\n"
    for h in hist:
        role = h["role"]
        content = h["content"]
        prompt += f"{role}: {content}\n"
    prompt += f"\n新しいユーザー発言: {user_text}\n\n{speaker_name}として敬語で、論理的に返答してください。"
    prompt += "\n※必要なら短く箇条書きで結論を示してください。ユーモアは本筋に関係ある範囲で軽く。"
    return prompt

def generate(persona_prompt, channel_id, user_text, speaker_name="エンジニアさん"):
    try:
        prompt = build_prompt(persona_prompt, channel_id, user_text, speaker_name)
        resp = model.generate_content(prompt)
        
        if not resp:
            raise Exception("No response from Gemini API")
        
        if not hasattr(resp, 'text') or not resp.text:
            raise Exception("Empty text response from Gemini API")
        
        return resp.text.strip()
        
    except Exception as e:
        error_msg = f"Error in generate function: {type(e).__name__}: {str(e)}"
        print(error_msg)
        
        # APIキー関連のエラーを特別に処理
        if "API_KEY" in str(e).upper() or "AUTHENTICATION" in str(e).upper():
            raise Exception("API認証エラー: APIキーを確認してください")
        elif "QUOTA" in str(e).upper() or "LIMIT" in str(e).upper():
            raise Exception("API使用量制限エラー: 制限を確認してください")
        elif "MODEL" in str(e).upper():
            raise Exception("モデルエラー: モデル名を確認してください")
        else:
            raise Exception(f"API呼び出しエラー: {str(e)}")

@client.event
async def on_ready():
    print("Engineer bot ready")

async def setup_hook():
    # バックグラウンドタスクを開始
    client.loop.create_task(periodic_initiator())

# setup_hookを設定
client.setup_hook = setup_hook

@client.event
async def on_message(message):
    if message.author.bot:
        return

    channel_id = message.channel.id
    content = message.content
    add_log(channel_id, "ユーザー", content)

    # If mentioned explicitly -> respond
    if client.user in message.mentions:
        try:
            reply = generate(PERSONA_PROMPT, channel_id, content, "エンジニアさん")
            add_log(channel_id, "エンジニアさん", reply)
            await message.channel.send(f"**[エンジニアさん]** {reply}")
        except Exception as e:
            error_details = str(e)
            print(f"Error in engineer bot: {type(e).__name__}: {e}")
            
            # ユーザーフレンドリーなエラーメッセージ
            if "API認証エラー" in error_details:
                await message.channel.send("申し訳ありません。API認証に問題があります。管理者にお知らせください。")
            elif "使用量制限" in error_details:
                await message.channel.send("申し訳ありません。現在API使用量制限に達しています。しばらくお待ちください。")
            elif "モデルエラー" in error_details:
                await message.channel.send("申し訳ありません。AIモデルの設定に問題があります。管理者にお知らせください。")
            else:
                await message.channel.send(f"申し訳ありません。返答中にエラーが発生しました。({error_details[:50]}...)")
        return

    # Otherwise consider autonomous response
    # base probability
    base_prob = 0.30
    # increase probability if other bots recently spoke
    recent = conversation_log.get(channel_id, [])[-6:]
    other_bot_spoke = any(h["role"] != "ユーザー" for h in recent)
    if other_bot_spoke:
        base_prob += 0.25

    if random.random() < base_prob and can_autoreply(channel_id):
        try:
            reply = generate(PERSONA_PROMPT, channel_id, content, "エンジニアさん")
            add_log(channel_id, "エンジニアさん", reply)
            record_autoreply(channel_id)
            await message.channel.send(f"**[エンジニアさん]** {reply}")
        except Exception as e:
            # quietly ignore / or log
            print(f"Error in engineer auto-reply: {type(e).__name__}: {e}")

# optional background autonomous behaviour (start when bot ready)
async def periodic_initiator():
    await client.wait_until_ready()
    while not client.is_closed():
        # every 30-45s try to start a discussion in channels the bot can see
        await asyncio.sleep(30 + random.random() * 15)
        for guild in client.guilds:
            for channel in guild.text_channels:
                try:
                    # check basic permissions
                    if not channel.permissions_for(guild.me).send_messages:
                        continue
                    chid = channel.id
                    # small chance to initiate
                    if random.random() < 0.05 and can_autoreply(chid):
                        seed = "少し技術的な観点から議論を始めてよいですか？"
                        reply = generate(PERSONA_PROMPT, chid, seed, "エンジニアさん")
                        add_log(chid, "エンジニアさん", reply)
                        record_autoreply(chid)
                        await channel.send(f"**[エンジニアさん]** {reply}")
                except Exception:
                    pass

client.run(DISCORD_TOKEN)

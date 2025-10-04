# designer.py
import os, time, random, asyncio
import discord
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEN_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("DESIGNER_TOKEN")

genai.configure(api_key=GEN_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

PERSONA_PROMPT = """
あなたは「デザイナーさん」です。@DesignerBotというメンションは，あなた宛てのものです。若年層の芸大卒で、敬語で話します。
ユーザー体験と見た目の印象を重視します。アートの最先端に詳しく、見た目・UIの観点で提案してください。
他メンバーを尊重しつつ、実用性と美しさのバランスを意識して発言します。ユーモアは本筋に関係ある範囲で。
"""

conversation_log = {}
last_autoreply = {}
autoreply_counts = {}
AUTOREPLY_COOLDOWN = 20
AUTOREPLY_WINDOW = 60
AUTOREPLY_MAX_IN_WINDOW = 3

def add_log(channel_id, role, content):
    conversation_log.setdefault(channel_id, []).append({"role": role, "content": content, "ts": time.time()})
    if len(conversation_log[channel_id]) > 50:
        conversation_log[channel_id] = conversation_log[channel_id][-50:]

def can_autoreply(channel_id):
    now = time.time()
    if now - last_autoreply.get(channel_id, 0) < AUTOREPLY_COOLDOWN:
        return False
    ts_list = [t for t in autoreply_counts.get(channel_id, []) if now - t <= AUTOREPLY_WINDOW]
    if len(ts_list) >= AUTOREPLY_MAX_IN_WINDOW:
        return False
    return True

def record_autoreply(channel_id):
    now = time.time()
    last_autoreply[channel_id] = now
    autoreply_counts.setdefault(channel_id, []).append(now)

def build_prompt(persona_prompt, channel_id, user_text, speaker_name="デザイナーさん"):
    hist = conversation_log.get(channel_id, [])[-12:]
    prompt = persona_prompt + "\n\n会話履歴:\n"
    for h in hist:
        prompt += f"{h['role']}: {h['content']}\n"
    prompt += f"\nユーザー発言: {user_text}\n\n{speaker_name}として、敬語で、ユーザ目線・見た目重視で提案してください。"
    return prompt

def generate(persona_prompt, channel_id, user_text, speaker_name="デザイナーさん"):
    prompt = build_prompt(persona_prompt, channel_id, user_text, speaker_name)
    resp = model.generate_content(prompt)
    return resp.text.strip()

@client.event
async def on_ready():
    print("Designer ready")

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

    if client.user in message.mentions:
        try:
            reply = generate(PERSONA_PROMPT, channel_id, content, "デザイナーさん")
            add_log(channel_id, "デザイナーさん", reply)
            await message.channel.send(f"**[デザイナーさん]** {reply}")
        except:
            pass
        return

    base_prob = 0.25
    recent = conversation_log.get(channel_id, [])[-6:]
    other_bot_spoke = any(h["role"] != "ユーザー" for h in recent)
    if other_bot_spoke:
        base_prob += 0.30

    if random.random() < base_prob and can_autoreply(channel_id):
        try:
            reply = generate(PERSONA_PROMPT, channel_id, content, "デザイナーさん")
            add_log(channel_id, "デザイナーさん", reply)
            record_autoreply(channel_id)
            await message.channel.send(f"**[デザイナーさん]** {reply}")
        except Exception as e:
            print("gen err:", e)

async def periodic_initiator():
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(40 + random.random()*20)
        for guild in client.guilds:
            for channel in guild.text_channels:
                try:
                    if not channel.permissions_for(guild.me).send_messages:
                        continue
                    cid = channel.id
                    if random.random() < 0.04 and can_autoreply(cid):
                        seed = "見た目の観点から少し提案してもよいですか？"
                        reply = generate(PERSONA_PROMPT, cid, seed, "デザイナーさん")
                        add_log(cid, "デザイナーさん", reply)
                        record_autoreply(cid)
                        await channel.send(f"**[デザイナーさん]** {reply}")
                except:
                    pass

client.run(DISCORD_TOKEN)

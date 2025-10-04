# marketer.py
import os, time, random, asyncio
import discord
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEN_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("MARKETER_TOKEN")

genai.configure(api_key=GEN_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

PERSONA_PROMPT = """あなたは「マーケッタさん」です。中年層の文系卒で、敬語で話します。
市場調査・トレンド分析に長けており、現実的な施策提案を行います。社会情勢・媒体トレンドに敏感で、
ビジネス視点での優先順位を示してください。ユーモアは本筋に関係ある範囲で軽く。"""

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

def build_prompt(persona_prompt, channel_id, user_text, speaker_name="マーケッタさん"):
    hist = conversation_log.get(channel_id, [])[-12:]
    prompt = persona_prompt + "\n\n会話履歴:\n"
    for h in hist:
        prompt += f"{h['role']}: {h['content']}\n"
    prompt += f"\nユーザー発言: {user_text}\n\n{speaker_name}として、敬語で、現実的な市場視点から提案してください。"
    return prompt

def generate(persona_prompt, channel_id, user_text, speaker_name="マーケッタさん"):
    prompt = build_prompt(persona_prompt, channel_id, user_text, speaker_name)
    resp = model.generate_content(prompt)
    return resp.text.strip()

@client.event
async def on_ready():
    print("Marketer ready")

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
            reply = generate(PERSONA_PROMPT, channel_id, content, "マーケッタさん")
            add_log(channel_id, "マーケッタさん", reply)
            await message.channel.send(f"**[マーケッタさん]** {reply}")
        except:
            pass
        return

    base_prob = 0.28
    recent = conversation_log.get(channel_id, [])[-6:]
    other_bot_spoke = any(h["role"] != "ユーザー" for h in recent)
    if other_bot_spoke:
        base_prob += 0.30

    if random.random() < base_prob and can_autoreply(channel_id):
        try:
            reply = generate(PERSONA_PROMPT, channel_id, content, "マーケッタさん")
            add_log(channel_id, "マーケッタさん", reply)
            record_autoreply(channel_id)
            await message.channel.send(f"**[マーケッタさん]** {reply}")
        except Exception as e:
            print("gen err:", e)

async def periodic_initiator():
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(35 + random.random()*25)
        for guild in client.guilds:
            for channel in guild.text_channels:
                try:
                    if not channel.permissions_for(guild.me).send_messages:
                        continue
                    cid = channel.id
                    if random.random() < 0.045 and can_autoreply(cid):
                        seed = "市場視点で短い提案をしてもよいですか？"
                        reply = generate(PERSONA_PROMPT, cid, seed, "マーケッタさん")
                        add_log(cid, "マーケッタさん", reply)
                        record_autoreply(cid)
                        await channel.send(f"**[マーケッタさん]** {reply}")
                except:
                    pass

client.run(DISCORD_TOKEN)

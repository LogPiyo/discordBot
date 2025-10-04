# thinker.py
import os, time, random, asyncio
import discord
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEN_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("THINKER_TOKEN")

genai.configure(api_key=GEN_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

PERSONA_PROMPT = """あなたは「老人さん」です。哲学と数学（論理学）を専門とする高齢者で、敬語で話します。
抽象的かつ普遍的な観点から議論し、根本的な問いを投げかけてください。ユーモアは本筋に関係ある範囲で。"""

conversation_log = {}
last_autoreply = {}
autoreply_counts = {}
AUTOREPLY_COOLDOWN = 30   # 老人さんは少し控えめなクールダウン
AUTOREPLY_WINDOW = 120
AUTOREPLY_MAX_IN_WINDOW = 4

def add_log(channel_id, role, content):
    conversation_log.setdefault(channel_id, []).append({"role": role, "content": content, "ts": time.time()})
    if len(conversation_log[channel_id]) > 60:
        conversation_log[channel_id] = conversation_log[channel_id][-60:]

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

def build_prompt(persona_prompt, channel_id, user_text, speaker_name="老人さん"):
    hist = conversation_log.get(channel_id, [])[-20:]
    prompt = persona_prompt + "\n\n会話履歴:\n"
    for h in hist:
        prompt += f"{h['role']}: {h['content']}\n"
    prompt += f"\nユーザー発言: {user_text}\n\n{speaker_name}として、敬語で抽象的・本質的な観点から問いや洞察を述べてください。"
    return prompt

def generate(persona_prompt, channel_id, user_text, speaker_name="老人さん"):
    prompt = build_prompt(persona_prompt, channel_id, user_text, speaker_name)
    resp = model.generate_content(prompt)
    return resp.text.strip()

@client.event
async def on_ready():
    print("Thinker ready")

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
            reply = generate(PERSONA_PROMPT, channel_id, content, "老人さん")
            add_log(channel_id, "老人さん", reply)
            await message.channel.send(f"**[老人さん]** {reply}")
        except:
            pass
        return

    base_prob = 0.18
    recent = conversation_log.get(channel_id, [])[-8:]
    other_bot_spoke = any(h["role"] != "ユーザー" for h in recent)
    if other_bot_spoke:
        base_prob += 0.35

    if random.random() < base_prob and can_autoreply(channel_id):
        try:
            reply = generate(PERSONA_PROMPT, channel_id, content, "老人さん")
            add_log(channel_id, "老人さん", reply)
            record_autoreply(channel_id)
            await message.channel.send(f"**[老人さん]** {reply}")
        except Exception as e:
            print("gen err:", e)

async def periodic_initiator():
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(60 + random.random()*60)
        for guild in client.guilds:
            for channel in guild.text_channels:
                try:
                    if not channel.permissions_for(guild.me).send_messages:
                        continue
                    cid = channel.id
                    if random.random() < 0.03 and can_autoreply(cid):
                        seed = "少し本質的な問いを投げかけてもよろしいでしょうか？"
                        reply = generate(PERSONA_PROMPT, cid, seed, "老人さん")
                        add_log(cid, "老人さん", reply)
                        record_autoreply(cid)
                        await channel.send(f"**[老人さん]** {reply}")
                except:
                    pass

client.run(DISCORD_TOKEN)

import os
import json
import requests
import random
import math
from datetime import datetime

# --- 配置區（建議從環境變數讀取） ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
THREADS_TOKEN = os.getenv("THREADS_TOKEN")
# 你的 Threads 用戶 ID，可透過 API 獲取，或在發文失敗後的 error 中查看
THREADS_USER_ID = os.getenv("THREADS_USER_ID") 

SIGNS = [
    "牡羊座", "金牛座", "雙子座", "巨蟹座", "獅子座", "處女座",
    "天秤座", "天蠍座", "射手座", "摩羯座", "水瓶座", "雙魚座"
]

def get_gemini_content(sign, date_str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={GEMINI_API_KEY}"
    prompt = f"你是專業占星師。請為今天（{date_str}）的{sign}撰寫一份運勢。要求：1. 描述 (description)：精煉 2-3 句，約 80-120 字。口吻自然療癒。2. 提醒 (advice)：一句 30 字內短評。回傳 JSON。"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "description": {"type": "string"},
                    "advice": {"type": "string"}
                },
                "required": ["description", "advice"]
            }
        }
    }
    
    response = requests.post(url, json=payload)
    return response.json()['candidates'][0]['content']['parts'][0]['text']

def generate_scores(sign, date_str):
    # 模擬前端的隨機種子邏輯
    seed = hash(sign + date_str)
    random.seed(seed)
    
    def get_bar(score):
        filled = round(score / 10)
        return "▓" * filled + "░" * (10 - filled)

    scores = {
        "total": random.randint(65, 98),
        "love": random.randint(60, 95),
        "work": random.randint(60, 95),
        "money": random.randint(55, 95),
        "health": random.randint(65, 95)
    }
    
    colors = ["琥珀金", "午夜藍", "玫瑰粉", "森林綠", "薰衣草紫", "象牙白", "冷霧灰", "寶石紅", "珍珠白", "炭木黑"]
    lucky_color = random.choice(colors)
    lucky_num = random.randint(1, 99)
    
    score_text = (
        f"🔮 綜合運 [{get_bar(scores['total'])}] {scores['total']}\n"
        f"💕 愛情運 [{get_bar(scores['love'])}] {scores['love']}\n"
        f"💼 事業運 [{get_bar(scores['work'])}] {scores['work']}\n"
        f"💰 財　運 [{get_bar(scores['money'])}] {scores['money']}\n"
        f"🌿 健康運 [{get_bar(scores['health'])}] {scores['health']}"
    )
    
    return score_text, lucky_color, lucky_num

def post_to_threads(content):
    # 1. 創建媒體容器 (Threads API 流程)
    post_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    params = {
        "media_type": "TEXT",
        "text": content,
        "access_token": THREADS_TOKEN
    }
    res = requests.post(post_url, params=params)
    container_id = res.json().get("id")
    
    if container_id:
        # 2. 發布容器
        publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
        publish_params = {
            "creation_id": container_id,
            "access_token": THREADS_TOKEN
        }
        requests.post(publish_url, publish_params)
        print("發布成功！")

def main():
    date_str = datetime.now().strftime("%Y/%m/%d")
    # 每天隨機選一個星座發布，或循環發布
    sign = random.choice(SIGNS) 
    
    ai_json = json.loads(get_gemini_content(sign, date_str))
    score_text, color, num = generate_scores(sign, date_str)
    
    # 按照你的要求排序：Title, Description, 指數, 提醒, 幸運, Hashtags
    full_text = (
        f"✦ {date_str} {sign}運勢 ✦\n\n"
        f"{ai_json['description']}\n\n"
        f"{score_text}\n\n"
        f"💡 今日提醒：{ai_json['advice']}\n"
        f"🍀 幸運加持：{color}・{num}\n\n"
        f"#星座運勢 #OmniAstro #星軌觀測所 #{sign}"
    )
    
    print(f"準備發布內容：\n{full_text}")
    post_to_threads(full_text)

if __name__ == "__main__":
    main()

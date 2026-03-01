import os
import json
import requests
import random
import re
from datetime import datetime

# --- 配置區 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
THREADS_TOKEN = os.getenv("THREADS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID") 

SIGNS = ["牡羊座", "金牛座", "雙子座", "巨蟹座", "獅子座", "處女座", "天秤座", "天蠍座", "射手座", "摩羯座", "水瓶座", "雙魚座"]

def get_gemini_content(sign, date_str):
    print(f"正在向 Gemini 請求 {sign} 的深度運勢內容...")
    # 切換回 v1beta 路徑，這對 gemini-1.5-flash 的支援最為穩定
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        f"你是專業占星師。請為今日（{date_str}）的{sign}撰寫一份詳細且具療癒感的運勢。\n"
        f"要求：\n"
        f"1. 描述 (description)：請撰寫約 50-120 字的內容。包含今日的整體星象氛圍、情緒起伏建議，以及具體的行動指引。語氣要溫暖且專業。\n"
        f"2. 提醒 (advice)：一句 30 字內的靈魂短評或行動金句。\n"
        f"請務必回傳純 JSON 格式，範例：\n"
        f"{{\"description\": \"今日星象顯示...\", \"advice\": \"在繁忙中找尋安靜的角落...\"}}\n"
        f"注意：絕對不要輸出任何 markdown 標籤（如 ```json）或額外的開場白。"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = requests.post(url, json=payload)
    res_data = response.json()
    
    if "error" in res_data:
        raise Exception(f"Gemini API 報錯: {res_data['error']['message']}")

    if "candidates" not in res_data:
        raise Exception(f"API 回傳異常: {json.dumps(res_data)}")
    
    raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
    
    # 清理並解析 JSON
    try:
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            raise ValueError("回傳內容不包含有效的 JSON 結構")
    except Exception as e:
        print(f"解析失敗，原始文字：{raw_text}")
        raise e

def generate_scores(sign, date_str):
    seed = sum(ord(c) for c in (sign + date_str))
    random.seed(seed)
    
    def get_bar(score): 
        filled = round(score / 10)
        return "▓" * filled + "░" * (10 - filled)
    
    scores = {k: random.randint(68, 98) for k in ["total", "love", "work", "money", "health"]}
    colors = ["琥珀金", "午夜藍", "玫瑰粉", "森林綠", "薰衣草紫", "象牙白", "冷霧灰", "寶石紅", "珍珠白", "炭木黑", "深靛青", "古銅金"]
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
    if not THREADS_USER_ID or not THREADS_USER_ID.isdigit():
        print(f"❌ 錯誤：THREADS_USER_ID ({THREADS_USER_ID}) 格式不正確。請確保它是純數字 ID。")
        return

    print(f"📡 準備發布貼文至 Threads (ID: {THREADS_USER_ID})")
    
    container_url = f"[https://graph.threads.net/v1.0/](https://graph.threads.net/v1.0/){THREADS_USER_ID}/threads"
    res = requests.post(container_url, params={
        "media_type": "TEXT",
        "text": content,
        "access_token": THREADS_TOKEN
    })
    
    res_data = res.json()
    if "id" not in res_data:
        print(f"❌ 建立容器失敗：{json.dumps(res_data, indent=2, ensure_ascii=False)}")
        return

    container_id = res_data["id"]
    publish_url = f"[https://graph.threads.net/v1.0/](https://graph.threads.net/v1.0/){THREADS_USER_ID}/threads_publish"
    pub_res = requests.post(publish_url, params={
        "creation_id": container_id,
        "access_token": THREADS_TOKEN
    })
    
    if pub_res.status_code == 200:
        print("🎉 深度運勢貼文已成功發布到 Threads！")
    else:
        print(f"❌ 發布失敗：{pub_res.text}")

def main():
    if not all([GEMINI_API_KEY, THREADS_TOKEN, THREADS_USER_ID]):
        print("❌ 錯誤：GitHub Secrets 設定不完整。")
        return

    date_str = datetime.now().strftime("%Y/%m/%d")
    sign = random.choice(SIGNS)
    
    try:
        ai_data = get_gemini_content(sign, date_str)
        score_text, color, num = generate_scores(sign, date_str)
        
        # 組合內容
        full_text = (
            f"✦ {date_str} {sign}運勢 ✦\n\n"
            f"{ai_data['description']}\n\n"
            f"{score_text}\n\n"
            f"💡 今日提醒：{ai_data['advice']}\n"
            f"🍀 幸運加持：{color}・{num}\n\n"
            f"#星座運勢 #OmniAstro #星軌觀測所 #{sign}"
        )
        
        post_to_threads(full_text)
        
    except Exception as e:
        print(f"💥 程式運行失敗：{e}")

if __name__ == "__main__":
    main()

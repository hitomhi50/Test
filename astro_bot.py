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
    print(f"正在向 Gemini 請求 {sign} 的運勢內容...")
    # 使用最穩定的 v1 正式版路徑
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        f"你是專業占星師。請為今日（{date_str}）的{sign}撰寫一份運勢。\n"
        f"要求：\n"
        f"1. 描述 (description)：精煉 2-3 句，約 60-100 字。\n"
        f"2. 提醒 (advice)：一句 30 字內短評。\n"
        f"請務必回傳純 JSON 格式，格式如下：\n"
        f"{{\"description\": \"內容...\", \"advice\": \"短評...\"}}\n"
        f"注意：不要輸出任何 markdown 標籤或額外解釋文字。"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = requests.post(url, json=payload)
    res_data = response.json()
    
    if "error" in res_data:
        raise Exception(f"Gemini API 報錯: {res_data['error']['message']}")

    if "candidates" not in res_data:
        raise Exception(f"API 回傳異常，找不到內容: {json.dumps(res_data)}")
    
    raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
    
    # 強力清理邏輯：只提取第一個 { 到最後一個 } 之間的內容
    try:
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        else:
            raise ValueError("無法在 AI 回傳中找到 JSON 結構")
    except Exception as e:
        print(f"解析內容失敗，原始文字：{raw_text}")
        raise e

def generate_scores(sign, date_str):
    # 使用日期和星座作為隨機推薦碼，確保同一天同一星座結果一致
    seed = sum(ord(c) for c in (sign + date_str))
    random.seed(seed)
    
    def get_bar(score): 
        filled = round(score / 10)
        return "▓" * filled + "░" * (10 - filled)
    
    scores = {k: random.randint(65, 98) for k in ["total", "love", "work", "money", "health"]}
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
    if not THREADS_USER_ID or not THREADS_USER_ID.isdigit():
        print(f"❌ 錯誤：THREADS_USER_ID ({THREADS_USER_ID}) 必須是純數字。請至 ID Finder 重新查詢。")
        return

    print(f"📡 正在發布至 Threads (ID: {THREADS_USER_ID})...")
    
    # 步驟 1：建立媒體容器
    container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    res = requests.post(container_url, params={
        "media_type": "TEXT",
        "text": content,
        "access_token": THREADS_TOKEN
    })
    
    res_data = res.json()
    if "id" not in res_data:
        print(f"❌ 建立容器失敗：{json.dumps(res_data, indent=2, ensure_ascii=False)}")
        return

    # 步驟 2：正式發布
    container_id = res_data["id"]
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    pub_res = requests.post(publish_url, params={
        "creation_id": container_id,
        "access_token": THREADS_TOKEN
    })
    
    if pub_res.status_code == 200:
        print("🎉 恭喜！今日運勢已成功發布到 Threads！")
    else:
        print(f"❌ 最後發布失敗：{pub_res.text}")

def main():
    if not all([GEMINI_API_KEY, THREADS_TOKEN, THREADS_USER_ID]):
        print("❌ 錯誤：GitHub Secrets (API KEY/TOKEN/ID) 尚未設定。")
        return

    date_str = datetime.now().strftime("%Y/%m/%d")
    sign = random.choice(SIGNS)
    
    try:
        # 獲取 AI 內容 (現在直接回傳 dict)
        ai_data = get_gemini_content(sign, date_str)
        
        # 產生指數與幸運物
        score_text, color, num = generate_scores(sign, date_str)
        
        # 組合最終文案
        full_text = (
            f"✦ {date_str} {sign}運勢 ✦\n\n"
            f"{ai_data['description']}\n\n"
            f"{score_text}\n\n"
            f"💡 今日提醒：{ai_data['advice']}\n"
            f"🍀 幸運加持：{color}・{num}\n\n"
            f"#星座運勢 #OmniAstro #星軌觀測所 #{sign}"
        )
        
        # 發布
        post_to_threads(full_text)
        
    except Exception as e:
        print(f"💥 程式運行中斷：{e}")

if __name__ == "__main__":
    main()

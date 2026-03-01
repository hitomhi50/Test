import os
import json
import requests
import random
from datetime import datetime

# --- 配置區 ---
# 這些變數會從 GitHub Actions 的 Secrets 自動讀取
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
THREADS_TOKEN = os.getenv("THREADS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID") 

SIGNS = ["牡羊座", "金牛座", "雙子座", "巨蟹座", "獅子座", "處女座", "天秤座", "天蠍座", "射手座", "摩羯座", "水瓶座", "雙魚座"]

def get_gemini_content(sign, date_str):
    print(f"正在向 Gemini 請求 {sign} 的運勢內容...")
    # 使用穩定版模型
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"你是專業占星師。請為今日（{date_str}）的{sign}撰寫一份運勢。要求：1. 描述 (description)：精煉 2-3 句。2. 提醒 (advice)：一句 30 字內短評。請務必回傳純 JSON 格式。"
    
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
    res_data = response.json()
    
    # 診斷 API 錯誤
    if "error" in res_data:
        raise Exception(f"Gemini API 報錯: {res_data['error']['message']}")
    
    if "candidates" not in res_data:
        raise Exception(f"API 回傳格式異常。完整回應: {json.dumps(res_data)}")
        
    return res_data['candidates'][0]['content']['parts'][0]['text']

def generate_scores(sign, date_str):
    # 使用固定種子確保同天結果一致
    seed = sum(ord(c) for c in (sign + date_str))
    random.seed(seed)
    
    def get_bar(score): 
        filled = round(score / 10)
        return "▓" * filled + "░" * (10 - filled)
    
    scores = {k: random.randint(65, 98) for k in ["total", "love", "work", "money", "health"]}
    colors = ["琥珀金", "午夜藍", "玫瑰粉", "森林綠", "薰衣草紫", "象牙白", "冷霧灰", "寶石紅", "珍珠白", "炭木黑"]
    lucky_color = random.choice(colors)
    lucky_num = random.randint(1, 99)
    
    # 格式化運勢指數
    score_text = (
        f"🔮 綜合運 [{get_bar(scores['total'])}] {scores['total']}\n"
        f"💕 愛情運 [{get_bar(scores['love'])}] {scores['love']}\n"
        f"💼 事業運 [{get_bar(scores['work'])}] {scores['work']}\n"
        f"💰 財　運 [{get_bar(scores['money'])}] {scores['money']}\n"
        f"🌿 健康運 [{get_bar(scores['health'])}] {scores['health']}"
    )
    return score_text, lucky_color, lucky_num

def post_to_threads(content):
    if not THREADS_USER_ID or THREADS_USER_ID == "123":
        print("警告：THREADS_USER_ID 設定不正確，目前僅進行內容模擬。")
        print(f"待發布內容：\n{content}")
        return

    print(f"正在發布至 Threads (User ID: {THREADS_USER_ID})...")
    
    # 第一步：建立媒體容器
    container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    res = requests.post(container_url, params={
        "media_type": "TEXT",
        "text": content,
        "access_token": THREADS_TOKEN
    })
    
    res_data = res.json()
    if "id" not in res_data:
        print(f"容器建立失敗：{json.dumps(res_data, indent=2, ensure_ascii=False)}")
        return

    # 第二步：正式發布
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    pub_res = requests.post(publish_url, params={
        "creation_id": res_data["id"],
        "access_token": THREADS_TOKEN
    })
    
    if pub_res.status_code == 200:
        print("✅ 成功發布到 Threads！")
    else:
        print(f"❌ 發布失敗：{pub_res.text}")

def main():
    if not GEMINI_API_KEY:
        print("錯誤：找不到 GEMINI_API_KEY。")
        return

    date_str = datetime.now().strftime("%Y/%m/%d")
    sign = random.choice(SIGNS)
    
    try:
        raw_ai = get_gemini_content(sign, date_str)
        ai_json = json.loads(raw_ai)
        score_text, color, num = generate_scores(sign, date_str)
        
        # 依照指定順序組合：Title, Description, 指數, 提醒, 幸運, Hashtags
        full_text = (
            f"✦ {date_str} {sign}運勢 ✦\n\n"
            f"{ai_json['description']}\n\n"
            f"{score_text}\n\n"
            f"💡 今日提醒：{ai_json['advice']}\n"
            f"🍀 幸運加持：{color}・{num}\n\n"
            f"#星座運勢 #OmniAstro #星軌觀測所 #{sign}"
        )
        
        post_to_threads(full_text)
        
    except Exception as e:
        print(f"執行失敗：{e}")

if __name__ == "__main__":
    main()

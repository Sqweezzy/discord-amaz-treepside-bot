from datetime import datetime, timezone, timedelta
from sqlalchemy import text

import aiohttp
import requests
import time
import json 
from decouple import config

from db import database

ACCESS_TOKEN = config("VK_ACCESS_TOKEN")
API_VERSION = "5.199"
GROUP_DOMAIN = "criminalrussia"
POLL_INTERVAL = 15
STORAGE_FILE = "last_post_id.json"

COUNT = 3

first_run = True

if first_run:
    COUNT = 15

def validate_text(text: str) -> str:
    for i in ('[vk.com/criminalrussia|', ']', '[club174935492|'):
        while i in text:
            print('i ------', i)
            text = text.replace(i, '')
            print(text)
    return text

def get_video(videos_id):
    url = "https://api.vk.com/method/video.get"
    params = {
        "domain": GROUP_DOMAIN if not GROUP_DOMAIN.lstrip("-").isdigit() else None,
        "videos": videos_id,
        "access_token": ACCESS_TOKEN,
        "v": API_VERSION,
    }
    params = {k: v for k, v in params.items() if v is not None}
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"VK API error: {data['error']}")

    files = data["response"]["items"][0]['files']
    for quality in ("mp4_720", "mp4_480", "mp4_360", "mp4_240"):
        if quality in files:
            return files[quality]
    return None

def get_wall_posts(count):
    url = "https://api.vk.com/method/wall.get"
    params = {
        "domain": GROUP_DOMAIN if not GROUP_DOMAIN.lstrip("-").isdigit() else None,
        "owner_id": GROUP_DOMAIN if GROUP_DOMAIN.lstrip("-").isdigit() else None,
        "count": count,
        "access_token": ACCESS_TOKEN,
        "v": API_VERSION,
    }
    params = {k: v for k, v in params.items() if v is not None}
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"VK API error: {data['error']}")

    return data["response"]["items"]

def get_all_photos(post: dict):
    photos = []
    attachments = post['attachments']
    if attachments:
        for i in attachments:
            if 'photo' in i.keys():
                photos.append(i['photo']['sizes'][-1])
    return photos

async def download_file(url: str) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://vk.com/"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=False) as resp:
            resp.raise_for_status()
            return await resp.read()

def handle_new_post(post):
    mes_text = []
    date_utc = datetime.fromtimestamp(post.get('date'), tz=timezone.utc)
    date_utc = date_utc + timedelta(hours=3)
    formatted_date = date_utc.strftime('%d.%m.%Y %H:%M')
    print("=" * 50)
    print(f"Новый пост ID {post['id']} от {formatted_date} по МСК")
    first_part = f"Пост от {formatted_date} по МСК"
    text = post.get("text", "Анлучка")
    print('валидация текста')
    second_part = validate_text(text)
    print('получение всех фоток')
    photos = get_all_photos(post)
    third_part = photos
    print('получение типа поста')
    type_att = post['attachments'][0]['type']
    if photos:
        for i in photos:
            print(f"Фото: {i}")
    for i in (first_part, second_part, third_part):
        print(i)
        mes_text.append(i)
    if type_att == 'clip':
        mes_text.append(f'videoid;{post['owner_id']}_{post['attachments'][0]['clip']['id']}')
    else:
        mes_text.append('video_none')
        
    return mes_text


def fetch_new_vk_post():
    last_id = database.get_last_id()
    print("Мониторинг запущен. Последний известный ID:", last_id)

    try:
        new_posts = get_wall_posts(count=COUNT)
    except Exception as e:
        print("Ошибка запроса:", e)
        return None
        
    
    if not new_posts:
        return None
    
    lposts = []
    
    for i in new_posts:
        if i['type'] == 'ads':
            continue
        lposts.append(i)

    ready_to_post = []

    if last_id is None:
        last_id = lposts[-1]["id"]
        database.save_last_id(last_id)
        ready_to_post.append(lposts[-1])
        handle_new_post(lposts[-1])
        # print('array:!!!!!!!!!!!!!!!!!!!!!!!!!', handle_new_post(lposts[-1]))
        
        
    for i in new_posts[::-1]:
        if last_id < i['id']:
            ready_to_post.append(i)
            last_id = i['id']
            database.save_last_id(last_id)

    post_to_discord = []
    
    for post in ready_to_post:
        handle_new_post(post)
        post_to_discord.append(handle_new_post(post))
        # print('array:!!!!!!!!!!!!!!!!!!!!!!!!!', handle_new_post(post))
    if post_to_discord:
        print("Новые посты готовы к отправке в Discord:", post_to_discord)
        return post_to_discord
        # time.sleep(POLL_INTERVAL)
    
# if __name__ == "__main__":
    
#     # posts = get_wall_posts(2)
    
#     # with open(STORAGE_FILE, "w") as f:
#     #     for i in posts:
#     #         # json.dump({f"post{i}": i}, f)
    #         # f.write('\n')
    #         print(i['id'])
    # main()
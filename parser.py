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
FIRST_RUN = True
COUNT = 3

if FIRST_RUN:
    COUNT = 15

class VKAuthErrorCust(Exception):
    """Токен VK истёк или невалиден."""
    pass


def _check_vk_error(data: dict):
    if "error" in data:
        error_code = data["error"].get("error_code")
        error_msg = data["error"].get("error_msg", "")
        if error_code == 5:  # User authorization failed
            raise VKAuthErrorCust(f"VK токен не авторизован: {error_msg}")
        raise RuntimeError(f"VK API error: {data['error']}")

def validate_date(date):
    date_utc = datetime.fromtimestamp(date, tz=timezone.utc)
    date_utc = date_utc + timedelta(hours=3)
    formatted_date = date_utc.strftime('%d.%m.%Y %H:%M')
    return formatted_date

def get_post_type(post):
    attachments = post['attachments']
    type_set = set()
    for i in attachments:
        type_set.add(i['type'])
    return type_set
        
def validate_text(text: str) -> str:
    for i in ('[vk.com/criminalrussia|', ']', '[club174935492|'):
        while i in text:
            # print('i ------', i)
            text = text.replace(i, '')
            # print(text)
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

    _check_vk_error(data)

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

    _check_vk_error(data)

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


def handle_new_post(post) -> dict:
    posts_array = dict()
    raw_date = post.get('date')
    validated_date = validate_date(raw_date)

    raw_text = post.get("text", "Анлучка")
    
    print("=" * 50)
    print(f"Новый пост ID {post['id']} от {validated_date} по МСК")
    
    header = f"Пост от {validated_date} по МСК"
    description = validate_text(raw_text)
    
    posts_array.update({'header': header})
    posts_array.update({'description': description})

    post_type = get_post_type(post)
    print(post_type)
    
    files = dict()
    
    if 'video' in post_type:
        print('упал в видео')
        raw_url_video = f'videoid;{post['owner_id']}_{post['id']}'
        files.update({'video': raw_url_video})
        print('добавил видео в файлы')
    if 'clip' in post_type:
        print('упал в клип')
        raw_url_clip = f'clipid;{post['owner_id']}_{post['id']}'
        files.update({'clip': raw_url_clip})
        print('добавил клип в файлы')
    if 'photo' in post_type:
        print('упал в фото')
        photos = get_all_photos(post)
        files.update({'photo': photos})
        print('добавил фото в файлы')
    posts_array.update({'files': files})

    return posts_array

def fetch_new_vk_post():
    last_id = database.get_last_id()
    if last_id is not None:
        last_id = int(last_id)
    print("Мониторинг запущен. Последний известный ID:", last_id)
    
    queue_posts = []
    ready_to_post = []
    post_to_discord = []

    try:
        new_posts = get_wall_posts(count=3)
    except VKAuthErrorCust:
        raise
    except Exception as e:
        print("Ошибка запроса:", e)
        time.sleep(POLL_INTERVAL)
        
    if not new_posts:
        return None
    
    for post in new_posts:
        if post['type'] == 'ads':
            continue
        queue_posts.append(post)

    if last_id is None:
        last_id = queue_posts[-1]["id"]
        database.save_last_id(last_id)
        ready_to_post.append(queue_posts[-1])
        handle_new_post(queue_posts[-1])
        
    for post in new_posts[::-1]:
        if last_id < post['id']:
            ready_to_post.append(post)
            last_id = post['id']
            database.save_last_id(last_id)

    for post in ready_to_post:
        post_to_discord.append(handle_new_post(post))
    if post_to_discord:
        return post_to_discord
    else:
        return None
    
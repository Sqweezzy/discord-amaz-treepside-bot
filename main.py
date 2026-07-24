import asyncio
import io
import time
from datetime import datetime, timezone

import disnake
from disnake.ext import tasks
from disnake.ext import commands
from decouple import config

from db import database
from parser import VKAuthErrorCust, download_file, fetch_new_vk_post, get_video, FIRST_RUN

bot = commands.Bot(command_prefix="*", help_command=None, intents=disnake.Intents.all())

RESET_DB = False

start_time = time.time()

@bot.event
async def on_ready():
    CHANNEL_INFO = bot.get_channel(1530229217034375218)
    if RESET_DB:
        database.drop_models()
        database.create_models()
    if CHANNEL_INFO:
        await CHANNEL_INFO.send('Бот запустился')
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    check_external_source.start()
    periodic_status_report.start()
    


def build_status_embed():
    uptime_seconds = int(time.time() - start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}ч {minutes}м {seconds}с"

    is_running = check_external_source.is_running()
    is_failed = check_external_source.failed() if hasattr(check_external_source, 'failed') else "неизвестно"
    current_loop = check_external_source.current_loop
    next_iteration = check_external_source.next_iteration

    if next_iteration:
        next_iter_str = next_iteration.astimezone().strftime('%d.%m.%Y %H:%M:%S')
        seconds_left = int((next_iteration - datetime.now(timezone.utc)).total_seconds())
    else:
        next_iter_str = "не запущена"
        seconds_left = None

    try:
        last_id = database.get_last_id()
    except Exception as e:
        last_id = f"ошибка: {e}"

    embed = disnake.Embed(title="Статус бота", color=disnake.Color.green() if is_running else disnake.Color.red())
    embed.add_field(name="Бот онлайн", value="✅ Да", inline=True)
    embed.add_field(name="Аптайм", value=uptime_str, inline=True)
    embed.add_field(name="Пинг", value=f"{round(bot.latency * 1000)} мс", inline=True)
    embed.add_field(name="Задача мониторинга запущена", value="✅ Да" if is_running else "❌ Нет", inline=True)
    embed.add_field(name="Задача упала с ошибкой", value=str(is_failed), inline=True)
    embed.add_field(name="Итераций выполнено", value=str(current_loop), inline=True)
    embed.add_field(name="Следующий запуск", value=f"{next_iter_str}" + (f" (через {seconds_left} сек)" if seconds_left else ""), inline=False)
    embed.add_field(name="Последний post_id в БД", value=str(last_id), inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    return embed

@bot.command()
async def get_info(ctx):
    await ctx.send(embed=build_status_embed())


@tasks.loop(minutes=60)  # раз в час, поставьте свой интервал
async def periodic_status_report():
    CHANNEL_INFO = bot.get_channel(1530229217034375218)
    if CHANNEL_INFO:
        await CHANNEL_INFO.send(embed=build_status_embed())

@tasks.loop(seconds=1800)
async def check_external_source():
    
    MAIN_CHANNEL = bot.get_channel(1526972461877428276)
    CHANNEL_INFO = bot.get_channel(1530229217034375218)
    
    try:
        new_posts_data = await asyncio.to_thread(fetch_new_vk_post)
    except VKAuthErrorCust as e:
        if CHANNEL_INFO:
            await CHANNEL_INFO.send(f"🔴 **VK токен истёк/невалиден!**\n```{e}```\nОбнови `VK_ACCESS_TOKEN` в `.env` и перезапусти бота.")
        print(f"[FATAL] VK auth error: {e}")
        return
    except Exception as e:
        if CHANNEL_INFO:
            await CHANNEL_INFO.send(f"⚠️ Ошибка в цикле мониторинга: `{e}`")
        print(f"Ошибка в цикле check_external_source: {e}")
        return
    
    if not new_posts_data:
        return

    
    if not MAIN_CHANNEL:
        print("Канал не найден! Проверьте ID или права бота.")
        return

    print('начинается цикл отправки постов в дискорд')
    
    for post in new_posts_data:
        
        print(f"Обрабатывается пост {post['header']}")

        header = post['header']
        description = post['description']
        files = [] # то что будем отправлять в дискорд / резервированная переменная для файлов
        post_files = post['files'] # все файлы что мы получили из поста (видео, клипы, фото)
    
        video = post_files['video'] if 'video' in post_files else None
        clip = post_files['clip'] if 'clip' in post_files else None
        photos = post_files['photo'] if 'photo' in post_files else None
        
        embed = disnake.Embed(title=header, description=description, color=disnake.Color.blue())
        
        if video:
            # print('упал в видео')
            video_id = video.split(';')[1]
            # video_url = get_video(video_id)
            # video_bytes = await download_file(video_url)
            # if len(video_bytes) <= 25 * 1024 * 1024:  # лимит Discord на размер файла
            #     buffer = io.BytesIO(video_bytes)
            #     video_file = disnake.File(buffer, filename="video.mp4")
            #     files.append(video_file)
            #     print('добавил видео в файлы')
            embed = disnake.Embed(title=header, description=f'ВИДЕО, СМОТРЕТЬ В ВК | URL - https://vk.ru/wall{video_id}', color=disnake.Color.blue())
        if clip:
            # print('упал в клип')
            clip_id = clip.split(';')[1]
            # clip_url = get_video(clip_id)
            # clip_bytes = await download_file(clip_url)
            # if len(clip_bytes) <= 25 * 1024 * 1024:  # лимит Discord на размер файла
            #     buffer = io.BytesIO(clip_bytes)
            #     clip_file = disnake.File(buffer, filename="clip.mp4")
            #     files.append(clip_file)
            #     print('добавил клип в файлы')
            embed = disnake.Embed(title=header, description=f'ВИДЕО, СМОТРЕТЬ В ВК | URL - https://vk.ru/wall{clip_id}', color=disnake.Color.blue())
        if photos:
            print('упал в фото')
            for photo in photos:
                photo_bytes = await download_file(photo['url'])
                buffer = io.BytesIO(photo_bytes)
                photo_file = disnake.File(buffer, filename="photo.jpg")
                files.append(photo_file)
                print('добавил фото в файлы')
    
        if files:
            await MAIN_CHANNEL.send(embed=embed, files=files)
        else:
            await MAIN_CHANNEL.send(embed=embed)
    
    
@check_external_source.error
async def check_external_source_error(error):
    CHANNEL_INFO = bot.get_channel(1530229217034375218)
    if CHANNEL_INFO:
        await CHANNEL_INFO.send(f'tasks.loop упал: {error}')
    print(f"[FATAL] tasks.loop упал: {error}")
    if not check_external_source.is_running():
        if CHANNEL_INFO:
            await CHANNEL_INFO.send('Попытка рестарта')
        try:
            check_external_source.restart()
            if CHANNEL_INFO:
                await CHANNEL_INFO.send('Цикл перезапущен успешно')
        except Exception as e:
            if CHANNEL_INFO:
                await CHANNEL_INFO.send('Попытка провалена')
    

bot.run(config("DISCORD_TOKEN"))

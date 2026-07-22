import asyncio
import io

import disnake
from disnake.ext import tasks
from disnake.ext import commands
from decouple import config

from db import database
from parser import download_file, fetch_new_vk_post, get_video

bot = commands.Bot(command_prefix="*", help_command=None, intents=disnake.Intents.all())

flag = True

@bot.event
async def on_ready():
    if flag:
        database.drop_models()
        database.create_models()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    check_external_source.start()
    
@bot.command()
async def test(ctx):
    await ctx.send('!~!!!!!!!!!!!!!!!!!')

@tasks.loop(seconds=1800)
async def check_external_source():
    try:
        new_data = await asyncio.to_thread(fetch_new_vk_post)
    except Exception as e:
        print(f"Ошибка в цикле check_external_source: {e}")
        return
    
    if not new_data:
        return

#1528298119219904634

    channel = bot.get_channel(1529475027911704576)
    if not channel:
        print("Канал не найден! Проверьте ID или права бота.")
        return

    for i in new_data:
        title = i[0]
        description = i[1]
        files = []
        
        print(i)
        if i[2]:
            for j in i[2]:
                photo_bytes = await download_file(j['url'])
                buffer = io.BytesIO(photo_bytes)
                files.append(disnake.File(buffer, filename="photo.jpg"))
                
        embed = disnake.Embed(title=title, description=description, color=disnake.Color.blue())
        
        if files:
            await channel.send(embed=embed, files=files)
        else:
            await channel.send(embed=embed)
            
        if i[-1] != 'video_none':
            video_id = i[-1].split(';')[1]
            video_url = get_video(video_id)
            video_bytes = await download_file(video_url)

            if len(video_bytes) <= 25 * 1024 * 1024:  # лимит Discord
                buffer = io.BytesIO(video_bytes)
                file = disnake.File(buffer, filename="video.mp4")
                await channel.send(file=file)
            else:
                await channel.send(f"Видео слишком большое для загрузки: {video_url}")
                
    # except Exception as e:
    #     print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!Ошибка в цикле check_external_source: {e}")

@check_external_source.error
async def check_external_source_error(error):
    print(f"tasks.loop упал с ошибкой: {error}")

bot.run(config("DISCORD_TOKEN"))

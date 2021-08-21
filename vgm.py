import io
import requests
import urllib
from rich import inspect
from bs4 import BeautifulSoup
import logging
import asyncio
import aiohttp
import sys
import os

logging.basicConfig(level=logging.DEBUG)

ALBUM_NAME = sys.argv[1]
URL = 'https://downloads.khinsider.com'
ALBUM_DIR = os.path.join(os.getcwd(), ALBUM_NAME)

async def get_raw_data(client, song):
    song_data = await client.get(f'{URL}{song.a["href"]}')
    song_html = BeautifulSoup(await song_data.text(), 'html.parser')
    mp3 = song_html.select('.songDownloadLink')
    for m in mp3:
        song_url = m.parent['href']
        try:
            sys.argv[2]
        except IndexError:
            sys.argv.insert(2, '--mp3')
        if '--flac' in sys.argv[2] and 'mp3' in song_url:
            continue
        elif '--mp3' in sys.argv[2] and 'flac' in song_url:
            continue
        print(song_url)
        song_bin = await client.get(song_url)
        b = io.BytesIO()
        async for s in song_bin.content.iter_chunked(65535):
            b.write(s)
        b.seek(0)
        with open(os.path.join(ALBUM_DIR, urllib.parse.unquote(os.path.basename(song_url))), 'wb') as f:
            print(f"saving {urllib.parse.unquote(os.path.basename(song_url))}...")
            f.write(b.read())
        print("closing stream to relieve data...")
        b.close()
        

async def get_vgm_data():
    #data = requests.get(f"{URL}/game-soundtracks/album/{ALBUM_NAME}")
    client = aiohttp.ClientSession(headers={'User-Agent': 'kalkacli / 0.0.5'})
    data = await client.get(f"{URL}/game-soundtracks/album/{ALBUM_NAME}")
    print(f"successfully got client {client.headers}")
    html = BeautifulSoup(await data.text(), 'html.parser')
    song_list = html.select('.playlistDownloadSong')
    box_art = html.find('img')['src']
    tasks = []
    for l in song_list:
        task = asyncio.create_task(get_raw_data(client, l))
        tasks.append(task)
    await asyncio.gather(*tasks)
    await client.close()


def main():
    if not os.path.exists(ALBUM_DIR):
        os.mkdir(ALBUM_DIR)
    loop = asyncio.get_event_loop()
    task = loop.create_task(get_vgm_data())
    loop.run_until_complete(task)


main()
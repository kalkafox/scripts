import io
import os
import sys
import logging
import requests

from rich.logging import RichHandler
from rich import inspect
from rich.progress import Progress


def assemble_log():
    logging.basicConfig(handlers=[RichHandler()], level=logging.NOTSET)
    rich = logging.getLogger("cf")
    return rich


def main():
    log = assemble_log()
    args = sys.argv[1:]
    if not args:
        log.info(
            "\n\nCurseForge \nUsage: cf \n\nAvailable commands:\nget <curseforge_url>")
        sys.exit(1)
    if 'get' in args:
        try:
            loader = args[1]
        except IndexError:
            loader = 'forge'
        try:
            url = args[2]
        except IndexError:
            try:
                url = args[1]
            except IndexError:
                url = []
        try:
            version = args[3]
        except IndexError:
            version = "1.17.1"
        if 'curseforge' not in url:
            print(url)
            log.error(
                "Please specify a CurseForge URL. `cf get https://www.curseforge.com/minecraft/mc-mods/<mod-slug>`")
            sys.exit(0)
        mod_slug = os.path.basename(url)
        curse_kalkaio_url = "https://get.kalka.io/curseforge.json"
        cfwidget_url = f"https://api.cfwidget.com/minecraft/mc-mods/{mod_slug}"
        curseforge_url = "https://addons-ecs.forgesvc.net/api/v2/addon/"
        request = requests.get(curse_kalkaio_url)
        if request.status_code == 200:
            data = request.json()
            mod = ''
            for d in data:
                if mod_slug == d['slug']:
                    mod = d['id']
            mod == '' and sys.exit(log.error("No mod found"))
            curse_r = requests.get(f'{curseforge_url}{mod}', headers={
                                   'User-Agent': 'cfcli / kalka.io'})
            if curse_r.status_code == 200:
                curse_data = curse_r.json()
                print(mod)
                dates = [f['fileDate'] for f in curse_data['latestFiles']
                         if (loader in f['gameVersion'] or version in f['gameVersion'])]
                not dates and sys.exit(
                    log.error(f"Version {version} not found for {mod_slug}"))
                latest = max(dates)
                download_url = [f['downloadUrl']
                                for f in curse_data['latestFiles'] if f['fileDate'] == latest][0]
                log.info(
                    f"Preparing to download {mod_slug} ({download_url})...")
                stream_jar = requests.get(download_url, stream=True)
                stream_length = stream_jar.headers['Content-Length']
                b = io.BytesIO()
                b.seek(0)
                chunk = 0
                import time
                start = time.time()
                with Progress() as progress:
                    task = progress.add_task(
                        description=f"Downloading {mod_slug}... {int(stream_length)} total bytes", total=int(stream_length))
                    for s in stream_jar.iter_content(chunk_size=65535):
                        b.write(s)
                        chunk += len(s)
                        speed = (chunk // (time.time() - start) /
                                 1000000) > 1 and f'{chunk // (time.time() - start) / 1000000} MB/s' or f'{chunk // (time.time() - start) / 1000} KB/s'
                        progress.update(
                            task, description=f"Downloading {mod_slug}... {chunk > 1000000 and chunk / 1000000 or chunk / 1000} {chunk > 1000000 and 'MB' or 'KB'}/{int(stream_length) > 1000000 and int(stream_length) / 1000000 or int(stream_length) / 1000} {int(stream_length) > 1000000 and 'MB' or 'KB'} {speed} ({(time.time() - start)} elapsed)", advance=len(s))
                if int(stream_length) == chunk:
                    save_path = f'{os.getcwd()}/{os.path.basename(download_url)}'
                    log.info(f"Saving contents to {save_path}...")
                    with open(save_path, 'wb') as f:
                        f.write(b.getbuffer())
                b.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass


import argparse
import datetime
import io
import json
import os
import sys
import logging
import requests
import time

from rich.logging import RichHandler
from rich import inspect
from rich.progress import Progress

def parse_args(parser):
    args = parser.parse_args()
    return args

def init_args():
    parser = argparse.ArgumentParser(
        description="cf utility"
    )
    parser.add_argument('-m', '--modloader', help='Specify the modloader. Usually `forge` or `fabric`. Defaults to `forge`.', default='forge')
    parser.add_argument('-dep', '--disable-dependencies', help='Disable dependencies.', action='store_true')
    parser.add_argument('-v', '--version', metavar='MINECRAFT_VERSION', default="1.16.5", help='Specify Minecraft version.')
    parser.add_argument('mods', metavar='MOD_SLUG', type=str, nargs='+', help='Poll CurseForge and attempt to download the specified mod(s).')
    parser.add_argument('-d', '--download-path', help=f'Alternate download path. Defaults to {os.getcwd()}/<mod_filename.jar>', default=os.getcwd(), type=str)
    return parser

parser = init_args()
args = parse_args(parser)

def assemble_log():
    logging.basicConfig(handlers=[RichHandler()], level=logging.INFO)
    rich = logging.getLogger("curseutility")
    return rich


def save_curseforge_data(log, request):
    log.info("Saving CurseForge data...")
    with open('/tmp/curseforge.json', 'wb') as f:
        for chunk in request.iter_content(65535):
            f.write(chunk)

def curse_request(m, modid):
    curseforge_url = "https://addons-ecs.forgesvc.net/api/v2/addon/"
    return requests.get(f'{curseforge_url}{m.get("id")}/file/{modid}', headers={
                                'User-Agent': 'cfcli / kalka.io'})

TYPE_FORGE = 1
TYPE_FABRIC = 4

TYPE_REQUIRED = 3
TYPE_OPTIONAL = 2

def get_mod_file(log, m):
    for f in m.get("latest_files"):
        if f.get('modLoader') == None and args.modloader.lower() == 'fabric':
            continue
        if (f.get('modLoader') == TYPE_FORGE and args.modloader.lower() == 'fabric') or (f.get('modLoader') == TYPE_FABRIC and args.modloader.lower() == 'forge'):
            continue
        if isinstance(args.version, list):
            if f.get('gameVersion') not in args.version:
                continue
        elif isinstance(args.version, str):
            if f.get('gameVersion') != args.version:
                continue
        if f.get('gameVersion') in args.version:
            log.info(f"Found version {f.get('projectFileName')}")
            return f


def download_mod(log, mod_slug, download_url):
    log.info(
    f"Preparing to download {mod_slug} ({download_url})...")
    stream_jar = requests.get(download_url, stream=True)
    stream_length = stream_jar.headers['Content-Length']
    b = io.BytesIO()
    b.seek(0)
    chunk = 0
    import time
    start = time.time()
    save_path = f'{args.download_path}/{os.path.basename(download_url)}'
    with Progress() as progress:
        task = progress.add_task(
            description=f"> Downloading {mod_slug}... {int(stream_length)} total bytes", total=int(stream_length))
        for s in stream_jar.iter_content(chunk_size=65535):
            b.write(s)
            chunk += len(s)
            speed = (chunk // (time.time() - start) /
                        1000000) > 1 and f'{chunk // (time.time() - start) / 1000000} MB/s' or f'{chunk // (time.time() - start) / 1000} KB/s'
            progress.update(
                task, description=f"> Downloading {mod_slug}... {chunk > 1000000 and chunk / 1000000 or chunk / 1000} {chunk > 1000000 and 'MB' or 'KB'}/{int(stream_length) > 1000000 and int(stream_length) / 1000000 or int(stream_length) / 1000} {int(stream_length) > 1000000 and 'MB' or 'KB'} {speed} ({(time.time() - start)} elapsed)", advance=len(s))
    if int(stream_length) == chunk:
        log.info(f"Saving contents to {save_path}...")
        with open(save_path, 'wb') as f:
            f.write(b.getbuffer())
    b.close()


def main():
    log = assemble_log()
    curse_kalkaio_url = "https://get.kalka.io/curseforge.json"
    request = requests.get(curse_kalkaio_url, stream=True)
    log.info("Polled the stream data, but we're not downloading it yet")
    if os.path.exists('/tmp/curseforge.json'):
        curseforge_date = datetime.datetime.strptime(request.headers.get("last-modified"), "%a, %d %b %Y %H:%M:%S %Z")
        import pytz
        if curseforge_date.astimezone(pytz.utc) > datetime.datetime.now(tz=datetime.timezone.utc):
            log.info(datetime.datetime.now(tz=datetime.timezone.utc))
            log.info("Need an update.")
            if request.status_code == 200:
                save_curseforge_data(log, request)
            else:
                log.critical("Failed to get local data! Continuing with latest cache.")
        else:
            log.info("Don't need to anyway.")
        with open('/tmp/curseforge.json', 'rb') as f:
            data = json.loads(f.read())
    else:
        if request.status_code == 200:
            save_curseforge_data(log, request)
            data = json.loads(open('/tmp/curseforge.json', 'rb').read())
        else:
            sys.exit("Couldn't get what we needed.")
    mods = []
    for cm in args.mods:
        log.info(f"Looking for {cm}...")
        mod = [d for d in data if cm == d.get("slug")]
        if mod:
            log.info(f"Found {cm}!")
            mods += mod
    not mods and sys.exit(
        log.error("No mod found")
    )
    if args.version == "1.16.5":
        args.version = []
        for i in range(1, 6):
            args.version.append("1.16." + str(i))
    for m in mods:
        log.info(f"Assembling {m.get('name')}...")
        found_file = get_mod_file(log, m)
        if not found_file:
            sys.exit(log.critical(f"We did not find a {args.modloader.capitalize()} version for {m.get('name')}. Perhaps try with a different modloader?"))
        curse_r = curse_request(m, found_file.get("projectFileId"))
        if curse_r.status_code == 200:
            curse_data = curse_r.json()
            if not args.disable_dependencies:
                deps = []
                for dep in curse_data.get("dependencies"):
                    deps += [d for d in data if dep.get("addonId") == d.get("id") and dep.get("type") == TYPE_REQUIRED]
                for d in deps:
                    dep_file = get_mod_file(log, d)
                    dep_r = curse_request(d, dep_file.get("projectFileId"))
                    if dep_r.status_code == 200:
                        dep_data = dep_r.json()
                        download_mod(log, d.get("slug"), dep_data.get("downloadUrl"))
            download_mod(log, m.get("slug"), curse_data.get("downloadUrl"))

                    
        continue


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

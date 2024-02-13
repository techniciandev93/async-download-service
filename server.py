import argparse
import asyncio
import logging
import os

from aiohttp import web
import aiofiles

logger = logging.getLogger('Logger download service')


async def archive(request, delay, photo_path):
    archive_name = request.match_info.get('archive_hash', 'No_name')
    folder_photo_path = os.path.join(photo_path, archive_name)
    if os.path.exists(folder_photo_path):
        return await send_archive_in_parts(folder_photo_path, request, delay=delay)
    return web.Response(status=404, text='Архив не существует или был удален')


async def send_archive_in_parts(directory_path, request, chunk_size=1024 * 100, delay=0):
    process = await asyncio.create_subprocess_exec(
        'zip', '-r', '-', '.', cwd=directory_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    response = web.StreamResponse()
    try:
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename="archive.zip"'
        await response.prepare(request)

        while True:
            try:
                chunk = await process.stdout.read(chunk_size)
                if not chunk:
                    break
                await response.write(chunk)
                logging.info('Sending archive chunk ...')
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                logger.error(f'Download was interrupted')
                raise

    except BaseException as error:
        logging.error(f'BaseException occurred. Exiting. {error}')
        raise

    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()
        await response.write_eof()

    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Этот скрипт запускает веб-сервис на Python для скачивания картинок, '
                                                 'использующий библиотеку aiohttp для обработки запросов.')
    parser.add_argument('--log', action='store_true', help='Укажите --log чтобы включить логирование. '
                                                           'По умолчанию без аргумента False')

    parser.add_argument('--delay', type=int, help='Укажите --delay и количество секунд для задержки. '
                                                  'По умолчанию будет 0 секунд.', nargs='?', default=0)

    parser.add_argument('--photo_path', type=str, help='Укажите --photo_path и путь к каталогам с фото. По умолчанию '
                                                       'будет использоваться путь test_photos/ из корня проекта.',
                        nargs='?', default='test_photos/')

    args = parser.parse_args()

    if args.log:
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
        )
        logger.setLevel(logging.INFO)

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', lambda request: archive(request, args.delay, args.photo_path)),
    ])
    web.run_app(app)

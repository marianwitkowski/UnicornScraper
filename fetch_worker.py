from starlette.concurrency import run_in_threadpool
import threading
from consts import *
from utils import *
import asyncio
import pymongo
import random
import json
import os
import time
import shutil
import logging
import requests
from deepdiff import DeepDiff


class FetchWorker:
    """
    Class for reading tasks from mongodb and fetching data from URLs
    """

    def __init__(self, db, max_workers: int = 3):
        self._db = db
        self._ua_list = get_user_agents()  # get UA list
        self._MAX_WORKERS = max_workers
        self._workers = 0
        self._lock = threading.Lock()
        self._proxies = []
        os.makedirs(CACHE_DIR, exist_ok=True)

    async def grab_data(self, doc):
        """
        Wrapper method for fetching data from URL
        :param doc: task document from mongoDB
        :return:
        """
        self._lock.acquire()
        self._workers += 1
        self._lock.release()

        query = {"_id": doc.get('_id')}
        await self._db[COLLECTION_TASKS]. \
            update_one(query, {"$set": {"status": TaskStatus.INPROGRESS.value}})

        await self.find_in_cache(doc.get('_id'), doc.get('url'), doc.get('task'))
        task_result = await run_in_threadpool(self.exec_task, doc)
        logging.info(task_result)

        await self._db[COLLECTION_TASKS]. \
            update_one(query, {"$set": {"status": TaskStatus.DONE.value}})

        self._lock.acquire()
        self._workers -= 1
        self._lock.release()
        return

    async def run(self):
        """
        Start listening mongoDB collection for retrieving data
        :return:
        """
        logging.info("Fetch worker start...")
        loop = asyncio.get_event_loop()
        colls = await self._db.list_collection_names()
        if not COLLECTION_TASKS in colls:
            await self._db.create_collection(COLLECTION_TASKS,
                                             capped=True, max=1_000_000, size=50 * 1024 * 1024)

        while True:
            # take only alive proxies
            condition = {"status_check": HttpCheckStatus.OK.value}
            self._proxies = await self._db[COLLECTION_PROXIES]. \
                find(condition, {"_id": 0, "response": 0}). \
                sort([('latency', 1)]).to_list(None)

            cursor = self._db[COLLECTION_TASKS].find(
                {"status": TaskStatus.NEW.value}, cursor_type=pymongo.CursorType.TAILABLE_AWAIT).limit(
                self._MAX_WORKERS)
            while cursor.alive:

                async for doc in cursor:
                    loop.create_task(self.grab_data(doc))
                    while self._workers >= self._MAX_WORKERS:
                        await asyncio.sleep(5)

            await asyncio.sleep(5)
        logging.debug('run - done')

    def exec_task(self, doc):
        """
        Execute single URL downloading
        :param doc: document from task collection from mongo
        :return: status of downloading URL
        """
        task_params = json.loads(doc.get('task', {}))
        _id = str(doc.get('_id'))
        _url = doc.get('url')

        _headers = {"Accept-Encoding": "gzip, deflate, br"}
        if task_params.get('user_agent') is None or task_params.get('user_agent', "") == "":
            _headers["User-Agent"] = self._ua_list[random.randint(0, len(self._ua_list) - 1)]
        else:
            _headers["User-Agent"] = task_params.get('user_agent', "")
        if task_params.get('headers'):
            _headers.update(task_params.get('headers'))

        _method = task_params.get('method', 'GET').upper()
        _cookies = task_params.get('cookies', {})
        _timeout = task_params.get('timeout', 60)
        _params = task_params.get('params')
        _retries = task_params.get('retries', 0)

        params_get, params_post = None, None
        if _method == "GET":
            params_get = _params
        if _method == "POST":
            params_post = _params

        logging.info(f"{_id} : Task start")

        status = HttpCheckStatus.OK
        result = {"_id": _id}
        while True:
            try:

                _proxies = None
                if not task_params.get('no_proxy', False):
                    is_https = _url.lower().startswith("https")
                    avail_proxies = [p for p in self._proxies if p["https"] == is_https]
                    if len(avail_proxies):
                        proxy = avail_proxies[random.randint(0, len(avail_proxies) - 1)]
                        _proxies = {
                            'http': f'http://{proxy.get("proxy_server")}',
                            'https': f'http://{proxy.get("proxy_server")}',
                        }
                        result.update({"proxy": proxy.get('proxy_server')})
                        logging.info(f"{str(doc.get('_id'))} : use proxy {proxy.get('proxy_server')}")

                ts1 = time.monotonic()
                r = requests.request(_method, url=_url,
                                     params=params_get, data=params_post,
                                     headers=_headers, cookies=_cookies,
                                     timeout=_timeout, proxies=_proxies)
                r.raise_for_status()
                ts2 = time.monotonic()

                # store in cache
                filename = f"{_id}.cache"
                with open(os.path.join(CACHE_DIR, filename), "wb") as fd:
                    fd.write(r.content)

                result.update({"status": TaskStatus.DONE.value,
                               "download_time": ts2 - ts1})
                logging.info(f"{_id} : Task done")
                return result

            except requests.exceptions.HTTPError as err:
                status = HttpCheckStatus.HTTP_ERROR
                logging.exception(str(err))
            except requests.exceptions.ProxyError as err:
                status = HttpCheckStatus.HTTP_PROXY_ERROR
                logging.exception(str(err))
            except requests.exceptions.InvalidProxyURL as err:
                status = HttpCheckStatus.HTTP_PROXY_INVALID_URL
                logging.exception(str(err))
            except requests.exceptions.ConnectionError as err:
                status = HttpCheckStatus.CONN_ERROR
                logging.exception(str(err))
            except requests.exceptions.SSLError as err:
                status = HttpCheckStatus.SSL_ERROR
                logging.exception(str(err))
            except requests.exceptions.Timeout as err:
                status = HttpCheckStatus.TIMEOUT_ERROR
                logging.exception(str(err))
            except Exception as err:
                status = HttpCheckStatus.GENERAL_ERROR
                logging.exception(str(err))

            if status != HttpCheckStatus.OK and _retries > 0:
                _retries -= 1
                logging.error(f"{_id} : Error while fetching {_url} : {status}")
                continue

            break

        logging.info(f"{_id} : Task error : {status.value}")
        result.update({"status": TaskStatus.ERROR, "error_reason": status.value})
        return result

    async def find_in_cache(self, curr_id, url, params):
        """
        Finding objects in cache - comparing URL, HTTP method and params
        :param curr_id: current object id
        :param url: url of data
        :param params: params of task
        :return: None if not found object in cache, otherwise document id of cached document
        """
        params = json.loads(params)
        condition = {"url": url, "status": TaskStatus.DONE.value}
        items = await self._db[COLLECTION_TASKS] \
            .find(condition) \
            .sort([('_id', -1)]) \
            .limit(1).to_list(None)
        if len(items) == 0:
            return None

        for item in items:
            task = json.loads(item.get('task'))
            if task.get('method') == params.get('method'):
                # found object
                diff: DeepDiff = DeepDiff(task.get('params'), params.get('params'))
                if diff.to_dict() == {}:
                    object_id = item.get("_id")
                    fn = os.path.join(CACHE_DIR, f"{object_id}.cache")
                    if os.path.exists(fn):
                        dest_fn = os.path.join(CACHE_DIR, f"{curr_id}.cache")
                        shutil.copy(fn, dest_fn)
                        return object_id

        return None

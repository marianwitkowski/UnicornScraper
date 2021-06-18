import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

from consts import *
from utils import check_ip


class ProxyManager:
    """
    Proxy servers manager
    """

    def __init__(self, db, proxy_list_file: str = None):
        """Init proxy manager
        :param db: pointer to database
        :param proxy_list_file: location of file with proxies
        """
        self._db = db
        self._proxy_list_file = proxy_list_file

    async def set(self):
        """Parse txt file with proxies and store to MongoDB
        :return: none
        """
        if self._proxy_list_file is None:
            self.fetch_from_github()

        try:
            with open(self._proxy_list_file, "rt") as fd:
                for line in fd:
                    items = line.strip().split(" ")
                    if len(items) < 3:
                        continue

                    if not ":" in items[0]: continue
                    ip_addr, port = items[0].split(":")
                    port = int(port)

                    is_https = False
                    props = items[1].split("-")
                    if len(props) and 'S' in props[-1]:
                        is_https = True

                    country = items[1].split("-")[0]

                    if not check_ip(ip_addr) or not 80 <= port <= 65535:
                        continue

                    query = {"proxy_server": {"$eq": items[0]}}
                    res = await self._db[COLLECTION_PROXIES].find_one(query)
                    if res:
                        if items[2] == '-':
                            await self._db[COLLECTION_PROXIES].delete_one(query)
                        continue

                    if items[2] == '+':
                        query = {"proxy_server": items[0],
                                 "status_check": HttpCheckStatus.UNKNOWN.value,
                                 "https": is_https, "country": country}

                        await self._db[COLLECTION_PROXIES].insert_one(query)
        except Exception as exc:
            logging.critical(exc, exc_info=True)
            raise exc

    def validate_proxy(self, row):
        """Validating proxy server
        :param row: document taken from mongo collection
        :return: none
        """
        if not row.get('proxy_server'):
            return
        if row.get("is_https", False):
            url = "https://lumtest.com/myip.json"
        else:
            url = "http://lumtest.com/myip.json"

        status, latency, response, response_code, last_alive = [None] * 5
        try:
            _proxies = {
                "http": f"http://{row.get('proxy_server')}",
                "https": f"https://{row.get('proxy_server')}",
            }
            ts1 = time.monotonic()
            r = requests.get(url,
                             timeout=(PROXY_CONNECT_TIMEOUT, PROXY_CHECK_TIMEOUT),
                             proxies=_proxies)
            r.raise_for_status()
            ts2 = time.monotonic()
            latency = ts2 - ts1
            status = HttpCheckStatus.OK
            response = r.text
            response_code = r.status_code
            if response_code == 200:
                last_alive = datetime.utcnow()
        except requests.exceptions.HTTPError as err:
            status = HttpCheckStatus.HTTP_ERROR
        except requests.exceptions.ConnectionError as err:
            status = HttpCheckStatus.CONN_ERROR
        except requests.exceptions.Timeout as err:
            status = HttpCheckStatus.TIMEOUT_ERROR
        except Exception as err:
            status = HttpCheckStatus.GENERAL_ERROR

        status_data = {"status_check": status.value, "http_code": response_code,
                       "last_check": datetime.utcnow(),
                       "latency": latency, "response": response}
        if last_alive:
            status_data["last_alive"] = last_alive

        values = {"$set": status_data}
        logging.debug(f"{row.get('proxy_server')}, {values}")
        return row.get('proxy_server'), values

    async def check(self):
        """Checking state of proxy server and updates database
        :return:
        """
        logging.info("Check proxies status...")
        docs = await self._db[COLLECTION_PROXIES].find({}, {"_id": 0}).to_list(None)

        with ThreadPoolExecutor(max_workers=MAX_PROXY_WORKERS) as pool:
            loop = asyncio.get_running_loop()
            futures = [
                loop.run_in_executor(pool, self.validate_proxy, doc)
                for doc in docs
            ]
            try:
                results = await asyncio.gather(*futures, return_exceptions=False)
            except Exception as ex:
                raise

        for server, values in results:
            query = {"proxy_server": server}
            await self._db[COLLECTION_PROXIES].update_one(query, values)

    async def fetch_from_github(self):
        """Fetching file with proxies from Github
        :return: True if file was fetched
        """
        try:
            r = requests.get("https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list.txt")
            r.raise_for_status()
            with open(PROXY_FILE, "wt") as fd:
                fd.write(r.text)
            return True
        except BaseException as exc:
            return False

    async def get_alive_proxies(self, limit: int = 5):
        """ Get only alive proxy servers
        :param limit: number of the servers
        :return: list of objects
        """
        await self._db[COLLECTION_PROXIES]. \
            find({"latency": {"$gt": 0}}, {"_id": 0, "response": 0}). \
            sort([('latency', 1)]).to_list(None)

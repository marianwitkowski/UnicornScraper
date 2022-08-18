import asyncio
import logging

import uvicorn
from fastapi import FastAPI, Response, status, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi_utils.tasks import repeat_every

from fetch_worker import FetchWorker
from model import FetchManyUrl, FetchOneUrl, TaskIds
from proxy_manager import ProxyManager
from utils import *

# Apply configuration for logger
log_format = "%(asctime)s:%(levelname)s:%(filename)s:%(message)s"
logging.basicConfig(
    level=logging.INFO,  # debug level
    format=log_format,  # log format
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ],
    datefmt="%Y-%m-%dT%H:%M:%S%z"
)

db_conn = get_db_conn()  # connect to database
proxy_manager = ProxyManager(db_conn, PROXY_FILE)  # initialization of Proxy Manager
fetch_worker = FetchWorker(db_conn, 5)  # initialization of fetching module

app = FastAPI(description="API for fetching URLs")


@app.on_event("startup")
@repeat_every(seconds=3600 * 3)
async def update_proxies():
    await asyncio.sleep(5)
    await proxy_manager.fetch_from_github()  # upload local assets with proxy list
    asyncio.create_task(proxy_manager.set())


@app.on_event("startup")
@repeat_every(seconds=3600)
async def check_proxies():
    asyncio.create_task(fetch_worker.run())  # start worker for fetch data
    await asyncio.sleep(15)
    asyncio.create_task(proxy_manager.check())  # check proxies availability


@app.get("/proxies", description="Get list of proxy servers")
async def get_proxies(alive: int = 0):
    """
    Get proxies list
    - **alive**: if positive - returning only alive proxies
    - **return**: list of proxies
    """
    if alive > 0:  # you can grab only alive servers
        condition = {"status_check": HttpCheckStatus.OK.value}
    else:
        condition = {}

    proxies = await db_conn[COLLECTION_PROXIES]. \
        find(condition, {"_id": 0, "response": 0}). \
        sort([('latency', 1)]).to_list(None)
    return proxies

@app.get("/get_object/{task_id}", response_class=FileResponse)
async def get_object(task_id: str):
    """
    Get object for the task
    :param task_id: ID of the task
    :return: if object exists content is returned , otherwise - returns 404
    """
    try:
        filename = os.path.join(CACHE_DIR, f"{task_id}.cache")
        return FileResponse(filename)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/get_task/{task_id}", status_code=status.HTTP_200_OK)
async def get_task(task_id: str):
    """
    Get status of the task
    :param task_id: ID of the task
    :return: if task exists document from mongo is returned, otherwise - returns 404
    """
    condition = {"_id": ObjectId(task_id)}
    task = await db_conn[COLLECTION_TASKS]. \
        find_one(condition, {"_id": 0})
    if task:
        return task
    raise HTTPException(status_code=404, detail="task not found")


@app.post("/get_tasks", status_code=status.HTTP_200_OK)
async def get_tasks(task_data: TaskIds, response: Response):
    """
    Get tasks status
    - **task_data**: TaskIds object
    - **response**:
    - **return** JSON with ObjectIDs
    """
    condition = {"_id": {"$in": [ObjectId(t) for t in task_data.ids]}}
    tasks = await db_conn[COLLECTION_TASKS]. \
        find(condition).to_list(None)
    if tasks is None or len(tasks)==0:
        raise HTTPException(status_code=404, detail="tasks not found")
    return JSONEncoder().encode(tasks)


@app.post("/fetch_one", status_code=status.HTTP_200_OK)
async def fetch_url(fetch_data: FetchOneUrl, response: Response):
    """
    Fetch one URL
    - **fetch_data**: FetchOneUrl object
    - **response**:
    - **return** JSON with ObjectID
    """
    task = json.dumps(fetch_data.dict(exclude={'url'}))
    url = fetch_data.url
    res = await db_conn[COLLECTION_TASKS].insert_one(
        {"url": url, "task": task, "insert_ts": datetime.datetime.utcnow(),
         "status": TaskStatus.NEW.value,
         "cache": False, "update_ts": datetime.datetime.utcnow(), "download_time": 0.0})
    result = {"url": url, "task_id": str(res.inserted_id)}
    return JSONResponse(content=result, status_code=200)


@app.post("/fetch_many", status_code=status.HTTP_200_OK)
async def fetch_urls(fetch_data: FetchManyUrl, response: Response):
    """
    Fetch many URLs
    - **fetch_data**: FetchManyUrl object (list wiyh URLs)
    - **response**:
    - **return** JSON with ObjectID
    """
    result = []
    task = json.dumps(fetch_data.dict(exclude={'urls'}))
    for url in fetch_data.urls:
        res = await db_conn[COLLECTION_TASKS].insert_one(
            {"url": url, "task": task, "insert_ts": datetime.datetime.utcnow(),
             "status": TaskStatus.NEW.value,
             "cache": False, "update_ts": datetime.datetime.utcnow(), "download_time": 0.0})
        result.append({"url": url, "task_id": str(res.inserted_id)})
    return JSONResponse(content=result, status_code=200)


# run uvicorn server and start FastAPI app on port 8000 of localhost
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

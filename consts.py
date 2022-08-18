import enum
import os
from dotenv import dotenv_values

# LOCATION FOR FILE WITH PROXIES
PROXY_FILE = os.path.join(os.path.dirname(__file__), "assets/proxy-list.txt")

# LOCATION FOR FILE WITH USER AGENTS
UA_FILE = os.path.join(os.path.dirname(__file__), "assets/user-agents.csv")

# CACHE DIR
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

CONF = dotenv_values( os.path.join(os.path.dirname(__file__), "unicorn.conf") )
MONGO_CONN_STR = CONF.get("MONGO_CONN_STR", "mongodb://localhost:27017/")  # mongodb conn string
DB_NAME = CONF.get("DB_NAME", "unicorn_scraper" )  # database name
COLLECTION_PROXIES = CONF.get("COLLECTION_PROXIES", "proxies")  # collection with proxies
COLLECTION_TASKS = CONF.get("COLLECTION_TASKS", "tasks")  # collection with tasks

# CONSTANTS RELATED WITH PROXIES CHECKING PROCESS
MAX_PROXY_WORKERS = CONF.get("MAX_PROXY_WORKERS",20)
PROXY_CHECK_TIMEOUT = CONF.get("PROXY_CHECK_TIMEOUT", 60)
PROXY_CONNECT_TIMEOUT = CONF.get("PROXY_CONNECT_TIMEOUT", 15)


# FETCHING DATA STATUSES
class HttpCheckStatus(enum.Enum):
    OK = 0
    HTTP_ERROR = -1
    CONN_ERROR = -2
    TIMEOUT_ERROR = -3
    GENERAL_ERROR = -4
    HTTP_PROXY_ERROR = -5
    HTTP_PROXY_INVALID_URL = -6
    SSL_ERROR = -7
    UNKNOWN = -99


# TASKS STATUSES
class TaskStatus(enum.Enum):
    NEW = 0
    INPROGRESS = 1
    DONE = 2
    ERROR = 3

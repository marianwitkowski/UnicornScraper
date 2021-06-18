import enum
import os

# LOCATION FOR FILE WITH PROXIES
PROXY_FILE = os.path.join( os.path.dirname(__file__), "assets/proxy-list.txt")

# LOCATION FOR FILE WITH USER AGENTS
UA_FILE = os.path.join( os.path.dirname(__file__), "assets/user-agents.csv")

# CACHE DIR
CACHE_DIR = os.path.join( os.path.dirname(__file__), "cache")

# CONSTANTS RELATED WITH MONGO
MONGO_CONN_STR = "mongodb://localhost:27017/" # mongodb conn string
DB_NAME = "unicorn_scraper" # database name
COLLECTION_PROXIES = "proxies" # collection with proxies
COLLECTION_TASKS = "tasks" # collection with tasks

# CONSTANTS RELATED WITH PROXIES CHECKING PROCESS
MAX_PROXY_WORKERS = 20
PROXY_CHECK_TIMEOUT = 60
PROXY_CONNECT_TIMEOUT = 15

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
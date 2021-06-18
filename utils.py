import re
import motor.motor_tornado
from consts import *

def get_db_conn():
    """Making connection to Mongo DB
    :return:
    """
    client = motor.motor_tornado.MotorClient(MONGO_CONN_STR)
    db = client[DB_NAME]
    return db

def check_ip(ip: str):
    """Validate IP address
    :param ip: IP address to validate
    :return: True - if correct, False - if not
    """
    regex = "^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])$"
    return re.search(regex, ip)


def get_user_agents():
    """Parsing User Agents file
    :return: list of user agents
    """
    ua = []
    try:
        with open(UA_FILE,"rt") as fd:
            for line in fd:
                line = line.strip()
                items = line.split(",")
                if len(items)>0:
                    ua.append(items[0])
    except Exception as exc:
        pass
    return ua

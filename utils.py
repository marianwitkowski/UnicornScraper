import re
import datetime
import motor.motor_tornado
from consts import *
import json
from bson import ObjectId


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


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return str(o)
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)
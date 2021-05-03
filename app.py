import os
import requests, json, re
from datetime import date, datetime
import configparser
from paho.mqtt.client import Client
from enum import IntEnum

class ErrorCode(IntEnum):
    NO_ERROR = 0
    GET_SHOPPING_LIST_ITEMS = 1
    GET_VOLATILE = 2
    GET_PRODUCT = 3
    GET_USERFIELDS_PRODUCT = 4
    ADD_PRODUCT_IN_SHOPPING_LIST = 5
    GET_MEALPLAN = 6
    CONSUME_PRODUCT = 7
    CONSUME_RECIPE = 8
    GET_PRODUCT_STOCK = 9

class Grocy:

    def __init__(self, host, api_key, payload={}):
        payload["errors"] = ErrorCode.NO_ERROR
        self.grocy_host = host
        self.grocy_api_key = api_key
        self.payload = payload

    def get_all_shopping_lists_items(self):
        resp = requests.get(f'{self.grocy_host}/api/objects/shopping_list', headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_SHOPPING_LIST_ITEMS
        return resp.json()

    def get_volatile_products(self):
        resp = requests.get(f'{self.grocy_host}/api/stock/volatile?expiring_days=5', headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_VOLATILE
        return resp.json()

    def get_product(self, id):
        resp = requests.get(f'{self.grocy_host}/api/objects/products/{id}', headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_PRODUCT
        return resp.json()
    
    def get_product_in_stock(self, id):
        resp = requests.get(f'{self.grocy_host}/api/stock/products/{id}', headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_PRODUCT_STOCK
        return resp.json()

    def get_userfields_product(self, id):
        resp = requests.get(f'{self.grocy_host}/api/userfields/products/{id}', headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_USERFIELDS_PRODUCT
        return resp.json()

    def add_product_in_shopping_list(self, product_id, list_id, product_amount=1, cause=None):
        note = "Item added by grocy2mqtt"
        if cause:
            note = f"{note} cause: {cause}"
        data = {
            "product_id": product_id,
            "list_id": list_id,
            "product_amount": product_amount,
            "note": note
        }
        resp = requests.post(f'{self.grocy_host}/api/stock/shoppinglist/add-product', headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key}, data=data)
        if resp.status_code != 204:
            self.payload["errors"] = ErrorCode.ADD_PRODUCT_IN_SHOPPING_LIST
        return resp.status_code

    def manage_volatile_products(self, products, shopping_lists_items, cause=None):
        for product in products:
            min_stock_amount = product["min_stock_amount"]
            if int(min_stock_amount) > 0:
                id = product["id"]
                userfields = self.get_userfields_product(id)
                if self.payload["errors"]:
                    return
                if not userfields:
                    continue
                shoppinglist_id = userfields.get("shoppinglist")
                if shoppinglist_id:
                    shoppinglist_item = next(filter(lambda item: item["shopping_list_id"] == shoppinglist_id and item["product_id"] == id, shopping_lists_items), None)
                    if not shoppinglist_item:
                        self.add_product_in_shopping_list(id, shoppinglist_id, cause=cause)
    
    def get_mealplan(self):
        resp = requests.get(f'{self.grocy_host}/api/objects/meal_plan', headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_MEALPLAN
        return resp.json()
    
    def delete_mealplan(self, mealplan_id):
        requests.delete(f'{self.grocy_host}/api/objects/meal_plan/{mealplan_id}', headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key})
        # if resp.status_code != 204:
        #     self.payload["errors"] = ErrorCode.DELETE_MEALPLAN
        # return resp.json()

    def consume_product(self, product_id, product_amount):
        resp = requests.post(
                f'{self.grocy_host}/api/stock/products/{product_id}/consume', 
                headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key},
                data={ "amount": product_amount, "transaction_type": "consume",  "spoiled": "false" }
            )
        if resp.status_code != 200 and resp.status_code != 204:
            self.payload["errors"] = ErrorCode.CONSUME_PRODUCT

    def consume_recipe(self, recipe_id):
        resp = requests.post(
            f'{self.grocy_host}/api/recipes/{recipe_id}/consume', 
            headers={'accept': 'application/json', 'GROCY-API-KEY': self.grocy_api_key}
        )
        if resp.status_code != 200 and resp.status_code != 204:
            self.payload["errors"] = ErrorCode.CONSUME_RECIPE

def int_or_zero(id):
    numeric_id = 0
    if id:
        numeric_id = int(float(id))
    return numeric_id

def __grocy_mealplan_list__(day=date.today(), diff_days=15):
    grocy = Grocy(grocy_host, grocy_api, { "mealplan": [], "note": "" })
    mealplanlist = grocy.get_mealplan()
    for meal in mealplanlist:
        daylist = meal['day'].split('-')
        thatday = date(int(daylist[0]), int(daylist[1]), int(daylist[2]))
        if (day - thatday).days > diff_days:
            grocy.delete_mealplan(meal['id'])
        elif thatday == day:
            if meal['type'] != "note":
                grocy.payload["mealplan"].append({ 
                    "id": int_or_zero(meal['id']), 
                    "type": meal['type'], 
                    "recipe_id": int_or_zero(meal['recipe_id']), 
                    "recipe_servings": int_or_zero(meal['recipe_servings']), 
                    "product_id": int_or_zero(meal["product_id"]), 
                    "product_amount": int_or_zero(meal["product_amount"]) 
                })
            else:
                grocy.payload["note"] = re.sub(r'[\r\n]*(<br />)+[\r\n]*|[\r\n]+', '\n', meal["note"])
    return grocy.payload

def __grocy_mealplan_consume__(day=date.today()):
    payload = __grocy_mealplan_list__(day)
    if payload["errors"]:
        return payload
    grocy = Grocy(grocy_host, grocy_api, payload)
    for p in payload["mealplan"]:
        if p["type"] == "product":
            grocy.consume_product(p["product_id"], p["product_amount"])
        elif p["type"] == "recipe":
            for i in range(0, int(p["recipe_servings"])):
                grocy.consume_recipe(p["recipe_id"])

    return grocy.payload

def __grocy_shoppinglists_add__():
    grocy = Grocy(grocy_host, grocy_api, { "expiring": 0, "expired": 0, "missing": 0 })

    shopping_lists_items = grocy.get_all_shopping_lists_items()
    if grocy.payload["errors"] > 0:
        return grocy.payload

    volatile_products = grocy.get_volatile_products()
    if grocy.payload["errors"] > 0:
        return grocy.payload
    expiring_products = []
    expired_products = []
    missing_products = []
    if volatile_products.get("expiring_products"):
        expiring_products = [product["product"] for product in volatile_products["expiring_products"]]
        grocy.payload["expiring"] = len(expiring_products)
    if volatile_products.get("expired_products"):
        expired_products = [product["product"] for product in volatile_products["expired_products"]]
        grocy.payload["expired"] = len(expired_products)
    if volatile_products.get("missing_products"):
        grocy.payload["missing"] = len(volatile_products["missing_products"])
        missing_products = [grocy.get_product(missing_product["id"]) for missing_product in volatile_products["missing_products"]]
    if grocy.payload["errors"] > 0:
        return grocy.payload
    
    grocy.manage_volatile_products(expiring_products, shopping_lists_items, cause="it's expiring")
    grocy.manage_volatile_products(expired_products, shopping_lists_items, cause="it's expired")
    
    if grocy.payload["errors"] > 0:
        return grocy.payload
    grocy.manage_volatile_products(missing_products, shopping_lists_items, cause="it's missing")

    return grocy.payload

def on_connect(client, userdata, flags, rc):
    print("Connected")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"Unexpected disconnection. Error code: {rc}")

def __retrieve_date_from_payload(payload):
    day = date.today()
    if payload:
        daylist = re.split(r"\D+", payload.decode("UTF-8"))
        try:
            day = date(int(daylist[0]), int(daylist[1]), int(daylist[2]))
        except:
            pass
    return day

def on_message_grocy_mealplan_list(client, userdata, message):
    day = __retrieve_date_from_payload(message.payload)
    print(day)
    payload = __grocy_mealplan_list__(day)
    exists = len(payload.get("mealplan"))
    payload["exists"] = exists
    client.publish(TOPIC_HOME_MEALPLAN_LIST, payload=json.dumps(payload), qos=2)

def on_message_grocy_mealplan_consume(client, userdata, message):
    day = __retrieve_date_from_payload(message.payload)
    print(day)
    payload = __grocy_mealplan_consume__(day)
    client.publish(TOPIC_HOME_MEALPLAN_CONSUMED, payload=json.dumps(payload), qos=2)

def on_message_grocy_shoppinglists_add(client, userdata, message):
    payload = __grocy_shoppinglists_add__()
    client.publish(TOPIC_HOME_SHOPPINGLISTS_ADDED, payload=json.dumps(payload), qos=2)

def on_message_grocy_stock_get(client, userdata, message):
    product_id = message.payload.decode("utf-8")
    now = datetime.now()
    date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
    print(date_time + " - " + product_id)
    grocy = Grocy(grocy_host, grocy_api)
    topic = TOPIC_HOME_PRODUCT_IN_STOCK + str(product_id)
    product = grocy.get_product_in_stock(int(float(product_id)))
    payload = json.dumps(product)
    print(date_time + " - " + payload)
    client.publish(topic, payload=payload, qos=2)
    print("paylad " + payload + " published for product " + product_id)

def message_append(client, topic):
    client.message_callback_add(topic[0], topic[2])
    return (topic[0], topic[1])

config = configparser.ConfigParser()
config.read('config.ini')

if os.environ.get('GROCY_HOST'):
    grocy_host = os.environ.get('GROCY_HOST')
else:
    grocy_host = config['grocy']['host']

if os.environ.get('GROCY_API_KEY'):
    grocy_api = os.environ.get('GROCY_API_KEY')
else:
    grocy_api = config['grocy']['api_key']

if os.environ.get('MQTT_HOST'):
    mqtt_host = os.environ.get('MQTT_HOST')
else:
    mqtt_host = config['mqtt']['host']

if os.environ.get('MQTT_USER'):
    mqtt_user = os.environ.get('MQTT_USER')
else:
    mqtt_user = config['mqtt']['user']

if os.environ.get('MQTT_PWD'):
    mqtt_password = os.environ.get('MQTT_PWD')
else:
    mqtt_password = config['mqtt']['pwd']

TOPIC_HOME_MEALPLAN_LIST = "home/mealplan/list"
TOPIC_HOME_MEALPLAN_CONSUMED = "home/mealplan/consumed"
TOPIC_HOME_SHOPPINGLISTS_ADDED = "home/shoppinglists/added"
TOPIC_HOME_PRODUCT_IN_STOCK = "home/stock/"

TOPICS = (
    ("grocy/mealplan/list", 2, on_message_grocy_mealplan_list), 
    ("grocy/mealplan/consume", 2, on_message_grocy_mealplan_consume),
    ("grocy/shoppinglists/add", 2, on_message_grocy_shoppinglists_add),
    ("grocy/stock/get", 2, on_message_grocy_stock_get)
)

if __name__ == "__main__":
    client = Client(client_id="grocy")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    tops = [message_append(client, topic) for topic in TOPICS]

    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, password=mqtt_password)

    print(mqtt_host)
    print(grocy_host)
    client.connect(mqtt_host)
    client.subscribe(tops)
    try:
        client.loop_forever()
    except (KeyboardInterrupt, SystemExit):
        client.disconnect()
        raise

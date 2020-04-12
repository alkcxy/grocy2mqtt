
import requests, json, re
from datetime import date
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

class Grocy:

    def __init__(self, payload={}):
        payload["errors"] = ErrorCode.NO_ERROR
        self.payload = payload

    def get_all_shopping_lists_items(self):
        resp = requests.get(f'{grocy_host}/api/objects/shopping_list', headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_SHOPPING_LIST_ITEMS
        return resp.json()

    def get_volatile_products(self):
        resp = requests.get(f'{grocy_host}/api/stock/volatile?expiring_days=5', headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_VOLATILE
        return resp.json()

    def get_product(self, id):
        resp = requests.get(f'{grocy_host}/api/objects/products/{id}', headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_PRODUCT
        return resp.json()

    def get_userfields_product(self, id):
        resp = requests.get(f'{grocy_host}/api/userfields/products/{id}', headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api})
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
        resp = requests.post(f'{grocy_host}/api/stock/shoppinglist/add-product', headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api}, data=data)
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
                shoppinglist_id = userfields.get("shoppinglist")
                if shoppinglist_id:
                    shoppinglist_item = next(filter(lambda item: item["shopping_list_id"] == shoppinglist_id and item["product_id"] == id, shopping_lists_items), None)
                    if not shoppinglist_item:
                        self.add_product_in_shopping_list(id, shoppinglist_id, cause=cause)
    
    def get_mealplan(self):
        resp = requests.get(grocy_host + '/api/objects/meal_plan', headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api})
        if resp.status_code != 200:
            self.payload["errors"] = ErrorCode.GET_MEALPLAN
        return resp.json()

    def consume_product(self, product_id, product_amount):
        resp = requests.post(
                f'{grocy_host}/api/stock/products/{product_id}/consume', 
                headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api},
                data={ "amount": product_amount, "transaction_type": "consume",  "spoiled": "false" }
            )
        if resp.status_code != 200 and resp.status_code != 204:
            self.payload["errors"] = ErrorCode.CONSUME_PRODUCT

    def consume_recipe(self, recipe_id):
        resp = requests.post(
            f'{grocy_host}/api/recipes/{recipe_id}/consume', 
            headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api}
        )
        if resp.status_code != 200 and resp.status_code != 204:
            self.payload["errors"] = ErrorCode.CONSUME_RECIPE

def int_or_zero(id):
    numeric_id = 0
    if id:
        numeric_id = int(float(id))
    return numeric_id

def __grocy_mealplan_list__(day=date.today()):
    grocy = Grocy({ "mealplan": [], "note": "" })
    mealplanlist = grocy.get_mealplan()
    for meal in mealplanlist:
        daylist = meal['day'].split('-')
        thatday = date(int(daylist[0]), int(daylist[1]), int(daylist[2]))
        if thatday == day:
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
    grocy = Grocy(payload)
    for p in payload["mealplan"]:
        if p["type"] == "product":
            grocy.consume_product(p["product_id"], p["product_amount"])
        elif p["type"] == "recipe":
            for i in range(0, int(p["recipe_servings"])):
                grocy.consume_recipe(p["recipe_id"])

    return grocy.payload

def __grocy_shoppinglists_add__():
    grocy = Grocy({ "expiring": 0, "expired": 0, "missing": 0 })

    shopping_lists_items = grocy.get_all_shopping_lists_items()
    if grocy.payload["errors"] > 0:
        return grocy.payload

    volatile_products = grocy.get_volatile_products()
    if grocy.payload["errors"] > 0:
        return grocy.payload
    
    expiring_products = [product["product"] for product in volatile_products["expiring_products"]]
    grocy.payload["expiring"] = len(expiring_products)
    expired_products = [product["product"] for product in volatile_products["expired_products"]]
    grocy.payload["expired"] = len(expired_products)
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

client = Client(client_id="grocy")

def on_connect(client, userdata, flags, rc):
    print("Connesso con successo")

def on_message(client, userdata, message):
    topic = message.topic

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection.")

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
    payload = __grocy_mealplan_list__(day)
    exists = len(payload.get("mealplan"))
    payload["exists"] = exists
    client.publish(TOPIC_HOME_MEALPLAN_LIST, payload=json.dumps(payload), qos=2)

def on_message_grocy_mealplan_consume(client, userdata, message):
    day = __retrieve_date_from_payload(message.payload)
    payload = __grocy_mealplan_consume__(day)
    client.publish(TOPIC_HOME_MEALPLAN_CONSUMED, payload=json.dumps(payload), qos=2)

def on_message_grocy_shoppinglists_add(client, userdata, message):
    payload = __grocy_shoppinglists_add__()
    client.publish(TOPIC_HOME_SHOPPINGLISTS_ADDED, payload=json.dumps(payload), qos=2)

config = configparser.ConfigParser()
config.read('config.ini')

grocy_host = config['grocy']['host']
grocy_api = config['grocy']['api_key']

mqtt_user = config['mqtt']['user']
mqtt_password = config['mqtt']['pwd']

TOPIC_HOME_MEALPLAN_LIST = "home/mealplan/list"
TOPIC_HOME_MEALPLAN_CONSUMED = "home/mealplan/consumed"
TOPIC_HOME_SHOPPINGLISTS_ADDED = "home/shoppinglists/added"

TOPICS = (
    ("grocy/mealplan/list", 2, on_message_grocy_mealplan_list), 
    ("grocy/mealplan/consume", 2, on_message_grocy_mealplan_consume),
    ("grocy/shoppinglists/add", 2, on_message_grocy_shoppinglists_add)
)

client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

tops = []
for topic in TOPICS:
    client.message_callback_add(topic[0], topic[2])
    tops.append((topic[0], topic[1]))

if mqtt_user and mqtt_password:
    client.username_pw_set(mqtt_user, password=mqtt_password)

client.connect(config['mqtt']['host'])
client.subscribe(tops)
try:
    client.loop_forever()
except (KeyboardInterrupt, SystemExit):
    client.disconnect()

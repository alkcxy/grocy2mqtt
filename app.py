
import requests, json, re
from datetime import date
import configparser
from paho.mqtt.client import Client

def int_or_zero(id):
    numeric_id = 0
    if id:
        numeric_id = int(float(id))
    return numeric_id

def grocy_meal_plan(day=date.today()):
    resp = requests.get(grocy_host + '/api/objects/meal_plan', headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api})
    if resp.status_code != 200:
        # This means something went wrong.
        print(f"ERROR {resp.status_code}")
        raise Exception('GET /api/objects/meal_plan {}'.format(resp.status_code))
    mealplan = []
    note = ""
    for meal in resp.json():
        daylist = meal['day'].split('-')
        thatday = date(int(daylist[0]), int(daylist[1]), int(daylist[2]))
        if thatday == day:
            if meal['type'] != "note":
                print('{} {} {} {} {} {} {}'.format(meal['id'], meal['day'], meal['type'], meal['recipe_id'], meal['recipe_servings'], meal['product_id'], meal['product_amount']))
                mealplan.append({ 
                    "id": int_or_zero(meal['id']), 
                    "type": meal['type'], 
                    "recipe_id": int_or_zero(meal['recipe_id']), 
                    "recipe_servings": int_or_zero(meal['recipe_servings']), 
                    "product_id": int_or_zero(meal["product_id"]), 
                    "product_amount": int_or_zero(meal["product_amount"]) 
                })
            else:
                note = meal["note"]
    return { "mealplan": mealplan, "note": note }

def grocy_meal_plan_consume():
    meal = grocy_meal_plan()
    status = 1
    mealplan = meal.get("mealplan", [])
    
    for p in mealplan:
        print(p)
        if p["type"] == "product":
            resp = requests.post(
                f'{grocy_host}/api/stock/products/{p["product_id"]}/consume', 
                headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api},
                data={ "amount": p["product_amount"], "transaction_type": "consume",  "spoiled": "false" }
            )
        elif p["type"] == "recipe":
            resp = requests.post(
                f'{grocy_host}/api/recipes/{p["recipe_id"]}/consume', 
                headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api}
            )
        if resp.status_code != 200 and resp.status_code != 204:
            status = 0
    return status


client = Client(client_id="grocy")

def on_connect(client, userdata, flags, rc):
    print("Connesso con successo")

def on_message(client, userdata, message):
    topic = message.topic
    print(topic)

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

def on_message_grocy_meaplan(client, userdata, message):
    day = __retrieve_date_from_payload(message.payload)
    mealplan = grocy_meal_plan(day)
    exists = len(mealplan.get("mealplan"))
    note = mealplan.get("note")
    note = re.sub(r'[\r\n]*(<br />)+[\r\n]*|[\r\n]+', '\n', note)
    payload = { "note": note, "exists": exists }
    
    client.publish(TOPIC_GROCY_MEALPLAN_TODAY, payload=json.dumps(payload), qos=2)

def on_message_grocy_meaplan_today_consume(client, userdata, message):
    payload = grocy_meal_plan_consume()
    client.publish(TOPIC_GROCY_MEALPLAN_TODAY_CONSUMED, payload=payload, qos=2)

config = configparser.ConfigParser()
config.read('config.ini')

grocy_host = config['grocy']['host']
grocy_api = config['grocy']['api_key']

mqtt_user = config['mqtt']['user']
mqtt_password = config['mqtt']['pwd']

TOPIC_GROCY_MEALPLAN="grocy/mealplan"
TOPIC_GROCY_MEALPLAN_TODAY="grocy/mealplan/today"
TOPIC_GROCY_MEALPLAN_TODAY_CONSUME="grocy/mealplan/today/consume"
TOPIC_GROCY_MEALPLAN_TODAY_CONSUMED="grocy/mealplan/today/consumed"

client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

client.message_callback_add(TOPIC_GROCY_MEALPLAN, on_message_grocy_meaplan)
client.message_callback_add(TOPIC_GROCY_MEALPLAN_TODAY_CONSUME, on_message_grocy_meaplan_today_consume)

if mqtt_user and mqtt_password:
    client.username_pw_set(mqtt_user, password=mqtt_password)

client.connect(config['mqtt']['host'])
client.subscribe([(TOPIC_GROCY_MEALPLAN, 2), (TOPIC_GROCY_MEALPLAN_TODAY_CONSUME, 2)])
client.loop_forever()

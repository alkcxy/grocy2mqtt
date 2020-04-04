
import requests, json
from datetime import date
import configparser
from paho.mqtt.client import Client

config = configparser.ConfigParser()
config.read('config.ini')
grocy_host = config['grocy']['host']
grocy_api = config['grocy']['api_key']

def int_or_zero(id):
    numeric_id = 0
    if id:
        numeric_id = int(float(id))
    return numeric_id

def grocy_meal_plan():
    resp = requests.get(grocy_host + '/api/objects/meal_plan', headers={'accept': 'application/json', 'GROCY-API-KEY': grocy_api})
    if resp.status_code != 200:
        # This means something went wrong.
        raise Exception('GET /api/objects/meal_plan {}'.format(resp.status_code))
    today = date.today()
    mealplan = []
    for meal in resp.json():
        day = meal['day'].split('-')
        thatday = date(int(day[0]), int(day[1]), int(day[2]))
        if thatday == today and meal['type'] != "note":
            print('{} {} {} {} {} {} {}'.format(meal['id'], meal['day'], meal['type'], meal['recipe_id'], meal['recipe_servings'], meal['product_id'], meal['product_amount']))
            mealplan.append({ 
                "meal_id": int_or_zero(meal['id']), 
                "type": meal['type'], 
                "recipe_id": int_or_zero(meal['recipe_id']), 
                "recipe_servings": int_or_zero(meal['recipe_servings']), 
                "product_id": int_or_zero(meal["product_id"]), 
                "product_amount": int_or_zero(meal["product_amount"]) 
            })
    return mealplan

def grocy_meal_plan_consume():
    meal = grocy_meal_plan()
    r = []
    for p in meal:
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
        r.append(resp.text)
    return r


client = Client(client_id="grocy")

def on_connect(client, userdata, flags, rc):
    print("Connesso con successo")

def on_message(client, userdata, message):
    topic = message.topic
    print(topic)
    if topic == "grocy/mealplan":
        publish_topic = f'grocy/mealplan/today'
        payload = json.dumps({ "meal": grocy_meal_plan() })
    elif topic == "grocy/mealplan/today/consume":
        publish_topic = f'grocy/mealplan/today/consumed'
        payload = json.dumps({ "responses": grocy_meal_plan_consume()})
    print(payload)
    client.publish(publish_topic, payload=payload, qos=2)

client.on_connect = on_connect
client.on_message = on_message

client.username_pw_set(config['mqtt']['user'], password=config['mqtt']['pwd'])
client.connect(config['mqtt']['host'])
client.subscribe([("grocy/mealplan", 2), ("grocy/mealplan/today/consume", 2)])
client.loop_forever()

# if __name__ == "__main__":
#     print(grocy_meal_plan())
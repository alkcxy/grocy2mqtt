# grocy2mqtt
Workaround to connect grocy to home assistant

```
docker run -itd --name mosquitto -p 1883:1883 -p 9001:9001 -v ./mosquitto/config/mosquitto.conf:/mosquitto/config/mosquitto.conf -v ./mosquitto/data:/mosquitto/data -v ./mosquitto/log:/mosquitto/log eclipse-mosquitto
```

```
mosquitto_pub -h 127.0.0.1 -p 1883 -t grocy/mealplan -n -r -d
```

```
mosquitto_sub -h 127.0.0.1 -p 1883 -t "grocy/mealplan/today"
```

## How to build

```bash
    docker buildx build --platform linux/arm64 -t alkcxy/grocy2mqtt:0.0.6-arm64 -f Dockerfile.arm64 .
```

## How to push

```bash
    docker push alkcxy/grocy2mqtt:0.0.6-arm64
```

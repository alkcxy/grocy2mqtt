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

## Configuration

Settings are read from the environment, falling back to a `config.ini` that is
gitignored and therefore absent from a clean checkout:

| Environment | `config.ini` | Required |
|---|---|---|
| `GROCY_HOST` | `[grocy] host` | yes |
| `GROCY_API_KEY` | `[grocy] api_key` | yes |
| `MQTT_HOST` | `[mqtt] host` | yes |
| `MQTT_USER` | `[mqtt] user` | no |
| `MQTT_PWD` | `[mqtt] pwd` | no |

## Images

Images are built and pushed by GitHub Actions for `linux/amd64` and
`linux/arm64` under a single tag, so no architecture suffix is needed:

- a push to `master` publishes `alkcxy/grocy2mqtt:latest`
- a tag `vX.Y.Z` publishes `alkcxy/grocy2mqtt:X.Y.Z` and `alkcxy/grocy2mqtt:X.Y`
- a pull request builds and smoke-tests the image without pushing it

The workflow needs the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository
secrets.

To build one by hand:

```bash
    docker buildx build --platform linux/amd64,linux/arm64 -t alkcxy/grocy2mqtt:dev .
```

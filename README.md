# grocy2mqtt
Workaround to connect grocy to home assistant

```
docker run -itd --name mosquitto -p 1883:1883 -p 9001:9001 -v ./mosquitto/config/mosquitto.conf:/mosquitto/config/mosquitto.conf -v ./mosquitto/data:/mosquitto/data eclipse-mosquitto
```

The example config logs to stdout, so `docker logs mosquitto` shows the
broker log and no log volume is needed.

```
mosquitto_pub -h 127.0.0.1 -p 1883 -t grocy/mealplan -n -r -d
```

```
mosquitto_sub -h 127.0.0.1 -p 1883 -t "grocy/mealplan/today"
```

## Development

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`, both
managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync            # create .venv and install the locked versions
uv run python app.py
uv add <package>   # add a dependency and update the lock
uv lock --upgrade  # refresh the lock within the declared ranges
```

`uv sync` installs the exact versions in `uv.lock`, which is the same set the
image gets, so a local run and the container cannot drift apart. uv fetches a
matching Python itself, so no system Python 3.13 is required.

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

Images are built in exactly three cases and no other:

- a push to `master` publishes `alkcxy/grocy2mqtt:latest`
- a tag `vX.Y.Z` publishes `alkcxy/grocy2mqtt:X.Y.Z` and `alkcxy/grocy2mqtt:X.Y`
- adding the `build-docker` label to a pull request publishes it under the
  branch name, so a feature branch can be deployed and tried out before it is
  merged. The label is removed once the run finishes, so a later commit does
  not silently republish

Ordinary pull request commits build nothing.

The workflow needs the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository
secrets.

To build one by hand:

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t alkcxy/grocy2mqtt:dev .
```

There is a single `Dockerfile` for both architectures: buildx cross-builds it,
and every dependency in the lock is either pure Python or ships an `aarch64`
wheel, so nothing needs compiling on the Pi.

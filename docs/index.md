# nio-bot uptime kuma integration
This is a simple plugin to ease integration with uptime kuma.

## Installing
You can install with `pip`:
```bash
pip install nio-bot-uptime-kuma
```
or from source:
```bash
pip install git+https://github.com/nexy7574.co.uk/niobot-uptime-kuma.git
```

## Usage
```python
import niobot
from niobot.utils.uptime_kuma import KumaMonitor


client = niobot.NioBot(...)
monitor = KumaMonitor(client, "https://kuma.example.com/api/push/abcdefg")
monitor.start()

client.run(password="abcdefg")
monitor.stop()
```
This example will send a heartbeat ping to https://kuma.example.com/api/push/abcdefg.

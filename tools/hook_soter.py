#!/usr/bin/env python3
# usage:
#   python hook_soter.py
# requires:
#   - frida-server running on the device
#   - agent_soter.compiled.js built with:
#       npm install frida-java-bridge frida-compile
#       npx frida-compile agent_soter.js -o agent_soter.compiled.js

import sys
import time

import frida

PROCESS = "com.tencent.soter.soterserver"


def on_message(message, data):
    if message.get("type") == "send":
        print(message["payload"], flush=True)
    else:
        print(message, flush=True)


def main() -> int:
    device = frida.get_usb_device(timeout=10)
    pid = device.get_process(PROCESS).pid
    session = device.attach(pid)
    with open("agent_soter.compiled.js", "r", encoding="utf-8") as f:
        source = f.read()
    script = session.create_script(source)
    script.on("message", on_message)
    script.load()
    print("ready: pid=%d process=%s" % (pid, PROCESS), flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())

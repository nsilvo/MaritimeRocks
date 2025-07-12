# mqtt_sniffer.py

import paho.mqtt.client as mqtt

# Define event callbacks
def on_connect(client, userdata, flags, rc):
    print(f"[INFO] Connected with result code {rc}")
    client.subscribe("#")  # Subscribe to all topics

def on_message(client, userdata, msg):
    print(f"[MESSAGE] Topic: {msg.topic} | Payload: {msg.payload.decode(errors='ignore')}")

def on_disconnect(client, userdata, rc):
    print(f"[INFO] Disconnected with result code {rc}")

# Create MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# Connect to local Mosquitto broker
client.connect("192.168.1.250", 1883, 60)

# Start the loop
try:
    print("[INFO] Starting MQTT sniffer...")
    client.loop_forever()
except KeyboardInterrupt:
    print("\n[INFO] Exiting...")
    client.disconnect()

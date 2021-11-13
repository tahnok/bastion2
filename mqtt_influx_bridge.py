import json

import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient

topics = ["indoor"]

def save(influx_client, topic, fields):
        x = [{
                "measurement": topic,
                "fields": fields
            }]
        try:
            influx_client.write_points(x)
        except Exception as e:
                print(f"Exception {e}")

def main():
    influxdb_client = InfluxDBClient(host="192.168.2.8", database="hummingbird")

    def on_connect(client, userdata, flags, rc):
        print("Connected")

        for topic in topics:
            client.subscribe(topic)

    def on_message(client, userdata, msg):
        print(f"new message on {msg.topic}")
        body = json.loads(msg.payload.decode("utf-8"))
        save(influxdb_client, msg.topic, body)
        print("saved")

    mqtt_client = mqtt.Client()
    mqtt_client.enable_logger()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect("localhost", 1883, 60)

    mqtt_client.loop_forever()


if __name__ == "__main__":
    main()

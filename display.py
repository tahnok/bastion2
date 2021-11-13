import json

import paho.mqtt.client as mqtt

from waveshare_epd import epd2in9
from PIL import Image,ImageDraw,ImageFont

import numpy as np
import matplotlib.pyplot as plt

WHITE = 255
BLACK = 0

class Data:
    def __init__(self, temperature, pressure, humidity):
        self.temperature = temperature
        self.pressure = pressure
        self.humidity = humidity

class EPaper():
    def __init__(self):

        self.epd = epd2in9.EPD()
        self.epd.init(self.epd.lut_full_update)
        self.epd.Clear(0xFF)
        self.smol_font = ImageFont.truetype('DejaVuSansMono.ttf', 10)
        self.medium_font = ImageFont.truetype('DejaVuSansMono.ttf', 16)
        self.large_font = ImageFont.truetype('DejaVuSansMono.ttf', 34)


    def draw(self, data):
            section_width = self.epd.height // 3
            section_height = self.epd.width

            screen = Image.new('1', (self.epd.height, self.epd.width), WHITE)  # 255: clear the frame
            draw = ImageDraw.Draw(screen)

            temperature = "{:.1f}C".format(data.temperature)
            draw.text((10, 10), temperature, font = self.large_font, fill = BLACK)

            humidity = "{:.1f}%".format(data.humidity)
            draw.text((10, 45), humidity, font = self.large_font, fill = BLACK)

            pressure = "{:.1f}hPa".format(data.pressure)
            draw.text((10, 80), pressure, font = self.large_font, fill = BLACK)


#            line_height = 16
#            temp = ("temp", "{:.1f} C".format(packet.temperature))
#            pressure = ("pres", "{:.1f} kPa".format(packet.pressure / 1000.0))
#            battery_voltage = ("batt", "{:.1f} V".format(packet.battery_voltage))
#            flight_number = ("flit", str(packet.flight_number))
#            packet_number = ("pckt", str(packet.packet_number))
#            for line, (label, value) in enumerate([temp, pressure, battery_voltage, flight_number, packet_number]):
#                draw.text((4, (section_height) + 10 + (line * line_height)), label, font = self.smol_font, fill = BLACK)
#                draw.text((36, (section_height) + 8 + (line * line_height)), value, font = self.medium_font, fill = BLACK)
#
#
#            draw.line((0, section_height, self.epd.width, section_height))
#            draw.line((0, 2 * section_height, self.epd.width, 2 * section_height))
#
#            graph = plot_to_image(self.pressures, section_width, section_height)
##
#            screen.paste(graph, (0, 2 * section_height + 2))

            self.epd.display(self.epd.getbuffer(screen.rotate(180)))

topics = ["indoor"]

if __name__ == '__main__':
    e = EPaper()
    body = {'pressure': 1000.9069290864675, 'temperature': 25.746875, 'humidity': 36.70866768746555}
    e.draw(Data(temperature=body["temperature"], humidity=body["humidity"], pressure=body["pressure"]))

    def on_connect(client, userdata, flags, rc):
        print("Connected")

        for topic in topics:
            client.subscribe(topic)

    def on_message(client, userdata, msg):
        print(f"new message on {msg.topic}")
        body = json.loads(msg.payload.decode("utf-8"))
        print(body)
        e.draw(Data(temperature=body["temperature"], humidity=body["humidity"], pressure=body["pressure"]))

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    mqtt_client.connect("localhost", 1883, 60)

    mqtt_client.loop_forever()

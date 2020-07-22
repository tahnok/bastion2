"""
RFM9x to influxdb bridge

Learn Guide: https://learn.adafruit.com/lora-and-lorawan-for-raspberry-pi
"""
import struct


import board
import busio
import adafruit_rfm9x

from digitalio import DigitalInOut, Direction, Pull

from influxdb import InfluxDBClient

from waveshare_epd import epd2in9
from PIL import Image,ImageDraw,ImageFont


import threading, queue

import crc8


epaper_queue = queue.Queue()
influxdb_queue = queue.Queue()

class Packet:
    def __init__(self, raw_packet):
        self.raw_packet = raw_packet
        parsed_packet = struct.unpack("ddfIIBxxx", raw_packet) # https://docs.python.org/3.7/library/struct.html#format-strings
        (
            self.temperature,
            self.pressure,
            self.battery_voltage,
            self.packet_number,
            self.flight_number,
            self.crc,
        ) = parsed_packet

    def validate(self):
        checksum = crc8.crc8()
        checksum.update(self.raw_packet[0:28])
        checksum = int.from_bytes(checksum.digest(), byteorder='big') 
        return checksum == self.crc

    @property
    def altitude(self):
        """Altitude calculation from I forget where"""

        sealevel_pressure = 102800 
        return (
            ((sealevel_pressure / self.pressure) ** (1 / 5.257) - 1)
            * (self.temperature + 273.15)
        ) / 0.0065

    def for_influxdb(self):
        """Format from https://github.com/influxdata/influxdb-python#examples"""
        return [{
            "measurement": "packet",
            "fields": {
                "flight_number": self.flight_number,
                "packet_number": self.packet_number,
                "pressure": self.pressure,
                "battery_voltage": self.battery_voltage,
                "altitude": self.altitude,
                "temperature": self.temperature,
                "valid": self.validate(),
            },
        }]


def get_rfm9x():
    CS = DigitalInOut(board.D26)
    RESET = DigitalInOut(board.D16)
    spi = busio.SPI(board.SCK_1, MOSI=board.MOSI_1, MISO=board.MISO_1)

    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 915.0)
    return rfm9x


def loop(rfm9x):
    """May need to run with PYTHONUNBUFFERED=1 if you aren't seeing . and !"""

    while True:
        print(".", end="")
        raw_packet = rfm9x.receive()
        if raw_packet is None:
            continue

        try:
            parsed_packet = Packet(raw_packet)
            parsed_packet.validate()
        except struct.error:
            print("Invalid packet")
            print(raw_packet)
            continue

        epaper_queue.put(parsed_packet)
        influxdb_queue.put(parsed_packet)
        print("!", end="")


class EPaper():
    def __init__(self, queue):
        self.queue = queue

        self.epd = epd2in9.EPD()
        self.epd.init(self.epd.lut_full_update)
        self.epd.Clear(0xFF)
        self.smol_font = ImageFont.truetype('DejaVuSansMono.ttf', 10)
        self.medium_font = ImageFont.truetype('DejaVuSansMono.ttf', 16)
        self.large_font = ImageFont.truetype('DejaVuSansMono.ttf', 34)

        self.pressures = np.array([])

    def loop(self):
        while True:
            packet = self.queue.get()
            self.pressures = np.append(self.pressures, packet.pressure)
            if len(self.pressures) % 20 == 0:
                self.draw(packet)

    def draw(self, packet):
            section_height = self.epd.height // 3
            section_width = self.epd.width

            screen = Image.new('1', (self.epd.width, self.epd.height), WHITE)  # 255: clear the frame
            draw = ImageDraw.Draw(screen)

            draw.text((10, 2), "altitude:", font = self.smol_font, fill = BLACK)

            height = "{:.1f}M".format(packet.altitude)
            draw.text((0, 20), height, font = self.large_font, fill = BLACK)

            max_pressure = self.pressures.max() / 1000.0
            average_pressure  = np.average(self.pressures) / 1000.0
            max_height = "max:{:.1f}M/avg:{:.1f}M".format(max_pressure, average_pressure)
            draw.text((0, self.epd.height / 3 - 14), max_height, font = self.smol_font, fill = BLACK)

            line_height = 16
            temp = ("temp", "{:.1f} C".format(packet.temperature))
            pressure = ("pres", "{:.1f} kPa".format(packet.pressure / 1000.0))
            battery_voltage = ("batt", "{:.1f} V".format(packet.battery_voltage))
            flight_number = ("flit", str(packet.flight_number))
            packet_number = ("pckt", str(packet.packet_number))
            for line, (label, value) in enumerate([temp, pressure, battery_voltage, flight_number, packet_number]):
                draw.text((4, (section_height) + 10 + (line * line_height)), label, font = self.smol_font, fill = BLACK)
                draw.text((36, (section_height) + 8 + (line * line_height)), value, font = self.medium_font, fill = BLACK)


            draw.line((0, section_height, self.epd.width, section_height))
            draw.line((0, 2 * section_height, self.epd.width, 2 * section_height))

            graph = plot_to_image(self.pressures, section_width, section_height)

            screen.paste(graph, (0, 2 * section_height + 2))

            self.epd.display(self.epd.getbuffer(screen.rotate(180)))

def plot_to_image(data, width, height, dpi = 100):
    plt.figure(figsize=[width / dpi, height / dpi], dpi=dpi)

    fig = plt.gcf()
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)

    plt.plot(data, linewidth = 1)

    fig.canvas.draw()

    image =  Image.frombytes('RGB', fig.canvas.get_width_height(),fig.canvas.tostring_rgb())

    plt.close()

    return image


import numpy as np
import matplotlib.pyplot as plt

WHITE = 255
BLACK = 0

class InfluxDB():
    def __init__(self, queue):
        self.client = InfluxDBClient(host="192.168.1.20", database="hummingbird")
        self.queue = queue

    def loop(self):
        while True:
            try:
                packet = self.queue.get()
                self.client.write_points(packet.for_influxdb())
            except Exception as e:
                print(f"Exception {e}")


def main():
    rfm9x = get_rfm9x()
    epaper_thread = EPaper(epaper_queue)
    influxdb_thread = InfluxDB(influxdb_queue)
    threading.Thread(target=influxdb_thread.loop).start()
    threading.Thread(target=epaper_thread.loop).start()
    print("Starting loop")
    loop(rfm9x)


def fake_packet():
    return Packet(bytearray(b'b\xdd\xbeAL\x86\x01\x00\x00\x00\x00\x00r\x02\x00\x00*\x00\x00\x00'))

if __name__ == "__main__":
    # epaper_thread = EPaper(epaper_queue)
    # epaper_thread.draw(fake_packet())
    # epd2in9.epdconfig.module_exit()

    main()

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


epaper_queue = queue.Queue()
influxdb_queue = queue.Queue()

class Packet:
    def __init__(self, raw_packet):
        parsed_packet = struct.unpack("fifII", raw_packet) # https://docs.python.org/3.7/library/struct.html#format-strings
        (
            self.temperature,
            self.pressure,
            self.battery_voltage,
            self.packet_number,
            self.flight_number,
        ) = parsed_packet

    @property
    def altitude(self):
        """Altitude calculation from I forget where"""

        sealevel_pressure = 101325
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
        print(raw_packet)

        try:
            parsed_packet = Packet(raw_packet)
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
        self.font24 = ImageFont.truetype('FiraCode-Regular.ttf', 24)

    def loop(self):
        while True:
            packet = self.queue.get()
            self.draw(packet)

    def draw(self, packet):
            Himage = Image.new('1', (self.epd.height, self.epd.width), 255)  # 255: clear the frame
            draw = ImageDraw.Draw(Himage)
            temp = "{:.2f} C".format(packet.temperature)
            draw.text((10, 0), temp, font = self.font24, fill = 0)

            pressure = "{:.2f} kPa".format(packet.pressure / 1000.0)
            draw.text((10, 25), pressure, font = self.font24, fill = 0)

            self.epd.display(self.epd.getbuffer(Himage.rotate(180)))

    # epd2in9.epdconfig.module_exit()

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
    epaper_thread = EPaper(epaper_queue)
    epaper_thread.draw(fake_packet())

    # main()

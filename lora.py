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
    CS = DigitalInOut(board.CE1)
    RESET = DigitalInOut(board.D25)
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 915.0)
    return rfm9x


def loop(rfm9x, influxdb):
    """May need to run with PYTHONUNBUFFERED=1 if you aren't seeing . and !"""

    while True:
        print(".", end="")
        raw_packet = rfm9x.receive()
        if raw_packet is None:
            continue

        try:
            parsed_packet = Packet(raw_packet)
        except struct.error:
            print("Invalid packet")
            print(raw_packet)
            continue

        store_packet(influxdb, parsed_packet)
        print("!", end="")

def store_packet(influxdb, packet):
    try:
        influxdb.write_points(packet.for_influxdb())
    except Exception as e:
        print(f"Exception {e}")


def main():
    rfm9x = get_rfm9x()
    influxdb = InfluxDBClient(host="192.168.1.20", database="hummingbird")
    print("Starting loop")
    loop(rfm9x, influxdb)


if __name__ == "__main__":
    main()

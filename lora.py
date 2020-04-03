"""
Learn Guide: https://learn.adafruit.com/lora-and-lorawan-for-raspberry-pi
"""
import asyncio
import json
import time
import struct
import sys
import threading

from datetime import datetime
from asyncio import Queue

import board
import busio
import adafruit_rfm9x

from digitalio import DigitalInOut, Direction, Pull


import websockets


class Packet:
    def __init__(self, raw_packet):
        self.now = datetime.now()
        parsed_packet = struct.unpack('fifII', raw_packet)
        self.temperature, self.pressure, self.battery_voltage, self.packet_number, self.flight_number = parsed_packet

    def __str__(self):
        return "%fm, %d, %s, %d, %fC, %d Pa, %fV" %  (self.altitude(), self.flight_number, self.now.strftime('%H:%M:%S'), self.packet_number, self.temperature, self.pressure, self.battery_voltage)

    def altitude(self):
        sealevel_pressure = 101325
        return (((sealevel_pressure/self.pressure)**(1/5.257)-1)*(self.temperature+273.15))/0.0065

    def to_json(self):
        structured = {
                "flight_number": self.flight_number,
                "packet_number": self.packet_number,
                "received_at": str(self.now),
                "pressure": self.pressure,
                "battery_voltage": self.battery_voltage,
                "altitude": self.altitude(),
                "temperature": self.temperature
                }
        return json.dumps(structured)


def lora_setup():
    # Configure RFM9x LoRa Radio
    CS = DigitalInOut(board.CE1)
    RESET = DigitalInOut(board.D25)
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

    rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, 915.0)
    rfm9x.tx_power = 23

    print("RFM9x: detected")
    return rfm9x


async def lora_loop(rfm9x):
    while True:
        raw_packet = rfm9x.receive()
        if raw_packet is not None:
            try:
                parsed_packet = Packet(raw_packet)
            except struct.error:
                print("Invalid packet")
                print(raw_packet)
                continue
            print(parsed_packet)
            for subscriber in subscribers:
                subscriber.put_nowait(parsed_packet.to_json())
            await asyncio.sleep(1)
        sys.stdout.flush()

        await asyncio.sleep(0.1)

async def lora_main():
    rfm9x = lora_setup()
    await lora_loop(rfm9x) 


async def webhook_handler(websocket, path):
    print("Connected!")
    queue = Queue()
    try:
        subscribers.add(queue)
        print("queue added")
        print(len(subscribers))
        while True:
            packet = await queue.get()
            print(f"Sending packet {packet}")
            await websocket.send(packet)
    finally:
        print("removing queue")
        subscribers.remove(queue)

    # while True:
    #     print("Waiting for queue..")
    #     packet = queue.get()
    #     print(f"Waiting to send {packet}..")
    #     await websocket.send(packet)
    #     print("Sent")


subscribers = set()

def main():
    eventloop = asyncio.get_event_loop()
    start_server = websockets.serve(webhook_handler, "0.0.0.0", 5678)
    eventloop.run_until_complete(start_server)
    eventloop.run_until_complete(lora_main())
    eventloop.run_forever()

if __name__ == "__main__":
    main()

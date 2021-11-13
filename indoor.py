import logging
import json
import time
 
import board
import busio
import adafruit_bme280


import paho.mqtt.publish as publish


def main():
    # Create library object using our Bus I2C port
    i2c = busio.I2C(board.SCL, board.SDA)
    bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
     
     
    while True:
        data = {
                "pressure": bme280.pressure,
                "temperature": bme280.temperature,
                "humidity": bme280.humidity
                }

        payload = json.dumps(data)

        try:
            publish.single("indoor", payload, hostname="localhost")
        except Exception as e:
                print(f"Exception {e}")
        print("\nTemperature: %0.1f C" % bme280.temperature)
        print("Humidity: %0.1f %%" % bme280.humidity)
        print("Pressure: %0.1f hPa" % bme280.pressure)
        time.sleep(2)

if __name__ == "__main__":
    main()

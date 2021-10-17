import sys
import time
import utime
import framebuf
from machine import Pin, I2C, Timer
from ssd1306 import SSD1306_I2C
from rotary_irq import RotaryIRQ

_oled_w = 128
_oled_h = 32
oled = SSD1306_I2C(_oled_w, _oled_h, i2c=I2C(0,sda=Pin(0), scl=Pin(1), freq=400000))

oled.text("test",0,0)
oled.show()

r = RotaryIRQ(pin_num_clk=12, pin_num_dt=13, pin_num_btn=14, reverse=False, range_mode=RotaryIRQ.RANGE_UNBOUNDED)
def button_pressed(args):
    print("{} passed, Button pressed".format(args))

def ccw_turn(args):
    print("{} passed, CCW turn".format(args))
def cw_turn(args):
    print("{} passed, CW turn".format(args))
r.add_btn_listener(button_pressed, (1, 1))
r.add_cw_listener(cw_turn, 1)
r.add_ccw_listener(ccw_turn, 2)
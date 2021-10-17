# The MIT License (MIT)
# Copyright (c) 2020 Mike Teachman
# https://opensource.org/licenses/MIT

# Platform-independent MicroPython code for the rotary encoder module

# Documentation:
#   https://github.com/MikeTeachman/micropython-rotary
from machine import Pin
from micropython import const
import micropython

_DIR_CW = const(0x10)  # Clockwise step
_DIR_CCW = const(0x20)  # Counter-clockwise step

# Rotary Encoder States
_R_START = const(0x0)
_R_CW_1 = const(0x1)
_R_CW_2 = const(0x2)
_R_CW_3 = const(0x3)
_R_CCW_1 = const(0x4)
_R_CCW_2 = const(0x5)
_R_CCW_3 = const(0x6)
_R_ILLEGAL = const(0x7)

_transition_table = [

    # |------------- NEXT STATE -------------|            |CURRENT STATE|
    # CLK/DT    CLK/DT     CLK/DT    CLK/DT
    #   00        01         10        11
    [_R_START, _R_CCW_1, _R_CW_1,  _R_START],             # _R_START
    [_R_CW_2,  _R_START, _R_CW_1,  _R_START],             # _R_CW_1
    [_R_CW_2,  _R_CW_3,  _R_CW_1,  _R_START],             # _R_CW_2
    [_R_CW_2,  _R_CW_3,  _R_START, _R_START | _DIR_CW],   # _R_CW_3
    [_R_CCW_2, _R_CCW_1, _R_START, _R_START],             # _R_CCW_1
    [_R_CCW_2, _R_CCW_1, _R_CCW_3, _R_START],             # _R_CCW_2
    [_R_CCW_2, _R_START, _R_CCW_3, _R_START | _DIR_CCW],  # _R_CCW_3
    [_R_START, _R_START, _R_START, _R_START]]             # _R_ILLEGAL

_transition_table_half_step = [
    [_R_CW_3,            _R_CW_2,  _R_CW_1,  _R_START],
    [_R_CW_3 | _DIR_CCW, _R_START, _R_CW_1,  _R_START],
    [_R_CW_3 | _DIR_CW,  _R_CW_2,  _R_START, _R_START],
    [_R_CW_3,            _R_CCW_2, _R_CCW_1, _R_START],
    [_R_CW_3,            _R_CW_2,  _R_CCW_1, _R_START | _DIR_CW],
    [_R_CW_3,            _R_CCW_2, _R_CW_3,  _R_START | _DIR_CCW]]

_STATE_MASK = const(0x07)
_DIR_MASK = const(0x30)


def _wrap(value, incr, lower_bound, upper_bound):
    range = upper_bound - lower_bound + 1
    value = value + incr

    if value < lower_bound:
        value += range * ((lower_bound - value) // range + 1)

    return lower_bound + (value - lower_bound) % range

def _bound(value, incr, lower_bound, upper_bound):
    return min(upper_bound, max(lower_bound, value + incr))
        
def _cw_trigger(rotary_instance):
    for listener in rotary_instance._cw_listener:
        listener[0](listener[1])
        
def _ccw_trigger(rotary_instance):
    for listener in rotary_instance._ccw_listener:
        listener[0](listener[1])
        
def _btn_trigger(rotary_instance):
    for listener in rotary_instance._btn_listener:
        listener[0](listener[1])


class Rotary(object):

    RANGE_UNBOUNDED = const(1)
    RANGE_WRAP = const(2)
    RANGE_BOUNDED = const(3)

    def __init__(
        self,
        min_val, 
        max_val, 
        reverse, 
        range_mode, 
        half_step,
        pin_num_clk,
        pin_num_dt,
        pin_num_btn,
        ):
        
        self._min_val = min_val
        self._max_val = max_val
        self._reverse = -1 if reverse else 1
        self._range_mode = range_mode
        self._value = min_val
        self._state = _R_START
        self._half_step = half_step
        self._cw_listener = []
        self._ccw_listener = []
        self._btn_listener = []
        self._pin_clk = pin_num_clk
        self._pin_dt = pin_num_dt
        self._pin_btn = pin_num_btn

    def set(self, value=None, min_val=None,
            max_val=None, reverse=None, range_mode=None):
        # disable DT, CLK and BTN pin interrupts
        self._hal_disable_irq()

        if value is not None:
            self._value = value
        if min_val is not None:
            self._min_val = min_val
        if max_val is not None:
            self._max_val = max_val
        if reverse is not None:
            self._reverse = -1 if reverse else 1
        if range_mode is not None:
            self._range_mode = range_mode
        self._state = _R_START

        # enable DT and CLK pin interrupts
        self._hal_enable_irq()

    def value(self):
        return self._value

    def reset(self):
        self._value = 0

    def close(self):
        self._hal_close()

    def add_cw_listener(self, func, args):
        self._cw_listener.append((func, args))

    def remove_cw_listeners(self, l):
        self._cw_listener = []
        
    def add_ccw_listener(self, func, args):
        self._ccw_listener.append((func, args))

    def remove_ccw_listeners(self):
        self._ccw_listener = []
        
    def add_btn_listener(self, func, args):
        self._btn_listener.append((func, args))
        
    def remove_btn_listeners(self):
        self._btn_listener = []
        
    def remove_all_listeners(self):
        self._btn_listener = []
        self._cw_listener = []
        self._ccw_listener = []
    
    def _process_rotary_button(self, pin):
        micropython.schedule(_btn_trigger, self)
    
    def _process_rotary_pins(self, pin):
        old_value = self._value
        clk_dt_pins = (self._hal_get_clk_value() <<
                       1) | self._hal_get_dt_value()
        # Determine next state
        if self._half_step:
            self._state = _transition_table_half_step[self._state &
                                                      _STATE_MASK][clk_dt_pins]
        else:
            self._state = _transition_table[self._state &
                                            _STATE_MASK][clk_dt_pins]
        direction = self._state & _DIR_MASK

        incr = 0
        if direction == _DIR_CW:
            incr = 1
        elif direction == _DIR_CCW:
            incr = -1

        incr *= self._reverse

        if self._range_mode == self.RANGE_WRAP:
            self._value = _wrap(
                self._value,
                incr,
                self._min_val,
                self._max_val)
        elif self._range_mode == self.RANGE_BOUNDED:
            self._value = _bound(
                self._value,
                incr,
                self._min_val,
                self._max_val)
        else:
            self._value = self._value + incr
            
        try:
            if direction == _DIR_CW and len(self._cw_listener) != 0:
                micropython.schedule(_cw_trigger, self)
            if direction == _DIR_CCW and len(self._ccw_listener) != 0:
                micropython.schedule(_ccw_trigger, self)
        except:
            pass

    def _enable_clk_irq(self, callback=None):
        self._pin_clk.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=callback)
        
    def _enable_dt_irq(self, callback=None):
        self._pin_dt.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=callback)
        
    def _disable_clk_irq(self):
        self._pin_clk.irq(handler=None)
        
    def _disable_dt_irq(self):
        self._pin_dt.irq(handler=None)   

    def _hal_get_clk_value(self):
        return self._pin_clk.value()
        
    def _hal_get_dt_value(self):
        return self._pin_dt.value()   
    
    def _hal_enable_irq(self):
        self._enable_clk_irq(self._process_rotary_pins)        
        self._enable_dt_irq(self._process_rotary_pins)   

    def _hal_disable_irq(self): 
        self._disable_clk_irq()
        self._disable_dt_irq()     

    def _hal_close(self):
        self._hal_disable_irq()




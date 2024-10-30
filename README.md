# Readout of the current measured by the Kethley 6485 via TCP
A microcontroller board with an ethernet port is used to read the analog output
of the PicoAmp meter. The value is sent to ethernet with TCP.

The microcontroller is a ESP32-based board WT32-ETH01
https://github.com/egnor/wt32-eth01

The analog output is readed with a 16-bit ADC, connected via I2C to the board
https://www.mikroe.com/adc-8-click?srsltid=AfmBOoqZEmPZ9MGbNtYGYMLj2gfj2xJ5dwkVnUDY3hvhHKmOwEfDkgbo

The project is deleveloped in micropython, using the external library from:
https://github.com/robert-hh/ads1x15
for the ADC.

The instrument provides RS232 communication from which one could retrieve the reading. But
this would set the meter in remote mode, and will interfere with the display and the readings. 
The analog output on the other hand, does not provide the range of the measurement. It gives 
only a 0-2Volt signal proportional to the current in the ranges 2 nA, 20 nA, 0.2 uA, 2 uA, ...
In AUTORANGE, the device would scale-up when passing 105% of the upper edge, and scale-down under
10% of the range.

In order to retrieve the absolute value in the fastest way, with minimum intrusion to the 
device. The MCU assumes there is no change in scale until one of those thresholds is passed, 
and only retrieve the range, via RS232, once the next readings are back within the limits. 

In addition, the ADC is set to sample at 32 SPS (with a 40 ms interval), in order to catch fast 
variations, specially when changing the range. But it will push the data to ethernet at slower
rates. A base rate of ~1 reading/second in case there are no large variations. And a rate of 
~300 ms when the next reading is over 5% difference respect to a moving average filter.

The project is meant to work with the OCL new control system. And the device will push data 
continuously after sending the instruction 'pull' to the board.




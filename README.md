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





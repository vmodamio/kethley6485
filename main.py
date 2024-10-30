"""
NOTE: Ethernet failed: On the prompt RELP, write lan.active(False)
KETHLEY 6485 picoAmp meter. Controller board
ESP32 based WT32-ETH01 board, with ethernet.

The board is program to act as a TCP server, providing to the client
a continuous readout of the Beam current.
To be as responsive as possible and interfere as minimum with the phisical
device, the board reads only the Analog Output from the Kethley, using one 
ADC channel. And only when the measurement changes to another scale, it 
fetches via RS-232 the current range.

The only command necessary to retrieve the range is 
SENS:CURR:RANG?
Additionally, to set the kethley in local/remote mode
SYST:REM and SYST:LOC

Analog output in AUTO: 
The kethley range is 2.0 nA, 20 nA, 0.2 uA, etc... Will change scale up over 105%
of the value. I.e. over 21 nA, etc And will scale down below the value of the previous
range (below 10%). Note also, the integration time in default for the kethley is around 
16 ms.

Typical range change transient
See the PicoAmp manual, but upscaling is worst while downscaling is almost negligible.

"""
import time
import network
import machine 
import socket
import array
import struct
from ads1x15 import ADS1115

ipaddr = '192.168.0.43'
port = 3333
n_samples = 8
_ADC_RATE = const(2) ## [8, 16, 32, 64, 128, 250, 475, 860] SPS
_ADC_SLEEP_ms = 40 # at 32 SPS is 31ms rate, so 50ms is safe
_ADC_CHANNEL = const(0)
TCPSLOWN = 25 # about 1 sec
TCPFASTN = 8  # about 320 ms
tcp_sample = TCPSLOWN
TRIGG_FAST = 0.02 # fraction of vrange difference over previous average to trigger fast send
_ADC_SAMPLES_TRANSIENT = 8 # number of samples within thresholds before requesting getrange
adc_sample = 0  # -1: do nothing, 0: request getrange, >0 count down


lan = network.LAN(mdc=machine.Pin(23), mdio=machine.Pin(18), phy_type=network.PHY_LAN8720, phy_addr=1, power=machine.Pin(16), id=0)

lan.ifconfig((ipaddr, '255.255.255.0', '192.168.0.1', '8.8.8.8'))
lan.active(True)

addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]
"""
KETHLEY RS-232 baud: 57600, 38400, 19200, 9600 8 bit parity None 1 stop bit, terminator is LF or CR or LFCR or CRLF
Pin out is: 
    pin 1: DCD data carrierdetect
    pin 2: TXD
    pin 3: RXD
    pin 4: DTR 
    pin 5: GND
    pin 6: DSR
    pin 7: RTS
    pin 8: CTS
    pin 9: No connected
"""
## here: check if setting the tx rx with machine.Pin() works. Other, check if the RX pin is actually 5 and not 
## the 
uart2 = machine.UART(2, tx=machine.Pin(17), rx=machine.Pin(5))
uart2.init(baudrate=57600, bits=8, parity=None)
cmd_remote = b'SYST:REM\r\n'
cmd_local = b'SYST:LOC\r\n'
cmd_range = b'CURR:RANG?\r\n'
cmd_terminator = b'\r\n'

"""
ADC for the Kethley analog output. The kethley produces a signal from -2 to 2V signal for the range, inverted.
Example: a 10.5 nA in the 20 nA range would produce -2.0*10.5/20 = -1.05v

The ADC from the ESP boards are 12-bit (4095), and measures until Vref (around 1.1V). The pin can be programmed
with 4 different attenuation factors to reach different ranges. 
ADC_ATTEN_DB_11: range (150 mV to 2450 mV)

The external ADC ADS1115 is 16-bit with range 0-4.096V in gain 1.

That means: the Kethley analog out need to be inverted, and protected to not exceed 2400 mV.
"""
#adc = machine.ADC(machine.Pin(36))
#adc.atten(machine.ADC.ATTN_11DB)

i2c = machine.I2C(0, sda=machine.Pin(15), scl=machine.Pin(14))
adc = ADS1115(i2c, address=72, gain=1)
#adc.set_conv(4,0) # rate 4: 128 SPS


diff_threshold = 0.3   # Volt

prev = 0
rval = 0
#irange = 2.1e-9 
vrange = 2.0
scaling_factor = 2/3.0  ## account for Jon W. OPA circuit
irange = 0.0 ## from now show current in nA
vthres = (0.1*vrange, 1.05*vrange)
zerothres = 0.1
#
""" The Kethley range answer will be a number in the format 2.100000E-0N
"""
def getrange():
    uart2.write(cmd_remote)
    time.sleep_ms(25)
    uart2.write(cmd_range)
    time.sleep_ms(15)
    rangedata = uart2.readline()
    time.sleep_ms(2)
    uart2.write(cmd_local)
    if rangedata is not None:
        rangedata = rangedata.rstrip(cmd_terminator)
        try:
            val = float(rangedata) / 2.1e-9
        except:
            return 0
        else:
            return val
    else:
        return 0


""" Cheap and fast implementation of a moving average filter using 
a simple array and tracking the position with an external variable.
Once created an instance of the generator
mav = moving_average_window()
one have to call 
next(mav) to go to the next yield, and then
mav.send(value) will return the average value
"""
def moving_average_window():
    average = 0.0
    pos = 0
    buffer = array.array('d', [0 for _ in range(n_samples)])
    while True:
        newval = yield
        average-= buffer[pos]
        buffer[pos] = newval/n_samples
        average+= buffer[pos]
        pos = (pos+1)%n_samples
        yield average


mav = moving_average_window()
average = 0.0

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
s.bind(addr)
s.listen(1)

while True:
    #lan.active(True)
    conn, addr = s.accept()
    data = conn.recv(32)
    if not data: break
    elif (data[:-2] == b'pull'):
        while True:
            rval = scaling_factor*adc.raw_to_v(adc.read(_ADC_RATE,_ADC_CHANNEL))

            time.sleep_ms(_ADC_SLEEP_ms)

            if (rval > vthres[1]) or ((rval < vthres[0]) and (irange > 1) and (average > vthres[0])):
                adc_sample = _ADC_SAMPLES_TRANSIENT
            elif (adc_sample > 0):
                adc_sample+= -1
            elif (adc_sample == 0):
                r = getrange()
                if (r > 0):
                    irange = r
                    adc_sample = -1
                    tcp_sample =  0 if ((TCPSLOWN - tcp_sample) > TCPFASTN) else tcp_sample + TCPFASTN - TCPSLOWN  
                else:
                    adc_sample = _ADC_SAMPLES_TRANSIENT


            if tcp_sample:
                if (abs(rval-average) > TRIGG_FAST*vrange) and (adc_sample < 0):
                    if (tcp_sample < TCPSLOWN - TCPFASTN):
                        tcp_sample = 0
                    else:
                        tcp_sample = 0 if ((TCPSLOWN - tcp_sample) > TCPFASTN) else tcp_sample + TCPFASTN - TCPSLOWN 
                else:
                    tcp_sample+= -1

            if tcp_sample == 0: 
                tcp_sample = TCPSLOWN
                try:
                    sdata = struct.pack('f2s', rval*irange , b'\r\n') # constant 6 byte message
                    conn.send(sdata)
                except:
                    break
                    #sdata = struct.pack('f2s', 9.19191, b'\r\n')
                    #conn.send(sdata)

            next(mav)
            average = mav.send(rval)
    time.sleep(5)
    #uart2.write(b'Adios amigo...')


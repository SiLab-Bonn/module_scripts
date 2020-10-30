#
#   Standalone controller class for Weiss Technik LabEvent climate chamber
#

import logging
import socket
import sys
import time


class WeissLabEvent(object):
    COMMANDS = {
        'start_manual_mode': b'14001',
        'set_temperature': b'11001',
        'get_temperature': b'11004'
    }

    RETURN_CODES = {
        1: "Command is accepted and executed.",
        -5: "Command number transmitted is unidentified!",
        -6: "Too few or incorrect parameters entered!",
        -8: "Data could not be read!",
    }

    DELIM = b'\xb6'

    def __init__(self, ip_address, port=2049):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip_address = ip_address
        self.port = port

    def init(self):
        self.sock.connect((self.ip_address, self.port))

    def _cmd(self, cmd, args=[], device_id=1):
        cmd = self.COMMANDS[cmd]
        cmd += self.DELIM + b'1'
        cmd += self.DELIM + str(device_id).encode('ascii')
        for arg in args:
            cmd += self.DELIM + arg.encode('ascii')
        cmd += b'\r'

        return cmd

    def _recv(self, device_id=1):
        data = self.sock.recv(512)
        
        if self.DELIM not in data:
            ret = data.decode().strip()
            if ret == '1':
                return True
            else:
                logging.error('Received error code {0}: {1}'.format(ret, self.RETURN_CODES[ret]))
                return False
        else:
            ret_device_id, ret = data.split(self.DELIM)
            if int(ret_device_id.decode()) != device_id:
                logging.error('Returning device ID does not match requested device ID!')

            return ret.decode()

    def get_temperature(self, device_id=1):
        cmd = self._cmd('get_temperature', device_id=device_id)
        self.sock.send(cmd)
        return float(self._recv(device_id))

    def start_manual_mode(self, device_id=1):
        cmd = self._cmd('start_manual_mode', args=['1'], device_id=device_id)
        self.sock.send(cmd)
        if not self._recv(device_id):
            logging.error('Unable to tart manual mode!')
            return False
        else:
            return True

    def set_temperature(self, target, device_id=1):
        cmd = self._cmd('set_temperature', args=[str(target)], device_id=device_id)
        self.sock.send(cmd)
        if not self._recv(device_id):
            logging.error('Unable to set temperature!')
            return False
        else:
            return True

    def go_to_temperature(self, target, timeout=600, delta=1):
        self.set_temperature(target)
        for _ in range(timeout):
            temp = self.get_temperature()
            if abs(target - temp) < delta:
                logging.info('Target temperature reached!')
                break
            time.sleep(1)
        else:
            logging.error('Target temperature was not reached within {}s. Maybe the limit is too strict?'.format(timeout))

    def close(self):
        self.sock.close()


if __name__ == '__main__':
    try:
        freezer = WeissLabEvent('192.168.10.2')
        freezer.init()

        temp = freezer.get_temperature()
        print(temp)
        
        freezer.start_manual_mode()
        
        freezer.go_to_temperature(20)
    finally:
        freezer.close()
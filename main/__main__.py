from .dobotplus import Dobot, CustomPosition, MODE_PTP
from configparser import ConfigParser
import os

config = ConfigParser()
if os.path.exists('config.ini'):
    print('Loading config from config.ini')
    config.read('config.ini')
else:
    print('config.ini not found, Asking for port input')
    # List available ports
    from serial.tools import list_ports
    available_ports = list_ports.comports()
    print(f'available ports: {[x.device for x in available_ports]}')
    port = input('Enter the port to connect to (e.g., COM3 or /dev/ttyUSB0): ')
    if port not in [x.device for x in available_ports]:
        print(f'Port {port} not found in available ports.')
        exit(1)
    config['DEFAULT'] = {'port': port}
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    


dobotPort = config['DEFAULT'].get('port', None)

device = Dobot(port=dobotPort)

pose = device.get_pose()
cus = CustomPosition(x=pose.position.x, y=pose.position.y, z=pose.position.z, r=pose.position.r)

print(f'Current Pose: {cus}')

device.clear_alarms()

device._set_sliding_rail_status(enabled=True, version=1)
f = device.home()

device.move_rel(z=40)

# print(device.get_pose())

# print(device.move_to(position=cus))

# print(device.get_pose())

# # Create a custom position
# pos1 = CustomPosition(x=200, y=50, z=50)

# # Move using direct coordinates
# moveto = device.move_to(x=200, y=50, z=50)

# device.get_pose()
device._set_ptp_with_l_cmd(MODE_PTP.MOVJ_XYZ, pose.position.x, pose.position.y, pose.position.z, pose.position.r, 40)


# # Move using custom position
# device.move_to(position=pos1)

print(device.get_pose())

print(device.get_alarms())

device.close()
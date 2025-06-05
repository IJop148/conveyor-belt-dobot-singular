from serial.tools import list_ports
from pydobotplus import Dobot, CustomPosition

available_ports = list_ports.comports()
print(f'available ports: {[x.device for x in available_ports]}')
port = available_ports[0].device

device = Dobot(port=port)
print(device.get_pose())

# Create a custom position
# pos1 = CustomPosition(x=200, y=50, z=50)

# Move using direct coordinates
# device.move_to(x=200, y=50, z=50)

# Move using custom position
# device.move_to(position=pos1)

device.close()
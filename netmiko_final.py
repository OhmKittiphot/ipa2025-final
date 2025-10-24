from netmiko import ConnectHandler
from pprint import pprint
import os

device_ip = os.getenv("ROUTER_IP", "10.0.15.61")
username  = os.getenv("ROUTER_USER", "admin")
password  = os.getenv("ROUTER_PASS", "cisco")

device_params = {
    "device_type": "cisco_ios",
    "ip": device_ip,
    "username": username,
    "password": password,
}

def gigabit_status():
    ans = ""
    with ConnectHandler(**device_params) as ssh:
        up = 0
        down = 0
        admin_down = 0

        # ใช้คำสั่ง show ip interface brief เพื่อดูสถานะ interface ทั้งหมด
        result = ssh.send_command("show ip interface brief", use_textfsm=True)
        gig_list = []

        # result จะเป็น list ของ dict เช่น
        # [{'intf': 'GigabitEthernet1', 'ipaddr': '10.0.15.61', 'status': 'up', 'proto': 'up'}, ...]
        for status in result:
            name = status.get("intf") or status.get("interface")
            if not name or not name.startswith("GigabitEthernet"):
                continue

            state = (status.get("status") or "").lower().strip()
            gig_list.append(f"{name} {state}")

            if state == "up":
                up += 1
            elif "administratively" in state:
                admin_down += 1
            else:
                down += 1

        # รวมข้อความตามรูปแบบในโจทย์
        ans = f"{', '.join(gig_list)} -> {up} up, {down} down, {admin_down} administratively down"

        pprint(ans)
        return ans

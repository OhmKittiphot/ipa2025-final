from netmiko import ConnectHandler
from pprint import pprint
import os

device_ip = os.getenv("ROUTER_IP", "")
username  = os.getenv("ROUTER_USER", "")
password  = os.getenv("ROUTER_PASS", "")

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

def read_motd(ip: str, username: str = None, password: str = None) -> str:
    """
    อ่านค่า MOTD:
      1) ลอง 'show banner motd'
      2) ถ้าไม่ได้ ค่อย parse จาก 'show running-config | s banner motd'
    คืนค่า:
      - ข้อความ MOTD
      - หรือ "Error: No MOTD Configured" ถ้าไม่พบ
    """
    if not ip:
        return "Error: No IP specified"

    import os, re
    from netmiko import ConnectHandler

    dev = {
        "device_type": "cisco_ios",
        "ip": ip,
        "username": username or os.getenv("ROUTER_USER", "admin"),
        "password": password or os.getenv("ROUTER_PASS", "cisco"),
        "fast_cli": True,
    }
    try:
        with ConnectHandler(**dev) as ssh:
            out = ssh.send_command("show banner motd", use_textfsm=True)
            text = out if isinstance(out, str) else str(out)
            text = (text or "").strip()
            if text and "Invalid input" not in text and "Incomplete" not in text:
                text_clean = re.sub(r"(?s)^\s*\^C\s*|\s*\^C\s*$", "", text).strip()
                if text_clean:
                    return text_clean

            run = ssh.send_command("show running-config | s banner motd", use_textfsm=True)
            run = run if isinstance(run, str) else str(run)
            m = re.search(r"banner\s+motd\s+(\S)\n(.*?)\n\1", run, flags=re.S)
            if m:
                return m.group(2).strip()

            return "Error: No MOTD Configured"
    except Exception as e:
        return f"Error: SSH connect failed ({e})"


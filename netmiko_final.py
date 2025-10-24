from netmiko import ConnectHandler
from pprint import pprint
import os, re

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
    อ่าน MOTD แบบดิบ (ไม่ใช้ TextFSM) เพื่อไม่ให้คำ/ช่องว่างหาย
    ขั้นตอน:
      1) terminal length 0 (กัน More)
      2) ถ้า ROUTER_SECRET มี -> เข้า enable
      3) ลอง show banner motd ก่อน
      4) ถ้ายังไม่ได้ ค่อยดึงจาก running-config โดยจับระหว่าง delimiter
    """
    if not ip:
        return "Error: No MOTD Configured"

    dev = {
        "device_type": "cisco_ios",
        "ip": ip,
        "username": username or os.getenv("ROUTER_USER", "admin"),
        "password": password or os.getenv("ROUTER_PASS", "cisco"),
        "fast_cli": True,
    }
    secret = os.getenv("ROUTER_SECRET", "").strip()

    import re
    from netmiko import ConnectHandler

    def _strip_delim_lines(lines):
        # ตัดเฉพาะบรรทัดหัว/ท้ายที่เป็น delimiter (เช่น ^C, #, $, ! ฯลฯ) แต่คงช่องว่างภายในไว้ครบ
        if not lines:
            return lines
        # ตัดหัว
        if lines[0].strip() in ("^C", "#", "$", "!", "%"):
            lines = lines[1:]
        # ตัดท้าย
        if lines and lines[-1].strip() in ("^C", "#", "$", "!", "%"):
            lines = lines[:-1]
        return lines

    def _cleanup(s: str) -> str:
        # ลบ CR, คง whitespace ภายใน
        return (s or "").replace("\r", "")

    try:
        with ConnectHandler(**dev) as ssh:
            # กัน pager และเข้า enable หากมี secret
            ssh.send_command("terminal length 0", expect_string=r"#")
            if secret:
                try:
                    ssh.enable()
                except Exception:
                    pass  # ถ้า user เดิมเป็น priv 15 อยู่แล้ว ก็ข้ามได้

            # 1) พยายามใช้ show banner motd ก่อน (ง่ายและครบสุด)
            raw = ssh.send_command("show banner motd", use_textfsm=False)
            raw = _cleanup(raw)
            # บางรุ่นจะ echo คำสั่งบรรทัดแรก ให้ลบถ้าตรงกัน
            if raw.startswith("show banner motd"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else ""

            lines = [l.rstrip("\n") for l in raw.splitlines()]
            lines = _strip_delim_lines(lines)
            motd = "\n".join(lines).rstrip()

            if motd:  # ได้แล้ว จบเลย
                return motd

            # 2) Fallback: ดึงจาก running-config แบบ section
            out = ssh.send_command("show running-config | section ^banner motd", use_textfsm=False)
            out = _cleanup(out)
            if not out or "Invalid input" in out:
                # IOS บางตัวไม่รองรับ section ใช้ทั้งไฟล์แล้ว regex เอา
                out = ssh.send_command("show running-config", use_textfsm=False)
                out = _cleanup(out)

            text = out if isinstance(out, str) else str(out)
            if "banner motd" not in text:
                return "Error: No MOTD Configured"

            # จับรูปแบบ banner motd <DELIM> ... <DELIM>
            # <DELIM> อาจเป็น ^C, #, $, ! หรืออักขระชุดอื่น
            m = re.search(r"banner\s+motd\s+(\S+)\s*\n(.*?)\n\1", text, flags=re.S)
            if not m:
                # บางเคส delimiter ต่อท้ายในบรรทัดเดียวกัน ให้ดึงแบบหลวมขึ้น
                m = re.search(r"banner\s+motd\s+(\S+)\s*\n(.*)", text, flags=re.S)
                if m:
                    delim = m.group(1)
                    body = m.group(2)
                    # ตัดจนถึง delimiter ถัดไป
                    body = body.split(f"\n{delim}\n")[0]
                    motd2 = body.rstrip()
                    return motd2 if motd2.strip() else "Error: No MOTD Configured"
                return "Error: No MOTD Configured"

            delim = m.group(1)
            body = m.group(2)
            # คืนค่าแบบคงรูป
            return body.rstrip() if body.strip() else "Error: No MOTD Configured"

    except Exception:
        return "Error: No MOTD Configured"

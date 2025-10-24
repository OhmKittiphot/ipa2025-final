import os
import shlex
import subprocess
from typing import Tuple, Optional

# --- Netmiko/TextFSM สำหรับอ่าน MOTD ---
from netmiko import ConnectHandler

# ถ้ามีโฟลเดอร์ ntc-templates ให้ตั้ง env นี้ (ใส่ path ของคุณแทนได้)
if not os.environ.get("NTC_TEMPLATES_DIR"):
    guess = os.path.join(os.getcwd(), "ntc-templates", "templates")
    if os.path.isdir(guess):
        os.environ["NTC_TEMPLATES_DIR"] = guess

def _parse_command(cmd: str) -> Tuple[str, str, str, Optional[str]]:
    """
    รูปแบบที่รองรับ:
    /<student_id> <ip> motd [message...]
    คืนค่า: (student_id, ip, action, message_or_None)
    """
    parts = cmd.strip().split()
    if len(parts) < 3:
        raise ValueError("รูปแบบคำสั่งไม่ถูกต้อง: /<student_id> <ip> motd [message...]")

    # ตัดนำหน้า '/' ถ้ามี
    student_id = parts[0].lstrip('/')
    ip = parts[1]
    action = parts[2].lower()

    message = None
    if len(parts) > 3:
        # ข้อความ MOTD อนุญาตให้มีช่องว่าง => join กลับ
        message = " ".join(parts[3:])

    return student_id, ip, action, message


# -----------------------------
#      ANSIBLE: ตั้ง MOTD
# -----------------------------
def set_motd_with_ansible(ip: str, message: str) -> str:
    """
    ใช้ ad-hoc command โมดูล cisco.ios.ios_banner ตั้ง MOTD
    ต้องมี ansible.cfg + inventory.ini ที่พร้อมใช้งาน
    """
    # ข้อสำคัญ: ข้อความที่มีช่องว่าง ต้องห่อด้วยเครื่องหมายคำพูด
    # state=present เพื่อ set/overwrite MOTD
    module_args = f'banner=motd text="{message}" state=present'
    command = [
        "ansible",
        "-i", "inventory.ini",
        ip,
        "-m", "cisco.ios.ios_banner",
        "-a", module_args,
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return f"ตั้ง MOTD สำเร็จที่ {ip}\n{result.stdout}"
    else:
        return f"ตั้ง MOTD ไม่สำเร็จที่ {ip}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


# -----------------------------
#  NETMIKO/TEXTFSM: อ่าน MOTD
# -----------------------------
def read_motd_with_netmiko(ip: str) -> str:
    """
    อ่าน MOTD ด้วย Netmiko; พยายามใช้ TextFSM ก่อน
    ถ้าเทมเพลตไม่มี จะคืน raw output
    """
    device = {
        "device_type": "cisco_ios",
        "host": ip,
        "username": os.environ.get("ROUTER_USER", "admin"),
        "password": os.environ.get("ROUTER_PASS", "cisco"),
        "secret": os.environ.get("ROUTER_ENABLE", "cisco"),
        "fast_cli": False,
    }

    with ConnectHandler(**device) as conn:
        conn.enable()

        # 1) ลองใช้ show banner motd (รองรับบน IOS ส่วนใหญ่)
        try:
            out = conn.send_command("show banner motd", use_textfsm=True)
            # ถ้า TextFSM มีเทมเพลต อาจคืน list/dict; ถ้าไม่มีจะเป็น str
            if isinstance(out, (list, dict)):
                # แปลงให้เป็นสตริงสวย ๆ
                text = str(out)
            else:
                text = out
            if text.strip():
                return text.strip()
        except Exception:
            pass

        # 2) Fallback: ดูใน running-config
        out = conn.send_command("show running-config | section banner motd")
        if not out.strip():
            # เผื่อบาง image ใช้คำสั่งนี้
            out = conn.send_command("show run | i banner motd")

        return out.strip() or "(ไม่พบบทความ MOTD บนอุปกรณ์)"

# -----------------------------
#       ENTRY POINT หลัก
# -----------------------------
def handle_command(raw: str) -> str:
    """
    รวม logic:
     - ไม่มีข้อความต่อท้าย => อ่าน MOTD (Netmiko/TextFSM)
     - มีข้อความต่อท้าย => ตั้ง MOTD (Ansible)
    """
    try:
        student_id, ip, action, message = _parse_command(raw)
    except ValueError as e:
        return str(e)

    if action != "motd":
        return "ยังไม่รองรับ action อื่นนอกจาก 'motd'"

    if message and message.strip():
        # SET MOTD
        return set_motd_with_ansible(ip, message.strip())
    else:
        # READ MOTD
        motd = read_motd_with_netmiko(ip)
        return motd

# -----------------------------
# ตัวอย่างการเรียกจาก CLI:
# python ansible_final.py "/66070230 10.0.15.61 motd Authorized users only! Managed by 66070239"
# python ansible_final.py "/66070239 10.0.15.61 motd"
# -----------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("วิธีใช้: python ansible_final.py \"/<student_id> <ip> motd [message...]\"")
        sys.exit(1)

    cmd = sys.argv[1]
    print(handle_command(cmd))

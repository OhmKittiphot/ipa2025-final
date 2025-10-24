import json
import os
import requests

# ปิดคำเตือน SSL
requests.packages.urllib3.disable_warnings()

# ====== ENV & Base URLs ======
ROUTER_IP   = os.getenv("ROUTER_IP", "10.0.15.61")   # IP ของ Router จะถูกเปลี่ยนทุกครั้งจาก ipa2024_final.py
ROUTER_USER = os.getenv("ROUTER_USER", "admin")
ROUTER_PASS = os.getenv("ROUTER_PASS", "cisco")
STUDENT_ID  = os.getenv("STUDENT_ID", "66070123")    # ใช้สร้างชื่อ Loopback<studentID>

# RESTCONF base
BASE = f"https://{ROUTER_IP}/restconf"

# Config API (ietf-interfaces)
API_IF      = f"{BASE}/data/ietf-interfaces:interfaces"
IFNAME      = f"Loopback{STUDENT_ID}"
API_IF_ITEM = f"{API_IF}/interface={IFNAME}"

# Operational (state) API
API_IF_STATE_ITEM = f"{BASE}/data/ietf-interfaces:interfaces-state/interface={IFNAME}"

# RESTCONF headers (JSON)
headers = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json"
}
basicauth = (ROUTER_USER, ROUTER_PASS)

# ====== คำนวณ IP Loopback จาก Student ID ======
# เช่น STUDENT_ID = 66070123 -> last3 = 123 -> ip = 172.1.23.1
last3 = STUDENT_ID[-3:]
x = int(last3[0])
y = int(last3[1:])
ip = f"172.{x}.{y}.1"
netmask = "255.255.255.0"


# =================== Function: CREATE ===================
def create():
    yangConfig = {
        "ietf-interfaces:interface": {
            "name": IFNAME,
            "description": f"Loopback for student {STUDENT_ID}",
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {
                "address": [
                    {"ip": ip, "netmask": netmask}
                ]
            }
        }
    }

    resp = requests.post(
        API_IF,
        data=json.dumps(yangConfig),
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=20
    )

    if 200 <= resp.status_code <= 299:
        return f"Interface loopback {STUDENT_ID} is created successfully"
    elif resp.status_code == 409:
        return f"Cannot create: Interface loopback {STUDENT_ID}"
    else:
        return f"Error: Status Code {resp.status_code}"


# =================== Function: DELETE ===================
def delete():
    resp = requests.delete(
        API_IF_ITEM,
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=15
    )

    if 200 <= resp.status_code <= 299:
        return f"Interface loopback {STUDENT_ID} is deleted successfully"
    elif resp.status_code == 404:
        return f"Cannot delete: Interface loopback {STUDENT_ID}"
    else:
        return f"Error: Status Code {resp.status_code}"


# =================== Function: ENABLE ===================
def enable():
    yangConfig = {
        "ietf-interfaces:interface": {
            "enabled": True
        }
    }

    resp = requests.patch(
        API_IF_ITEM,
        data=json.dumps(yangConfig),
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=15
    )

    if 200 <= resp.status_code <= 299:
        return f"Interface loopback {STUDENT_ID} is enabled successfully"
    elif resp.status_code == 404:
        return f"Cannot enable: Interface loopback {STUDENT_ID}"
    else:
        return f"Error: Status Code {resp.status_code}"


# =================== Function: DISABLE ===================
def disable():
    yangConfig = {
        "ietf-interfaces:interface": {
            "enabled": False
        }
    }

    resp = requests.patch(
        API_IF_ITEM,
        data=json.dumps(yangConfig),
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=15
    )

    if 200 <= resp.status_code <= 299:
        return f"Interface loopback {STUDENT_ID} is shutdowned successfully"
    elif resp.status_code == 404:
        return f"Cannot shutdown: Interface loopback {STUDENT_ID}"
    else:
        return f"Error: Status Code {resp.status_code}"


# =================== Function: STATUS ===================
def status():
    # อ่านฝั่ง config เพื่อตรวจว่า interface มีอยู่ไหม + admin-status (enabled)
    resp_cfg = requests.get(
        API_IF_ITEM,
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=15
    )

    if resp_cfg.status_code == 404:
        return f"No Interface loopback {STUDENT_ID}"
    elif not (200 <= resp_cfg.status_code <= 299):
        return f"Error: Status Code {resp_cfg.status_code}"

    cfg_json = resp_cfg.json()
    enabled = cfg_json.get("ietf-interfaces:interface", {}).get("enabled", False)
    admin_status = "up" if enabled else "down"

    # อ่านฝั่ง state เพื่อดู oper-status
    resp_st = requests.get(
        API_IF_STATE_ITEM,
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=15
    )

    oper_status = None
    if 200 <= resp_st.status_code <= 299:
        st_json = resp_st.json()
        oper_status = st_json.get("ietf-interfaces:interface", {}).get("oper-status", None)

    # ตีความสถานะ
    if admin_status == "up" and oper_status == "up":
        return f"Interface loopback {STUDENT_ID} is enabled"
    elif admin_status == "down" and (oper_status in (None, "down")):
        return f"Interface loopback {STUDENT_ID} is disabled"
    else:
        # เผื่อกรณี enabled=True แต่ oper ยัง down
        if enabled and oper_status == "down":
            return f"Interface loopback {STUDENT_ID} is disabled"
        return f"Interface loopback {STUDENT_ID} is disabled"

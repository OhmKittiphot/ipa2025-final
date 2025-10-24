import json
import os
import requests


requests.packages.urllib3.disable_warnings() #ปิดคำเตือน SSL

# ====== ENV & Base URLs ======
ROUTER_IP   = os.getenv("ROUTER_IP", "10.0.15.61")   # .61–.65 หรือ .181–.184 ตาม lab
ROUTER_USER = os.getenv("ROUTER_USER", "admin")
ROUTER_PASS = os.getenv("ROUTER_PASS", "cisco")
STUDENT_ID  = os.getenv("STUDENT_ID", "66070239")    # ใช้สร้างชื่อ Loopback<studentID>

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

# คำนวณ 172.x.y.1/24 จาก 3 หลักท้ายของ student_id
last3 = STUDENT_ID[-3:]
x = int(last3[0])
y = int(last3[1:])
ip = f"172.{x}.{y}.1"
netmask = "255.255.255.0"

def create():
      # YANG(JSON) payload ตาม ietf-interfaces + ietf-ip
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

    # POST ไปที่ collection (/interfaces) เพื่อสร้าง resource ใหม่
    resp = requests.post(
        API_IF,
        data=json.dumps(yangConfig),
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=20
    )

    if 200 <= resp.status_code <= 299:
        print("STATUS OK: {}".format(resp.status_code))
        return f"Interface loopback {STUDENT_ID} is created successfully"
    elif resp.status_code == 409:
        print("ALREADY EXISTS")
        return f"Cannot create: Interface loopback {STUDENT_ID}"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))

def delete():
     # DELETE ที่ resource รายตัว
    resp = requests.delete(
        API_IF_ITEM,
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=15
    )

    if 200 <= resp.status_code <= 299:
        print("STATUS OK: {}".format(resp.status_code))
        return f"Interface loopback {STUDENT_ID} is deleted successfully"
    elif resp.status_code == 404:
        print("NOT FOUND")
        return f"Cannot delete: Interface loopback {STUDENT_ID}"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))

def enable():
    # PATCH เฉพาะ field enabled = True
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
        print("STATUS OK: {}".format(resp.status_code))
        return f"Interface loopback {STUDENT_ID} is enabled successfully"
    elif resp.status_code == 404:
        print("NOT FOUND")
        return f"Cannot enable: Interface loopback {STUDENT_ID}"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))


def disable():
    # PATCH เฉพาะ field enabled = False
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
        print("STATUS OK: {}".format(resp.status_code))
        # ตามโจทย์ระบุคำนี้
        return f"Interface loopback {STUDENT_ID} is shutdowned successfully"
    elif resp.status_code == 404:
        print("NOT FOUND")
        return f"Cannot shutdown: Interface loopback {STUDENT_ID}"
    else:
        print('Error. Status Code: {}'.format(resp.status_code))

def status():
    # อ่านฝั่ง config เพื่อตรวจว่า interface มีอยู่ไหม + admin (enabled)
    resp_cfg = requests.get(
        API_IF_ITEM,
        auth=basicauth,
        headers=headers,
        verify=False,
        timeout=15
    )

    if resp_cfg.status_code == 404:
        print("STATUS NOT FOUND: {}".format(resp_cfg.status_code))
        return f"No Interface loopback {STUDENT_ID}"
    elif not (200 <= resp_cfg.status_code <= 299):
        print('Error. Status Code (config): {}'.format(resp_cfg.status_code))
        return

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

    # ตีความตามเงื่อนไขโจทย์
    if admin_status == "up" and oper_status == "up":
        return f"Interface loopback {STUDENT_ID} is enabled"
    elif admin_status == "down" and (oper_status in (None, "down")):
        return f"Interface loopback {STUDENT_ID} is disabled"
    else:
        # เผื่อกรณี enabled=True แต่ oper ยัง down ให้ถือว่า disabled
        if enabled and oper_status == "down":
            return f"Interface loopback {STUDENT_ID} is disabled"
        return f"Interface loopback {STUDENT_ID} is disabled"

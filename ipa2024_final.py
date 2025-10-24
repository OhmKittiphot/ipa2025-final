#######################################################################################
# Yourname: Kittiphot Mongkolrat
# Your student ID: 66070239
# Your GitHub Repo: https://github.com/OhmKittiphot/IPA2024-Final.git
#
# ipa2024_final.py
# - รับคำสั่งจากห้อง Webex
# - ต้อง "ตั้งค่า method" ก่อน (restconf | netconf) ด้วย /<SID> <method>
# - จากนั้นสั่ง /<SID> <IP> <command>  โดย command = create|delete|enable|disable|status|gigabit_status|showrun
# - รูปแบบข้อความตอบกลับจะเติม "using <Method>" หรือ "(checked by <Method>)" ตามสเปคที่ให้มา
#######################################################################################

import os
import re
import time
import json
import importlib
import requests
from requests_toolbelt import MultipartEncoder  # สำหรับส่งไฟล์แนบให้ Webex

# โมดูลงานแต่ละส่วน
import restconf_final as rest         # ต้องมีไฟล์ restconf_final.py
import netconf_final as net           # ต้องมีไฟล์ netconf_final.py (เติมเนื้อหาเรียบร้อย)
import netmiko_final as nm            # ต้องมีไฟล์ netmiko_final.py (ฟังก์ชัน gigabit_status)
import ansible_final as ans           # ต้องมีไฟล์ ansible_final.py (ฟังก์ชัน showrun)

requests.packages.urllib3.disable_warnings()  # ปิด SSL warnings

# ====== CONFIG (ENV) ======
STUDENT_ID = os.environ.get("STUDENT_ID", "66070239")

ACCESS_TOKEN = os.environ.get("WEBEX_BOT_TOKEN", "")
if not ACCESS_TOKEN:
    raise RuntimeError("WEBEX_BOT_TOKEN is not set in environment variables")

ROOM_ID = os.environ.get("WEBEX_ROOM_ID", "")
if not ROOM_ID:
    raise RuntimeError("WEBEX_ROOM_ID is not set in environment variables")

AUTH_HEADER = f"Bearer {ACCESS_TOKEN}"

# ====== STATE ======
CURRENT_METHOD = None  # "restconf" | "netconf" | None
IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def _normalize_method(s: str):
    s = (s or "").strip().lower()
    if s in ("restconf", "netconf"):
        return s
    return None


def _cap(s: str):
    return s.capitalize() if s else s


def _send_text(text: str):
    """ส่งข้อความธรรมดาเข้า Webex room"""
    postData = json.dumps({"roomId": ROOM_ID, "text": text})
    headers = {"Authorization": AUTH_HEADER, "Content-Type": "application/json"}
    r = requests.post("https://webexapis.com/v1/messages", data=postData, headers=headers, verify=False)
    if r.status_code != 200:
        raise Exception(f"Incorrect reply from Webex Teams API. Status code: {r.status_code}")


def _send_file_with_text(text: str, filepath: str):
    """ส่งข้อความ + แนบไฟล์เข้า Webex room"""
    filename = os.path.basename(filepath)
    fileobject = open(filepath, "rb")
    filetype = "text/plain"
    try:
        mp = MultipartEncoder(
            fields={
                "roomId": ROOM_ID,
                "text": text,
                "files": (filename, fileobject, filetype),
            }
        )
        headers = {
            "Authorization": AUTH_HEADER,
            "Content-Type": mp.content_type,
        }
        r = requests.post("https://webexapis.com/v1/messages", data=mp, headers=headers, verify=False)
        if r.status_code != 200:
            raise Exception(f"Incorrect reply from Webex Teams API. Status code: {r.status_code}")
    finally:
        try:
            fileobject.close()
        except:
            pass


def _handle_message(message_text: str):
    """
    ประมวลผลข้อความจากห้อง Webex ตามสเปค:
      - ต้องตั้ง method ก่อน: "/<SID> restconf" หรือ "/<SID> netconf" -> "Ok: Restconf/Netconf"
      - คำสั่งใช้งาน: "/<SID> <IP> <command>"
        * ถ้าไม่มี method -> "Error: No method specified"
        * ถ้าไม่มี IP -> "Error: No IP specified"
        * ถ้าใส่แค่ IP -> "Error: No command found."
      - เติม "using <Method>" เมื่อ success (ยกเว้น status ให้เติม "(checked by <Method>)")
      - บาง failure (disable) ให้เติม "(checked by <Method>)" ตามตัวอย่าง
    """
    global CURRENT_METHOD

    # ต้องเริ่มด้วย /<SID>
    if not message_text.startswith(f"/{STUDENT_ID}"):
        return  # ข้ามข้อความอื่น

    parts = message_text.strip().split()
    tokens = parts[1:]  # ตัด "/<SID>" ออก

    # กรณีไม่มีอะไรเลยหลัง /SID
    if not tokens:
        _send_text("Error: No method specified")
        return

    # 1) ผู้ใช้ตั้ง method: "/SID restconf" หรือ "/SID netconf"
    maybe_method_only = _normalize_method(tokens[0])
    if len(tokens) == 1 and maybe_method_only:
        CURRENT_METHOD = maybe_method_only
        _send_text(f"Ok: {_cap(CURRENT_METHOD)}")
        return

    # ถ้ายังไม่ได้ตั้ง method -> แจ้งเตือน
    if not CURRENT_METHOD:
        _send_text("Error: No method specified")
        return

    # 2) โหมดคำสั่ง: คาดหวัง "/SID <IP> <command>" หรือ "/SID <IP>"
    ip = None
    cmd = None

    # โทเค็นแรกควรเป็น IP
    if IPV4_RE.match(tokens[0]):
        ip = tokens[0]
        if len(tokens) >= 2:
            cmd = tokens[1].lower().strip()
    else:
        # ถ้าเริ่มด้วย method อีก -> เปลี่ยน method ตรงนี้ได้ด้วย (เผื่อผู้ใช้พิมพ์ method ซ้ำ)
        maybe_method = _normalize_method(tokens[0])
        if maybe_method and len(tokens) == 1:
            CURRENT_METHOD = maybe_method
            _send_text(f"Ok: {_cap(CURRENT_METHOD)}")
            return

        # ผู้ใช้ใส่คำสั่งโดยไม่มี IP
        _send_text("Error: No IP specified")
        return

    # "/SID <IP>" อย่างเดียว
    if cmd is None and ip and len(tokens) == 1:
        _send_text("Error: No command found.")
        return

    # มีทั้ง method + ip + command
    # เตรียมโมดูลปลายทางให้ใช้ IP นี้
    os.environ["ROUTER_IP"] = ip
    dev = importlib.reload(rest) if CURRENT_METHOD == "restconf" else importlib.reload(net)

    # แมพคำสั่ง
    if cmd in ("create", "delete", "enable", "disable", "status"):
        try:
            base_msg = getattr(dev, cmd)()
        except Exception as e:
            base_msg = f"Error executing {cmd}: {e}"

        low = (base_msg or "").lower()

        if cmd == "status":
            # status => "… (checked by <Method>)"
            _send_text(f"{base_msg} (checked by {_cap(CURRENT_METHOD)})")
        else:
            # success (มีคำว่า successfully) => "… using <Method>"
            if "successfully" in low:
                _send_text(f"{base_msg} using {_cap(CURRENT_METHOD)}")
            else:
                # failure
                # ตัวอย่างสเปค: disable ล้มเหลว -> เติม (checked by <Method>)
                if cmd == "disable" and ("cannot" in low or "not found" in low):
                    _send_text(f"{base_msg} (checked by {_cap(CURRENT_METHOD)})")
                else:
                    _send_text(base_msg)

    elif cmd == "gigabit_status":
        # Netmiko ให้ใช้ IP เดียวกัน (อ่านจาก ENV ใน netmiko_final.py)
        importlib.reload(nm)
        try:
            ans = nm.gigabit_status()
        except Exception as e:
            ans = f"Error executing gigabit_status: {e}"
        _send_text(ans)

    elif cmd == "showrun":
        # เรียก Ansible ให้ดึง show running-config แล้วแนบไฟล์กลับห้อง
        result = ans.showrun()
        if isinstance(result, str) and result.endswith(".txt") and os.path.exists(result):
            _send_file_with_text("show running config", result)
        else:
            # ถ้าไม่ได้ไฟล์ ให้ส่งข้อความ log/ผลลัพธ์กลับ
            _send_text(result if isinstance(result, str) else str(result))

    else:
        _send_text("Error: No command or unknown command")


def main():
    # วนลูปอ่านข้อความล่าสุดจากห้อง Webex แล้วประมวลผล
    while True:
        time.sleep(1)  # กัน rate limit

        get_params = {"roomId": ROOM_ID, "max": 1}
        headers = {"Authorization": AUTH_HEADER}

        r = requests.get(
            "https://webexapis.com/v1/messages",
            params=get_params,
            headers=headers,
            verify=False
        )
        if r.status_code != 200:
            raise Exception(f"Incorrect reply from Webex Teams API. Status code: {r.status_code}")

        data = r.json()
        items = data.get("items", [])
        if not items:
            continue

        message = items[0]
        text = message.get("text", "") or ""
        # หมายเหตุ: ถ้าต้องกันไม่ให้บอทตอบตัวเอง อาจเช็ค personEmail/createdBy เทียบกับบอท แล้วข้าม (ถ้าจำเป็น)
        print("Received message:", text)
        _handle_message(text)


if __name__ == "__main__":
    main()
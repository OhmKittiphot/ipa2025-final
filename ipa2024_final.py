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
import netconf_final as net           # ต้องมีไฟล์ netconf_final.py
import netmiko_final as nm            # ฟังก์ชัน gigabit_status
import ansible_final as ans           # ฟังก์ชัน showrun

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

    if not tokens:
        _send_text("Error: No method specified")
        return

    # helper
    def _is_ip(s):
        return IPV4_RE.match(s or "") is not None

    def _is_no_method_cmd(s):
        return (s or "").lower().strip() in ("showrun", "gigabit_status")

    # 1) ผู้ใช้ตั้ง method: "/SID restconf" หรือ "/SID netconf"
    maybe_method_only = _normalize_method(tokens[0])
    if len(tokens) == 1 and maybe_method_only:
        CURRENT_METHOD = maybe_method_only
        _send_text(f"Ok: {_cap(CURRENT_METHOD)}")
        return

    # 2) ถ้าเป็น "/SID <IP> <cmd>" และ <cmd> เป็น showrun/gigabit_status ให้ผ่านได้โดยไม่ต้องตั้ง method
    bypass_method_check = False
    if len(tokens) >= 2 and _is_ip(tokens[0]) and _is_no_method_cmd(tokens[1]):
        bypass_method_check = True

    # 3) ถ้าไม่ bypass และยังไม่ตั้ง method -> error
    if not bypass_method_check and not CURRENT_METHOD:
        _send_text("Error: No method specified")
        return

    # --- เริ่ม parse โหมดคำสั่ง ---
    ip = None
    cmd = None

    if _is_ip(tokens[0]):
        ip = tokens[0]
        if len(tokens) >= 2:
            cmd = tokens[1].lower().strip()
    else:
        maybe_method = _normalize_method(tokens[0])
        if maybe_method and len(tokens) == 1:
            CURRENT_METHOD = maybe_method
            _send_text(f"Ok: {_cap(CURRENT_METHOD)}")
            return

        _send_text("Error: No IP specified")
        return

    if cmd is None and ip and len(tokens) == 1:
        _send_text("Error: No command found.")
        return

    # ตั้ง ENV ให้โมดูลอื่นใช้ IP นี้
    os.environ["ROUTER_IP"] = ip

    # ====== กลุ่มคำสั่งที่ขึ้นกับ method (restconf/netconf) ======
    if cmd in ("create", "delete", "enable", "disable", "status"):
        dev = importlib.reload(rest) if CURRENT_METHOD == "restconf" else importlib.reload(net)
        try:
            base_msg = getattr(dev, cmd)()
        except Exception as e:
            base_msg = f"Error executing {cmd}: {e}"

        low = (base_msg or "").lower()

        if cmd == "status":
            _send_text(f"{base_msg} (checked by {_cap(CURRENT_METHOD)})")
        else:
            if "successfully" in low:
                _send_text(f"{base_msg} using {_cap(CURRENT_METHOD)}")
            else:
                if cmd == "disable" and ("cannot" in low or "not found" in low):
                    _send_text(f"{base_msg} (checked by {_cap(CURRENT_METHOD)})")
                else:
                    _send_text(base_msg)

    # ====== คำสั่งที่ "ไม่ต้องมี method" ======
    elif cmd == "gigabit_status":
        importlib.reload(nm)
        try:
            gig_result = nm.gigabit_status()
        except Exception as e:
            gig_result = f"Error executing gigabit_status: {e}"
        _send_text(gig_result)

    elif cmd == "showrun":
        result = ans.showrun()
        if isinstance(result, str) and result.endswith(".txt") and os.path.exists(result):
            _send_file_with_text("show running config", result)
        else:
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
        print("Received message:", text)
        _handle_message(text)


if __name__ == "__main__":
    main()

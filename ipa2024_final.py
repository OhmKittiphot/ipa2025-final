#######################################################################################
# Yourname: Kittiphot Mongkolrat
# Your student ID: 66070123
# Your GitHub Repo: https://github.com/OhmKittiphot/IPA2024-Final.git
#
# ipa2024_final.py
# - ต้อง "ตั้งค่า method" ก่อน (restconf | netconf) ด้วย /<SID> <method>
# - จากนั้นสั่ง /<SID> <IP> <command>
# - command: create | delete | enable | disable | status | gigabit_status | showrun
# - ตอบ “using <Method>” เมื่อ success (ยกเว้น status จะ “(checked by <Method>)”)
#######################################################################################

# ===== Load .env early =====
import os as _os, os
from dotenv import load_dotenv
load_dotenv(dotenv_path=_os.path.join(_os.path.dirname(__file__), ".env"))

# ===== Standard imports =====
import re
import time
import json
import importlib
import requests
from requests_toolbelt import MultipartEncoder  # สำหรับแนบไฟล์ให้ Webex

# ===== Project modules =====
import restconf_final as rest         # RESTCONF (Part 1)
import netconf_final as net           # NETCONF  (Part 1)
import netmiko_final as nm            # Part 2 (gigabit_status)
import ansible_final as ans           # Part 2 (showrun)

requests.packages.urllib3.disable_warnings()  # ปิด SSL warnings

# ===== Read ENV =====
STUDENT_ID = os.environ.get("STUDENT_ID", "")

ACCESS_TOKEN = os.environ.get("WEBEX_BOT_TOKEN", "")
if not ACCESS_TOKEN:
    raise RuntimeError("WEBEX_BOT_TOKEN is not set in environment variables")

ROOM_ID = os.environ.get("WEBEX_ROOM_ID", "")
if not ROOM_ID:
    raise RuntimeError("WEBEX_ROOM_ID is not set in environment variables")

AUTH_HEADER = f"Bearer {ACCESS_TOKEN}"

# ===== Runtime state =====
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
    data = json.dumps({"roomId": ROOM_ID, "text": text})
    headers = {"Authorization": AUTH_HEADER, "Content-Type": "application/json"}
    r = requests.post("https://webexapis.com/v1/messages", data=data, headers=headers, verify=False)
    if r.status_code != 200:
        raise Exception(f"Incorrect reply from Webex Teams API. Status code: {r.status_code}")


def _send_file_with_text(text: str, filepath: str):
    filename = os.path.basename(filepath)
    fileobject = open(filepath, "rb")
    filetype = "text/plain"
    try:
        mp = MultipartEncoder(fields={"roomId": ROOM_ID, "text": text, "files": (filename, fileobject, filetype)})
        headers = {"Authorization": AUTH_HEADER, "Content-Type": mp.content_type}
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
    สเปคการตอบ:
    - ต้องตั้ง method ก่อน: "/<SID> restconf" หรือ "/<SID> netconf" -> "Ok: Restconf/Netconf"
    - คำสั่งใช้งาน: "/<SID> <IP> <command>"
      * ถ้าไม่มี method -> "Error: No method specified"
      * ถ้าไม่มี IP   -> "Error: No IP specified"
      * ถ้าใส่แค่ IP -> "Error: No command found."
    - เติม "using <Method>" เมื่อ success (ยกเว้น status -> "(checked by <Method>)")
    """
    global CURRENT_METHOD

    if not message_text.startswith(f"/{STUDENT_ID}"):
        return  # ไม่ใช่คำสั่งของเรา

    parts = message_text.strip().split()
    tokens = parts[1:]  # ตัด "/<SID>"

    # กรณีไม่มีอะไรต่อจาก /SID
    if not tokens:
        _send_text("Error: No method specified")
        return

    # ตั้ง method: "/SID restconf" หรือ "/SID netconf"
    maybe_method_only = _normalize_method(tokens[0])
    if len(tokens) == 1 and maybe_method_only:
        CURRENT_METHOD = maybe_method_only
        _send_text(f"Ok: {_cap(CURRENT_METHOD)}")
        return

    # ยังไม่ได้ตั้ง method มาก่อน
    if not CURRENT_METHOD:
        _send_text("Error: No method specified")
        return

    # โหมดคำสั่ง: "/SID <IP> <command>" หรือ "/SID <IP>"
    ip = None
    cmd = None

    # token แรกคาดหวังเป็น IP
    if IPV4_RE.match(tokens[0]):
        ip = tokens[0]
        if len(tokens) >= 2:
            cmd = tokens[1].lower().strip()
    else:
        # ถ้าพิมพ์ method อีกรอบ (เปลี่ยน method ทันที)
        maybe_method = _normalize_method(tokens[0])
        if maybe_method and len(tokens) == 1:
            CURRENT_METHOD = maybe_method
            _send_text(f"Ok: {_cap(CURRENT_METHOD)}")
            return
        # ไม่มี IP
        _send_text("Error: No IP specified")
        return

    # กรณี "/SID <IP>" อย่างเดียว
    if cmd is None and ip and len(tokens) == 1:
        _send_text("Error: No command found.")
        return

    # มี method + IP + command แล้ว
    os.environ["ROUTER_IP"] = ip
    dev = importlib.reload(rest) if CURRENT_METHOD == "restconf" else importlib.reload(net)

    if cmd in ("create", "delete", "enable", "disable", "status"):
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
                # ตัวอย่างระบุ disable ล้มเหลวให้ใส่ (checked by ...)
                if cmd == "disable" and ("cannot" in low or "not found" in low):
                    _send_text(f"{base_msg} (checked by {_cap(CURRENT_METHOD)})")
                else:
                    _send_text(base_msg)

    elif cmd == "gigabit_status":
        # Netmiko อ่าน ROUTER_IP จาก ENV เช่นกัน
        importlib.reload(nm)
        try:
            ans = nm.gigabit_status()
        except Exception as e:
            ans = f"Error executing gigabit_status: {e}"
        _send_text(ans)

    elif cmd == "showrun":
        result = ans.showrun()
        if isinstance(result, str) and result.endswith(".txt") and os.path.exists(result):
            _send_file_with_text("show running config", result)
        else:
            _send_text(result if isinstance(result, str) else str(result))

    else:
        _send_text("Error: No command or unknown command")


def main():
    # วนลูปอ่านข้อความล่าสุดจากห้อง Webex
    while True:
        time.sleep(1)  # กัน rate limit

        get_params = {"roomId": ROOM_ID, "max": 1}
        headers = {"Authorization": AUTH_HEADER}

        r = requests.get("https://webexapis.com/v1/messages",
                         params=get_params, headers=headers, verify=False)
        if r.status_code != 200:
            raise Exception(f"Incorrect reply from Webex Teams API. Status code: {r.status_code}")

        data = r.json()
        items = data.get("items", [])
        if not items:
            continue

        msg = items[0]
        text = msg.get("text", "") or ""
        print("Received message:", text)
        _handle_message(text)


if __name__ == "__main__":
    main()
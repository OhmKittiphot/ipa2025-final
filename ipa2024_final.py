#######################################################################################
# Yourname: Kittiphot Mongkolrat
# Your student ID: 66070239
# Your GitHub Repo: https://github.com/OhmKittiphot/IPA2024-Final.git
#
# ipa2024_final.py
#######################################################################################

import os
import re
import time
import json
import importlib
import requests
from requests_toolbelt import MultipartEncoder  # สำหรับส่งไฟล์แนบให้ Webex

# โมดูลงานแต่ละส่วน
import restconf_final as rest
import netconf_final as net
import netmiko_final as nm
import ansible_final as ans

requests.packages.urllib3.disable_warnings()

STUDENT_ID = os.environ.get("STUDENT_ID", "66070239")

ACCESS_TOKEN = os.environ.get("WEBEX_BOT_TOKEN", "")
if not ACCESS_TOKEN:
    raise RuntimeError("WEBEX_BOT_TOKEN is not set in environment variables")

ROOM_ID = os.environ.get("WEBEX_ROOM_ID", "")
if not ROOM_ID:
    raise RuntimeError("WEBEX_ROOM_ID is not set in environment variables")

AUTH_HEADER = f"Bearer {ACCESS_TOKEN}"

CURRENT_METHOD = None
IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

def _normalize_method(s: str):
    s = (s or "").strip().lower()
    if s in ("restconf", "netconf"):
        return s
    return None

def _cap(s: str):
    return s.capitalize() if s else s

def _send_text(text: str):
    postData = json.dumps({"roomId": ROOM_ID, "text": text})
    headers = {"Authorization": AUTH_HEADER, "Content-Type": "application/json"}
    r = requests.post("https://webexapis.com/v1/messages", data=postData, headers=headers, verify=False)
    if r.status_code != 200:
        raise Exception(f"Incorrect reply from Webex Teams API. Status code: {r.status_code}")

def _send_file_with_text(text: str, filepath: str):
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
    global CURRENT_METHOD

    if not message_text.startswith(f"/{STUDENT_ID}"):
        return

    parts = message_text.strip().split()
    tokens = parts[1:]

    if not tokens:
        _send_text("Error: No method specified")
        return

    def _is_ip(s): return IPV4_RE.match(s or "") is not None
    def _is_no_method_cmd(s): return (s or "").lower().strip() in ("showrun", "gigabit_status", "motd")

    maybe_method_only = _normalize_method(tokens[0])
    if len(tokens) == 1 and maybe_method_only:
        CURRENT_METHOD = maybe_method_only
        _send_text(f"Ok: {_cap(CURRENT_METHOD)}")
        return

    bypass_method_check = False
    if len(tokens) >= 2 and _is_ip(tokens[0]) and _is_no_method_cmd(tokens[1]):
        bypass_method_check = True

    if not bypass_method_check and not CURRENT_METHOD:
        _send_text("Error: No method specified")
        return

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

    os.environ["ROUTER_IP"] = ip

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

    elif cmd == "motd":
        # /<SID> <IP> motd <ข้อความ>  -> ตั้ง MOTD (Ansible)
        # /<SID> <IP> motd            -> อ่าน MOTD (Netmiko)
        msg = " ".join(tokens[2:]).strip() if len(tokens) >= 3 else ""
        os.environ["ROUTER_IP"] = ip

        if msg:
            try:
                result = ans.set_motd(ip, msg)
            except Exception as e:
                result = f"Error: {e}"
            _send_text(result)
        else:
            importlib.reload(nm)
            try:
                motd = nm.read_motd(ip)
            except Exception as e:
                motd = f"Error: {e}"
            _send_text(motd)

    else:
        _send_text("Error: No command or unknown command")

def main():
    while True:
        time.sleep(1)
        get_params = {"roomId": ROOM_ID, "max": 1}
        headers = {"Authorization": AUTH_HEADER}
        r = requests.get("https://webexapis.com/v1/messages", params=get_params, headers=headers, verify=False)
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

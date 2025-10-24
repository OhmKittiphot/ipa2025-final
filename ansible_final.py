import subprocess, json
import os
import re

ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")  # ลบโค้ดสี ANSI

def _clean_path(p: str) -> str:
    if not p:
        return p
    p = ANSI_RE.sub("", p)
    p = p.strip().strip('"').strip("'")
    return p

def showrun():
    ip = os.getenv("ROUTER_IP", "").strip()
    if not ip:
        return "Error: No IP specified"

    cmd = [
        "ansible-playbook",
        "showrun.yml",
        "-i", "inventory.ini",
        "-l", ip,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    m = re.search(r"Saved running-config to\s+(.+?\.txt)", output)
    if m:
        saved_path = _clean_path(m.group(1))
        if not os.path.isabs(saved_path):
            saved_path = os.path.join(os.getcwd(), saved_path)
        saved_path = _clean_path(saved_path)
        if os.path.exists(saved_path):
            return saved_path
        alt_path = _clean_path(os.path.join(os.path.dirname(__file__), os.path.relpath(saved_path, os.getcwd())))
        if os.path.exists(alt_path):
            return alt_path
        return f"Playbook success but output file not found on disk: {saved_path}\n\n{output}"

    return output

# ===== MOTD =====
def _run(cmd: list, env: dict | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
    return r.returncode, out.strip()

def set_motd(ip: str, text: str) -> str:
    """
    ตั้งค่า MOTD ด้วย playbook motd.yml (limit ไปที่ IP ที่ระบุ)
    ใช้ -e แบบ JSON เพื่อไม่ให้ค่าสตริงถูกตัดคำเวลามีช่องว่าง/อักขระพิเศษ
    """
    if not ip:
        return "Error: No IP specified"
    if not text or not text.strip():
        return "Error: No MOTD text provided"

    extra_vars_json = json.dumps({"MOTD_TEXT": text}, ensure_ascii=False)

    cmd = [
        "ansible-playbook", "motd.yml",
        "-i", "inventory.ini",
        "-l", ip,
        "-e", extra_vars_json,   # <<<<<< ป้องกันการตัดคำด้วยช่องว่าง
    ]

    rc, out = _run(cmd)

    if rc == 0 and ("failed=0" in out or "fatal:" not in out.lower()):
        return "Ok: success"
    return f"Error: ansible failed (rc={rc})\n{out}"
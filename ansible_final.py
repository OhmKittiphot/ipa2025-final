import subprocess
import os
import re

ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")  # ลบโค้ดสี ANSI

def _clean_path(p: str) -> str:
    if not p:
        return p
    p = ANSI_RE.sub("", p)         # ตัด ANSI color
    p = p.strip().strip('"').strip("'")  # ตัดช่องว่าง + " และ '
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

    # หา path จาก debug ของ playbook:  msg: "Saved running-config to outputs/xxx.txt"
    # จับทั้งกรณีมี/ไม่มี quote
    m = re.search(r"Saved running-config to\s+(.+?\.txt)", output)
    if m:
        saved_path = _clean_path(m.group(1))

        # ทำให้เป็น absolute ถ้ายังเป็น relative
        if not os.path.isabs(saved_path):
            saved_path = os.path.join(os.getcwd(), saved_path)

        # เช็คไฟล์ (เผื่อยังมี quote/space แฝงอีก ลอง clean อีกรอบ)
        saved_path = _clean_path(saved_path)
        if os.path.exists(saved_path):
            return saved_path

        # เผื่อ Ansible เขียนไฟล์ไว้ใต้โฟลเดอร์โปรเจ็กต์ แต่ Python ถูกเรียกจาก CWD อื่น
        alt_path = _clean_path(os.path.join(os.path.dirname(__file__), os.path.relpath(saved_path, os.getcwd())))
        if os.path.exists(alt_path):
            return alt_path

        return f"Playbook success but output file not found on disk: {saved_path}\n\n{output}"

    # ถ้าไม่เจอข้อความ debug ก็ส่ง log กลับไป
    return output

# -------- MOTD (เพิ่มเฉพาะส่วนนี้) --------
def _run_ans_motd(cmd: list, env: dict | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
    return r.returncode, out.strip()

def set_motd(ip: str, text: str) -> str:
    """
    ตั้งค่า MOTD ด้วย playbook motd.yml (limit ไปที่ IP ที่ระบุ)
    คืนค่า: "Ok: success" หรือ "Error: ..."
    """
    if not ip:
        return "Error: No IP specified"
    if not text or not text.strip():
        return "Error: No MOTD text provided"

    env = os.environ.copy()
    env["MOTD_TEXT"] = text
    cmd = ["ansible-playbook", "motd.yml", "-i", "inventory.ini", "-l", ip]
    rc, out = _run_ans_motd(cmd, env=env)

    if ("failed=0" in out) and ("changed=1" in out or "ok=" in out):
        return "Ok: success"
    if "Error: No MOTD text provided" in out:
        return "Error: No MOTD text provided"
    if rc != 0:
        return f"Error: ansible failed (rc={rc})\n{out}"
    return "Ok: success"
# -------- จบส่วนเพิ่ม --------

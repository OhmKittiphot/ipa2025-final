import subprocess
import os

def showrun(ip: str | None = None):
    """
    ดึง running-config ของอุปกรณ์เป้าหมายด้วย Ansible
    - รับ ip จากอาร์กิวเมนต์ หรืออ่านจาก ENV ROUTER_IP
    - ใช้ --limit (-l) เป็น IP นั้น
    - คาดหวังไฟล์ outputs/showrun_<ip>.txt จาก playbook
    """
    ip = (ip or os.getenv("ROUTER_IP", "")).strip()
    if not ip:
        return "Error: No IP specified"

    command = ['ansible-playbook', 'showrun.yml', '-i', 'inventory.ini', '-l', ip]

    result = subprocess.run(command, capture_output=True, text=True)
    result_text = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")

    output_file = f"outputs/showrun_{ip}.txt"

    ok = ("failed=0" in result_text) and ("unreachable=0" in result_text)
    if ok and os.path.exists(output_file):
        return output_file
    if ok and not os.path.exists(output_file):
        return f"Playbook success but output file not found.\n{result_text.strip()}"
    return result_text.strip()


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

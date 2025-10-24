import subprocess
import os

def showrun():
    # ใช้ ansible-playbook เรียก playbook ที่เขียนไว้ชื่อ showrun.yml
    # ซึ่งจะเก็บ running-config ลงไฟล์ outputs/showrun_10.0.15.61.txt
    command = ['ansible-playbook', 'showrun.yml', '-i', 'inventory.ini', '-l', '10.0.15.61']

    # run คำสั่ง แล้วเก็บ stdout/stderr เป็น string
    result = subprocess.run(command, capture_output=True, text=True)
    result_text = result.stdout

    # ถ้า playbook ทำงานสำเร็จ จะเจอข้อความประมาณ:
    # "PLAY RECAP *********************************************************************"
    # "10.0.15.61              : ok=2    changed=0    unreachable=0    failed=0"
    if 'ok=2' in result_text and 'failed=0' in result_text:
        # ตรวจว่ามีไฟล์ผลลัพธ์จริงก่อน return
        output_file = "outputs/showrun_10.0.15.61.txt"
        if os.path.exists(output_file):
            return output_file
        else:
            return "Playbook success but output file not found."
    else:
        # ถ้ามี error ให้คืน stdout ทั้งหมดกลับไปดู
        return result_text

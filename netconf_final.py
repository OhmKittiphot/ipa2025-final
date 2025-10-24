from ncclient import manager
import xmltodict
import os

# ===== ENV / Defaults =====
ROUTER_IP   = os.getenv("ROUTER_IP", "10.0.15.61")
ROUTER_PORT = int(os.getenv("NETCONF_PORT", "830"))
ROUTER_USER = os.getenv("ROUTER_USER", "admin")
ROUTER_PASS = os.getenv("ROUTER_PASS", "cisco")
STUDENT_ID  = os.getenv("STUDENT_ID", "66070123")   # ใช้สร้างชื่อ Loopback<studentID>

IFNAME = f"Loopback{STUDENT_ID}"

# คำนวณ IP 172.x.y.1/24 จาก 3 หลักท้ายของ STUDENT_ID
last3 = STUDENT_ID[-3:]
x = int(last3[0])
y = int(last3[1:])
LO_IP = f"172.{x}.{y}.1"
LO_MASK = "255.255.255.0"

# ===== NETCONF session =====
m = manager.connect(
    host=ROUTER_IP,
    port=ROUTER_PORT,
    username=ROUTER_USER,
    password=ROUTER_PASS,
    hostkey_verify=False,
    allow_agent=False,
    look_for_keys=False,
    timeout=20
)

def netconf_edit_config(netconf_config):
    return m.edit_config(target="running", config=netconf_config)

def create():
    netconf_config = f"""
    <config>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"
                  xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">
        <interface>
          <name>{IFNAME}</name>
          <description>Loopback for student {STUDENT_ID}</description>
          <type>ianaift:softwareLoopback</type>
          <enabled>true</enabled>
          <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
            <address>
              <ip>{LO_IP}</ip>
              <netmask>{LO_MASK}</netmask>
            </address>
          </ipv4>
        </interface>
      </interfaces>
    </config>
    """
    try:
        netconf_reply = netconf_edit_config(netconf_config)
        xml_data = netconf_reply.xml
        print(xml_data)
        if "<ok/>" in xml_data:
            return f"Interface loopback {STUDENT_ID} is created successfully"
        else:
            return f"Cannot create: Interface loopback {STUDENT_ID}"
    except Exception as e:
        print("Error!", e)
        return f"Cannot create: Interface loopback {STUDENT_ID}"

def delete():
    netconf_config = f"""
    <config>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"
                  xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
        <interface nc:operation="delete">
          <name>{IFNAME}</name>
        </interface>
      </interfaces>
    </config>
    """
    try:
        netconf_reply = netconf_edit_config(netconf_config)
        xml_data = netconf_reply.xml
        print(xml_data)
        if "<ok/>" in xml_data:
            return f"Interface loopback {STUDENT_ID} is deleted successfully"
        else:
            return f"Cannot delete: Interface loopback {STUDENT_ID}"
    except Exception as e:
        print("Error!", e)
        return f"Cannot delete: Interface loopback {STUDENT_ID}"

def enable():
    netconf_config = f"""
    <config>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface>
          <name>{IFNAME}</name>
          <enabled>true</enabled>
        </interface>
      </interfaces>
    </config>
    """
    try:
        netconf_reply = netconf_edit_config(netconf_config)
        xml_data = netconf_reply.xml
        print(xml_data)
        if "<ok/>" in xml_data:
            return f"Interface loopback {STUDENT_ID} is enabled successfully"
        else:
            return f"Cannot enable: Interface loopback {STUDENT_ID}"
    except Exception as e:
        print("Error!", e)
        return f"Cannot enable: Interface loopback {STUDENT_ID}"

def disable():
    netconf_config = f"""
    <config>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface>
          <name>{IFNAME}</name>
          <enabled>false</enabled>
        </interface>
      </interfaces>
    </config>
    """
    try:
        netconf_reply = netconf_edit_config(netconf_config)
        xml_data = netconf_reply.xml
        print(xml_data)
        if "<ok/>" in xml_data:
            return f"Interface loopback {STUDENT_ID} is shutdowned successfully"
        else:
            return f"Cannot shutdown: Interface loopback {STUDENT_ID}"
    except Exception as e:
        print("Error!", e)
        return f"Cannot shutdown: Interface loopback {STUDENT_ID}"

def status():
    # ใช้ <get> (operational) ดึง interfaces-state ของ IFNAME
    netconf_filter = f"""
    <filter>
      <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface>
          <name>{IFNAME}</name>
        </interface>
      </interfaces-state>
    </filter>
    """
    try:
        netconf_reply = m.get(netconf_filter)
        print(netconf_reply.xml)

        netconf_reply_dict = xmltodict.parse(netconf_reply.xml)

        # เดิน dict ไปยัง interfaces-state/interface
        data = (netconf_reply_dict.get("rpc-reply", {}) or {}).get("data", {})
        if not data:
            # อุปกรณ์บางตัวห่อเป็น <data> … ; ถ้าไม่มี data ลองอ่านตรง interfaces-state
            data = netconf_reply_dict.get("rpc-reply", {})

        ifaces = None
        # ลองสองรูปแบบ
        if "interfaces-state" in data:
            ifaces = data["interfaces-state"].get("interface")
        elif "data" in data and "interfaces-state" in data["data"]:
            ifaces = data["data"]["interfaces-state"].get("interface")

        if not ifaces:
            return f"No Interface loopback {STUDENT_ID}"

        # ถ้า interface เดียว xmltodict จะให้เป็น dict ถ้าหลายตัวจะเป็น list
        if isinstance(ifaces, list):
            iface = next((i for i in ifaces if i.get("name") == IFNAME), None)
        else:
            iface = ifaces

        if not iface:
            return f"No Interface loopback {STUDENT_ID}"

        admin_status = iface.get("admin-status", "").lower()
        oper_status  = iface.get("oper-status", "").lower()

        if admin_status == "up" and oper_status == "up":
            return f"Interface loopback {STUDENT_ID} is enabled"
        elif admin_status == "down" and oper_status == "down":
            return f"Interface loopback {STUDENT_ID} is disabled"
        else:
            # กรณีค่าแปลก ให้ถือว่า disabled ตามเกณฑ์เดียวกับ RESTCONF
            return f"Interface loopback {STUDENT_ID} is disabled"
    except Exception as e:
        print("Error!", e)
        # ถ้าดึงสถานะไม่ได้ ให้สื่อว่าไม่มี / ใช้เกณฑ์ปลอดภัย
        return f"No Interface loopback {STUDENT_ID}"

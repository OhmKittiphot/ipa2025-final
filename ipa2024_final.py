#######################################################################################
# Yourname: Kittiphot Mongkolrat
# Your student ID: 66070239
# Your GitHub Repo: https://github.com/OhmKittiphot/IPA2024-Final.git

#######################################################################################
# 1. Import libraries for API requests, JSON formatting, time, os, (restconf_final or netconf_final), netmiko_final, and ansible_final.

import os
import time
import json
import requests

# เลือกใช้ RESTCONF (สำหรับ Part 1)
import restconf_final as dev   # ต้องมีไฟล์ restconf_final.py ตามที่ทำไว้
# Part2
import netmiko_final as nm              # <- ฟังก์ชัน gigabit_status()
import ansible_final as ans             # <- ฟังก์ชัน showrun()
from requests_toolbelt import MultipartEncoder  # <- ส่งไฟล์แนบให้ Webex


requests.packages.urllib3.disable_warnings()    # ปิด warning SSL

# student id สำหรับจับ prefix คำสั่งจาก Webex
STUDENT_ID = "66070239"

#######################################################################################
# 2. Assign the Webex access token to the variable ACCESS_TOKEN using environment variables.

ACCESS_TOKEN = os.environ.get("WEBEX_BOT_TOKEN", "")
if not ACCESS_TOKEN:
    raise RuntimeError("WEBEX_BOT_TOKEN is not set in environment variables")

# เตรียม Bearer header
AUTH_HEADER = f"Bearer {ACCESS_TOKEN}"

#######################################################################################
# 3. Prepare parameters get the latest message for messages API.

# Defines a variable that will hold the roomId
# เลือกใช้ ENV เพื่อไม่ hardcode roomId (ถ้าไม่ได้ตั้ง ENV ให้เติมค่า roomId ตรง fallback)
roomIdToGetMessages = os.environ.get(
    "WEBEX_ROOM_ID",
)

# วนลูปรอข้อความใหม่จากห้อง
while True:
    # always add 1 second of delay to the loop to not go over a rate limit of API calls
    time.sleep(1)

    # the Webex Teams GET parameters
    #  "roomId" is the ID of the selected room
    #  "max": 1  limits to get only the very last message in the room
    getParameters = {"roomId": roomIdToGetMessages, "max": 1}

    # the Webex Teams HTTP header, including the Authoriztion
    getHTTPHeader = {"Authorization": AUTH_HEADER}

    # 4. Provide the URL to the Webex Teams messages API, and extract location from the received message.
    # Send a GET request to the Webex Teams messages API.
    # - Use the GetParameters to get only the latest message.
    # - Store the message in the "r" variable.
    r = requests.get(
        "https://webexapis.com/v1/messages",   # URL ของ Webex Messages API
        params=getParameters,                  # HTTP parameters
        headers=getHTTPHeader,                 # HTTP headers
        verify=False
    )
    # verify if the returned HTTP status code is 200/OK
    if not r.status_code == 200:
        raise Exception(
            "Incorrect reply from Webex Teams API. Status code: {}".format(r.status_code)
        )

    # get the JSON formatted returned data
    json_data = r.json()

    # check if there are any messages in the "items" array
    if len(json_data["items"]) == 0:
        raise Exception("There are no messages in the room.")

    # store the array of messages
    messages = json_data["items"]
    
    # store the text of the first message in the array
    message = messages[0].get("text", "")
    print("Received message: " + message)

    # check if the text of the message starts with the magic character "/" followed by your studentID and a space and followed by a command name
    #  e.g.  "/66070123 create"
    if message.startswith(f"/{STUDENT_ID}"):
        # extract the command (คำ 2 หลัง studentID)
        parts = message.strip().split()
        command = parts[1].lower() if len(parts) > 1 else ""
        print("command:", command)

        # 5. Complete the logic for each command
        responseMessage = "Error: No command or unknown command"  # default

        if command == "create":
            responseMessage = dev.create()
        elif command == "delete":
            responseMessage = dev.delete()
        elif command == "enable":
            responseMessage = dev.enable()
        elif command == "disable":
            responseMessage = dev.disable()
        elif command == "status":
            responseMessage = dev.status()
        elif command == "gigabit_status":
            # Netmiko/TextFSM
            responseMessage = nm.gigabit_status()
        elif command == "showrun":
            # เรียก Ansible playbook
            result = ans.showrun()  # ถ้าสำเร็จ ควร return path ไฟล์ เช่น outputs/showrun_10.0.15.61.txt
            # ถ้า ans.showrun() ดีไซน์ให้คืน "ok" + เขียนไฟล์ คุณปรับตามฟังก์ชันของคุณได้
            if isinstance(result, str) and result.endswith(".txt") and os.path.exists(result):
                responseMessage = "ok"
                showrun_file_path = result
            else:
                # กรณีผิดพลาด ให้ส่ง log ข้อความเต็มกลับห้อง
                responseMessage = result if isinstance(result, str) else str(result)
        else:
            responseMessage = "Error: No command or unknown command"
        
# 6. Complete the code to post the message to the Webex Teams room.

        # The Webex Teams POST JSON data for command showrun
        # - "roomId" is is ID of the selected room
        # - "text": is always "show running config"
        # - "files": is a tuple of filename, fileobject, and filetype.

        # the Webex Teams HTTP headers, including the Authoriztion and Content-Type
        
        # Prepare postData and HTTPHeaders for command showrun
        # Need to attach file if responseMessage is 'ok'; 
        # Read Send a Message with Attachments Local File Attachments
        # https://developer.webex.com/docs/basics for more detail

        if command == "showrun" and responseMessage == 'ok':
            filename = os.path.basename(showrun_file_path)        # เช่น showrun_10.0.15.61.txt
            fileobject = open(showrun_file_path, "rb")            # เปิดไฟล์ที่ ansible สร้าง
            filetype = "text/plain"                               # content-type ของไฟล์ .txt

            # Multipart form
            postData = MultipartEncoder(
                fields={
                    "roomId": roomIdToGetMessages,
                    "text": "show running config",
                    "files": (filename, fileobject, filetype),
                }
            )
            HTTPHeaders = {
                "Authorization": AUTH_HEADER,
                "Content-Type": postData.content_type,
            }
            # Post the call to the Webex Teams message API (multipart)
            r = requests.post(
                "https://webexapis.com/v1/messages",
                data=postData,
                headers=HTTPHeaders,
                verify=False
            )
            # ปิดไฟล์หลังส่ง
            try:
                fileobject.close()
            except:
                pass

            if not r.status_code == 200:
                raise Exception(
                    "Incorrect reply from Webex Teams API. Status code: {}".format(r.status_code)
                )

        else:
            # other commands only send text, or no attached file.
            postData = {"roomId": roomIdToGetMessages, "text": responseMessage}
            postData = json.dumps(postData)

            # the Webex Teams HTTP headers, including the Authoriztion and Content-Type
            HTTPHeaders = {"Authorization": AUTH_HEADER, "Content-Type": "application/json"}   

            # Post the call to the Webex Teams message API.
            r = requests.post(
                "https://webexapis.com/v1/messages",
                data=postData,
                headers=HTTPHeaders,
                verify=False
            )
            if not r.status_code == 200:
                raise Exception(
                    "Incorrect reply from Webex Teams API. Status code: {}".format(r.status_code)
                )
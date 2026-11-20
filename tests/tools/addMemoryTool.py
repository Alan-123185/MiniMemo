
"""
批量发送添加记忆的请求
"""
import asyncio
import re
import requests

async def add_memory(user_id, agent_name, origin_content,session_id, role):
    response = requests.post(
        "http://127.0.0.1:1314/MiniMemo/memory/add",
        json={
            "user_id": user_id,
            "agent_id": agent_name,
            "origin_content": origin_content,
            "session_id": session_id,
            "role": role,
        },
        timeout=30,
    )
    print(response.status_code, response.text)
    response.raise_for_status()

def read_memory_from_file(file_path,session_id):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        content = f.read().replace("\r\n", "\n")

    messages = []
    current_role = None
    current_content = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        question = re.match(r"^问\d*[：:]\s*(.*)$", line)
        answer = re.match(r"^答[：:]\s*(.*)$", line)
        if question or answer:
            if current_role is not None:
                messages.append((current_role, "\n".join(current_content)))
            current_role = "user" if question else "assistant"
            current_content = [question.group(1) if question else answer.group(1)]
        elif current_role is not None:
            current_content.append(line)

    if current_role is not None:
        messages.append((current_role, "\n".join(current_content)))

    async def send_messages():
        for role, message in messages:
            await add_memory(
                user_id="徐姝",
                agent_name="xushu",
                origin_content=message,
                session_id=session_id,
                role=role,
            )

    asyncio.run(send_messages())



if __name__ == "__main__":
    # 读取文件内容并发送请求
    read_memory_from_file("D:/IDEA文件/python文件/MiniMemo/testdatas/healthy.txt","healthy")
    read_memory_from_file("D:/IDEA文件/python文件/MiniMemo/testdatas/codex.txt","codex")
    read_memory_from_file("D:/IDEA文件/python文件/MiniMemo/testdatas/race.txt","race")
    read_memory_from_file("D:/IDEA文件/python文件/MiniMemo/testdatas/keyboard.txt","keyboard")
    read_memory_from_file("D:/IDEA文件/python文件/MiniMemo/testdatas/raze.txt","raze")
    read_memory_from_file("D:/IDEA文件/python文件/MiniMemo/testdatas/study_life.txt","study_life")


import uuid

def sessionId(problems):
    while True:
        id = str(uuid.uuid4())
        if not id in problems:
            break
    return id

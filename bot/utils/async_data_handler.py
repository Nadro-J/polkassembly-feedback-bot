import json
import aiofiles
from datetime import datetime


class AsyncDataHandler:
    def __init__(self, file_path):
        self.file_path = file_path

    async def _read_json(self):
        try:
            async with aiofiles.open(self.file_path, 'r') as f:
                contents = await f.read()
                return json.loads(contents)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    async def _write_json(self, data):
        async with aiofiles.open(self.file_path, 'w') as f:
            await f.write(json.dumps(data, indent=4))

    async def record(self, discord_message_id, context, index, status, created_by_usr, created_by_uid):
        data = await self._read_json()
        created_on = datetime.utcnow().isoformat()

        data[discord_message_id] = {
            "index": index,
            "status": status,
            "context": context,
            "approved": 0,
            "rejected": 0,
            "signatories": [],
            "created_on": created_on,
            "updated_on": created_on,
            "created_by_usr": created_by_usr,
            "created_by_uid": created_by_uid
        }

        await self._write_json(data)

    async def update(self, discord_message_id, **kwargs):
        data = await self._read_json()

        if discord_message_id in data:
            for key, value in kwargs.items():
                if key in data[discord_message_id]:
                    data[discord_message_id][key] = value
            # Update updated_on to current time on any update
            data[discord_message_id]["updated_on"] = datetime.utcnow().isoformat()

        await self._write_json(data)

    async def add_signatory(self, discord_message_id, user_id, username, decision):
        data = await self._read_json()

        if str(discord_message_id) in list(data.keys()):
            signatory = {
                user_id: {
                    "username": username,
                    "decision": decision
                }
            }
            data[str(discord_message_id)]["signatories"].append(signatory)
            # Update updated_on to current time when adding a signatory
            data[str(discord_message_id)]["updated_on"] = datetime.utcnow().isoformat()

        await self._write_json(data)

    async def get_signatories(self, discord_message_id):
        data = await self._read_json()

        if str(discord_message_id) in data \
                and "signatories" in data[str(discord_message_id)] \
                and data[str(discord_message_id)]["signatories"]:
            return list(data[str(discord_message_id)]["signatories"][0].keys())
        else:
            return False

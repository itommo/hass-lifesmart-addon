import logging
import time
import hashlib
import json

import aiohttp

_LOGGER = logging.getLogger(__name__)


class LifeSmartClient:
    """A class for manage LifeSmart API."""

    def __init__(
        self,
        baseurl,
        appkey,
        apptoken,
        usertoken,
        userid,
    ) -> None:
        self._baseurl = baseurl
        self._appkey = appkey
        self._apptoken = apptoken
        self._usertoken = usertoken
        self._userid = userid

    async def get_all_device_async(self):

        url = self.get_api_url() + "/api.EpGetAll"
        tick = int(time.time())
        sdata = (
            "method:EpGetAll,"
            + self.generate_time_and_credential_data(tick)
        )

        send_values = {
            "id": 1,
            "method": "EpGetAll",
            "system": self.generate_system_request_body(tick, sdata),
        }
        header = self.generate_header()
        send_data = json.dumps(send_values)

        response = json.loads(await self.post_async(url, send_data, header))
        if response["code"] == 0:
            return response["message"]
        return False

    async def get_all_scene_async(self, agt):
        url = self.get_api_url() + "/api.SceneGet"
        tick = int(time.time())
        sdata = (
            "method:SceneGet,agt:"
            + agt
            + ","
            + self.generate_time_and_credential_data(tick)
        )
        send_values = {
            "id": 1,
            "method": "SceneGet",
            "params": {
                "agt": agt,
            },
            "system": self.generate_system_request_body(tick, sdata),
        }
        header = self.generate_header()
        send_data = json.dumps(send_values)
        response = json.loads(await self.post_async(url, send_data, header))
        if response["code"] == 0:
            return response["message"]
        return False

    async def set_scene_async(self, agt, id):
        url = self.get_api_url() + "/api.SceneSet"
        tick = int(time.time())
        # keys = str(keys)
        sdata = (
            "method:SceneSet,agt:"
            + agt
            + ",id:"
            + id
            + ","
            + self.generate_time_and_credential_data(tick)
        )
        send_values = {
            "id": 101,
            "method": "SceneSet",
            "params": {
                "agt": agt,
                "id": id,
            },
            "system": self.generate_system_request_body(tick, sdata),
        }
        header = self.generate_header()
        send_data = json.dumps(send_values)

        response = json.loads(await self.post_async(url, send_data, header))
        return response

    async def send_ir_key_async(self, agt, ai, me, category, brand, keys):
        url = self.get_api_url() + "/irapi.SendKeys"
        tick = int(time.time())
        # keys = str(keys)
        sdata = (
            "method:SendKeys,agt:"
            + agt
            + ",ai:"
            + ai
            + ",brand:"
            + brand
            + ",category:"
            + category
            + ",keys:"
            + keys
            + ",me:"
            + me
            + ","
            + self.generate_time_and_credential_data(tick)
        )
        send_values = {
            "id": 1,
            "method": "SendKeys",
            "params": {
                "agt": agt,
                "me": me,
                "category": category,
                "brand": brand,
                "ai": ai,
                "keys": keys,
            },
            "system": self.generate_system_request_body(tick, sdata),
        }
        header = self.generate_header()
        send_data = json.dumps(send_values)

        response = json.loads(await self.post_async(url, send_data, header))
        return response

    async def send_ir_ackey_async(self, agt, ai, me, category, brand, keys, power, mode, temp, wind, swing, ):
        url = self.get_api_url() + "/irapi.SendACKeys"
        tick = int(time.time())
        # keys = str(keys)
        sdata = (
            "method:SendACKeys,agt:"
            + agt
            + ",ai:"
            + ai
            + ",brand:"
            + brand
            + ",category:"
            + category
            + ",keys:"
            + keys
            + ",me:"
            + me
            + ",mode:"
            + str(mode)
            + ",power:"
            + str(power)
            + ",swing:"
            + str(swing)
            + ",temp:"
            + str(temp)
            + ",wind:"
            + str(wind)
            + ","
            + self.generate_time_and_credential_data(tick)
        )
        _LOGGER.debug("sendackey: %s", str(sdata))
        send_values = {
            "id": 1,
            "method": "SendACKeys",
            "params": {
                "agt": agt,
                "me": me,
                "category": category,
                "brand": brand,
                "ai": ai,
                "keys": keys,
                "power": power,
                "mode": mode,
                "temp": temp,
                "wind": wind,
                "swing": swing,
            },
            "system": self.generate_system_request_body(tick, sdata),
        }
        header = self.generate_header()
        send_data = json.dumps(send_values)

        response = json.loads(await self.post_async(url, send_data, header))
        _LOGGER.debug("sendackey_res: %s", str(response))
        return response

    async def send_epset_async(self, type, val, idx, agt, me):
        url = self.get_api_url() + "/api.EpSet"
        tick = int(time.time())
        sdata = (
            "method:EpSet,agt:"
            + agt
            + ",idx:"
            + idx
            + ",me:"
            + me
            + ",type:"
            + type
            + ",val:"
            + str(val)
            + ","
            + self.generate_time_and_credential_data(tick)
        )
        send_values = {
            "id": 1,
            "method": "EpSet",
            "system": self.generate_system_request_body(tick, sdata),
            "params": {"agt": agt, "me": me, "idx": idx, "type": type, "val": val},
        }

        header = self.generate_header()
        send_data = json.dumps(send_values)

        response = json.loads(await self.post_async(url, send_data, header))
        _LOGGER.debug("epset_res: %s", str(response))
        return response["code"]

    async def get_epget_async(self, agt, me):
        url = self.get_api_url() + "/api.EpGet"
        tick = int(time.time())
        sdata = (
            "method:EpGet,agt:"
            + agt
            + ",me:"
            + me
            + ","
            + self.generate_time_and_credential_data(tick)
        )
        send_values = {
            "id": 1,
            "method": "EpGet",
            "system": self.generate_system_request_body(tick, sdata),
            "params": {"agt": agt, "me": me},
        }
        header = self.generate_header()
        send_data = json.dumps(send_values)

        response = json.loads(await self.post_async(url, send_data, header))
        _LOGGER.debug("epget_res: %s", str(response))
        return response["message"]["data"]

    async def get_ir_remote_list_async(self, agt):
        url = self.get_api_url() + "/irapi.GetRemoteList"

        tick = int(time.time())
        sdata = (
            "method:GetRemoteList,agt:"
            + agt
            + ","
            + self.generate_time_and_credential_data(tick)
        )
        send_values = {
            "id": 1,
            "method": "GetRemoteList",
            "params": {"agt": agt},
            "system": self.generate_system_request_body(tick, sdata),
        }
        header = self.generate_header()
        send_data = json.dumps(send_values)

        response = json.loads(await self.post_async(url, send_data, header))
        _LOGGER.debug("GetRemoteList_res: %s", str(response))
        return response["message"]

    async def get_ir_remote_async(self, agt, ai):
        url = self.get_api_url() + "/irapi.GetRemote"

        tick = int(time.time())
        sdata = (
            "method:GetRemote,agt:"
            + agt
            + ",ai:"
            + ai
            + ",needKeys:2"
            + ","
            + self.generate_time_and_credential_data(tick)
        )
        send_values = {
            "id": 1,
            "method": "GetRemote",
            "params": {"agt": agt, "ai": ai, "needKeys": 2},
            "system": self.generate_system_request_body(tick, sdata),
        }
        header = self.generate_header()
        send_data = json.dumps(send_values)

        response = json.loads(await self.post_async(url, send_data, header))
        _LOGGER.debug("get_ir_remote_res: %s", str(response))
        return response["message"]["codes"]

    async def post_async(self, url, data, headers):
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as response:
                r = await response.text()
                return r

    def get_signature(self, data):
        return hashlib.md5(data.encode(encoding="UTF-8")).hexdigest()

    def get_api_url(self):
        return "https://" + self._baseurl + "/app"

    def get_wss_url(self):
        return "wss://" + self._baseurl + ":8443/wsapp/",

    def generate_system_request_body(self, tick, data):
        return {
                "ver": "1.0",
                "lang": "en",
                "userid": self._userid,
                "appkey": self._appkey,
                "time": tick,
                "sign": self.get_signature(data),                
                }

    def generate_time_and_credential_data(self, tick):
        return "time:" + str(tick) + ",userid:" + self._userid + ",usertoken:" + self._usertoken + ",appkey:" + self._appkey + ",apptoken:" + self._apptoken

    def generate_header(self):
        return {"Content-Type": "application/json"}

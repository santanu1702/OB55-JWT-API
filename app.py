#!/usr/bin/env python3
"""
JWT Generator API - Fixed Version
Output format: {server, status, message, token, uid}

Developer : @SRKING5306B
Credits   : @ffapis
"""
import os
import re
import time
import json
import logging
import traceback
import binascii
import warnings

import requests
from flask import Flask, jsonify, request
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from urllib3.exceptions import InsecureRequestWarning

import my_pb2
import output_pb2

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# ==================== SETUP ====================
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
log = logging.getLogger("jwt-api")

app = Flask(__name__)

# ==================== CONSTANTS ====================
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

OAUTH_URL       = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
MAJOR_LOGIN_URL = "https://loginbp.ppmainecoonghj.com/MajorLogin"

_token_cache = {}   # {uid:password -> token_json}

# ==================== OAUTH ====================
def get_token(password, uid):
    key = f"{uid}:{password}"
    if key in _token_cache:
        return _token_cache[key]

    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close",
    }
    data = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067",
    }
    try:
        res = requests.post(OAUTH_URL, headers=headers, data=data,
                            timeout=15, verify=False)
        if res.status_code != 200:
            log.warning(f"OAuth HTTP {res.status_code}: {res.text[:150]}")
            return None
        j = res.json()
        if "access_token" in j and "open_id" in j:
            _token_cache[key] = j
            return j
        log.warning(f"OAuth missing fields: {j}")
        return None
    except Exception as e:
        log.error(f"OAuth error: {e}")
        return None

# ==================== CRYPTO ====================
def encrypt_message(key, iv, plaintext):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(plaintext, AES.block_size))


def decrypt_message(key, iv, ciphertext):
    if not ciphertext or len(ciphertext) % 16 != 0:
        return ciphertext
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(ciphertext), AES.block_size)
    except Exception:
        return ciphertext

# ==================== PROTOBUF PARSE ====================
def parse_garena_response(raw_bytes):
    """Return dict with token, region, status, account_id from Garena_420."""
    out = {"token": None, "region": None, "status": None, "account_id": None}

    # Try protobuf first
    try:
        msg = output_pb2.Momin()
        msg.ParseFromString(raw_bytes)
        if msg.token:
            out["token"] = msg.token
        if msg.region:
            out["region"] = msg.region
        if msg.status:
            out["status"] = msg.status
        if msg.account_id:
            out["account_id"] = msg.account_id
        if out["token"]:
            return out
    except Exception as e:
        log.debug(f"Proto parse failed: {e}")

    # Fallback: decrypt then regex for JWT
    dec = decrypt_message(AES_KEY, AES_IV, raw_bytes)
    try:
        msg = output_pb2.Garena_420()
        msg.ParseFromString(dec)
        if msg.token:
            out["token"] = msg.token
        if msg.region:
            out["region"] = msg.region
        if msg.status:
            out["status"] = msg.status
        if msg.account_id:
            out["account_id"] = msg.account_id
        if out["token"]:
            return out
    except Exception:
        pass

    # Regex fallback on decoded text
    text = dec.decode("utf-8", errors="ignore")
    m = re.search(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", text)
    if m:
        out["token"] = m.group(0)

    return out

# ==================== BUILD GAME DATA ====================
def build_game_data(token_data):
    g = my_pb2.GameData()
    g.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    g.game_name = "free fire"
    g.game_version = 1
    g.version_code = "1.132.1"
    g.os_info = "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)"
    g.device_type = "Handheld"
    g.network_provider = "Verizon Wireless"
    g.connection_type = "WIFI"
    g.screen_width = 1280
    g.screen_height = 960
    g.dpi = "240"
    g.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
    g.total_ram = 5951
    g.gpu_name = "Adreno (TM) 640"
    g.gpu_version = "OpenGL ES 3.0"
    g.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
    g.ip_address = "172.190.111.97"
    g.language = "en"
    g.open_id = token_data["open_id"]
    g.access_token = token_data["access_token"]
    g.platform_type = 4
    g.device_form_factor = "Handheld"
    g.device_model = "Asus ASUS_Z01QD"
    g.field_60 = 32968
    g.field_61 = 29815
    g.field_62 = 2479
    g.field_63 = 914
    g.field_64 = 31213
    g.field_65 = 32968
    g.field_66 = 31213
    g.field_67 = 32968
    g.field_70 = 4
    g.field_73 = 2
    g.library_path = "/data/app/com.dts.freefireth-QPvBnTUhYWE-7DMZSOGdmA==/lib/arm"
    g.field_76 = 1
    g.apk_info = "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-QPvBnTUhYWE-7DMZSOGdmA==/base.apk"
    g.field_78 = 6
    g.field_79 = 1
    g.os_architecture = "32"
    g.build_number = "2019117877"
    g.field_85 = 1
    g.graphics_backend = "OpenGLES2"
    g.max_texture_units = 16383
    g.rendering_api = 4
    g.field_92 = 9204
    g.marketplace = "@SRKING5306B"   # credit tag
    g.encryption_key = "KqsHT2B4It60T/65PGR5PXwFxQkVjGNi+IMCK3CFBCBfrNpSUA1dZnjaT3HcYchlIFFL1ZJOg0cnulKCPGD3C3h1eFQ="
    g.total_storage = 111107
    g.field_97 = 1
    g.field_98 = 1
    g.field_99 = "4"
    g.field_100 = "4"
    return g

# ==================== ROUTE ====================
@app.route('/token', methods=['GET'])
def get_single_response():
    uid = request.args.get('uid')
    password = request.args.get('password')
    try:
        count = int(request.args.get('count', 1))
    except ValueError:
        count = 1

    if not uid or not password:
        return jsonify({"error": "Both uid and password parameters are required"}), 400

    # OAuth
    token_data = get_token(password, uid)
    if not token_data:
        return jsonify({
            "server": "N/A",
            "status": "invalid_credentials",
            "timestamp": time.time(),
            "token": "N/A",
            "uid": uid,
            "message": "Invalid UID or Password",
        }), 400

    results = []

    for _ in range(count):
        try:
            game_data = build_game_data(token_data)
            serialized = game_data.SerializeToString()
            encrypted  = encrypt_message(AES_KEY, AES_IV, serialized)

            headers = {
                "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
                "Accept-Encoding": "deflate, gzip",
                "X-GA-SV": "1789535859",
                "Authorization": "Bearer",
                "X-GA": "v1 1",
                "ReleaseVersion": "OB55",
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Unity-Version": "2018.4.12f1",
            }

            log.info(f"MajorLogin request for uid={uid}")
            response = requests.post(MAJOR_LOGIN_URL, data=encrypted,
                                     headers=headers, verify=False, timeout=15)

            if response.status_code != 200:
                results.append({
                    "server": "N/A",
                    "status": "error",
                    "timestamp": time.time(),
                    "token": "N/A",
                    "uid": uid,
                    "error": f"HTTP {response.status_code}",
                })
                continue

            parsed = parse_garena_response(response.content)

            results.append({
                "server": parsed["region"] or "N/A",
                "status": parsed["status"] or ("live" if parsed["token"] else "error"),
                "message": "success" if parsed["token"] else "no token in response",
                "token": parsed["token"] or "N/A",
                "uid": uid,
            })

        except Exception as e:
            log.error(f"Internal error:\n{traceback.format_exc()}")
            results.append({
                "server": "N/A",
                "status": "error",
                "timestamp": time.time(),
                "token": "N/A",
                "uid": uid,
                "error": f"Internal error: {e}",
            })

    if count == 1:
        return jsonify(results[0] if results else {
            "server": "N/A", "status": "error", "timestamp": time.time(),
            "token": "N/A", "uid": uid, "error": "No tokens generated",
        })
    return jsonify(results)


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": time.time()})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5310))
    app.run(host="0.0.0.0", port=port, debug=False)
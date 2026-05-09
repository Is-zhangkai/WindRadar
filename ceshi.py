
import requests
import sqlite3
import time
import logging
from datetime import datetime
import signal
import sys

# ========== 配置==========
API_HOST = "https://kw3v5an2q7.re.qweatherapi.com"
API_KEY = "d1b303e61b474dfbb17a1bb7a72bac5a"  # API Key
LOCATION = "125.41,43.85"  # 经纬度
INTERVAL = 3600  # 采集间隔（秒）
DB_PATH = "weather_data.db"      # SQLite数据库文件路径

url = f"{API_HOST}/v7/weather/now" #实时天气
url_grid = f"{API_HOST}/v7/grid-weather/now" #实时天气
params = {"location": LOCATION}
headers = {"X-QW-Api-Key": API_KEY}



try:
    response = requests.get(url_grid, headers=headers, params=params, timeout=10)
    response.raise_for_status()  # 如果状态码不是 2xx，抛出异常

    # 自动处理 gzip 压缩，直接打印 JSON 内容
    print("状态码:", response.status_code)
    print("响应内容:", response.json())  # 按 JSON 格式输出

except requests.exceptions.RequestException as e:
    print("请求失败:", e)
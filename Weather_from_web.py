#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project        ：WindRadar 
@File           ：Weather_from_web.py
@Author         ：zhangkai
@Date           ：2026/4/25 17:22 
@Version        : 1.0.0
@Description    : 从动态网页抓取信息
@Record         :260425--从动态网页抓取信息
                 260427--获取数据量较大，保存原始数据时只保留有用数据，增加删除数据库列函数2个

"""

import requests
import sqlite3
import logging
from datetime import datetime
import signal
import csv
import threading
import os

# ========== 配置 ==========

CITY_ID = "Z_0101160303_S441"            # 城市ID

INTERVAL = 1800  # 采集间隔（秒）

# 最美天气API接口
API_BASE_URL = "https://h5-api.zuimeitianqi.com/h5zh/api/pc"
ACTUAL_URL = f"{API_BASE_URL}/actual?cityId={CITY_ID}"  # 实时天气+空气质量+预报

# 请求头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.zuimeitianqi.com/",
}

# 数据保存路径
Data_DIR = "weather_data_zmtq"  # 文件目录
os.makedirs(Data_DIR, exist_ok=True)  # 确保目录存在
DB_FILENAME = "weather_data_zmtq.db"       # SQLite数据库文件路径
CSV_FILENAME = "weather_records_zmtq.csv"  # CSV文件名
LOG_FILENAME = "weather_fetcher_zmtq.log"  # 日志文件名
DB_PATH = os.path.join(Data_DIR, DB_FILENAME)
csv_path = os.path.join(Data_DIR, CSV_FILENAME)
log_path = os.path.join(Data_DIR, LOG_FILENAME)

# ========== 设置日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


# ========== 初始化数据库 ==========
def init_db():
    """创建SQLite数据表（如果不存在）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA auto_vacuum = FULL")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            fetch_time TEXT NOT NULL,      -- 采集时间（ISO格式）
            text TEXT,                     -- 天气描述
            obsTime TEXT,                  -- 数据观测时间
            temp TEXT,                     -- 温度
            feels_like TEXT,               -- 体感温度
            humidity TEXT,                 -- 相对湿度，百分比数值
            wind_speed TEXT,               -- 风速
            wind_dir TEXT,                 -- 风向
            wind360 TEXT,                  -- 风向角
            windScale TEXT,                -- 风力等级
            pressure TEXT,                 -- 气压 默认单位：百帕
            visibility TEXT,               -- 能见度默认单位：公里

            -- 空气质量数据
            aqi REAL,                      -- AQI指数
            pm2p5 REAL,                    -- PM2.5浓度 (μg/m3)
            pm10 REAL,                     -- PM10浓度 (μg/m3)
            no2 REAL,                      -- 二氧化氮浓度 (ppb)
            o3 REAL,                       -- 臭氧浓度 (ppb)
            co REAL,                       -- 一氧化碳浓度 (ppm)

            raw_response TEXT              -- 原始返回数据（备用）
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("数据库初始化完成")
    logging.info(f"数据保存目录: {Data_DIR}")


# ========== 获取天气和空气质量数据（一站式） ==========
def fetch_all_data():
    """从最美天气API获取实时天气和空气质量数据"""
    try:
        response = requests.get(ACTUAL_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            logging.error(f"API返回错误: {data}")
            return None, None

        result = data.get("data", {})
        actual = result.get("actual", {})      # 实时天气
        aqi_data = result.get("aqi", {})       # 空气质量

        # 1. 天气数据
        weather_info = {
            "text": actual.get("weaName"),                     # 天气描述
            "obsTime": actual.get("pubTime"),                  # 观测时间
            "temp": actual.get("temperature"),                 # 温度
            "feels_like": actual.get("realfeel"),              # 体感温度
            "humidity": actual.get("humidity"),                # 湿度
            "wind_speed": actual.get("windspeed"),             # 风速
            "wind_dir": actual.get("windName"),                # 风向
            "wind360": actual.get("winddegrees"),              # 风向角
            "wind_scale": actual.get("windlevel"),             # 风力等级
            "pressure": actual.get("pressure"),                # 气压
            "visibility": actual.get("visibility"),            # 能见度
            # "raw_response": str(data)                          # 原始数据
        }

        # 2. 空气质量数据
        air_quality_info = {
            "aqi": aqi_data.get("aqivalue"),    # AQI指数
            "pm2p5": aqi_data.get("pm25"),      # PM2.5
            "pm10": aqi_data.get("pm10"),       # PM10
            "no2": aqi_data.get("no2"),         # 二氧化氮
            "o3": aqi_data.get("o3"),           # 臭氧
            "co": aqi_data.get("co"),           # 一氧化碳
        }
        # 3. 精简的原始响应（只保留 actual 和 aqi，cityInfo）
        raw = {
            "code": data.get("code"),
            "data": {
                "actual": actual,
                "aqi": aqi_data,
                "cityInfo": result.get("cityInfo", {})
                # 不包含 aqiTop, days, hourAqi, indexList, todayInfo 等
            }
        }
        weather_info["raw_response"] = str(raw)  # 或者使用 json.dumps

        logging.info(f"获取成功 - 温度: {weather_info['temp']}°C, 天气: {weather_info['text']}, AQI: {air_quality_info['aqi']}")
        return weather_info, air_quality_info

    except requests.exceptions.RequestException as e:
        logging.error(f"网络请求失败: {e}")
        return None, None
    except Exception as e:
        logging.error(f"数据解析错误: {e}")
        return None, None


# ========== 保存到数据库 ==========
def save_to_db(weather_data, air_quality_data):
    """保存天气和空气质量数据到数据库"""
    if not weather_data and not air_quality_data:
        logging.warning("无数据可保存")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO weather_records 
        (fetch_time, text, obsTime, temp, feels_like, humidity, 
         wind_speed, wind_dir, wind360, windScale, pressure, visibility,
         aqi, pm2p5, pm10, no2, o3, co, raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),                        # fetch_time
        weather_data.get("text") if weather_data else None,
        weather_data.get("obsTime") if weather_data else None,
        weather_data.get("temp") if weather_data else None,
        weather_data.get("feels_like") if weather_data else None,
        weather_data.get("humidity") if weather_data else None,
        weather_data.get("wind_speed") if weather_data else None,
        weather_data.get("wind_dir") if weather_data else None,
        weather_data.get("wind360") if weather_data else None,
        weather_data.get("wind_scale") if weather_data else None,
        weather_data.get("pressure") if weather_data else None,
        weather_data.get("visibility") if weather_data else None,
        air_quality_data.get("aqi") if air_quality_data else None,
        air_quality_data.get("pm2p5") if air_quality_data else None,
        air_quality_data.get("pm10") if air_quality_data else None,
        air_quality_data.get("no2") if air_quality_data else None,
        air_quality_data.get("o3") if air_quality_data else None,
        air_quality_data.get("co") if air_quality_data else None,
        weather_data.get("raw_response") if weather_data else None,
    ))

    conn.commit()

    # 获取并打印当前总记录数
    cursor.execute("SELECT COUNT(*) FROM weather_records")
    total = cursor.fetchone()[0]
    conn.close()

    logging.info(f"数据保存成功 - 当前数据库共 {total} 条记录")


# ========== 浮点数保留两位小数 ==========
def safe_float(value, decimals=2):
    """安全转换为浮点数并保留两位小数"""
    if value is None:
        return None
    try:
        return round(float(value), decimals)
    except (ValueError, TypeError):
        return value


# ========== 保存到CSV ==========
def save_to_csv(weather_data, air_quality_data):
    """保存天气和空气质量数据到CSV文件"""
    if not weather_data and not air_quality_data:
        logging.warning("无数据可保存到CSV")
        return

    weather = weather_data or {}
    air = air_quality_data or {}

    # 计算风速（km/h 转 m/s）
    wind_speed_ms = None
    if weather.get("wind_speed"):
        try:
            wind_speed_ms = round(float(weather.get("wind_speed")) / 3.6, 2)
        except (ValueError, TypeError):
            pass

    row = {
        "获取时间": datetime.now().isoformat(),
        "天气状况": weather.get("text"),
        "数据更新时间": weather.get("obsTime"),
        "气温": safe_float(weather.get("temp")),
        "体感温度": safe_float(weather.get("feels_like")),
        "湿度": safe_float(weather.get("humidity")),
        "风速(m/s)": wind_speed_ms,
        "风向": weather.get("wind_dir"),
        "风向角": safe_float(weather.get("wind360")),
        "风力等级": weather.get("wind_scale"),
        "气压(hPa)": safe_float(weather.get("pressure")),
        "能见度(km)": safe_float(weather.get("visibility")),
        "AQI": air.get("aqi"),
        "PM2.5": safe_float(air.get("pm2p5")),
        "PM10": safe_float(air.get("pm10")),
        "NO2": safe_float(air.get("no2")),
        "O3": safe_float(air.get("o3")),
        "CO": safe_float(air.get("co")),
    }

    fieldnames = list(row.keys())
    file_exists = os.path.exists(csv_path)

    try:
        with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
                logging.info(f"创建CSV文件并写入表头: {CSV_FILENAME}")
            writer.writerow(row)
        logging.info(f"数据已追加到CSV: {CSV_FILENAME}")
    except Exception as e:
        logging.error(f"CSV写入失败: {e}")


# ========== 导出数据库到CSV ==========
def export_to_csv():
    """将数据库所有数据导出到CSV文件"""
    os.makedirs(Data_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 
            id, fetch_time, text, obsTime, temp, feels_like, humidity,
            wind_speed, wind_dir, wind360, windScale, pressure, visibility,
            aqi, pm2p5, pm10, no2, o3, co
        FROM weather_records 
        ORDER BY fetch_time
    ''')
    rows = cursor.fetchall()
    conn.close()

    if rows:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(Data_DIR, f"weather_export_{timestamp}.csv")

        with open(export_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "fetch_time", "weather", "obsTime", "temp", "feels_like",
                "humidity", "wind_speed", "wind_dir", "wind360", "windScale",
                "pressure", "visibility", "aqi", "pm2p5", "pm10", "no2", "o3", "co"
            ])
            writer.writerows(rows)

        logging.info(f"已导出 {len(rows)} 条记录到 {export_path}")
    else:
        logging.warning("数据库无数据，无法导出")

# ========== 删除raw_response字段的数据(不保留数据) ==========
def clear_raw_response_columns():
    """清空 raw_response字段的数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 将两列的值全部设为 NULL
    cursor.execute("UPDATE weather_records SET raw_response = NULL")

    conn.commit()
    conn.close()
    logging.info("已清空 raw_response 字段的数据")

# ========== 删除raw_response字段的数据(保留最后n行) ==========
def keep_recent_raw_response(n=100):
    """只保留最后 n 条记录的 raw_response，其余设为 NULL"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 获取总记录数
    cursor.execute("SELECT COUNT(*) FROM weather_records")
    total = cursor.fetchone()[0]
    if total <= n:
        logging.info(f"总记录数({total})不超过保留数({n})，无需清理")
        conn.close()
        return
    # 计算需要清理的记录数
    keep_count = n
    delete_count = total - n

    # 方法：找到需要保留的最小 id
    cursor.execute(f'''
        SELECT id FROM weather_records 
        ORDER BY id DESC 
        LIMIT 1 OFFSET {keep_count - 1}
    ''')
    result = cursor.fetchone()
    if result:
        min_keep_id = result[0]
        # 将 id < min_keep_id 的记录的 raw_response 设为 NULL
        cursor.execute('''
                       UPDATE weather_records
                       SET raw_response = NULL
                       WHERE id < ?
                       ''', (min_keep_id,))
        conn.commit()
        logging.info(f"已清理 {delete_count} 条旧记录的 raw_response，仅保留最近 {keep_count} 条")
    else:
        logging.warning("无法确定保留范围")
    conn.close()

# ========== 退出处理 ==========
stop_event = threading.Event()


def signal_handler(sig, frame):
    stop_event.set()
    logging.info("收到退出信号，正在优雅退出...")


signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # 终止信号


# ========== 主循环 ==========
def main():
    logging.info(f"程序启动，采集间隔: {INTERVAL // 3600}小时{(INTERVAL % 3600) // 60}分")
    init_db()

    while not stop_event.is_set():
        data_time = datetime.now().replace(microsecond=0)
        logging.info(f"执行采集: {data_time}")

        # 获取数据（一次性获取天气和空气质量）
        weather_data, air_quality_data = fetch_all_data()

        if weather_data or air_quality_data:
            save_to_db(weather_data, air_quality_data)
            save_to_csv(weather_data, air_quality_data)
        else:
            logging.error("获取数据失败，跳过本次保存")

        # 等待下一次采集
        if stop_event.wait(INTERVAL):
            break

    logging.info("程序正常退出")


if __name__ == "__main__":
    main()
    # clear_raw_response_columns()
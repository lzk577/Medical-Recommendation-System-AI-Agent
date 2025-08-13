# location_server.py

import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP
import aiohttp
import requests

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),         # 输出到控制台
        # logging.FileHandler("log/location_server.log")   # 写入文件
    ]
)
logger = logging.getLogger(__name__)

# 1. Create the MCP server instance
mcp = FastMCP("Location Assistant")

# 2. Define tool functions using the @mcp.tool() decorator
# @mcp.tool()
# async def get_coordinates(address: str) -> dict:
#     """
#     Convert address to latitude and longitude using OpenStreetMap Nominatim API.
#     """
#     url = "https://nominatim.openstreetmap.org/search" # 定位
#     params = {
#         "q": address,
#         "format": "json",
#         "limit": 1
#     }

#     async with aiohttp.ClientSession() as session:
#         async with session.get(url, params=params, headers={"User-Agent": "YourAppName/1.0"}) as response:
#             data = await response.json()
#             if data:
#                 return {
#                     "latitude": float(data[0]["lat"]),
#                     "longitude": float(data[0]["lon"])
#                 }
#             else:
#                 return {"error": "Address not found"}

@mcp.tool()
async def find_nearby_hospitals(address: Optional[str] = None, client_ip: Optional[str] = None, radius_m: int = 10000) -> list: # 半径2000米
    """
    Given a human-readable address, find nearby hospitals within the radius.

    Args:
        address: The address string, e.g. "123 Main St, City, State"
        radius_m: Search radius in meters (default 2000)

    Returns:
        A list of hospitals with name, distance (m), and address.
    """
    # 1. If add is not provided, use IP address to get lat/lon
    # 网站ipapi.co有时会限流，查看日志
    if address is None:
        logger.info("Address not provided. Falling back to IP-based location.")
        url = f"https://ipapi.co/{client_ip}/json/"
        ip_response = requests.get(url)
        ip_data = ip_response.json()
        logger.info(ip_data)
        lat = ip_data.get("latitude")
        lon = ip_data.get("longitude")
        logger.info(f"1Address geocoded to coordinates: ({lat}, {lon})")
    else: # 2. Geocode address to get lat/lon using Nominatim
        logger.info(f"Finding hospitals near address: {address} within {radius_m} meters")
        nominatim_url = "https://nominatim.openstreetmap.org/search" # Nomination API免费网站
        params = {"q": address, "format": "json", "limit": 1}
        # 必须添加自定义 User-Agent, Nominatim不允许匿名请求(LocateAgent/1.0标识身份)
        headers = {"User-Agent": "LocateAgent/1.0 (test@gmail.com)"}

        async with aiohttp.ClientSession() as session:
            async with session.get(nominatim_url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    return [f"Failed to geocode address, status {resp.status}"]
                data = await resp.json()
                if not data:
                    return [f"Address not found: {address}"]

                lat = data[0]["lat"]
                lon = data[0]["lon"]

        logger.info(f"2Address geocoded to coordinates: ({lat}, {lon})")

    # 3. Overpass API (OpenStreetMap) to find hospitals nearby
    headers = {"User-Agent": "LocateAgent/1.0 (test@gmail.com)"}
    overpass_url = "https://overpass-api.de/api/interpreter" # 找医院
    # Overpass QL query: find hospitals within radius_m meters of lat/lon
    query = f"""
    [out:json];
    node["amenity"="hospital"](around:{radius_m},{lat},{lon});
    out center;
    """

    async with aiohttp.ClientSession() as session:
        async with session.post(overpass_url, data=query, headers=headers) as resp:
            if resp.status != 200:
                return [f"Failed to query nearby hospitals, status {resp.status}"]
            result = await resp.json()

    # 将返回的医院提取为列表
    hospitals = []
    for element in result.get("elements", []):
        name = element.get("tags", {}).get("name", "Unnamed Hospital")
        hosp_lat = element.get("lat")
        hosp_lon = element.get("lon")
        # 简单计算距离（球面距离可用更精准算法）
        dist = haversine(float(lat), float(lon), hosp_lat, hosp_lon)
        hospitals.append({
            "name": name,
            "distance_m": round(dist),
            "lat": hosp_lat,
            "lon": hosp_lon
        })

    # 按距离排序
    hospitals.sort(key=lambda x: x["distance_m"])

    return hospitals

# 计算球面距离工具函数
def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth surface.
    Return distance in meters.
    """
    from math import radians, cos, sin, asin, sqrt
    R = 6371000  # Earth radius in meters

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))

    return R * c


# @mcp.tool()
# async def reverse_geocode(lat: Optional[float] = None, lon: Optional[float] = None) -> str:
#     """
#     Converts lat/lon to a human-readable address.
#     If lat/lon is not provided, uses IP-based location first.

#     Args:
#         lat: Latitude
#         lon: Longitude

#     Returns:
#         A human-readable address string.
#     """
#     # Step 1: Use IP address to locate
#     if lat is None or lon is None:
#         logger.info("Latitude/Longitude not provided. Falling back to IP-based location.")
#         ip_response = requests.get("https://ipapi.co/json/")
#         ip_data = ip_response.json()
#         lat = ip_data["latitude"]
#         lon = ip_data["longitude"]

#     logger.info(f"Reverse geocoding coordinates: ({lat}, {lon})")

#     # Step 2: Use Nominatim API to get geocode
#     headers = {"User-Agent": "LocateAgent/1.0 (your_email@example.com)"}
#     url = "https://nominatim.openstreetmap.org/reverse"
#     params = {
#         "lat": lat,
#         "lon": lon,
#         "format": "json"
#     }
#     async with aiohttp.ClientSession(headers=headers) as session:
#         async with session.get(url, params=params) as response:
#             if response.status != 200:
#                 return f"Failed to fetch address, status code: {response.status}"
#             data = await response.json()
#             address = data.get("display_name", None)

#     if address:
#         return f"Your approximate address is: {address}"
#     else:
#         return f"Could not determine address, but your coordinates are: ({lat}, {lon})"



# 3. Allow the script to be run directly
if __name__ == "__main__":
    mcp.run()

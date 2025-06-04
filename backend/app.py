# backend/app.py
from flask import Flask, request, jsonify
import requests
import re
import json
import logging
import sys
import traceback # Added import for traceback

# 配置日志输出
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- 从 kuaishou.py 迁移过来的核心逻辑 ---
def extract_video_url(html_content, source_url=""):
    """从HTML响应中提取视频URL"""
    logger.info(f"开始从来源 {source_url} 提取视频URL...")

    # 尝试查找APOLLO_STATE对象（包含视频信息的JSON对象）
    pattern = r'window\.__APOLLO_STATE__=(.*?);\(function\(\)'
    match = re.search(pattern, html_content, re.DOTALL)

    if not match:
        logger.error("未找到视频信息数据 (__APOLLO_STATE__)")
        return None

    try:
        # 解析JSON数据
        data_str = match.group(1)
        data_str = data_str.replace('\u002F', '/') # 替换 / 为 /
        data = json.loads(data_str)
        logger.info("成功解析JSON数据")

        video_urls = []

        # 方法1: 直接使用正则表达式查找所有包含mp4的URL (在整个data_str中查找)
        # **重要：修复正则表达式**
        mp4_pattern = r'(https?://[^"''\s]+?\.mp4[^"''\s]*)' # 修正后的正则表达式
        # 在之前的版本中，这个表达式可能是 `r'(https?://[^"']+?\.mp4[^"'\s]*)'`
        # 主要变化是确保了对反斜杠的正确处理，并简化了字符集

        mp4_urls_from_data_str = re.findall(mp4_pattern, data_str)
        if mp4_urls_from_data_str:
            logger.info(f"通过正则表达式从data_str找到 {len(mp4_urls_from_data_str)} 个视频链接")
            video_urls.extend(mp4_urls_from_data_str)

        # 方法2: 遍历解析后的JSON对象寻找视频信息
        try:
            all_keys = list(data.keys())
            # logger.info(f"JSON数据顶层键数量: {len(all_keys)}") # 日志可以按需保留

            for key in all_keys:
                # 检查 data[key] 是否为字典类型，以及 __typename 是否匹配
                if isinstance(data.get(key), dict) and data[key].get("__typename") == "VisionVideoDetailPhoto":
                    photo_data = data[key]
                    logger.info(f"找到VisionVideoDetailPhoto数据对象: {key}")

                    if "photoUrl" in photo_data and photo_data["photoUrl"]:
                        video_urls.append(photo_data["photoUrl"])
                        logger.info(f"找到 photoUrl")

                    if "photoH265Url" in photo_data and photo_data["photoH265Url"]:
                        video_urls.append(photo_data["photoH265Url"])
                        logger.info(f"找到 photoH265Url")

                    # 在manifestH265中查找
                    if "manifestH265" in photo_data and isinstance(photo_data["manifestH265"], dict) and \
                       "json" in photo_data["manifestH265"] and isinstance(photo_data["manifestH265"]["json"], dict):
                        manifest_data_h265 = photo_data["manifestH265"]["json"]
                        logger.info("开始解析 manifestH265 数据")
                        if "adaptationSet" in manifest_data_h265 and isinstance(manifest_data_h265["adaptationSet"], list):
                            for adapt_set in manifest_data_h265["adaptationSet"]:
                                if isinstance(adapt_set, dict) and "representation" in adapt_set and isinstance(adapt_set["representation"], list):
                                    for rep in adapt_set["representation"]:
                                        if isinstance(rep, dict) and "url" in rep and rep["url"]:
                                            video_urls.append(rep["url"])
                                            logger.info(f"从 manifestH265 找到URL")
                                        if isinstance(rep, dict) and "backupUrl" in rep and isinstance(rep["backupUrl"], list):
                                            for b_url in rep["backupUrl"]:
                                                if b_url: video_urls.append(b_url)
                                            logger.info(f"从 manifestH265 找到备份URL")

                    # 在videoResource中查找
                    if "videoResource" in photo_data and isinstance(photo_data["videoResource"], dict) and \
                       "json" in photo_data["videoResource"] and isinstance(photo_data["videoResource"]["json"], dict):
                        resource_data = photo_data["videoResource"]["json"]
                        logger.info("开始解析 videoResource 数据")
                        for format_type in ["h264", "hevc"]:
                            if format_type in resource_data and isinstance(resource_data[format_type], dict):
                                format_data = resource_data[format_type]
                                if "adaptationSet" in format_data and isinstance(format_data["adaptationSet"], list):
                                    for adapt_set in format_data["adaptationSet"]:
                                        if isinstance(adapt_set, dict) and "representation" in adapt_set and isinstance(adapt_set["representation"], list):
                                            for rep in adapt_set["representation"]:
                                                if isinstance(rep, dict) and "url" in rep and rep["url"]:
                                                    video_urls.append(rep["url"])
                                                    logger.info(f"从 videoResource/{format_type} 找到URL")
                                                if isinstance(rep, dict) and "backupUrl" in rep and isinstance(rep["backupUrl"], list):
                                                    for b_url in rep["backupUrl"]:
                                                        if b_url: video_urls.append(b_url)
                                                    logger.info(f"从 videoResource/{format_type} 找到备份URL")
                    # 假设一个页面只有一个主要的VisionVideoDetailPhoto，找到后可以提前退出
                    break
        except Exception as e:
            logger.error(f"在解析特定JSON结构时出错: {e}")
            logger.error(traceback.format_exc())


        # 去重并处理URL中的转义字符 (确保在添加URL时已处理或统一处理)
        processed_urls = []
        for url in video_urls:
            if isinstance(url, str): # 确保是字符串再处理
                processed_urls.append(url.replace('\/', '/'))

        final_urls = sorted(list(set(processed_urls))) # 排序去重

        if not final_urls:
            # 如果在JSON结构中未找到，则回退到从原始HTML中提取所有mp4链接
            logger.info("在JSON结构中未找到视频链接，尝试从原始HTML内容中直接提取")
            # 使用修正后的 mp4_pattern
            raw_mp4_urls = re.findall(mp4_pattern, html_content)
            if raw_mp4_urls:
                logger.info(f"从原始HTML中找到 {len(raw_mp4_urls)} 个视频链接")
                processed_raw_urls = []
                for url in raw_mp4_urls:
                    if isinstance(url, str):
                        processed_raw_urls.append(url.replace('\/', '/'))
                final_urls.extend(processed_raw_urls)
                final_urls = sorted(list(set(final_urls)))

        if not final_urls:
            logger.warning("未找到任何视频链接")
            return None

        logger.info(f"总共找到 {len(final_urls)} 个唯一的视频链接: {final_urls}")
        return final_urls

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {e}. Data string (first 500 chars): {data_str[:500]}")
        return None
    except Exception as e:
        logger.error(f"提取视频URL时发生一般错误: {e}")
        logger.error(traceback.format_exc()) # Ensure traceback is logged
        return None
# --- 核心逻辑结束 ---

@app.route('/api/get_video_info', methods=['POST'])
def get_video_info_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"错误": "请求体为空或非JSON格式"}), 400

        target_url = data.get('url')
        cookie_str = data.get('cookie')

        if not target_url:
            return jsonify({"错误": "缺少 'url' 参数"}), 400

        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        }
        if cookie_str:
            headers['cookie'] = cookie_str
            logger.info(f"使用提供的Cookie进行请求")
        else:
            logger.info(f"未提供Cookie，将不带Cookie进行请求")


        logger.info(f"API开始请求目标URL: {target_url}")
        response = requests.get(target_url, headers=headers, timeout=15)
        response.raise_for_status()
        html_content = response.text
        logger.info(f"成功获取目标URL内容。内容长度: {len(html_content)}")

        video_urls = extract_video_url(html_content, source_url=target_url)

        if video_urls:
            logger.info(f"成功提取到视频链接: {video_urls}")
            return jsonify({"视频链接": video_urls, "消息": "视频链接提取成功"}), 200
        else:
            logger.error(f"未能从 {target_url} 提取到视频链接")
            return jsonify({"错误": "无法提取视频链接，请检查URL或稍后再试。查看后端日志获取更多信息。"}), 404

    except requests.exceptions.Timeout:
        logger.error(f"请求超时: {target_url}")
        return jsonify({"错误": f"请求目标URL超时: {target_url}"}), 504
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP错误: {http_err} - {response.status_code if 'response' in locals() else 'N/A'}") # Check if response exists
        status_code = response.status_code if 'response' in locals() else 500
        return jsonify({"错误": f"请求目标URL时发生HTTP错误: {http_err}", "状态码": status_code}), status_code
    except requests.exceptions.RequestException as req_err:
        logger.error(f"请求错误: {req_err}")
        return jsonify({"错误": f"请求目标URL时发生错误: {req_err}"}), 500
    except Exception as e:
        logger.error(f"处理 /api/get_video_info 请求时发生未知错误: {e}")
        logger.error(traceback.format_exc()) # Ensure traceback is logged
        return jsonify({"错误": f"服务器内部错误: {str(e)}"}), 500 # Return str(e) for basic error info

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

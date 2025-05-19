import requests
import re
import json
import logging
import sys

# 配置日志输出
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def extract_video_url(html_content):
    """从HTML响应中提取视频URL"""
    logger.info("开始提取视频URL...")

    # 尝试查找APOLLO_STATE对象（包含视频信息的JSON对象）
    pattern = r'window\.__APOLLO_STATE__=(.*?);\(function\(\)'
    match = re.search(pattern, html_content, re.DOTALL)

    if not match:
        logger.error("未找到视频信息数据")
        return None

    try:
        # 解析JSON数据
        data_str = match.group(1)
        # 替换掉转义的斜杠，使URL更易于解析
        data_str = data_str.replace('\\u002F', '/')
        data = json.loads(data_str)
        logger.info("成功解析JSON数据")

        # 视频链接可能存在的多种位置
        video_urls = []

        # 方法1: 直接使用正则表达式查找所有包含mp4的URL
        mp4_pattern = r'(https?://[^"\']+?\.mp4[^"\'\s]*)'
        mp4_urls = re.findall(mp4_pattern, data_str)
        if mp4_urls:
            logger.info(f"通过正则表达式找到 {len(mp4_urls)} 个视频链接")
            video_urls.extend(mp4_urls)

        # 方法2: 直接查找包含特定字段的结构
        try:
            # 查找主要视频URL（photoUrl字段）
            all_keys = list(data.keys())
            logger.info(f"JSON数据顶层键数量: {len(all_keys)}")

            # 遍历顶层对象寻找VisionVideoDetailPhoto
            for key in all_keys:
                if isinstance(data[key], dict) and data[key].get("__typename") == "VisionVideoDetailPhoto":
                    photo_data = data[key]
                    logger.info(f"找到VisionVideoDetailPhoto数据: {key}")

                    # 1. 提取直接的photoUrl
                    if "photoUrl" in photo_data:
                        photo_url = photo_data["photoUrl"]
                        logger.info(f"找到photoUrl: {photo_url[:100]}...")
                        video_urls.append(photo_url)

                    # 2. 提取photoH265Url
                    if "photoH265Url" in photo_data:
                        h265_url = photo_data["photoH265Url"]
                        logger.info(f"找到photoH265Url: {h265_url[:100]}...")
                        video_urls.append(h265_url)

                    # 3. 在manifestH265中查找
                    if "manifestH265" in photo_data and "json" in photo_data["manifestH265"]:
                        manifest_data = photo_data["manifestH265"]["json"]
                        logger.info("开始解析manifestH265数据")

                        # 遍历adaptationSet
                        if "adaptationSet" in manifest_data:
                            for adapt_set in manifest_data["adaptationSet"]:
                                if "representation" in adapt_set:
                                    for rep in adapt_set["representation"]:
                                        if "url" in rep:
                                            url = rep["url"]
                                            logger.info(f"从manifestH265找到URL: {url[:100]}...")
                                            video_urls.append(url)

                                            # 同时提取备份URL
                                            if "backupUrl" in rep and isinstance(rep["backupUrl"], list):
                                                for backup_url in rep["backupUrl"]:
                                                    logger.info(f"从manifestH265找到备份URL")
                                                    video_urls.append(backup_url)

                    # 4. 在videoResource中查找
                    if "videoResource" in photo_data and "json" in photo_data["videoResource"]:
                        resource_data = photo_data["videoResource"]["json"]
                        logger.info("开始解析videoResource数据")

                        # 检查h264和hevc格式
                        for format_type in ["h264", "hevc"]:
                            if format_type in resource_data:
                                format_data = resource_data[format_type]
                                logger.info(f"找到{format_type}格式数据")

                                if "adaptationSet" in format_data:
                                    for adapt_set in format_data["adaptationSet"]:
                                        if "representation" in adapt_set:
                                            for rep in adapt_set["representation"]:
                                                if "url" in rep:
                                                    url = rep["url"]
                                                    logger.info(f"从videoResource/{format_type}找到URL")
                                                    video_urls.append(url)

                                                    # 提取备份URL
                                                    if "backupUrl" in rep and isinstance(rep["backupUrl"], list):
                                                        for backup_url in rep["backupUrl"]:
                                                            logger.info(f"从videoResource/{format_type}找到备份URL")
                                                            video_urls.append(backup_url)

                    break  # 找到一个VisionVideoDetailPhoto就退出循环
        except Exception as e:
            logger.error(f"解析特定字段时出错: {e}")

        # 去重并处理URL中的转义字符
        video_urls = [url.replace('\\/', '/') for url in video_urls]
        video_urls = list(set(video_urls))

        if not video_urls:
            # 最后尝试：直接从HTML中提取所有mp4链接
            logger.info("尝试从原始HTML中直接提取视频链接")
            raw_mp4_pattern = r'https?://[^"\']+?\.mp4[^"\'\s]*'
            raw_mp4_urls = re.findall(raw_mp4_pattern, html_content)
            if raw_mp4_urls:
                logger.info(f"从原始HTML中找到 {len(raw_mp4_urls)} 个视频链接")
                video_urls.extend(raw_mp4_urls)
                video_urls = list(set(video_urls))

        if not video_urls:
            logger.warning("未找到任何视频链接")
            return None

        logger.info(f"总共找到 {len(video_urls)} 个视频链接")
        return video_urls

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {e}")
        return None
    except Exception as e:
        logger.error(f"提取视频URL时发生错误: {e}")
        logger.error(f"错误详情: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def main():
    url = 'https://www.kuaishou.com/short-video/3xu7a8thm3w39ne?authorId=3xfae9p534hfnag&streamSource=profile&area=profilexxnull'

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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'cookie': '填写你的cookie'
    }

    try:
        # 发送请求
        logger.info(f"开始请求URL: {url}")
        response = requests.get(url, headers=headers, timeout=10,
                                proxies={"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"})
        response.raise_for_status()  # 检查请求是否成功
        text = response.text
        logger.info("请求成功，获取到响应内容")

        # 提取简短的响应预览
        preview = text[:100] + "..." if len(text) > 100 else text
        logger.info(f"响应内容预览: {preview}")

        # 提取视频URL
        video_urls = extract_video_url(text)

        if video_urls:
            logger.info("成功提取视频链接:")
            for i, url in enumerate(video_urls, 1):
                print(f"\n视频链接 {i}:\n{url}")
        else:
            logger.error("无法提取视频链接")

    except requests.exceptions.RequestException as e:
        logger.error(f"请求错误: {e}")
    except Exception as e:
        logger.error(f"发生未知错误: {e}")
        logger.error(f"错误详情: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()

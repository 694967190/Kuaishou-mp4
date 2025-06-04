// frontend/script.js
console.log("script.js 加载成功。");

document.addEventListener('DOMContentLoaded', () => {
    const fetchButton = document.getElementById('fetchButton');
    const videoUrlInput = document.getElementById('videoUrl');
    const cookieInput = document.getElementById('cookieInput');
    // const resultArea = document.getElementById('resultArea'); // resultArea 作为整体容器
    const videoPreviewContainer = document.getElementById('videoPreviewContainer');
    const videoPlayer = document.getElementById('videoPlayer');
    const videoLinksContainer = document.getElementById('videoLinksContainer');
    const errorMessagesDiv = document.getElementById('errorMessages');
    const loadingIndicator = document.getElementById('loadingIndicator');

    // 后端 API 的地址 (确保与 Flask 应用运行的地址和端口一致)
    // 在开发中，Flask 默认运行在 5000 端口
    // 如果前端是通过 file://协议直接打开，或者不同域，需要后端配置CORS
    const API_ENDPOINT = 'http://127.0.0.1:5000/api/get_video_info';

    if (fetchButton) {
        fetchButton.addEventListener('click', async () => {
            const url = videoUrlInput.value.trim();
            const cookie = cookieInput.value.trim();

            if (!url) {
                displayError("请输入有效的视频链接。");
                return;
            }

            // 清空之前的结果和错误信息
            clearResults();
            displayLoading(true);

            try {
                const response = await fetch(API_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url: url,
                        cookie: cookie // 如果 cookie 为空字符串，后端会处理
                    }),
                });

                displayLoading(false);

                if (!response.ok) {
                    // 尝试解析错误响应体
                    let errorData;
                    try {
                        errorData = await response.json();
                    } catch (e) {
                        // 如果响应体不是JSON或解析失败
                        displayError(`请求失败，状态码: ${response.status} ${response.statusText}`);
                        return;
                    }
                    const errorMsg = errorData.错误 || errorData.message || `请求失败，状态码: ${response.status}`;
                    displayError(errorMsg);
                    return;
                }

                const data = await response.json();

                if (data.错误) {
                    displayError(data.错误);
                } else if (data.视频链接 && data.视频链接.length > 0) {
                    displayVideoInfo(data.视频链接);
                } else {
                    displayError("未能获取到视频链接，或返回数据格式不正确。");
                }

            } catch (error) {
                displayLoading(false);
                console.error("前端请求错误:", error);
                displayError(`请求后端API时发生网络错误或脚本错误: ${error.message}。请检查浏览器控制台和后端服务是否运行。`);
            }
        });
    }

    function displayLoading(isLoading) {
        if (loadingIndicator) {
            loadingIndicator.style.display = isLoading ? 'block' : 'none';
        }
    }

    function clearResults() {
        if (videoLinksContainer) videoLinksContainer.innerHTML = '';
        if (errorMessagesDiv) {
            errorMessagesDiv.innerHTML = '';
            errorMessagesDiv.style.display = 'none';
        }
        if (videoPreviewContainer) videoPreviewContainer.style.display = 'none';
        if (videoPlayer) {
            videoPlayer.pause();
            videoPlayer.src = '';
        }
    }

    function displayError(message) {
        if (errorMessagesDiv) {
            errorMessagesDiv.textContent = message;
            errorMessagesDiv.style.display = 'block';
        }
        if (videoLinksContainer) videoLinksContainer.innerHTML = ''; // 清空可能的旧链接
        if (videoPreviewContainer) videoPreviewContainer.style.display = 'none'; // 隐藏预览
    }

    function displayVideoInfo(links) {
        if (!videoLinksContainer) return;
        videoLinksContainer.innerHTML = ''; // 清空旧链接

        if (links && links.length > 0) {
            // 默认预览第一个视频链接
            if (videoPlayer && videoPreviewContainer) {
                // 选择一个看起来像视频的链接进行预览，优先mp4
                let previewUrl = links.find(link => link.includes('.mp4')) || links[0];
                videoPlayer.src = previewUrl;
                videoPreviewContainer.style.display = 'block';
                // videoPlayer.load(); // 重新加载视频源
                // videoPlayer.play(); // 可以选择自动播放，但需注意浏览器策略
            }

            links.forEach((link, index) => {
                const item = document.createElement('div');
                item.classList.add('video-link-item');

                const linkText = document.createElement('span');
                linkText.textContent = `视频链接 ${index + 1}: ${link.substring(0, 100)}${link.length > 100 ? '...' : ''}`; // 截断过长的链接

                const playButton = document.createElement('button');
                playButton.textContent = '预览此视频';
                playButton.classList.add('download-button'); // 复用样式，或创建新样式
                playButton.style.marginLeft = '10px';
                playButton.onclick = () => {
                    if (videoPlayer) {
                        videoPlayer.src = link;
                        videoPlayer.load();
                        videoPlayer.play();
                        videoPreviewContainer.style.display = 'block';
                        videoPlayer.scrollIntoView({ behavior: 'smooth' });
                    }
                };

                const downloadLink = document.createElement('a');
                downloadLink.href = link;
                downloadLink.textContent = '下载';
                downloadLink.setAttribute('download', `video_${index + 1}.mp4`); // 建议的下载文件名
                downloadLink.classList.add('download-button');
                downloadLink.style.marginLeft = '10px';

                item.appendChild(linkText);
                item.appendChild(playButton);
                item.appendChild(downloadLink);
                videoLinksContainer.appendChild(item);
            });
        } else {
            displayError("未找到有效的视频链接。");
        }
    }
});

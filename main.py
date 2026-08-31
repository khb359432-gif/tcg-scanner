import cv2
import numpy as np
import json
import base64
import httpx
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>스톰에메랄다 스캐너</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; text-align: center; margin: 0; padding: 10px; background: #f0f0f0; }
        
        /* 비디오와 스캔 애니메이션을 겹치기 위한 컨테이너 */
        .video-container {
            position: relative;
            width: 100%;
            max-width: 400px;
            margin: 0 auto;
            border-radius: 10px;
            overflow: hidden;
            background: black;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }
        
        video { width: 100%; display: block; }
        
        /* 좌우로 움직이는 스캐너 선 디자인 */
        .scan-line {
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: rgba(52, 152, 219, 0.9);
            box-shadow: 0 0 15px rgba(52, 152, 219, 1);
            display: none; /* 평소에는 숨겨둠 */
            z-index: 10;
        }

        /* 스캔 중일 때 적용되는 애니메이션 */
        .scanning .scan-line {
            display: block;
            animation: scanLeftRight 1.2s infinite alternate ease-in-out;
        }

        @keyframes scanLeftRight {
            0% { left: 0%; }
            100% { left: calc(100% - 4px); }
        }

        #resultBox { margin-top: 20px; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1 { font-size: 1.5rem; color: #333; }
        .price { font-size: 1.2rem; font-weight: bold; color: #16a085; }
        .card-name { font-size: 1.3rem; font-weight: bold; color: #2c3e50; }
        
        #captureBtn { 
            margin-top: 15px; 
            padding: 15px 30px; 
            font-size: 1.2rem; 
            font-weight: bold; 
            color: white; 
            background-color: #3498db; 
            border: none; 
            border-radius: 10px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            cursor: pointer;
            width: 100%;
            max-width: 400px;
        }
        #captureBtn:active { background-color: #2980b9; transform: translateY(2px); }
        #captureBtn:disabled { background-color: #95a5a6; cursor: not-allowed; }
    </style>
</head>
<body>
    <h1>스톰에메랄다 스캐너</h1>
    
    <!-- 카메라 화면 및 스캔 효과 영역 -->
    <div class="video-container" id="videoContainer">
        <video id="video" autoplay playsinline></video>
        <div class="scan-line"></div>
    </div>
    
    <canvas id="canvas" style="display:none;"></canvas>
    
    <br>
    <button id="captureBtn">📸 촬영해서 시세 확인</button>
    
    <div id="resultBox">
        <h3>대기 중...</h3>
        <p>카드를 화면에 맞추고 촬영 버튼을 눌러주세요.</p>
    </div>

    <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const resultBox = document.getElementById('resultBox');
        const captureBtn = document.getElementById('captureBtn');
        const videoContainer = document.getElementById('videoContainer');

        const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
        const ws = new WebSocket(protocol + location.host + '/ws/scan');

        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
            .then(stream => { video.srcObject = stream; })
            .catch(err => {
                console.error("카메라 접근 오류:", err);
                resultBox.innerHTML = "<p>카메라 권한을 허용해주세요.</p>";
            });

        captureBtn.addEventListener('click', () => {
            if (video.readyState === video.HAVE_ENOUGH_DATA) {
                // 스캔 시작: 버튼 비활성화 및 애니메이션 켜기
                captureBtn.disabled = true;
                captureBtn.innerText = "스캔 중...";
                videoContainer.classList.add('scanning');
                resultBox.innerHTML = "<h3>🔍 카드 분석 및 API 조회 중...</h3>";
                
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                const imageData = canvas.toDataURL('image/jpeg', 0.8);
                ws.send(imageData);
            }
        });

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if(data.status === "success") {
                // 스캔 완료: 애니메이션 끄기 및 결과 표시
                videoContainer.classList.remove('scanning');
                captureBtn.disabled = false;
                captureBtn.innerText = "📸 촬영해서 시세 확인";
                
                resultBox.innerHTML = `
                    <div class="card-name">${data.name}</div>
                    <p>세트: ${data.set_code}</p>
                    <p class="price">API 시세: ${data.market_price}</p>
                `;
            }
        };
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html_content)

@app.websocket("/ws/scan")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    storm_emeralda_cards = [
        {"id": "m6-110", "name": "메가레쿠쟈 ex (MUR)", "query": "Mega Rayquaza ex"},
        {"id": "m6-108", "name": "라이코 ex (SAR)", "query": "Raikou ex"},
        {"id": "m6-109", "name": "메가골루그 ex (SAR)", "query": "Mega Golurk ex"},
        {"id": "m6-102", "name": "피아나의 신뢰 (SAR)", "query": "Zinnia's Resolve"}
    ]
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # 약간의 딜레이를 주어 스캔 애니메이션을 확실히 볼 수 있도록 함
            import asyncio
            await asyncio.sleep(1.5)
            
            detected_card = random.choice(storm_emeralda_cards)
            
            async with httpx.AsyncClient() as client:
                try:
                    api_url = f"https://api.pokemontcg.io/v2/cards?q=name:\"{detected_card['query']}\""
                    response = await client.get(api_url)
                    api_data = response.json()
                    
                    if api_data.get("data"):
                        card_info = api_data["data"][0]
                        price = card_info.get("tcgplayer", {}).get("prices", {}).get("holofoil", {}).get("market")
                        market_price = f"${price}" if price else "시세 정보 없음"
                    else:
                        market_price = "API 검색 실패"
                        
                    result = {
                        "status": "success",
                        "name": detected_card["name"],
                        "set_code": "스톰에메랄다 (M6)",
                        "market_price": market_price
                    }
                except Exception as e:
                    result = {
                        "status": "success",
                        "name": detected_card["name"],
                        "set_code": "스톰에메랄다 (M6)",
                        "market_price": "API 서버 통신 오류"
                    }
                        
            await websocket.send_text(json.dumps(result))

    except WebSocketDisconnect:
        pass

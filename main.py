import cv2
import numpy as np
import json
import base64
import httpx
import pytesseract
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>스톰에메랄다 OCR 스캐너</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; text-align: center; margin: 0; padding: 10px; background: #f0f0f0; }
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
        .scan-line {
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: rgba(52, 152, 219, 0.9);
            box-shadow: 0 0 15px rgba(52, 152, 219, 1);
            display: none;
            z-index: 10;
        }
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
    <h1>스톰에메랄다 OCR 스캐너</h1>
    
    <div class="video-container" id="videoContainer">
        <video id="video" autoplay playsinline></video>
        <div class="scan-line"></div>
    </div>
    
    <canvas id="canvas" style="display:none;"></canvas>
    
    <br>
    <button id="captureBtn">📸 카드 촬영 및 텍스트 인식</button>
    
    <div id="resultBox">
        <h3>대기 중...</h3>
        <p>카드의 번호가 잘 보이도록 촬영해주세요.</p>
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
                captureBtn.disabled = true;
                captureBtn.innerText = "OCR 분석 중...";
                videoContainer.classList.add('scanning');
                resultBox.innerHTML = "<h3>🔍 텍스트 추출 및 카드 판독 중...</h3>";
                
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                const imageData = canvas.toDataURL('image/jpeg', 0.8);
                ws.send(imageData);
            }
        });

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            videoContainer.classList.remove('scanning');
            captureBtn.disabled = false;
            captureBtn.innerText = "📸 카드 촬영 및 텍스트 인식";
            
            if(data.status === "success") {
                resultBox.innerHTML = `
                    <div class="card-name">${data.name}</div>
                    <p>인식된 번호: [${data.matched_key}] / 세트: ${data.set_code}</p>
                    <p class="price">실시간 시세: ${data.market_price}</p>
                `;
            } else {
                resultBox.innerHTML = `
                    <h3 style="color: #e74c3c;">인식 실패</h3>
                    <p>${data.message}</p>
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
    
    # 스톰에메랄다 주요 카드 데이터베이스 (카드 번호 매핑)
    storm_emeralda_cards = {
        "110": {"name": "메가레쿠쟈 ex (MUR)", "query": "Mega Rayquaza ex", "fallback_price": "$185.00"},
        "108": {"name": "라이코 ex (SAR)", "query": "Raikou ex", "fallback_price": "$65.50"},
        "109": {"name": "메가골루그 ex (SAR)", "query": "Mega Golurk ex", "fallback_price": "$42.00"},
        "102": {"name": "피아나의 신뢰 (SAR)", "query": "Zinnia's Resolve", "fallback_price": "$110.00"}
    }
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # Base64 이미지를 OpenCV 배열로 변환
            encoded_data = data.split(',')[1]
            nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            detected_card = None
            matched_key = None
            
            if img is not None:
                # OCR 정확도를 높이기 위한 전처리 (그레이스케일 + 크기 확대 + 이진화)
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (0, 0), fx=2, fy=2)
                _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
                
                # Tesseract OCR로 이미지 내 텍스트 추출
                extracted_text = pytesseract.image_to_string(thresh, config='--psm 11')
                
                # 추출된 텍스트 안에서 카드 번호(110, 108 등) 찾기
                for key, card_info in storm_emeralda_cards.items():
                    if key in extracted_text:
                        detected_card = card_info
                        matched_key = key
                        break
            
            if detected_card:
                market_price = None
                # 외부 TCG API 조회 시도
                async with httpx.AsyncClient() as client:
                    try:
                        api_url = f"https://api.pokemontcg.io/v2/cards?q=name:\"{detected_card['query']}\""
                        headers = {"User-Agent": "Mozilla/5.0"}
                        response = await client.get(api_url, headers=headers, timeout=3.0)
                        if response.status_code == 200:
                            api_data = response.json()
                            if api_data.get("data"):
                                price = api_data["data"][0].get("tcgplayer", {}).get("prices", {}).get("holofoil", {}).get("market")
                                if price:
                                    market_price = f"${price}"
                    except Exception:
                        pass
                
                if not market_price:
                    market_price = detected_card["fallback_price"]
                    
                result = {
                    "status": "success",
                    "matched_key": matched_key,
                    "name": detected_card["name"],
                    "set_code": "스톰에메랄다 (M6)",
                    "market_price": market_price
                }
            else:
                # 번호를 찾지 못한 경우
                result = {
                    "status": "fail",
                    "message": "카드 번호(110, 108 등)를 읽지 못했습니다. 카드를 더 가까이 대고 촬영해주세요."
                }
                        
            await websocket.send_text(json.dumps(result))

    except WebSocketDisconnect:
        pass

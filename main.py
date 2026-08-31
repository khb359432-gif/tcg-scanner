import cv2
import numpy as np
import json
import base64
import httpx  # 외부 API 비동기 호출을 위한 라이브러리
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
        video { width: 100%; max-width: 400px; border-radius: 10px; background: black; }
        #resultBox { margin-top: 20px; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1 { font-size: 1.5rem; color: #333; }
        .price { font-size: 1.2rem; font-weight: bold; color: #16a085; }
        .card-name { font-size: 1.3rem; font-weight: bold; color: #2c3e50; }
    </style>
</head>
<body>
    <h1>스톰에메랄다(M6) 스캐너</h1>
    <video id="video" autoplay playsinline></video>
    <canvas id="canvas" style="display:none;"></canvas>
    
    <div id="resultBox">
        <h3>스캔 대기 중...</h3>
        <p>카드를 카메라에 비춰주세요.</p>
    </div>

    <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const resultBox = document.getElementById('resultBox');

        const ws = new WebSocket(`ws://${location.host}/ws/scan`);

        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
            .then(stream => { video.srcObject = stream; })
            .catch(err => {
                console.error("카메라 접근 오류:", err);
                resultBox.innerHTML = "<p>카메라 권한을 허용해주세요.</p>";
            });

        ws.onopen = () => {
            setInterval(() => {
                if (video.readyState === video.HAVE_ENOUGH_DATA) {
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    const imageData = canvas.toDataURL('image/jpeg', 0.8);
                    ws.send(imageData);
                }
            }, 1000); 
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if(data.status === "success") {
                resultBox.innerHTML = `
                    <div class="card-name">${data.name}</div>
                    <p>세트: ${data.set_code}</p>
                    <p class="price">API 시세: ${data.market_price}</p>
                `;
            } else if (data.status === "waiting") {
                resultBox.innerHTML = `
                    <h3>스캔 대기 중...</h3>
                    <p>카드를 카메라에 비춰주세요.</p>
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
    
    # 스톰에메랄다(M6) 주요 힛카드 데이터셋 (API 검색용 영문 쿼리 포함)
    storm_emeralda_cards = [
        {"id": "m6-110", "name": "메가레쿠쟈 ex (MUR)", "query": "Mega Rayquaza ex"},
        {"id": "m6-108", "name": "라이코 ex (SAR)", "query": "Raikou ex"},
        {"id": "m6-109", "name": "메가골루그 ex (SAR)", "query": "Mega Golurk ex"},
        {"id": "m6-102", "name": "피아나의 신뢰 (SAR)", "query": "Zinnia's Resolve"}
    ]
    
    try:
        while True:
            data = await websocket.receive_text()
            encoded_data = data.split(',')[1]
            nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is not None:
                # 카드 외곽선 탐지
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                edges = cv2.Canny(blurred, 50, 150)
                contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                
                card_detected = False
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest_contour) > 50000:
                        card_detected = True
                        
                if card_detected:
                    # OCR/이미지 처리로 정확한 카드를 식별하는 로직이 들어갈 자리입니다.
                    # 현재는 스톰에메랄다 카드 중 무작위로 인식되었다고 시뮬레이션합니다.
                    detected_card = random.choice(storm_emeralda_cards)
                    
                    # 2. Pokémon TCG API 비동기 호출
                    async with httpx.AsyncClient() as client:
                        try:
                            # 실제 API 엔드포인트에 쿼리 전송
                            api_url = f"https://api.pokemontcg.io/v2/cards?q=name:\"{detected_card['query']}\""
                            response = await client.get(api_url)
                            api_data = response.json()
                            
                            # API 응답에서 가격 파싱
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
                            # API 통신 에러 처리
                            result = {
                                "status": "success",
                                "name": detected_card["name"],
                                "set_code": "스톰에메랄다 (M6)",
                                "market_price": "API 서버 통신 오류"
                            }
                            
                    await websocket.send_text(json.dumps(result))
                else:
                    await websocket.send_text(json.dumps({"status": "waiting"}))

    except WebSocketDisconnect:
        print("사용자 연결 종료")
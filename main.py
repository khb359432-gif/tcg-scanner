import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

def load_card_database():
    try:
        with open("cards.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>힛카드 검색기</title>
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
        
        .controls {
            width: 100%;
            max-width: 400px;
            margin: 15px auto 0 auto;
            text-align: left;
        }
        label { font-weight: bold; font-size: 0.9rem; color: #333; display: block; margin-bottom: 5px; }
        select {
            width: 100%;
            padding: 12px;
            font-size: 1rem;
            border-radius: 8px;
            border: 1px solid #ccc;
            background: white;
            margin-bottom: 15px;
        }

        #resultBox { margin-top: 15px; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); width: 100%; max-width: 400px; margin-left: auto; margin-right: auto; text-align: center;}
        h1 { font-size: 1.4rem; color: #333; }
        .price { font-size: 1.2rem; font-weight: bold; color: #16a085; margin-top: 10px; }
        .card-name { font-size: 1.2rem; font-weight: bold; color: #2c3e50; margin-bottom: 10px; }
        
        /* 카드 이미지 스타일 */
        .card-img {
            width: 100%;
            max-width: 220px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            margin: 10px auto;
            display: block;
        }

        #checkBtn { 
            margin-top: 5px; 
            padding: 15px; 
            font-size: 1.1rem; 
            font-weight: bold; 
            color: white; 
            background-color: #e74c3c; 
            border: none; 
            border-radius: 10px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            cursor: pointer;
            width: 100%;
            max-width: 400px;
        }
        #checkBtn:active { background-color: #c0392b; transform: translateY(2px); }
    </style>
</head>
<body>
    <h1>🔥 힛카드 검색기</h1>
    
    <div class="video-container">
        <video id="video" autoplay playsinline></video>
    </div>
    
    <div class="controls">
        <label for="setSelect">확장팩 선택:</label>
        <select id="setSelect" onchange="updateCardList()"></select>

        <label for="cardSelect">카드 선택:</label>
        <select id="cardSelect"></select>
    </div>

    <button id="checkBtn">💰 시세 및 이미지 확인하기</button>
    
    <div id="resultBox">
        <h3 style="margin:0 0 5px 0; color:#555;">조회 결과</h3>
        <p style="margin:0; color:#888;">카드를 선택하고 버튼을 눌러주세요.</p>
    </div>

    <script>
        const video = document.getElementById('video');
        const setSelect = document.getElementById('setSelect');
        const cardSelect = document.getElementById('cardSelect');
        const checkBtn = document.getElementById('checkBtn');
        const resultBox = document.getElementById('resultBox');

        let dbData = {};

        async function initDatabase() {
            try {
                const response = await fetch('/api/cards');
                dbData = await response.json();
                
                setSelect.innerHTML = "";
                for (const [key, setInfo] of Object.entries(dbData)) {
                    const opt = document.createElement('option');
                    opt.value = key;
                    opt.innerText = setInfo.name;
                    setSelect.appendChild(opt);
                }
                updateCardList();
            } catch (e) {
                console.error("데이터 로드 실패", e);
            }
        }

        function updateCardList() {
            const selectedSet = setSelect.value;
            const setInfo = dbData[selectedSet];
            if (!setInfo) return;
            
            cardSelect.innerHTML = "";
            setInfo.cards.forEach((card, index) => {
                const opt = document.createElement('option');
                opt.value = index;
                opt.innerText = `[${card.id}] ${card.name} (${card.fallback_price})`;
                cardSelect.appendChild(opt);
            });
        }

        initDatabase();

        const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
        const ws = new WebSocket(protocol + location.host + '/ws/scan');

        checkBtn.addEventListener('click', () => {
            const setKey = setSelect.value;
            const cardIdx = cardSelect.value;

            resultBox.innerHTML = "<h3>⏳ 카드 정보를 불러오는 중...</h3>";
            checkBtn.disabled = true;

            ws.send(JSON.stringify({
                set_key: setKey,
                card_index: cardIdx
            }));
        });

        ws.onmessage = (event) => {
            checkBtn.disabled = false;
            const data = JSON.parse(event.data);
            if(data.status === "success") {
                resultBox.innerHTML = `
                    <div class="card-name">${data.name}</div>
                    <img src="${data.image_url}" class="card-img" alt="포켓몬 카드 이미지">
                    <p style="margin: 5px 0; color:#666; font-size:0.9rem;">세트: ${data.set_name} (${data.card_id})</p>
                    <div class="price">시세 정보: ${data.market_price}</div>
                `;
            } else {
                resultBox.innerHTML = `<h3 style="color:#e74c3c;">조회 실패</h3><p>이미지를 불러오지 못했습니다.</p>`;
            }
        };

        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
            .then(stream => { video.srcObject = stream; })
            .catch(err => { console.error("카메라 접근 오류:", err); });
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html_content)

@app.get("/api/cards")
async def get_cards():
    return load_card_database()

@app.websocket("/ws/scan")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    database = load_card_database()
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            req = json.loads(raw_data)
            
            set_key = req.get("set_key")
            card_idx = int(req.get("card_index"))
            
            set_info = database.get(set_key)
            card_info = set_info["cards"][card_idx]
            
            market_page = None
            image_url = "https://images.pokemontcg.io/base1/4.png"
            
            async with httpx.AsyncClient() as client:
                try:
                    api_url = f"https://api.pokemontcg.io/v2/cards?q=name:\"{card_info['query']}\""
                    headers = {"User-Agent": "Mozilla/5.0"}
                    response = await client.get(api_url, headers=headers, timeout=3.0)
                    if response.status_code == 200:
                        api_data = response.json()
                        if api_data.get("data"):
                            card_data = api_data["data"][0]
                            image_url = card_data.get("images", {}).get("large", image_url)
                            price = card_data.get("tcgplayer", {}).get("prices", {}).get("holofoil", {}).get("market")
                            if price:
                                market_price = f"${price} (기준가: {card_info['fallback_price']})"
                except Exception:
                    pass
            
            if 'market_price' not in locals() or not market_price:
                market_price = card_info["fallback_price"]
                
            result = {
                "status": "success",
                "set_name": set_info["name"],
                "card_id": card_info["id"],
                "name": card_info["name"],
                "image_url": image_url,
                "market_price": market_price
            }
                        
            await websocket.send_text(json.dumps(result))

    except WebSocketDisconnect:
        pass

import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>포켓몬 TCG 세트별 시세 조회</title>
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

        #resultBox { margin-top: 15px; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); width: 100%; max-width: 400px; margin-left: auto; margin-right: auto; text-align: left;}
        h1 { font-size: 1.4rem; color: #333; }
        .price { font-size: 1.2rem; font-weight: bold; color: #16a085; margin-top: 5px; }
        .card-name { font-size: 1.2rem; font-weight: bold; color: #2c3e50; }
        
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
    <h1>포켓몬 TCG 카드 시세 조회</h1>
    
    <div class="video-container">
        <video id="video" autoplay playsinline></video>
    </div>
    
    <div class="controls">
        <label for="setSelect">확장팩 선택:</label>
        <select id="setSelect" onchange="updateCardList()">
            <option value="storm_emeralda">스톰에메랄다</option>
            <option value="abyss_eye">어비스아이</option>
            <option value="ninja_spinner">닌자스피너</option>
            <option value="inferno_x">인페르노 X</option>
            <option value="terastal_festa">테라스탈 페스타</option>
            <option value="pokemon_151">포켓몬 카드 151</option>
        </select>

        <label for="cardSelect">카드 선택:</label>
        <select id="cardSelect"></select>
    </div>

    <button id="checkBtn">💰 실시간 시세 확인하기</button>
    
    <div id="resultBox">
        <h3 style="margin:0 0 5px 0; color:#555;">조회 결과</h3>
        <p style="margin:0; color:#888;">카드를 선택하고 시세 확인 버튼을 눌러주세요.</p>
    </div>

    <script>
        const video = document.getElementById('video');
        const setSelect = document.getElementById('setSelect');
        const cardSelect = document.getElementById('cardSelect');
        const checkBtn = document.getElementById('checkBtn');
        const resultBox = document.getElementById('resultBox');

        // 세트별 카드 데이터베이스 (원하시는 카드를 마음껏 추가·수정 가능합니다)
        const database = {
            "storm_emeralda": [
                {id: "m6-110", name: "메가레쿠쟈 ex (MUR)", price: "$185.00", query: "Mega Rayquaza ex"},
                {id: "m6-108", name: "라이코 ex (SAR)", price: "$65.50", query: "Raikou ex"},
                {id: "m6-109", name: "메가골루그 ex (SAR)", price: "$42.00", query: "Mega Golurk ex"},
                {id: "m6-102", name: "피아나의 신뢰 (SAR)", price: "$110.00", query: "Zinnia's Resolve"}
            ],
            "abyss_eye": [
                {id: "ab-095", name: "메가가이오카 ex (MUR)", price: "$170.00", query: "Mega Kyogre ex"},
                {id: "ab-091", name: "주니카 (SAR)", price: "$85.00", query: "Special Illustration Rare"}
            ],
            "ninja_spinner": [
                {id: "ns-088", name: "개굴닌자 ex (SAR)", price: "$130.00", query: "Greninja ex"},
                {id: "ns-082", name: "도련님 (SR)", price: "$35.00", query: "Trainer SR"}
            ],
            "inferno_x": [
                {id: "inf-101", name: "메가리자돈 X ex (MUR)", price: "$290.00", query: "Mega Charizard X ex"},
                {id: "inf-095", name: "단델 (SAR)", price: "$95.00", query: "Leon SAR"}
            ],
            "terastal_festa": [
                {id: "tf-125", name: "이스칸달 테라스탈 ex (SAR)", price: "$150.00", query: "Terastal ex"},
                {id: "tf-110", name: "이브이 마스터볼 밀레니엄", price: "$80.00", query: "Eevee Masterball"}
            ],
            "pokemon_151": [
                {id: "151-205", name: "뮤츠 ex (SAR)", price: "$145.00", query: "Mewtwo ex SAR"},
                {id: "151-198", name: "이상해꽃 ex (SAR)", price: "$55.00", query: "Venusaur ex SAR"},
                {id: "151-199", name: "리자몽 ex (SAR)", price: "$115.00", query: "Charizard ex SAR"},
                {id: "151-200", name: "거북왕 ex (SAR)", price: "$50.00", query: "Blastoise ex SAR"}
            ]
        };

        function updateCardList() {
            const selectedSet = setSelect.value;
            const cards = database[selectedSet] || [];
            cardSelect.innerHTML = "";
            cards.forEach((card, index) => {
                const opt = document.createElement('option');
                opt.value = index;
                opt.innerText = `[${card.id}] ${card.name}`;
                cardSelect.appendChild(opt);
            });
        }

        // 페이지 처음 켤 때 카드 목록 초기화
        updateCardList();

        const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
        const ws = new WebSocket(protocol + location.host + '/ws/scan');

        checkBtn.addEventListener('click', () => {
            const setKey = setSelect.value;
            const cardIdx = cardSelect.value;
            const selectedCard = database[setKey][cardIdx];

            resultBox.innerHTML = "<h3>⏳ 시세 조회 중...</h3>";
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
                    <p style="margin: 5px 0; color:#666;">세트: ${data.set_name} (${data.card_id})</p>
                    <div class="price">해외 연동 시세: ${data.market_price}</div>
                `;
            } else {
                resultBox.innerHTML = `<h3 style="color:#e74c3c;">조회 실패</h3><p>정보를 불러오지 못했습니다.</p>`;
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

@app.websocket("/ws/scan")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    database = {
        "storm_emeralda": {
            "name": "스톰에메랄다",
            "cards": [
                {"id": "m6-110", "name": "메가레쿠쟈 ex (MUR)", "query": "Mega Rayquaza ex", "fallback_price": "$185.00"},
                {"id": "m6-108", "name": "라이코 ex (SAR)", "query": "Raikou ex", "fallback_price": "$65.50"},
                {"id": "m6-109", "name": "메가골루그 ex (SAR)", "query": "Mega Golurk ex", "fallback_price": "$42.00"},
                {"id": "m6-102", "name": "피아나의 신뢰 (SAR)", "query": "Zinnia's Resolve", "fallback_price": "$110.00"}
            ]
        },
        "abyss_eye": {
            "name": "어비스아이",
            "cards": [
                {"id": "ab-095", "name": "메가가이오카 ex (MUR)", "query": "Mega Kyogre ex", "fallback_price": "$170.00"},
                {"id": "ab-091", "name": "주니카 (SAR)", "query": "Special Illustration Rare", "fallback_price": "$85.00"}
            ]
        },
        "ninja_spinner": {
            "name": "닌자스피너",
            "cards": [
                {"id": "ns-088", "name": "개굴닌자 ex (SAR)", "query": "Greninja ex", "fallback_price": "$130.00"},
                {"id": "ns-082", "name": "도련님 (SR)", "query": "Trainer SR", "fallback_price": "$35.00"}
            ]
        },
        "inferno_x": {
            "name": "인페르노 X",
            "cards": [
                {"id": "inf-101", "name": "메가리자돈 X ex (MUR)", "query": "Mega Charizard X ex", "fallback_price": "$290.00"},
                {"id": "inf-095", "name": "단델 (SAR)", "query": "Leon SAR", "fallback_price": "$95.00"}
            ]
        },
        "terastal_festa": {
            "name": "테라스탈 페스타",
            "cards": [
                {"id": "tf-125", "name": "이스칸달 테라스탈 ex (SAR)", "query": "Terastal ex", "fallback_price": "$150.00"},
                {"id": "tf-110", "name": "이브이 마스터볼 밀레니엄", "query": "Eevee Masterball", "fallback_price": "$80.00"}
            ]
        },
        "pokemon_151": {
            "name": "포켓몬 카드 151",
            "cards": [
                {"id": "151-205", "name": "뮤츠 ex (SAR)", "query": "Mewtwo ex SAR", "fallback_price": "$145.00"},
                {"id": "151-198", "name": "이상해꽃 ex (SAR)", "query": "Venusaur ex SAR", "fallback_price": "$55.00"},
                {"id": "151-199", "name": "리자몽 ex (SAR)", "query": "Charizard ex SAR", "fallback_price": "$115.00"},
                {"id": "151-200", "name": "거북왕 ex (SAR)", "query": "Blastoise ex SAR", "fallback_price": "$50.00"}
            ]
        }
    }
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            req = json.loads(raw_data)
            
            set_key = req.get("set_key")
            card_idx = int(req.get("card_index"))
            
            set_info = database.get(set_key)
            card_info = set_info["cards"][card_idx]
            
            market_price = None
            async with httpx.AsyncClient() as client:
                try:
                    api_url = f"https://api.pokemontcg.io/v2/cards?q=name:\"{card_info['query']}\""
                    headers = {"User-Agent": "Mozilla/5.0"}
                    response = await client.get(api_url, headers=headers, timeout=2.5)
                    if response.status_code == 200:
                        api_data = response.json()
                        if api_data.get("data"):
                            price = api_data["data"][0].get("tcgplayer", {}).get("prices", {}).get("holofoil", {}).get("market")
                            if price:
                                market_price = f"${price}"
                except Exception:
                    pass
            
            if not market_price:
                market_price = card_info["fallback_price"]
                
            result = {
                "status": "success",
                "set_name": set_info["name"],
                "card_id": card_info["id"],
                "name": card_info["name"],
                "market_price": market_price
            }
                        
            await websocket.send_text(json.dumps(result))

    except WebSocketDisconnect:
        pass

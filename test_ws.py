import asyncio
import websockets
import json

async def test_websocket():
    # Use o token que você usou no commit anterior (ou um válido)
    # Como não tenho um token real agora, vou simular um erro de auth ou conexão
    # Se você estiver rodando o servidor, ajuste a URL e o Token
    uri = "ws://localhost:8000/ws/recommend?token=SEU_TOKEN_AQUI"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Conectado ao WebSocket!")
            
            # Esperar mensagem de boas-vindas
            welcome = await websocket.recv()
            print(f"Recebido: {welcome}")
            
            # Enviar parâmetros
            params = {
                "client": "080e5298-76b5-4139-9fb8-696efc1a2496",
                "evaluationid": 985,
                "scale": 2,
                "ntop_similarity": 10,
                "ntop_recommendations": 7,
                "days_window": 7
            }
            await websocket.send(json.dumps(params))
            print(f"Enviado parâmetros: {params}")
            
            # Ouvir atualizações de progresso
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                print(f"Update: {data}")
                
                if data.get("status") == "completed" or data.get("status") == "error":
                    break
                    
    except Exception as e:
        print(f"Erro no teste: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())

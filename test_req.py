import urllib.request
import json

data = {
    "user_id": 111111,
    "name": "Test",
    "phone": "+998901234567",
    "grade": "10",
    "district": "Toshkent",
    "source": "Telegram"
}
req = urllib.request.Request('https://botttttttt-production.up.railway.app/api/submit', method='POST')
req.add_header('Content-Type', 'application/json')
try:
    res = urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8'))
    print("SUCCESS:", res.read().decode('utf-8'))
except Exception as e:
    print("ERROR:", str(e))

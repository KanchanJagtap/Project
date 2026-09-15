import requests

url = "http://127.0.0.1:8000/anpr/process"
files = {'file': open('data/test/indian-plates/images/image_0025.jpg', 'rb')}
try:
    response = requests.post(url, files=files)
    print(response.json())
except Exception as e:
    print(e)

from flask import Flask,url_for,request

app = Flask(__name__)
global qrMap
qrMap={}
@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"
@app.route('/qr/<int:qrID>', methods=['GET', 'POST'])
def login(qrID:int):
    global qrMap
    if request.method == 'POST':
        qrMap[qrID]=request.json["data"]
        return "ok"
    else:
        return qrMap.get(qrID,"")
with app.test_request_context():
    url_for('static', filename='index.html')
# ================================================================

import time
import board
import adafruit_dht
import RPi.GPIO as GPIO
from flask import Flask, jsonify, render_template_string, request, send_file
import threading
import qrcode
import io

# ================================================================
# GPIO 设置
# ================================================================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# 灯光引脚
PIN_MAIN = 18
PIN_BEDROOM = 17
PIN_HALL = 27

# 设置为输出并默认关闭
for pin in [PIN_MAIN, PIN_BEDROOM, PIN_HALL]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

device_states = {
    "main": False,
    "bedroom": False,
    "hall": False,
    "night":False,
    "all":False
}

# ================================================================
# DHT22 初始化
# ================================================================
dht = adafruit_dht.DHT22(board.D4, use_pulseio=False)

# 温湿度历史记录（用于折线图）
history_temp = []
history_humi = []

# ================================================================
# 温度报警线程（后台运行）
# ================================================================
import threading

ALARM_TEMP = 31.0     # 31°C 以上触发报警
alarm_active = False


def alarm_thread():
    global alarm_active
    while True:
        try:
            t = dht.temperature
            if t is not None and t > ALARM_TEMP:
                alarm_active = True
                # LED 快速闪烁
                for _ in range(5):
                    GPIO.output(PIN_HALL, GPIO.HIGH)
                    time.sleep(0.1)
                    GPIO.output(PIN_HALL, GPIO.LOW)
                    time.sleep(0.1)
            else:
                alarm_active = False
        except Exception:
            pass
        time.sleep(2)


# 启动报警线程

threading.Thread(target=alarm_thread, daemon=True).start()

# ================================================================
# Flask 初始化
# ================================================================
app = Flask(__name__)

# ================================================================
# 生成二维码（扫码进入控制页面）
# ================================================================
@app.route("/qrcode")
def qrcode_page():
    url = f"https://192.168.137.28:5000/"
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Smart Home Control System</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
body { background:#0d1117; color:#e6edf3; font-family:Arial; text-align:center; }
h1 { margin-top:25px; color:#58a6ff; }
.card {
    background:#161b22; width:420px; margin:20px auto; padding:20px;
    border-radius:12px; box-shadow:0 0 15px rgba(0,0,0,0.5);
}
button {
    width:90%; padding:12px; margin:8px; border:none; border-radius:6px;
    font-size:16px; cursor:pointer; color:white;display：block；
}
.on{background:#238636;} .off{background:#6e7681;}
.on:hover{background:#2ea043;} .off:hover{background:#8b949e;}
.sensor-value{font-size:20px; font-weight:bold;}
.qr{margin-top:10px;}

/* -------------------------------------------------
   ⚠ 新增：红色温度警报弹窗（居中悬浮）
---------------------------------------------------*/
#alarm_popup{
    position:fixed;
    top:50%;
    left:50%;
    transform:translate(-50%, -50%);
    width:70%;
    max-width:400px;
    padding:20px;
    background:#8b0000;
    border:3px solid #ff4d4d;
    box-shadow:0 0 25px #ff0000;
    border-radius:15px;
    color:white;
    z-index:9999;
    display:none;
    animation:alarmBlink 1s infinite;
}

@keyframes alarmBlink{
    0%{ box-shadow:0 0 5px #ff0000; opacity:1; }
    50%{ box-shadow:0 0 25px #ff5555; opacity:0.6; }
    100%{ box-shadow:0 0 5px #ff0000; opacity:1; }
}

#alarm_popup h2 {
    margin:0;
    padding:0;
    color:#ffaaaa;
}

</style>

</head>
<body>

<div id="alarm_popup>
    <h2> TEMPERATURE ALERT <h2>
    <p id="alarm_popup_text"  style="font-size:20px;"></p>
</div>

<div class="card">
    <h2>System Status</h2>
    <p>Time: <span id="now_time">--:--:--</span></p>
    <p>CPU Temp: <span id="cpu_temp">-- °C</span></p>
</div>

<h1>Smart Home Control System</h1>

<!-- ========================
     LIGHT CONTROL
     ========================
     中文注释：各种灯光控制按钮（全开、全关、单独控制、夜间模式）
-->
<div class="card">
    
    <button id="main_btn" class="off" onclick="toggle('main')">Main Light: OFF</button>
    <button id="bedroom_btn" class="off" onclick="toggle('bedroom')">Bedroom Light: OFF</button>
    <button id="hall_btn" class="off" onclick="toggle('hall')">Hall Light: OFF</button>
    <hr>
    <button id="all_btn" class="off" onclick="toggle('all')">All Lights: OFF</button>
    <button id="night_btn" class="off" onclick="toggle('night')">Night Mode: OFF</button>
</div>

<!-- ========================
     TEMPERATURE & HUMIDITY
     ========================
     中文注释：显示实时温度和湿度数据（自动刷新）
-->
<div class="card">
    <h2>Temperature & Humidity</h2>
    <p>Temperature: <span id="temp" class="sensor-value">--</span> °C</p>
    <p>Humidity: <span id="hum" class="sensor-value">--</span> %</p>
</div>

<!-- ========================
     HISTORY CHART
     ========================
     中文注释：使用 Chart.js 绘制历史温湿度曲线
-->
<div class="card">
    <h2>History Chart</h2>
    <canvas id="chart" width="380" height="200"></canvas>
</div>

<!-- ========================
     VOICE CONTROL
     ========================
     中文注释：语音控制（增强版）支持英文指令 + 英文语音反馈
-->
<div class="card">
    <h2>Voice Control</h2>
    <button class="on" onclick="toggleVoice()"> Start / Stop Voice</button>
    <p id='voice-status'>Not Started</p>
</div>

<!-- ========================
     QR CODE DISPLAY
     ========================
     中文注释：二维码用于手机快速进入控制界面
-->
<div class="card">
    <h2>Scan to Access Control Page</h2>
    <img class="qr" src="/qrcode" width="180">
</div>

<script>
function refreshTemp(){
    fetch('/api/temp')
        .then(r => r.json())
        .then(d => {
            document.getElementById('temp').innerText = d.temp;
            document.getElementById('hum').innerText = d.hum;

// ---- 新增：更新网页报警状态 ----
            updateAlarmUI(d.alarm, d.temp);
            if(d.temp !== "--" && d.hum !== "--"){
                addPoint(d.temp, d.hum);
            }
        })
        .catch(e =>console.log("TEMP ERROR:", err));
}

setInterval(refreshTemp, 5000);
refreshTemp();

// -------------------------------------------------------
// 灯光控制（发送 REST API）
// -------------------------------------------------------
function action(cmd){
    fetch('/action/' + cmd);
}


// -------------------------------------------------------
// 温湿度历史曲线
// -------------------------------------------------------
const ctx = document.getElementById('chart');
const chart = new Chart(ctx,{
    type:'line',
    data:{ labels:[], datasets:[
        { label: "Temperature (°C)", data: [], borderColor: "#58a6ff", borderWidth: 2, tension: 0.2 },
        { label: "Humidity (%)", data: [], borderColor: "#3fb950", borderWidth: 2, tension: 0.2 }
    ]
 },
    options: {
        animation: false,
        scales: { y: { beginAtZero: false } }
    }
});

// 添加历史数据点
function addPoint(t,h){
    let time = new Date().toLocaleTimeString();
    chart.data.labels.push(time);
    chart.data.datasets[0].data.push(t);
    chart.data.datasets[1].data.push(h);
    chart.update();
}

// -------------------------------------------------------
// 语音控制（增强版英文）
// -------------------------------------------------------
// 中文注释：包含持续监听、语音控制灯光、查询温湿度、英文语音反馈
let recog = null;
let listening = false;

function toggleVoice(){
    if(listening){
        recog.stop();
        listening = false;
        document.getElementById('voice-status').innerText='Voice Stopped';
        return;
    }
    startVoice();
}

function speak(text){
    let msg = new SpeechSynthesisUtterance(text);
    msg.lang = 'en-US';   // 英文语音
    speechSynthesis.speak(msg);
}

function startVoice(){
    recog = new(window.SpeechRecognition||window.webkitSpeechRecognition)();
    recog.lang='en-US';   // 英文识别
    recog.continuous = true;
    recog.start();

    listening = true;
    document.getElementById('voice-status').innerText='Listening...';

    recog.onresult = function(e){
        let text = e.results[e.results.length-1][0].transcript;
        document.getElementById('voice-status').innerText='Heard: '+text;

        text = text.toLowerCase(); // 英文统一小写匹配

        // ===========================
        // 英文语音控制灯光
        // ===========================
        if(text.includes('turn on main light')){ action('main_on'); speak('Main light is now on'); }
        if(text.includes('turn off main light')){ action('main_off'); speak('Main light is now off'); }

        if(text.includes('turn on bedroom light')){ action('bedroom_on'); speak('Bedroom light on'); }
        if(text.includes('turn off bedroom light')){ action('bedroom_off'); speak('Bedroom light off'); }

        if(text.includes('turn on hallway light')){ action('hall_on'); speak('Hallway light on'); }
        if(text.includes('turn off hallway light')){ action('hall_off'); speak('Hallway light off'); }

        if(text.includes('turn on all lights')){ action('all_on'); speak('All lights are now on'); }
        if(text.includes('turn off all lights')){ action('all_off'); speak('All lights are now off'); }

        if(text.includes('night mode')){ action('night_mode'); speak('Night mode activated'); }



        // ===========================
        // 英文快捷口令（更自然）
        // ===========================
        if(text.includes('i am home')){ action('all_on'); speak('Welcome home, lights are on'); }
        if(text.includes('i am leaving')){ action('all_off'); speak('Goodbye, lights turned off'); }
        if(text.includes('i am going to sleep')){ action('night_mode'); speak('Good night, night mode on'); }


        // ===========================
        // 温湿度查询（语音播报）
        // ===========================
        if(text.includes('temperature') || text.includes('humidity')){
            fetch('/api/temp').then(r=>r.json()).then(d=>{
                speak(`Current temperature is ${d.temp} degrees, and humidity is ${d.hum} percent.`);
            });
        }
    };

    recog.onerror = function(){
        speak('Voice recognition error');
    };
}

function update(id, state){
    let b = document.getElementById(id + "_btn");

    if(id === "night"){
        b.innerText = "Night Mode: " + (state ? "ON" : "OFF");
    } else if(id === "all"){
        b.innerText = "All Lights: " + (state ? "ON" : "OFF");
    } else {
        let name = id.charAt(0).toUpperCase() + id.slice(1);
        b.innerText = name + " Light: " + (state ? "ON" : "OFF");
    }

    b.className = state ? "on" : "off";
}

function refreshLights(){
    fetch('/state').then(r=>r.json()).then(s=>{

        update('main', s.main);
        update('bedroom', s.bedroom);
        update('hall', s.hall);

        let all_on = s.main && s.bedroom && s.hall;
        update('all', all_on);

        update('night', s.night);
    });
}
setInterval(refreshLights, 500);
refreshLights();

function toggle(id){
    fetch('/state').then(r=>r.json()).then(s=>{

        if(id === 'all'){
            let all_on = s.main && s.bedroom && s.hall;
            fetch('/action/' + (all_on ? 'all_off' : 'all_on'));
            return;
        }

        if(id === 'night'){
            fetch('/action/' + (s.night ? 'night_off' : 'night_on'));
            return;
        }

        fetch('/action/' + (s[id] ? id + '_off' : id + '_on'));
    });
}

function updateTime(){
    let now = new Date();
    document.getElementById("now_time").innerText =
        now.toLocaleTimeString();
}
setInterval(updateTime, 1000);
updateTime();

function updateCpuTemp(){
    fetch('/cpu_temp')
        .then(r=>r.json())
        .then(d=>{
            document.getElementById("cpu_temp").innerText = d.temp + " °C";
            checkAlert(d.temp);
        });
}
setInterval(updateCpuTemp, 3000);
updateCpuTemp();

function updateAlarmUI(alarm, temp){
    let popup = document.getElementById("alarm_popup");
    let text = document.getElementById("alarm_popup_text");

    if(alarm){
        card.style.display = "block";
        text.innerText = "High Temperature! Current: " + temp + "°C";
    } else {
        card.style.display = "none";
    }
}


</script>

</body>
</html>
"""


# ================================================================
# 后端 API：读取温湿度
# ================================================================
@app.route("/api/temp")
def api_temp():
    import time
    try:
        for _ in range(5):   # 尝试 5 次获取稳定值
            try:
                temperature = dht.temperature
                humidity = dht.humidity
                if (temperature is not None) and (humidity is not None):
                    return jsonify({
                        "temp": round(float(temperature), 1),
                        "hum": round(float(humidity), 1),
                        "fallback": False,
                        "alarm:alarm_active,
                        "ts": int(time.time())
                    })
            except RuntimeError:
                time.sleep(1)

        # 多次失败返回 fallback 值
        raise RuntimeError("DHT22 read failed after retries")

    except Exception as e:
        print("[DHT ERROR]", e, flush=True)
        return jsonify({
            "temp": 25.0,
            "hum": 50.0,
            "fallback": True,
            "ts": int(time.time())
        })

# ========== 温湿度 API ==========
import Adafruit_DHT

DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 4  # 如果你的 DHT22 DATA 接 GPIO4，请保持这个。不确定可以告诉我。

@app.route("/api/temp")
def temperature():
    humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)

    if humidity is None or temperature is None:
        return jsonify({"temperature": None, "humidity": None})

    return jsonify({
        "temperature": round(temperature, 1),
        "humidity": round(humidity, 1)
    })

# ================================================================
# 后端：灯光与模式控制 API
# ================================================================
@app.route("/api/states")
def api_states():
    return jsonify({
        "main": device_states.get("main", False),
        "bedroom": device_states.get("bedroom", False),
        "hall": device_states.get("hall", False),
        "all": (
            device_states.get("main", False)
            or device_states.get("bedroom", False)
            or device_states.get("hall", False)
        ),
        "night": device_states.get("night", False)
    })

@app.route('/toggle/<which>')
def toggle(which):
    # 主灯控制（自动 ON/OFF）
    if which == "main":
        device_states["main"] = not device_states["main"]
        GPIO.output(PIN_MAIN, GPIO.HIGH if device_states["main"] else GPIO.LOW)

    # 卧室灯
    elif which == "bedroom":
        device_states["bedroom"] = not device_states["bedroom"]
        GPIO.output(PIN_BEDROOM, GPIO.HIGH if device_states["bedroom"] else GPIO.LOW)

    # 走廊灯
    elif which == "hall":
        device_states["hall"] = not device_states["hall"]
        GPIO.output(PIN_HALL, GPIO.HIGH if device_states["hall"] else GPIO.LOW)

    # 全屋灯（重点！！你的之前代码缺少这个）
    elif which == "all":
        # 判断是否需要全开还是全关
        new_state = not (device_states["main"] or device_states["bedroom"] or device_states["hall"])

        # 更新所有灯光状态
        device_states["main"] = new_state
        device_states["bedroom"] = new_state
        device_states["hall"] = new_state

        # 实际 GPIO 输出
        GPIO.output(PIN_MAIN, GPIO.HIGH if new_state else GPIO.LOW)
        GPIO.output(PIN_BEDROOM, GPIO.HIGH if new_state else GPIO.LOW)
        GPIO.output(PIN_HALL, GPIO.HIGH if new_state else GPIO.LOW)

    # 夜间模式（只开走廊灯）
    elif which == "night":
        device_states["main"] = False
        device_states["bedroom"] = False
        device_states["hall"] = True

        GPIO.output(PIN_MAIN, GPIO.LOW)
        GPIO.output(PIN_BEDROOM, GPIO.LOW)
        GPIO.output(PIN_HALL, GPIO.HIGH)

    return ("OK", 200)

@app.route('/action/all')
def action_all():
    global main_light, bedroom_light, hall_light

    # 切换成相反状态
    new_state = not main_light

    main_light = new_state
    bedroom_light = new_state
    hall_light = new_state

    # 这里更新 GPIO 或你的硬件控制函数
    set_main(main_light)
    set_bedroom(bedroom_light)
    set_hall(hall_light)

    return jsonify({
        "main": main_light,
        "bedroom": bedroom_light,
        "hall": hall_light
    })

# 后端：灯光与模式控制 API
# ================================================================
@app.route('/action/<cmd>')
def action(cmd):
    # 主灯
    if cmd == 'main_on':
        GPIO.output(PIN_MAIN, GPIO.HIGH); device_states['main']=True
    elif cmd == 'main_off':
        GPIO.output(PIN_MAIN, GPIO.LOW); device_states['main']=False

    # 卧室灯
    elif cmd == 'bedroom_on':
        GPIO.output(PIN_BEDROOM, GPIO.HIGH); device_states['bedroom']=True
    elif cmd == 'bedroom_off':
        GPIO.output(PIN_BEDROOM, GPIO.LOW); device_states['bedroom']=False

    # 走廊灯
    elif cmd == 'hall_on':
        GPIO.output(PIN_HALL, GPIO.HIGH); device_states['hall']=True
    elif cmd == 'hall_off':
        GPIO.output(PIN_HALL, GPIO.LOW); device_states['hall']=False

    # All Lights
    elif cmd == 'all_on':
        GPIO.output(PIN_MAIN, GPIO.HIGH)
        GPIO.output(PIN_BEDROOM, GPIO.HIGH)
        GPIO.output(PIN_HALL, GPIO.HIGH)
        device_states["main"] = True
        device_states["bedroom"] = True
        device_states["hall"] = True
        device_states["all"] = True
        device_states["night"] = False

    elif cmd == 'all_off':
        GPIO.output(PIN_MAIN, GPIO.LOW)
        GPIO.output(PIN_BEDROOM, GPIO.LOW)
        GPIO.output(PIN_HALL, GPIO.LOW)
        device_states["main"] = False
        device_states["bedroom"] = False
        device_states["hall"] = False
        device_states["all"] = False

    # 夜间模式开启：只亮走廊灯（Hall）
    elif cmd == 'night_on':
        # 关闭所有灯
        GPIO.output(PIN_MAIN, GPIO.LOW)
        GPIO.output(PIN_BEDROOM, GPIO.LOW)
        GPIO.output(PIN_HALL, GPIO.LOW)

        # 只打开走廊灯（你的夜间指示灯）
        GPIO.output(PIN_HALL, GPIO.HIGH)

        # 更新状态
        device_states["main"] = False
        device_states["bedroom"] = False
        device_states["hall"] = True   # Hall 灯亮
        device_states["all"] = False
        device_states["night"] = True

    # 夜间模式关闭：关掉 Hall 灯
    elif cmd == 'night_off':
        GPIO.output(PIN_HALL, GPIO.LOW)
        device_states["hall"] = False
        device_states["night"] = False

    return ("OK", 200)

@app.route("/state")
def state():
    return jsonify(device_states)


@app.route("/cpu_temp")
def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            t = int(f.read()) / 1000
        return jsonify({"temp": round(t, 1)})
    except:
        return jsonify({"temp": -1})

# ================================================================
# 首页
# ================================================================
@app.route('/')
def index():
    return render_template_string(PAGE_HTML)

# ================================================================
# 主启动入口
# ================================================================
if __name__ == '__main__':
    try:
        app.run(
            host='0.0.0.0',
            port=5000, 
            debug=False，
            ssl_context=('cert.pem', 'key.pem')
        )
    finally:
        GPIO.cleanup()
#https://192.168.137.28:5000/
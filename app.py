from flask import Flask, request, jsonify, send_from_directory
import redis
import os

# --- 应用配置 ---
# QR 码数据在 Redis 中的有效期（秒）
QR_CODE_EXPIRATION_SECONDS = 300  # 5分钟
# 禁止用户在指定秒数内重复更新同一个 QR 码
UPDATE_LOCK_SECONDS = 5           # 5秒

app = Flask(__name__)

# --- Redis 连接 ---
# 从环境变量 REDIS_URL 获取连接字符串，如果未设置则使用默认值
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# 创建 Redis 连接实例
# decode_responses=True 确保从 Redis 获取的值是字符串而不是字节
try:
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    # 测试连接
    r.ping()
    print("成功连接到 Redis。")
except redis.exceptions.ConnectionError as e:
    print(f"无法连接到 Redis: {e}")
    # 在无法连接到 Redis 时，可以决定是退出应用还是继续运行（但功能会受限）
    # 这里我们选择打印错误并退出
    exit("请检查 Redis 服务是否正在运行，并确保 REDIS_URL 环境变量已正确设置。")


@app.route("/")
def index():
    """提供应用主页的静态 HTML 文件。"""
    return send_from_directory('static', 'index.html')

@app.route('/qr/<int:qrID>', methods=['GET', 'POST'])
def handle_qr_code(qrID: int):
    """
    处理 QR 码数据的获取和更新请求。
    - GET: 获取指定 qrID 的数据。
    - POST: 更新指定 qrID 的数据。
    """
    # 为数据和更新锁定义清晰的 Redis键 (key)
    qr_data_key = f"qr:data:{qrID}"
    update_lock_key = f"qr:lock:{qrID}"

    if request.method == 'POST':
        # --- 处理更新请求 ---

        # 1. 禁止频繁更新检查
        # 检查更新锁是否存在，如果存在，则意味着最近已有更新操作
        if r.exists(update_lock_key):
            # 返回 HTTP 429 Too Many Requests 错误，告知客户端操作过于频繁
            return jsonify({"error": f"操作过于频繁，请在 {UPDATE_LOCK_SECONDS} 秒后重试。"}), 429

        # 从请求的 JSON body 中获取数据
        data_to_store = request.json.get("data")
        if data_to_store is None:
            # 如果请求中没有 'data' 字段，返回 HTTP 400 Bad Request 错误
            return jsonify({"error": "请求体中缺少 'data' 字段。"}), 400

        # 2. 使用 Redis Pipeline 执行原子操作
        # Pipeline 可以将多个命令打包发送到 Redis，确保它们被连续执行，避免竞态条件
        pipe = r.pipeline()

        # 将数据存入 Redis，并设置过期时间
        pipe.set(qr_data_key, data_to_store, ex=QR_CODE_EXPIRATION_SECONDS)

        # 创建一个短暂的更新锁，防止在短时间内再次更新
        pipe.set(update_lock_key, "1", ex=UPDATE_LOCK_SECONDS)
        
        # 执行 Pipeline 中的所有命令
        pipe.execute()

        return jsonify({"status": "ok", "message": f"QR码 {qrID} 的数据已成功更新。"}), 200

    else: # request.method == 'GET'
        # --- 处理获取请求 ---
        
        # 3. 从 Redis 中获取数据
        # 如果键已过期或不存在，r.get() 会返回 None
        stored_data = r.get(qr_data_key)
        
        # 如果数据不存在（可能已过期或从未设置），返回空字符串，与原逻辑保持一致
        if stored_data is None:
            return jsonify({"data": ""}), 404 # Not Found
            
        return jsonify({"data": stored_data}), 200

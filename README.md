# Dự án CodeChat

📆 **Mô tả:** Dự án Python sử dụng OpenAI API, cài đặt các thư viện bằng **Poetry** và khởi chạy server với **FastAPI**.

---

## Yêu cầu hệ thống

-   **Python 3.8+**
-   **Poetry** - Công cụ quản lý gói cho Python.

## 1. Cài đặt Poetry

Nếu bạn chưa cài đặt Poetry, bạn có thể cài đặt bằng lệnh:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

🔍 Đảm bảo Poetry được cài đặt thành công:

```bash
poetry --version
```

## 2. Cấu hình API Key của OpenAI

Tạo API Key trên trang OpenAI: [https://platform.openai.com](https://platform.openai.com/)

Sau khi tạo xong, bạn tạo file `.env` trong thư mục gốc dự án và thêm API key của bạn như sau:

```plaintext
OPENAI_API_KEY=your_openai_api_key_here
```

> **Lưu ý:** Giữ API Key an toàn và không chia sẻ cho người khác.

## 3. Cài đặt thư viện cần thiết

Dùng Poetry để cài đặt các thư viện cần thiết cho dự án:

```bash
poetry install
```

File `pyproject.toml` đã bao gồm các thư viện cần thiết như:

-   **openai**: Sử dụng OpenAI API.
-   **python-dotenv**: Để đọc file `.env` chứa API key.
-   **fastapi**: Framework tạo API server.
-   **uvicorn**: Chạy server.

Nếu bạn cần thêm bất kỳ thư viện nào, sử dụng:

```bash
poetry add <tên-thư-viện>
```

## 4. Cấu hình env

```plaintext
SERVER_RELOAD="TRUE"
SERVER_MONGODB_URL="mongodb://localhost:27017/"
SERVER_MILVUS_DB_USERNAME="root"
SERVER_MILVUS_DB_PASSWORD=""
SERVER_MILVUS_DB_HOST="localhost"
SERVER_MILVUS_DB_PORT=19530
SERVER_MILVUS_DB_NAME="default"
SERVER_MILVUS_DB_COLLECTION="your_collection_name"
```

## 5. Chạy server

Khởi động server FastAPI bằng Poetry:

```bash
poetry run python -m server
```

Server sẽ khởi chạy và bạn có thể truy cập tại:

```
http://127.0.0.1:8000
```

## 6. Cấu trúc dự án

```bash
$ tree "server"
server
├── conftest.py  # Fixtures cho tất cả các bài kiểm tra.
├── __main__.py  # Script khởi động, chạy uvicorn.
├── services  # Thư mục chứa các dịch vụ bên ngoài như RabbitMQ, Redis, v.v.
├── settings.py  # Cấu hình chính cho dự án.
├── static  # Thư mục chứa các tài nguyên tĩnh.
├── tests  # Thư mục chứa các bài kiểm tra cho dự án.
└── web  # Thư mục chứa các thành phần web của server. Các handler, cấu hình khởi động.
    ├── api  # Thư mục chứa tất cả các handler.
    │   └── router.py  # Router chính của API.
    ├── application.py  # Cấu hình ứng dụng FastAPI.
    └── lifetime.py  # Các hành động thực hiện khi khởi động và tắt server.
```

## 7. Test API

Sau khi server chạy, bạn có thể gửi yêu cầu đến API bằng công cụ như **Postman** hoặc **curl**.

Ví dụ: Gửi yêu cầu `GET` đến endpoint `/`

```bash
curl http://127.0.0.1:8000/
```

Kết quả trả về:

```json
{ "detail": "Welcome to chat bot server" }
```

---

🎉 **Chúc bạn thành công!** 🚀

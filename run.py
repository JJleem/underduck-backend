import uvicorn

if __name__ == "__main__":
    # host="0.0.0.0" — nginx(127.0.0.1)에서 프록시. 별도 프로세스, cosmic-backend(:8000)와 분리.
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)

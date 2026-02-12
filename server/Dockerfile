FROM gcc:14

WORKDIR /server

COPY . .

RUN g++ -std=c++2a -I./libs ./src/http_ser.cpp -o server

EXPOSE 8080

CMD ["./server"]

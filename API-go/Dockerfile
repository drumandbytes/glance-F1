FROM golang:alpine AS builder

WORKDIR /build

COPY go.mod go.sum .
RUN go mod download && go mod tidy

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o f1-api .

FROM gcr.io/distroless/static-debian13

COPY --from=builder /build/f1-api /f1-api

EXPOSE 4463

ENTRYPOINT ["/f1-api"]
